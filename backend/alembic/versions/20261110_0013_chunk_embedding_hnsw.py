"""Add an HNSW cosine index on chunk embeddings.

Revision ID: 20261110_0013
Revises: 20260730_0012
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261110_0013"
down_revision: str | None = "20260730_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_document_chunks_embedding_hnsw"


def upgrade() -> None:
    # SQLite stores embeddings as JSON and scores them in Python; no index there.
    if op.get_context().dialect.name == "postgresql":
        op.create_index(
            INDEX_NAME,
            "document_chunks",
            ["embedding"],
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        )


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.drop_index(INDEX_NAME, table_name="document_chunks")
