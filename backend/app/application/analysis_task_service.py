"""Persistent state machine for resumable job analysis.

This remains a single-instance demo design. Claims have owned, expiring leases
so a restarted instance can recover abandoned work without clearing live work.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..infrastructure.database.models import Analysis, AnalysisTask, AnalysisTaskStatus
from ..infrastructure.database.repositories import (
    AnalysisRepository,
    AnalysisTaskRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)
from ..infrastructure.llm.provider import LLMServiceError
from ..schemas.analysis_task import AnalysisTaskStarted
from .analysis_service import (
    PROMPT_VERSION,
    SCORING_VERSION,
    ApplicationAnalysisService,
    AnalysisService,
    _profile_text,
)
from .crud_service import ResourceConflictError, ResourceNotFoundError
from .retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

ANALYSIS_TASK_LEASE_SECONDS = 300

PROGRESS_BY_STATUS = {
    AnalysisTaskStatus.PENDING: 0,
    AnalysisTaskStatus.FETCHING_JOB: 10,
    AnalysisTaskStatus.ANALYZING: 30,
    AnalysisTaskStatus.SAVING_RESULT: 80,
    AnalysisTaskStatus.WAITING_FOR_REVIEW: 90,
    AnalysisTaskStatus.COMPLETED: 100,
}

ALLOWED_TRANSITIONS = {
    AnalysisTaskStatus.PENDING: {
        AnalysisTaskStatus.FETCHING_JOB,
        AnalysisTaskStatus.FAILED,
    },
    AnalysisTaskStatus.FETCHING_JOB: {
        AnalysisTaskStatus.ANALYZING,
        AnalysisTaskStatus.FAILED,
    },
    AnalysisTaskStatus.ANALYZING: {
        AnalysisTaskStatus.SAVING_RESULT,
        AnalysisTaskStatus.FAILED,
    },
    AnalysisTaskStatus.SAVING_RESULT: {
        AnalysisTaskStatus.ANALYZING,  # controlled recovery for a missing payload
        AnalysisTaskStatus.WAITING_FOR_REVIEW,
        AnalysisTaskStatus.FAILED,
    },
    AnalysisTaskStatus.WAITING_FOR_REVIEW: {
        AnalysisTaskStatus.COMPLETED,
        AnalysisTaskStatus.FAILED,
    },
    AnalysisTaskStatus.FAILED: {
        AnalysisTaskStatus.PENDING,
        AnalysisTaskStatus.FETCHING_JOB,
        AnalysisTaskStatus.ANALYZING,
        AnalysisTaskStatus.SAVING_RESULT,
    },
    AnalysisTaskStatus.COMPLETED: set(),
}

RECOVERY_STEPS = {
    AnalysisTaskStatus.PENDING.value: AnalysisTaskStatus.PENDING,
    AnalysisTaskStatus.FETCHING_JOB.value: AnalysisTaskStatus.FETCHING_JOB,
    AnalysisTaskStatus.ANALYZING.value: AnalysisTaskStatus.ANALYZING,
    AnalysisTaskStatus.SAVING_RESULT.value: AnalysisTaskStatus.SAVING_RESULT,
}


def transition_analysis_task(
    task: AnalysisTask,
    target: AnalysisTaskStatus,
) -> None:
    """Validate and apply a transition to an in-memory object."""
    source = AnalysisTaskStatus(task.status)
    if target not in ALLOWED_TRANSITIONS[source]:
        raise ResourceConflictError(
            f"illegal analysis task transition: {source.value} -> {target.value}"
        )
    task.status = target.value
    if target is not AnalysisTaskStatus.FAILED:
        task.current_step = target.value
        task.progress = PROGRESS_BY_STATUS[target]
        task.error_code = None
        task.error_message = None


def validate_analysis_task(task: AnalysisTask) -> None:
    """Enforce lifecycle invariants at service transaction boundaries."""
    status = AnalysisTaskStatus(task.status)
    if status is not AnalysisTaskStatus.FAILED:
        if task.current_step != status.value:
            raise RuntimeError("analysis task status and current_step are inconsistent")
        if task.progress != PROGRESS_BY_STATUS[status]:
            raise RuntimeError("analysis task status and progress are inconsistent")
    if status is AnalysisTaskStatus.PENDING:
        if task.result_id is not None or task.completed_at is not None:
            raise RuntimeError("pending analysis task has result or completion time")
    elif status in {
        AnalysisTaskStatus.FETCHING_JOB,
        AnalysisTaskStatus.ANALYZING,
    }:
        if task.completed_at is not None:
            raise RuntimeError("active analysis task has completion time")
    elif status is AnalysisTaskStatus.SAVING_RESULT:
        if not task.result_payload or task.completed_at is not None:
            raise RuntimeError("saving analysis task is missing payload")
    elif status is AnalysisTaskStatus.WAITING_FOR_REVIEW:
        if task.result_id is None or task.completed_at is not None:
            raise RuntimeError("review task is missing its result")
    elif status is AnalysisTaskStatus.COMPLETED:
        if task.result_id is None or task.completed_at is None or task.progress != 100:
            raise RuntimeError("completed analysis task is incomplete")
    elif status is AnalysisTaskStatus.FAILED:
        if not task.error_message or task.completed_at is not None:
            raise RuntimeError("failed analysis task is missing its error")


class AnalysisTaskService:
    """Create, execute, resume, and review user-owned analysis tasks."""

    def __init__(
        self,
        session: Session,
        user_email: str,
        analyzer: AnalysisService,
        retrieval_service: RetrievalService,
        *,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = ANALYSIS_TASK_LEASE_SECONDS,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lease_seconds = lease_seconds
        self.users = UserRepository(session)
        self.jobs = JobRepository(session)
        self.profiles = ProfileRepository(session)
        self.analyses = AnalysisRepository(session)
        self.tasks = AnalysisTaskRepository(session)
        self.analysis_workflow = ApplicationAnalysisService(
            session,
            self.user_email,
            analyzer=analyzer,
            retrieval_service=retrieval_service,
        )

    def create(self, job_id: uuid.UUID) -> AnalysisTaskStarted:
        user = self.users.get_or_create_by_email(self.user_email)
        if self.jobs.get_for_user(job_id, user.id) is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        existing = self.tasks.get_active_for_job(user.id, job_id)
        if existing is not None:
            self.session.rollback()
            return self._started(existing)
        try:
            task = self.tasks.add(AnalysisTask(user_id=user.id, job_id=job_id))
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.tasks.get_active_for_job(user.id, job_id)
            if existing is None:
                raise
            task = existing
        validate_analysis_task(task)
        return self._started(task)

    def get(self, task_id: uuid.UUID) -> AnalysisTask:
        user = self.users.get_or_create_by_email(self.user_email)
        task = self.tasks.get_for_user(task_id, user.id)
        if task is None:
            self.session.rollback()
            raise ResourceNotFoundError("analysis task not found")
        return task

    def get_current_for_job(self, job_id: uuid.UUID) -> AnalysisTask:
        task = self.find_current_for_job(job_id)
        if task is None:
            self.session.rollback()
            raise ResourceNotFoundError("active analysis task not found")
        return task

    def find_current_for_job(self, job_id: uuid.UUID) -> AnalysisTask | None:
        """Return no task without turning the normal empty state into an HTTP error."""
        user = self.users.get_or_create_by_email(self.user_email)
        if self.jobs.get_for_user(job_id, user.id) is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        return self.tasks.get_current_for_job(user.id, job_id)

    def run(self, task_id: uuid.UUID) -> AnalysisTask:
        task = self.get(task_id)
        if task.status == AnalysisTaskStatus.COMPLETED.value:
            raise ResourceConflictError("completed analysis tasks cannot be run again")
        if task.status == AnalysisTaskStatus.FAILED.value:
            raise ResourceConflictError("failed analysis tasks must be retried")
        if task.status == AnalysisTaskStatus.WAITING_FOR_REVIEW.value:
            validate_analysis_task(task)
            return task
        claim_token = self._claim(task, increment_retry=False)
        if claim_token is None:
            self.session.expire_all()
            return self.get(task_id)
        return self._execute_claimed(task_id, claim_token)

    def retry(self, task_id: uuid.UUID) -> AnalysisTask:
        task = self.get(task_id)
        if task.status != AnalysisTaskStatus.FAILED.value:
            raise ResourceConflictError("only failed analysis tasks can be retried")
        if task.retry_count >= task.max_retries:
            raise ResourceConflictError("analysis task retry limit exceeded")
        active = self.tasks.get_active_for_job(task.user_id, task.job_id)
        if active is not None and active.id != task.id:
            raise ResourceConflictError(
                "another active analysis task already exists for this job"
            )
        recovery = RECOVERY_STEPS.get(task.current_step)
        if recovery is None:
            raise ResourceConflictError(
                f"analysis task cannot recover from step {task.current_step}"
            )
        if (
            recovery is AnalysisTaskStatus.SAVING_RESULT
            and not task.result_payload
        ):
            recovery = AnalysisTaskStatus.ANALYZING
        claim_token = self._claim(task, increment_retry=True)
        if claim_token is None:
            self.session.expire_all()
            return self.get(task_id)
        return self._execute_claimed(task_id, claim_token, recovery=recovery)

    def complete(self, task_id: uuid.UUID) -> AnalysisTask:
        task = self.get(task_id)
        if task.status != AnalysisTaskStatus.WAITING_FOR_REVIEW.value:
            raise ResourceConflictError(
                "only review-ready analysis tasks can be completed"
            )
        if task.result_id is None:
            raise ResourceConflictError("analysis task result is missing")
        analysis = self.session.get(Analysis, task.result_id)
        if (
            analysis is None
            or analysis.user_id != task.user_id
            or analysis.job_id != task.job_id
        ):
            raise ResourceConflictError("analysis task result ownership is invalid")
        now = self.clock()
        changed = self.tasks.compare_and_set(
            task.id,
            task.user_id,
            expected_status=AnalysisTaskStatus.WAITING_FOR_REVIEW.value,
            expected_version=task.version,
            require_idle=True,
            values={
                "status": AnalysisTaskStatus.COMPLETED.value,
                "current_step": AnalysisTaskStatus.COMPLETED.value,
                "progress": 100,
                "completed_at": now,
                "error_code": None,
                "error_message": None,
            },
        )
        if not changed:
            self.session.expire_all()
            raise ResourceConflictError("analysis task changed concurrently")
        self.session.expire_all()
        completed = self.get(task.id)
        validate_analysis_task(completed)
        return completed

    @staticmethod
    def _started(task: AnalysisTask) -> AnalysisTaskStarted:
        return AnalysisTaskStarted(
            task_id=task.id,
            status=AnalysisTaskStatus(task.status),
            current_step=task.current_step,
            progress=task.progress,
        )

    def _claim(self, task: AnalysisTask, *, increment_retry: bool) -> str | None:
        now = self.clock()
        claim_token = uuid.uuid4().hex
        try:
            claimed = self.tasks.claim(
                task.id,
                task.user_id,
                expected_status=task.status,
                expected_version=task.version,
                claim_token=claim_token,
                claimed_at=now,
                lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                increment_retry=increment_retry,
            )
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return claim_token if claimed else None

    def _execute_claimed(
        self,
        task_id: uuid.UUID,
        claim_token: str,
        *,
        recovery: AnalysisTaskStatus | None = None,
    ) -> AnalysisTask:
        try:
            self.session.expire_all()
            task = self.get(task_id)
            if recovery is not None:
                self._transition_claimed(task, recovery, claim_token)
            while task.status not in {
                AnalysisTaskStatus.WAITING_FOR_REVIEW.value,
                AnalysisTaskStatus.COMPLETED.value,
            }:
                status = AnalysisTaskStatus(task.status)
                if status is AnalysisTaskStatus.PENDING:
                    self._transition_claimed(
                        task,
                        AnalysisTaskStatus.FETCHING_JOB,
                        claim_token,
                        extra_values={"started_at": task.started_at or self.clock()},
                    )
                elif status is AnalysisTaskStatus.FETCHING_JOB:
                    self._validate_inputs(task)
                    self._transition_claimed(
                        task, AnalysisTaskStatus.ANALYZING, claim_token
                    )
                elif status is AnalysisTaskStatus.ANALYZING:
                    if task.result_payload:
                        self._transition_claimed(
                            task, AnalysisTaskStatus.SAVING_RESULT, claim_token
                        )
                    else:
                        self._analyze_and_advance(task, claim_token)
                elif status is AnalysisTaskStatus.SAVING_RESULT:
                    if not task.result_payload:
                        self._transition_claimed(
                            task, AnalysisTaskStatus.ANALYZING, claim_token
                        )
                        continue
                    self._save_result(task, claim_token)
                    self._transition_claimed(
                        task, AnalysisTaskStatus.WAITING_FOR_REVIEW, claim_token
                    )
                else:
                    raise ResourceConflictError(f"task cannot run from {status.value}")
            validate_analysis_task(task)
            return task
        except ResourceConflictError:
            self.session.rollback()
            self.session.expire_all()
            return self.get(task_id)
        except Exception as exc:
            self._fail(task_id, claim_token, exc)
            return self.get(task_id)
        finally:
            self._safe_release(task_id, claim_token)

    def _transition_claimed(
        self,
        task: AnalysisTask,
        target: AnalysisTaskStatus,
        claim_token: str,
        *,
        extra_values: dict[str, object] | None = None,
    ) -> None:
        source = AnalysisTaskStatus(task.status)
        if target not in ALLOWED_TRANSITIONS[source]:
            raise ResourceConflictError(
                f"illegal analysis task transition: {source.value} -> {target.value}"
            )
        values: dict[str, object] = {
            "status": target.value,
            "current_step": target.value,
            "progress": PROGRESS_BY_STATUS[target],
            "error_code": None,
            "error_message": None,
        }
        if extra_values:
            values.update(extra_values)
        changed = self.tasks.compare_and_set(
            task.id,
            task.user_id,
            expected_status=source.value,
            expected_version=task.version,
            claim_token=claim_token,
            values=values,
        )
        if not changed:
            raise ResourceConflictError("analysis task changed concurrently")
        self.session.refresh(task)

    def _validate_inputs(self, task: AnalysisTask) -> None:
        if self.jobs.get_for_user(task.job_id, task.user_id) is None:
            raise ResourceNotFoundError("job not found")
        if self.profiles.get_for_user(task.user_id) is None:
            raise ResourceNotFoundError("profile not found")

    def _analyze_and_advance(
        self, task: AnalysisTask, claim_token: str
    ) -> None:
        job = self.jobs.get_for_user(task.job_id, task.user_id)
        profile = self.profiles.get_for_user(task.user_id)
        if job is None or profile is None:
            raise ResourceNotFoundError("job or profile not found")
        extracted = self.analysis_workflow.analyzer.extract_job(
            job.title, job.description, _profile_text(profile)
        )
        evidence = self.analysis_workflow._retrieve_evidence(extracted)
        result = self.analysis_workflow.analyzer.analyze_job(
            job.title, job.description, _profile_text(profile, evidence)
        )
        payload = {
            "candidate_profile_id": str(profile.id),
            "analysis": result.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        changed = self.tasks.compare_and_set(
            task.id,
            task.user_id,
            expected_status=AnalysisTaskStatus.ANALYZING.value,
            expected_version=task.version,
            claim_token=claim_token,
            values={
                "result_payload": payload,
                "status": AnalysisTaskStatus.SAVING_RESULT.value,
                "current_step": AnalysisTaskStatus.SAVING_RESULT.value,
                "progress": PROGRESS_BY_STATUS[AnalysisTaskStatus.SAVING_RESULT],
            },
        )
        if not changed:
            raise ResourceConflictError("analysis task changed concurrently")
        self.session.refresh(task)
        validate_analysis_task(task)

    def _save_result(self, task: AnalysisTask, claim_token: str) -> None:
        if task.result_id is not None:
            analysis = self.session.get(Analysis, task.result_id)
            if (
                analysis is None
                or analysis.user_id != task.user_id
                or analysis.job_id != task.job_id
            ):
                raise ResourceConflictError("analysis task result ownership is invalid")
            return
        payload = task.result_payload
        if not payload.get("analysis") or not payload.get("candidate_profile_id"):
            raise RuntimeError("persisted analysis payload is missing")
        result = payload["analysis"]
        analysis = self.analyses.add(Analysis(
            user_id=task.user_id,
            job_id=task.job_id,
            candidate_profile_id=uuid.UUID(str(payload["candidate_profile_id"])),
            status="completed",
            score=result.get("score"),
            result_json=result,
            evidence_json=payload.get("evidence", []),
            scoring_version=SCORING_VERSION,
            prompt_version=PROMPT_VERSION,
            model_provider=os.getenv("LLM_PROVIDER", "deepseek").strip() or "deepseek",
            model_name=os.getenv("LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        ))
        changed = self.session.execute(
            update(AnalysisTask)
            .where(
                AnalysisTask.id == task.id,
                AnalysisTask.user_id == task.user_id,
                AnalysisTask.status == AnalysisTaskStatus.SAVING_RESULT.value,
                AnalysisTask.version == task.version,
                AnalysisTask.is_running.is_(True),
                AnalysisTask.claim_token == claim_token,
            )
            .values(result_id=analysis.id, version=AnalysisTask.version + 1)
        ).rowcount == 1
        if not changed:
            self.session.rollback()
            raise ResourceConflictError("analysis task changed concurrently")
        self.session.commit()
        self.session.refresh(task)

    def _fail(self, task_id: uuid.UUID, claim_token: str, exc: Exception) -> None:
        self.session.rollback()
        task = self.session.get(AnalysisTask, task_id)
        if (
            task is None
            or task.claim_token != claim_token
            or not task.is_running
            or task.status in {
                AnalysisTaskStatus.FAILED.value,
                AnalysisTaskStatus.COMPLETED.value,
            }
        ):
            return
        public_message = (
            exc.public_message
            if isinstance(exc, LLMServiceError)
            else str(exc)
            if isinstance(exc, ResourceNotFoundError)
            else "analysis task failed"
        )
        changed = self.tasks.compare_and_set(
            task.id,
            task.user_id,
            expected_status=task.status,
            expected_version=task.version,
            claim_token=claim_token,
            values={
                "status": AnalysisTaskStatus.FAILED.value,
                "current_step": task.status,
                "error_code": type(exc).__name__[:100],
                "error_message": public_message[:1000],
                "completed_at": None,
            },
        )
        if not changed:
            logger.warning("Analysis task failure state lost a concurrent CAS")

    def _safe_release(self, task_id: uuid.UUID, claim_token: str) -> None:
        try:
            self.tasks.release(task_id, claim_token)
        except SQLAlchemyError:
            self.session.rollback()
            logger.exception(
                "Failed to release analysis task claim",
                extra={"analysis_task_id": str(task_id)},
            )


def recover_interrupted_analysis_tasks(
    session: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Release only expired leases left by a stopped single demo instance."""
    return AnalysisTaskRepository(session).release_expired(
        now or datetime.now(timezone.utc)
    )
