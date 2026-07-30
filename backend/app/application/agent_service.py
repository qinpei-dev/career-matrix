"""Application service for constrained Career Copilot runs."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agents.career_copilot.schemas import (
    AgentFinalResult,
    AgentRunRead,
    AgentRunStarted,
    AgentRunStatus,
    AgentStepName,
    CalculateMatchScoreInput,
    CalculateMatchScoreOutput,
    GenerateApplicationMaterialInput,
    GenerateApplicationMaterialOutput,
    RetrieveCandidateEvidenceInput,
    RetrieveCandidateEvidenceOutput,
    SaveAnalysisResultInput,
    SaveAnalysisResultOutput,
    ValidatedAgentInput,
)
from ..agents.career_copilot.state import CareerCopilotState
from ..agents.career_copilot.tools import create_tool_registry
from ..agents.career_copilot.workflow import CareerCopilotWorkflow
from ..infrastructure.database.models import AgentRun, AgentStep, Analysis
from ..infrastructure.database.repositories import (
    AgentRunRepository,
    AnalysisRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)
from ..infrastructure.llm.parser import build_final_analysis
from ..services.scoring import calculate_match_score
from ..schemas.analysis import AnalysisEvidence
from .analysis_service import (
    EVIDENCE_MIN_SCORE,
    EVIDENCE_TOP_K,
    PROMPT_VERSION,
    SCORING_VERSION,
    AnalysisService,
)
from .crud_service import ResourceConflictError, ResourceNotFoundError
from .retrieval_service import RetrievalService
from ..core.security import public_error_message
from ..core.security import redact_sensitive_text


class AgentRunService:
    """Create, execute, and read user-scoped agent runs."""

    def __init__(
        self,
        session: Session,
        user_email: str,
        analyzer: AnalysisService,
        retrieval_service: RetrievalService,
        timeout_seconds: float = 120.0,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.analyzer = analyzer
        self.retrieval_service = retrieval_service
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.users = UserRepository(session)
        self.jobs = JobRepository(session)
        self.profiles = ProfileRepository(session)
        self.analyses = AnalysisRepository(session)
        self.runs = AgentRunRepository(session)
        self._active_run_id: uuid.UUID | None = None

    def create_run(self, job_id: uuid.UUID) -> AgentRunStarted:
        user = self.users.get_or_create_by_email(self.user_email)
        if self.jobs.get_for_user(job_id, user.id) is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        if self.runs.get_active_for_job(user.id, job_id) is not None:
            self.session.rollback()
            raise ResourceConflictError("an active agent run already exists for this job")
        try:
            run = self.runs.add(AgentRun(
                user_id=user.id,
                job_id=job_id,
                status=AgentRunStatus.PENDING.value,
                current_step=AgentStepName.VALIDATE_INPUT.value,
                result_json={},
            ))
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ResourceConflictError(
                "an active agent run already exists for this job"
            ) from exc
        return AgentRunStarted(run_id=run.id, status=AgentRunStatus.PENDING)

    def execute(self, run_id: uuid.UUID) -> None:
        user = self.users.get_or_create_by_email(self.user_email)
        run = self.runs.get_for_user(run_id, user.id)
        if run is None:
            self.session.rollback()
            return
        if run.status != AgentRunStatus.PENDING.value:
            return
        run.status = AgentRunStatus.RUNNING.value
        self.session.commit()
        self._active_run_id = run.id
        try:
            state = CareerCopilotState(run_id=run.id, job_id=run.job_id, user_id=user.id)
            tools = create_tool_registry(
                retrieve_handler=self._retrieve_candidate_evidence,
                calculate_handler=self._calculate_match_score,
                generate_handler=self._generate_application_material,
                save_handler=self._save_analysis_result,
            )
            workflow = CareerCopilotWorkflow(
                input_loader=self._load_input,
                extractor=self.analyzer.extract_job,
                tools=tools,
                step_started=self._step_started,
                step_finished=self._step_finished,
                step_failed=self._step_failed,
                run_finished=self._run_finished,
                timeout_seconds=self.timeout_seconds,
                clock=self.clock,
            )
            workflow.run(state)
        except Exception as exc:
            self.session.rollback()
            failed_run = self.session.get(AgentRun, run_id)
            if failed_run is not None and failed_run.status in {
                AgentRunStatus.PENDING.value,
                AgentRunStatus.RUNNING.value,
            }:
                failed_run.status = AgentRunStatus.FAILED.value
                failed_run.error_message = public_error_message(exc, "agent workflow failed")
                self.session.commit()
        finally:
            self._active_run_id = None

    def get_run(self, run_id: uuid.UUID) -> AgentRunRead:
        user = self.users.get_or_create_by_email(self.user_email)
        run = self.runs.get_for_user(run_id, user.id)
        if run is None:
            self.session.rollback()
            raise ResourceNotFoundError("agent run not found")
        return self._to_read(run)

    def get_active_run(self, job_id: uuid.UUID) -> AgentRunRead:
        """Return the persisted active run for refresh/restart recovery."""
        run = self.find_active_run(job_id)
        if run is None:
            self.session.rollback()
            raise ResourceNotFoundError("active agent run not found")
        return run

    def find_active_run(self, job_id: uuid.UUID) -> AgentRunRead | None:
        """Return no run without logging a normal empty state as a browser error."""
        user = self.users.get_or_create_by_email(self.user_email)
        if self.jobs.get_for_user(job_id, user.id) is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        run = self.runs.get_active_for_job(user.id, job_id)
        if run is None:
            return None
        return self._to_read(run)

    @staticmethod
    def _to_read(run: AgentRun) -> AgentRunRead:
        result = AgentFinalResult.model_validate(run.result_json) if run.result_json else None
        return AgentRunRead(
            run_id=run.id,
            user_id=run.user_id,
            job_id=run.job_id,
            status=run.status,
            current_step=run.current_step,
            steps=run.steps,
            result=result,
            error_message=run.error_message,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def _load_input(self, state: CareerCopilotState) -> ValidatedAgentInput:
        job = self.jobs.get_for_user(state.job_id, state.user_id)
        if job is None:
            raise ResourceNotFoundError("job not found")
        profile = self.profiles.get_for_user(state.user_id)
        if profile is None:
            raise ResourceNotFoundError("profile not found")
        return ValidatedAgentInput(
            job_title=job.title,
            job_description=job.description,
            candidate_profile_id=profile.id,
            candidate_name=profile.name,
            candidate_target_role=profile.target_role,
            candidate_summary=profile.summary,
            candidate_skills=list(profile.skills),
        )

    def _retrieve_candidate_evidence(
        self, payload: RetrieveCandidateEvidenceInput
    ) -> RetrieveCandidateEvidenceOutput:
        evidence = []
        for requirement in payload.requirements:
            for match in self.retrieval_service.search(requirement, EVIDENCE_TOP_K):
                if match.score >= EVIDENCE_MIN_SCORE:
                    evidence.append(AnalysisEvidence(
                        chunk_id=match.chunk_id,
                        document_id=match.document_id,
                        content=redact_sensitive_text(match.content),
                        section=redact_sensitive_text(match.section),
                        requirement=redact_sensitive_text(requirement),
                    ))
        return RetrieveCandidateEvidenceOutput(evidence=evidence)

    @staticmethod
    def _calculate_match_score(payload: CalculateMatchScoreInput) -> CalculateMatchScoreOutput:
        value = payload.extracted_analysis
        requirements = value.job_requirements
        calculated = calculate_match_score(
            core_skills=requirements.core_skills,
            preferred_skills=requirements.preferred_skills,
            project_requirements=requirements.project_requirements,
            education_requirements=requirements.education_requirements,
            experience_requirements=requirements.experience_requirements,
            matched_skills=value.matched_skills,
            partial_skills=value.partial_skills,
            missing_skills=value.missing_skills,
            unverified_skills=value.unverified_skills,
            project_status=value.project_status,
            education_status=value.education_status,
            experience_status=value.experience_status,
        )
        classified = calculated["classified_skills"]
        return CalculateMatchScoreOutput.model_validate({
            "score": calculated["score"],
            "score_breakdown": calculated["score_breakdown"],
            "matched_skills": classified["matched"],
            "partial_skills": classified["partial"],
            "missing_skills": classified["missing"],
            "unverified_skills": classified["unverified"],
        })

    @staticmethod
    def _generate_application_material(
        payload: GenerateApplicationMaterialInput,
    ) -> GenerateApplicationMaterialOutput:
        analysis = build_final_analysis(payload.extracted_analysis)
        if analysis.score != payload.calculated_score.score:
            raise RuntimeError("deterministic score verification failed")
        return GenerateApplicationMaterialOutput(analysis=analysis)

    def _save_analysis_result(self, payload: SaveAnalysisResultInput) -> SaveAnalysisResultOutput:
        analysis = self.analyses.add(Analysis(
            user_id=payload.user_id,
            job_id=payload.job_id,
            candidate_profile_id=payload.candidate_profile_id,
            status="completed",
            score=payload.analysis.score,
            result_json=payload.analysis.model_dump(mode="json"),
            evidence_json=[item.model_dump(mode="json") for item in payload.evidence],
            scoring_version=SCORING_VERSION,
            prompt_version=PROMPT_VERSION,
            model_provider=os.getenv("LLM_PROVIDER", "deepseek").strip() or "deepseek",
            model_name=os.getenv("LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        ))
        return SaveAnalysisResultOutput(analysis_id=analysis.id)

    def _active_run(self) -> AgentRun:
        if self._active_run_id is None:
            raise RuntimeError("agent run context is missing")
        run = self.session.get(AgentRun, self._active_run_id)
        if run is None:
            raise RuntimeError("agent run no longer exists")
        return run

    def _step_started(self, step_name: AgentStepName, input_summary: str) -> None:
        run = self._active_run()
        run.current_step = step_name.value
        self.runs.add_step(AgentStep(
            run_id=run.id,
            step_name=step_name.value,
            status="running",
            input_summary=input_summary,
        ))
        self.session.commit()
    def _step_finished(self, step_name: AgentStepName, output_summary: str, duration_ms: int) -> None:
        run = self._active_run()
        step = self.runs.get_step(run.id, step_name.value)
        if step is None:
            raise RuntimeError("agent step no longer exists")
        step.status = "completed"
        step.output_summary = output_summary
        step.duration_ms = duration_ms
        self.session.commit()

    def _step_failed(self, step_name: AgentStepName, message: str, duration_ms: int) -> None:
        self.session.rollback()
        run = self._active_run()
        step = self.runs.get_step(run.id, step_name.value)
        if step is not None:
            step.status = "failed"
            step.output_summary = message
            step.duration_ms = duration_ms
        self.session.commit()

    def _run_finished(self, state: CareerCopilotState) -> None:
        run = self._active_run()
        run.status = state.status.value
        run.current_step = state.current_step.value
        if state.status is AgentRunStatus.COMPLETED:
            if state.analysis_id is None or state.analysis_result is None:
                raise RuntimeError("completed run result is missing")
            run.result_json = AgentFinalResult(
                analysis_id=state.analysis_id,
                analysis=state.analysis_result,
                evidence=state.retrieved_evidence,
            ).model_dump(mode="json")
            run.error_message = None
        else:
            run.error_message = state.errors[-1].message if state.errors else "agent workflow failed"
        self.session.commit()


def recover_stale_agent_runs(
    session: Session,
    timeout_seconds: float,
    *,
    now: datetime | None = None,
) -> int:
    """Fail active tasks that stopped updating before the recovery cutoff."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(seconds=timeout_seconds)
    stale_runs = list(session.scalars(
        select(AgentRun).where(
            AgentRun.status.in_((
                AgentRunStatus.PENDING.value,
                AgentRunStatus.RUNNING.value,
            )),
            AgentRun.updated_at < cutoff,
        )
    ))
    for run in stale_runs:
        run.status = AgentRunStatus.FAILED.value
        run.error_message = "agent run was interrupted before completion"
        for step in run.steps:
            if step.status == "running":
                step.status = "failed"
                step.output_summary = "service restarted before this step completed"
    session.commit()
    return len(stale_runs)
