"""User-scoped semantic retrieval use case."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..infrastructure.database.repositories import RetrievalRepository, UserRepository
from ..infrastructure.database.vector import BGE_M3_DIMENSION
from ..infrastructure.embedding.provider import EmbeddingProvider, EmbeddingResponseError


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    section: str
    score: float


class RetrievalService:
    """Embed a query and retrieve only the current user's resume chunks."""

    def __init__(
        self,
        session: Session,
        user_email: str,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.embedding_provider = embedding_provider
        self.users = UserRepository(session)
        self.retrieval = RetrievalRepository(session)

    def search(
        self,
        query: str,
        top_k: int,
        document_id: uuid.UUID | None = None,
    ) -> list[RetrievalResult]:
        if self.embedding_provider.dimension != BGE_M3_DIMENSION:
            raise EmbeddingResponseError(
                "embedding provider dimension does not match the database schema"
            )
        query_embedding = self.embedding_provider.embed_query(query)
        if len(query_embedding) != BGE_M3_DIMENSION:
            raise EmbeddingResponseError("query embedding has an invalid dimension")
        user = self.users.get_or_create_by_email(self.user_email)
        matches = self.retrieval.search_for_user(
            user.id, query_embedding, top_k, document_id=document_id
        )
        self.session.commit()
        return [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                section=chunk.section,
                score=max(-1.0, min(1.0, score)),
            )
            for chunk, score in matches
        ]
