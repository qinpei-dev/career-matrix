"""Job persistence model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin

if TYPE_CHECKING:
    from .agent import AgentRun
    from .analysis import Analysis
    from .user import User
    from .tailored_resume import TailoredResume


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "job_fingerprint",
            name="uq_jobs_user_id_job_fingerprint",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    job_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    user: Mapped["User"] = relationship(back_populates="jobs")
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    tailored_resumes: Mapped[list["TailoredResume"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
