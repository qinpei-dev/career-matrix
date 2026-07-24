"""Add persistent, resumable analysis tasks.

Revision ID: 20260724_0009
Revises: 20260723_0008
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from backend.app.infrastructure.database.base import JSON_TYPE

revision: str = "20260724_0009"
down_revision: str | None = "20260723_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_id", sa.Uuid(), nullable=True),
        sa.Column("result_payload", JSON_TYPE, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_running", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
            "'SAVING_RESULT', 'WAITING_FOR_REVIEW', 'COMPLETED', 'FAILED')",
            name=op.f("ck_analysis_tasks_analysis_task_status"),
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name=op.f("ck_analysis_tasks_analysis_task_progress"),
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name=op.f("ck_analysis_tasks_analysis_task_retry_count"),
        ),
        sa.CheckConstraint(
            "max_retries >= 0",
            name=op.f("ck_analysis_tasks_analysis_task_max_retries"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="CASCADE",
            name=op.f("fk_analysis_tasks_job_id_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["result_id"], ["analyses.id"], ondelete="SET NULL",
            name=op.f("fk_analysis_tasks_result_id_analyses"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name=op.f("fk_analysis_tasks_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_tasks")),
        sa.UniqueConstraint("result_id", name=op.f("uq_analysis_tasks_result_id")),
    )
    op.create_index(
        op.f("ix_analysis_tasks_job_id"), "analysis_tasks", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_analysis_tasks_status"), "analysis_tasks", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_analysis_tasks_user_id"), "analysis_tasks", ["user_id"], unique=False
    )
    op.create_index(
        "uq_analysis_tasks_active_user_job",
        "analysis_tasks",
        ["user_id", "job_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
            "'SAVING_RESULT', 'WAITING_FOR_REVIEW')"
        ),
        sqlite_where=sa.text(
            "status IN ('PENDING', 'FETCHING_JOB', 'ANALYZING', "
            "'SAVING_RESULT', 'WAITING_FOR_REVIEW')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_analysis_tasks_active_user_job", table_name="analysis_tasks"
    )
    op.drop_index(op.f("ix_analysis_tasks_user_id"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_status"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_job_id"), table_name="analysis_tasks")
    op.drop_table("analysis_tasks")
