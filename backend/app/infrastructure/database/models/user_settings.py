"""Per-user preferences for the local workspace."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, JSON_TYPE, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint(
            "page_size IN (10, 20, 50, 100)",
            name="user_settings_page_size",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(
        String(100), default="Demo 用户", nullable=False
    )
    target_role: Mapped[str | None] = mapped_column(String(200))
    default_analysis_options: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        default=lambda: {"auto_run": True, "require_review": True},
        nullable=False,
    )
    page_size: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    show_technical_details: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="settings")
