"""User-scoped semantic retrieval use case."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from ..infrastructure.database.repositories import RetrievalRepository, UserRepository
from ..infrastructure.database.vector import BGE_M3_DIMENSION
from ..infrastructure.embedding.provider import EmbeddingProvider, EmbeddingResponseError
from ..infrastructure.embedding.reranker import Reranker

# Thresholds are measured with backend/eval (bge-m3 + bge-reranker-v2-m3); see README.
EVIDENCE_TOP_K = 2
# Cosine scores cluster in 0.4-0.7, so this only drops clearly unrelated chunks:
# 0.50 is the highest value that loses no correct evidence.
EVIDENCE_MIN_SCORE = 0.50
RERANK_CANDIDATES = 10
RERANK_MIN_SCORE = 0.05


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
        reranker: Reranker | None = None,
    ) -> None:
        self.session = session
        self.user_email = user_email.strip().lower()
        self.embedding_provider = embedding_provider
        self.reranker = reranker
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

    def rerank(self, query: str, candidates: list[RetrievalResult]) -> list[RetrievalResult]:
        """Reorder candidates by reranker relevance, replacing the cosine score."""
        if self.reranker is None or not candidates:
            return candidates
        scores = self.reranker.score(query, [candidate.content for candidate in candidates])
        rescored = [
            replace(candidate, score=score)
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        return sorted(rescored, key=lambda result: result.score, reverse=True)

    def search_evidence(self, requirement: str) -> list[RetrievalResult]:
        """Return the chunks that count as resume evidence for one job requirement."""
        if self.reranker is None:
            matches = self.search(requirement, EVIDENCE_TOP_K)
            return [match for match in matches if match.score >= EVIDENCE_MIN_SCORE]
        ranked = self.rerank(requirement, self.search(requirement, RERANK_CANDIDATES))
        return [
            match for match in ranked[:EVIDENCE_TOP_K] if match.score >= RERANK_MIN_SCORE
        ]
