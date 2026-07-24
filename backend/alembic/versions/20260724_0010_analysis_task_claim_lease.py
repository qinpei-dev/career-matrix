"""Add owned analysis-task claims and lease expiry.

Revision ID: 20260724_0010
Revises: 20260724_0009
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260724_0010"
down_revision: str | None = "20260724_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.add_column(sa.Column("claim_token", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.drop_constraint(
            "fk_analysis_tasks_result_id_analyses", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_analysis_tasks_result_id_analyses",
            "analyses",
            ["result_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    # A migration runs while the application is stopped. Any is_running row
    # inherited from 0009 has no owner or lease and is therefore a legacy claim.
    analysis_tasks = sa.table(
        "analysis_tasks",
        sa.column("is_running", sa.Boolean()),
        sa.column("claim_token", sa.String()),
        sa.column("claimed_at", sa.DateTime(timezone=True)),
        sa.column("lease_expires_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        analysis_tasks.update()
        .where(analysis_tasks.c.is_running.is_(True))
        .values(
            is_running=False,
            claim_token=None,
            claimed_at=None,
            lease_expires_at=None,
        )
    )
    op.create_index(
        op.f("ix_analysis_tasks_lease_expires_at"),
        "analysis_tasks",
        ["lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_analysis_tasks_lease_expires_at"),
        table_name="analysis_tasks",
    )
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.drop_constraint(
            "fk_analysis_tasks_result_id_analyses", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "fk_analysis_tasks_result_id_analyses",
            "analyses",
            ["result_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.drop_column("lease_expires_at")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("claim_token")
