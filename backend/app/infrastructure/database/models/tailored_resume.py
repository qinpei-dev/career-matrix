"""Evidence-backed tailored resume versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSON_TYPE, TimestampMixin

if TYPE_CHECKING:
    from .document import Document
    from .job import Job
    from .user import User


class TailoredResumeStatus:
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    EDITING = "EDITING"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"


class TailoredResume(TimestampMixin, Base):
    __tablename__ = "tailored_resumes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=TailoredResumeStatus.DRAFT, nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    skills_json: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list, nullable=False)
    experience_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    projects_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    education_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    warnings_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_TYPE, default=list, nullable=False
    )
    generated_content_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    user_edited_content_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE, default=dict, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(500))
    generation_key: Mapped[str | None] = mapped_column(String(64))
    is_generating: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="tailored_resumes")
    job: Mapped["Job"] = relationship(back_populates="tailored_resumes")
    source_document: Mapped["Document"] = relationship(back_populates="tailored_resumes")
