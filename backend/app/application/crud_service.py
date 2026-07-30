"""Transactional CRUD use cases for profiles, jobs, and analyses."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..infrastructure.database.models import Analysis, CandidateProfile, Job, User
from ..infrastructure.database.repositories import (
    AnalysisRepository,
    JobRepository,
    ProfileRepository,
    UserRepository,
)
from ..schemas import AnalysisCreate, JobCreate, ProfileCreate, ProfileUpdate
from ..schemas.job import JobUpdate
from .job_fingerprint import generate_job_fingerprint

# Development/demo fallback only. Authentication can replace the request-scoped
# email at the API dependency boundary without changing these CRUD use cases.
DEFAULT_USER_EMAIL = "demo@example.com"


class ResourceNotFoundError(RuntimeError):
    """A requested or associated resource is unavailable to the current user."""


class ResourceConflictError(RuntimeError):
    """Creating a resource would violate an application invariant."""


@dataclass(frozen=True)
class JobCreationResult:
    """The persisted job and whether this request created it."""

    job: Job
    status: Literal["created", "duplicate"]
    message: str | None = None


class CrudService:
    """Coordinate user-scoped persistence and transaction boundaries."""

    def __init__(self, session: Session, user_email: str) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)
        self.jobs = JobRepository(session)
        self.analyses = AnalysisRepository(session)

    def _current_user(self) -> User:
        return self.users.get_or_create_by_email(self.user_email)

    def _commit(self, entity: object) -> None:
        self.session.commit()
        self.session.refresh(entity)

    def get_profile(self) -> CandidateProfile:
        user = self._current_user()
        profile = self.profiles.get_for_user(user.id)
        if profile is None:
            self.session.rollback()
            raise ResourceNotFoundError("profile not found")
        self.session.commit()
        return profile

    def create_profile(self, payload: ProfileCreate) -> CandidateProfile:
        user = self._current_user()
        if self.profiles.get_for_user(user.id) is not None:
            self.session.rollback()
            raise ResourceConflictError("profile already exists")
        profile = self.profiles.add(
            CandidateProfile(user_id=user.id, **payload.model_dump())
        )
        self._commit(profile)
        return profile

    def update_profile(self, payload: ProfileUpdate) -> CandidateProfile:
        user = self._current_user()
        profile = self.profiles.get_for_user(user.id)
        if profile is None:
            self.session.rollback()
            raise ResourceNotFoundError("profile not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        self._commit(profile)
        return profile

    def create_job(self, payload: JobCreate) -> JobCreationResult:
        fingerprint = generate_job_fingerprint(
            source_url=payload.source_url,
            title=payload.title,
            company=payload.company,
            description=payload.description,
        )
        try:
            user = self._current_user()
            existing = self.jobs.get_by_fingerprint_for_user(fingerprint, user.id)
            if existing is not None:
                self.session.commit()
                return JobCreationResult(existing, "duplicate", "该岗位已保存")
            job = self.jobs.add(
                Job(
                    user_id=user.id,
                    job_fingerprint=fingerprint,
                    **payload.model_dump(),
                )
            )
            self._commit(job)
            return JobCreationResult(job, "created")
        except IntegrityError:
            # The composite unique constraint is the final concurrency guard.
            self.session.rollback()
            persisted_user = self.session.scalar(
                select(User).where(User.email == self.user_email)
            )
            if persisted_user is None:
                raise
            existing = self.jobs.get_by_fingerprint_for_user(
                fingerprint, persisted_user.id
            )
            if existing is None:
                raise
            self.session.commit()
            return JobCreationResult(existing, "duplicate", "该岗位已保存")

    def list_jobs(
        self,
        *,
        query: str | None = None,
        source_type: str | None = None,
        analysis_status: str | None = None,
        sort: str = "updated_desc",
        offset: int = 0,
        limit: int = 20,
    ) -> list[Job]:
        user = self._current_user()
        jobs = self.jobs.list_for_user(
            user.id,
            query=query,
            source_type=source_type,
            analysis_status=analysis_status,
            sort=sort,
            offset=offset,
            limit=limit,
        )
        self.session.commit()
        return jobs

    def get_job(self, job_id: uuid.UUID) -> Job:
        user = self._current_user()
        job = self.jobs.get_for_user(job_id, user.id)
        if job is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        self.session.commit()
        return job

    def update_job(self, job_id: uuid.UUID, payload: JobUpdate) -> Job:
        user = self._current_user()
        job = self.jobs.get_for_user(job_id, user.id)
        if job is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")

        values = payload.model_dump(exclude_unset=True)
        candidate = {
            "title": values.get("title", job.title),
            "company": values.get("company", job.company),
            "description": values.get("description", job.description),
            "source_url": values.get("source_url", job.source_url),
        }
        fingerprint = generate_job_fingerprint(**candidate)
        duplicate = self.jobs.get_by_fingerprint_for_user(fingerprint, user.id)
        if duplicate is not None and duplicate.id != job.id:
            self.session.rollback()
            raise ResourceConflictError("该岗位与已保存岗位重复")

        for field, value in values.items():
            setattr(job, field, value)
        job.job_fingerprint = fingerprint
        try:
            self._commit(job)
        except IntegrityError as exc:
            self.session.rollback()
            raise ResourceConflictError("该岗位与已保存岗位重复") from exc
        return job

    def delete_job(self, job_id: uuid.UUID) -> None:
        user = self._current_user()
        job = self.jobs.get_for_user(job_id, user.id)
        if job is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        if self.jobs.has_active_work(job.id, user.id):
            self.session.rollback()
            raise ResourceConflictError("岗位仍有运行中或待确认的分析任务，暂时无法删除")
        self.jobs.delete_with_dependents(job)
        self.session.commit()

    def create_analysis(self, payload: AnalysisCreate) -> Analysis:
        user = self._current_user()
        if self.jobs.get_for_user(payload.job_id, user.id) is None:
            self.session.rollback()
            raise ResourceNotFoundError("job not found")
        profile = self.profiles.get_for_user(user.id)
        if profile is None or profile.id != payload.candidate_profile_id:
            self.session.rollback()
            raise ResourceNotFoundError("profile not found")
        analysis = self.analyses.add(
            Analysis(user_id=user.id, **payload.model_dump())
        )
        self._commit(analysis)
        return analysis

    def list_analyses(self) -> list[Analysis]:
        user = self._current_user()
        analyses = self.analyses.list_for_user(user.id)
        self.session.commit()
        return analyses
