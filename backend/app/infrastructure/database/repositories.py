"""SQLAlchemy repositories for versioned CRUD APIs."""

import math
import uuid
from datetime import datetime

from sqlalchemy import Float, delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from .models import (
    AgentRun, AgentStep, Analysis, AnalysisTask, CandidateProfile, Document,
    DocumentChunk, Job, User,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_by_email(self, email: str) -> User:
        user = self.session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email)
            self.session.add(user)
            self.session.flush()
        return user


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: uuid.UUID) -> CandidateProfile | None:
        return self.session.scalar(
            select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        )

    def add(self, profile: CandidateProfile) -> CandidateProfile:
        self.session.add(profile)
        self.session.flush()
        return profile


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, job: Job) -> Job:
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_fingerprint_for_user(
        self, job_fingerprint: str, user_id: uuid.UUID
    ) -> Job | None:
        return self.session.scalar(
            select(Job).where(
                Job.job_fingerprint == job_fingerprint,
                Job.user_id == user_id,
            )
        )

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        query: str | None = None,
        source_type: str | None = None,
        analysis_status: str | None = None,
        sort: str = "updated_desc",
        offset: int = 0,
        limit: int | None = 20,
    ) -> list[Job]:
        statement = select(Job).where(Job.user_id == user_id)
        if query:
            pattern = f"%{query.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Job.title).like(pattern),
                    func.lower(func.coalesce(Job.company, "")).like(pattern),
                )
            )
        if source_type:
            statement = statement.where(Job.source_type == source_type)
        has_analysis = exists(
            select(Analysis.id).where(
                Analysis.job_id == Job.id,
                Analysis.user_id == user_id,
            )
        )
        if analysis_status == "analyzed":
            statement = statement.where(has_analysis)
        elif analysis_status == "pending":
            statement = statement.where(~has_analysis)
        ordering = {
            "updated_desc": (Job.updated_at.desc(), Job.id.desc()),
            "created_desc": (Job.created_at.desc(), Job.id.desc()),
            "title_asc": (func.lower(Job.title), Job.id),
            "company_asc": (func.lower(func.coalesce(Job.company, "")), Job.id),
        }[sort]
        statement = statement.order_by(*ordering).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement))

    def get_for_user(self, job_id: uuid.UUID, user_id: uuid.UUID) -> Job | None:
        return self.session.scalar(
            select(Job).where(Job.id == job_id, Job.user_id == user_id)
        )

    def has_active_work(self, job_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        active_task = self.session.scalar(
            select(AnalysisTask.id).where(
                AnalysisTask.job_id == job_id,
                AnalysisTask.user_id == user_id,
                or_(
                    AnalysisTask.is_running.is_(True),
                    AnalysisTask.status.in_(
                        (
                            "PENDING",
                            "FETCHING_JOB",
                            "ANALYZING",
                            "SAVING_RESULT",
                            "WAITING_FOR_REVIEW",
                        )
                    ),
                ),
            ).limit(1)
        )
        if active_task is not None:
            return True
        active_run = self.session.scalar(
            select(AgentRun.id).where(
                AgentRun.job_id == job_id,
                AgentRun.user_id == user_id,
                AgentRun.status.in_(("pending", "running")),
            ).limit(1)
        )
        return active_run is not None

    def delete_with_dependents(self, job: Job) -> None:
        # Tasks can point at analyses through a RESTRICT foreign key, so remove
        # every terminal task before the job's ORM cascades delete its results.
        self.session.execute(delete(AnalysisTask).where(AnalysisTask.job_id == job.id))
        self.session.delete(job)
        self.session.flush()


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        return document

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        self.session.add_all(chunks)
        self.session.flush()

    def get_for_user(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )

    def get_by_hash_for_user(self, file_hash: str, user_id: uuid.UUID) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.user_id == user_id,
            )
        )

    def list_for_user_with_chunk_count(
        self, user_id: uuid.UUID
    ) -> list[tuple[Document, int]]:
        rows = self.session.execute(
            select(Document, func.count(DocumentChunk.id))
            .outerjoin(DocumentChunk)
            .where(Document.user_id == user_id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        )
        return [(document, int(chunk_count)) for document, chunk_count in rows]

    def get_for_user_with_chunk_count(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Document, int] | None:
        row = self.session.execute(
            select(Document, func.count(DocumentChunk.id))
            .outerjoin(DocumentChunk)
            .where(Document.id == document_id, Document.user_id == user_id)
            .group_by(Document.id)
        ).one_or_none()
        if row is None:
            return None
        return row[0], int(row[1])

    def list_chunks_for_document(self, document_id: uuid.UUID) -> list[DocumentChunk]:
        return list(
            self.session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index, DocumentChunk.id)
            )
        )


class RetrievalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def search_for_user(
        self,
        user_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[tuple[DocumentChunk, float]]:
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            distance = DocumentChunk.embedding.op("<=>", return_type=Float)(query_embedding)
            rows = self.session.execute(
                select(DocumentChunk, (1.0 - distance).label("score"))
                .join(Document)
                .where(
                    Document.user_id == user_id,
                    Document.status == "ready",
                    DocumentChunk.embedding.is_not(None),
                )
                .order_by(distance)
                .limit(top_k)
            )
            return [(chunk, float(score)) for chunk, score in rows]

        chunks = list(
            self.session.scalars(
                select(DocumentChunk)
                .join(Document)
                .where(
                    Document.user_id == user_id,
                    Document.status == "ready",
                    DocumentChunk.embedding.is_not(None),
                )
            )
        )
        scored = [
            (
                chunk,
                self._cosine_similarity(
                    [float(value) for value in chunk.embedding or []],
                    query_embedding,
                ),
            )
            for chunk in chunks
            if chunk.embedding is not None and len(chunk.embedding) == len(query_embedding)
        ]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:top_k]


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, analysis: Analysis) -> Analysis:
        self.session.add(analysis)
        self.session.flush()
        return analysis

    def set_result(
        self,
        analysis: Analysis,
        *,
        status: str,
        score: int | None,
        result_json: dict[str, object],
        evidence_json: list[dict[str, object]] | None = None,
    ) -> Analysis:
        analysis.status = status
        analysis.score = score
        analysis.result_json = result_json
        if evidence_json is not None:
            analysis.evidence_json = evidence_json
        self.session.flush()
        return analysis

    def list_for_user(self, user_id: uuid.UUID) -> list[Analysis]:
        return list(
            self.session.scalars(
                select(Analysis)
                .where(Analysis.user_id == user_id)
                .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            )
        )


class AnalysisTaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, task: AnalysisTask) -> AnalysisTask:
        self.session.add(task)
        self.session.flush()
        return task

    def get_for_user(
        self, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> AnalysisTask | None:
        return self.session.scalar(
            select(AnalysisTask).where(
                AnalysisTask.id == task_id,
                AnalysisTask.user_id == user_id,
            )
        )

    def get_active_for_job(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> AnalysisTask | None:
        return self.session.scalar(
            select(AnalysisTask).where(
                AnalysisTask.user_id == user_id,
                AnalysisTask.job_id == job_id,
                AnalysisTask.status.in_(
                    ("PENDING", "FETCHING_JOB", "ANALYZING",
                     "SAVING_RESULT", "WAITING_FOR_REVIEW")
                ),
            )
        )

    def get_current_for_job(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> AnalysisTask | None:
        return self.session.scalar(
            select(AnalysisTask)
            .where(
                AnalysisTask.user_id == user_id,
                AnalysisTask.job_id == job_id,
                AnalysisTask.status.in_(
                    ("PENDING", "FETCHING_JOB", "ANALYZING",
                     "SAVING_RESULT", "WAITING_FOR_REVIEW", "FAILED")
                ),
            )
            .order_by(AnalysisTask.created_at.desc(), AnalysisTask.id.desc())
        )

    def claim(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        expected_status: str,
        expected_version: int,
        claim_token: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
        increment_retry: bool = False,
    ) -> bool:
        conditions = [
            AnalysisTask.id == task_id,
            AnalysisTask.user_id == user_id,
            AnalysisTask.status == expected_status,
            AnalysisTask.is_running.is_(False),
            AnalysisTask.version == expected_version,
        ]
        if increment_retry:
            conditions.append(AnalysisTask.retry_count < AnalysisTask.max_retries)
        values: dict[str, object] = {
            "is_running": True,
            "claim_token": claim_token,
            "claimed_at": claimed_at,
            "lease_expires_at": lease_expires_at,
            "version": AnalysisTask.version + 1,
        }
        if increment_retry:
            values["retry_count"] = AnalysisTask.retry_count + 1
        result = self.session.execute(
            update(AnalysisTask)
            .where(*conditions)
            .values(**values)
        )
        self.session.commit()
        return result.rowcount == 1

    def compare_and_set(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        expected_status: str,
        expected_version: int,
        values: dict[str, object],
        claim_token: str | None = None,
        require_idle: bool = False,
    ) -> bool:
        conditions = [
            AnalysisTask.id == task_id,
            AnalysisTask.user_id == user_id,
            AnalysisTask.status == expected_status,
            AnalysisTask.version == expected_version,
        ]
        if claim_token is not None:
            conditions.extend((
                AnalysisTask.is_running.is_(True),
                AnalysisTask.claim_token == claim_token,
            ))
        if require_idle:
            conditions.append(AnalysisTask.is_running.is_(False))
        result = self.session.execute(
            update(AnalysisTask)
            .where(*conditions)
            .values(**values, version=AnalysisTask.version + 1)
        )
        self.session.commit()
        return result.rowcount == 1

    def release(self, task_id: uuid.UUID, claim_token: str) -> bool:
        result = self.session.execute(
            update(AnalysisTask)
            .where(
                AnalysisTask.id == task_id,
                AnalysisTask.claim_token == claim_token,
                AnalysisTask.is_running.is_(True),
            )
            .values(
                is_running=False,
                claim_token=None,
                claimed_at=None,
                lease_expires_at=None,
                version=AnalysisTask.version + 1,
            )
        )
        self.session.commit()
        return result.rowcount == 1

    def release_expired(self, now: datetime) -> int:
        result = self.session.execute(
            update(AnalysisTask)
            .where(
                AnalysisTask.is_running.is_(True),
                AnalysisTask.lease_expires_at.is_not(None),
                AnalysisTask.lease_expires_at < now,
            )
            .values(
                is_running=False,
                claim_token=None,
                claimed_at=None,
                lease_expires_at=None,
                version=AnalysisTask.version + 1,
            )
        )
        self.session.commit()
        return result.rowcount


class AgentRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, run: AgentRun) -> AgentRun:
        self.session.add(run)
        self.session.flush()
        return run

    def get_for_user(self, run_id: uuid.UUID, user_id: uuid.UUID) -> AgentRun | None:
        return self.session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )

    def get_active_for_job(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> AgentRun | None:
        return self.session.scalar(
            select(AgentRun).where(
                AgentRun.user_id == user_id,
                AgentRun.job_id == job_id,
                AgentRun.status.in_(("pending", "running")),
            )
        )

    def add_step(self, step: AgentStep) -> AgentStep:
        self.session.add(step)
        self.session.flush()
        return step

    def get_step(self, run_id: uuid.UUID, step_name: str) -> AgentStep | None:
        return self.session.scalar(
            select(AgentStep).where(
                AgentStep.run_id == run_id,
                AgentStep.step_name == step_name,
            )
        )
