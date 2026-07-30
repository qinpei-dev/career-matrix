"""Add persistent per-user workspace settings.

Revision ID: 20260730_0011
Revises: 20260724_0010
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from backend.app.infrastructure.database.base import JSON_TYPE

revision: str = "20260730_0011"
down_revision: str | None = "20260724_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "display_name",
            sa.String(length=100),
            server_default="Demo 用户",
            nullable=False,
        ),
        sa.Column("target_role", sa.String(length=200), nullable=True),
        sa.Column(
            "default_analysis_options",
            JSON_TYPE,
            server_default=sa.text(
                """'{"auto_run": true, "require_review": true}'"""
            ),
            nullable=False,
        ),
        sa.Column("page_size", sa.Integer(), server_default="20", nullable=False),
        sa.Column(
            "show_technical_details",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_size IN (10, 20, 50, 100)",
            name=op.f("ck_user_settings_user_settings_page_size"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_settings")),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
