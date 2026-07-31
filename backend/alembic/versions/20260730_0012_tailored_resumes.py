"""Add evidence-backed tailored resume versions.

Revision ID: 20260730_0012
Revises: 20260730_0011
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from backend.app.infrastructure.database.base import JSON_TYPE

revision: str = "20260730_0012"
down_revision: str | None = "20260730_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tailored_resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="DRAFT", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("skills_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("experience_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("projects_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("education_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("evidence_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column("warnings_json", JSON_TYPE, server_default=sa.text("'[]'"), nullable=False),
        sa.Column(
            "generated_content_json", JSON_TYPE, server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "user_edited_content_json", JSON_TYPE, server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("generation_key", sa.String(length=64), nullable=True),
        sa.Column("is_generating", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','GENERATED','EDITING','FINALIZED','FAILED')",
            name=op.f("ck_tailored_resumes_tailored_resume_status"),
        ),
        sa.CheckConstraint("version >= 0", name=op.f("ck_tailored_resumes_version")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name=op.f("fk_tailored_resumes_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], ondelete="CASCADE",
            name=op.f("fk_tailored_resumes_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["documents.id"], ondelete="CASCADE",
            name=op.f("fk_tailored_resumes_source_document_id_documents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tailored_resumes")),
    )
    op.create_index(op.f("ix_tailored_resumes_user_id"), "tailored_resumes", ["user_id"])
    op.create_index(op.f("ix_tailored_resumes_job_id"), "tailored_resumes", ["job_id"])
    op.create_index(
        op.f("ix_tailored_resumes_source_document_id"),
        "tailored_resumes",
        ["source_document_id"],
    )
    op.create_index(op.f("ix_tailored_resumes_status"), "tailored_resumes", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tailored_resumes_status"), table_name="tailored_resumes")
    op.drop_index(
        op.f("ix_tailored_resumes_source_document_id"), table_name="tailored_resumes"
    )
    op.drop_index(op.f("ix_tailored_resumes_job_id"), table_name="tailored_resumes")
    op.drop_index(op.f("ix_tailored_resumes_user_id"), table_name="tailored_resumes")
    op.drop_table("tailored_resumes")
