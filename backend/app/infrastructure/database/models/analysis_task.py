"""Persistent, resumable job-analysis task model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSON_TYPE, TimestampMixin


class AnalysisTaskStatus(StrEnum):
    PENDING = "PENDING"
    FETCHING_JOB = "FETCHING_JOB"
    ANALYZING = "ANALYZING"
    SAVING_RESULT = "SAVING_RESULT"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ACTIVE_TASK_STATUSES = (
    AnalysisTaskStatus.PENDING.value,
    AnalysisTaskStatus.FETCHING_JOB.value,
    AnalysisTaskStatus.ANALYZING.value,
    AnalysisTaskStatus.SAVING_RESULT.value,
    AnalysisTaskStatus.WAITING_FOR_REVIEW.value,
)


class AnalysisTask(TimestampMixin, Base):
    __tablename__ = "analysis_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
            "'SAVING_RESULT', 'WAITING_FOR_REVIEW', 'COMPLETED', 'FAILED')",
            name="analysis_task_status",
        ),
        CheckConstraint("progress >= 0 AND progress <= 100", name="analysis_task_progress"),
        CheckConstraint("retry_count >= 0", name="analysis_task_retry_count"),
        CheckConstraint("max_retries >= 0", name="analysis_task_max_retries"),
        Index(
            "uq_analysis_tasks_active_user_job",
            "user_id",
            "job_id",
            unique=True,
            postgresql_where=text(
                "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
                "'SAVING_RESULT', 'WAITING_FOR_REVIEW')"
            ),
            sqlite_where=text(
                "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
                "'SAVING_RESULT', 'WAITING_FOR_REVIEW')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=AnalysisTaskStatus.PENDING.value, nullable=False, index=True
    )
    current_step: Mapped[str] = mapped_column(
        String(32), default=AnalysisTaskStatus.PENDING.value, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    result_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analyses.id", ondelete="RESTRICT"), unique=True
    )
    result_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    claim_token: Mapped[str | None] = mapped_column(String(64))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    result = relationship("Analysis", foreign_keys=[result_id])
