"""Add salary, location, experience and education to saved jobs.

Revision ID: 20261110_0014
Revises: 20261110_0013
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261110_0014"
down_revision: str | None = "20261110_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (("salary", 100), ("location", 200), ("experience", 100), ("education", 100))


def upgrade() -> None:
    for name, length in COLUMNS:
        op.add_column("jobs", sa.Column(name, sa.String(length=length), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        for name, _length in reversed(COLUMNS):
            batch.drop_column(name)
