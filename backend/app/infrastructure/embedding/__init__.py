"""Configurable embedding provider construction."""

from ...core.config import Settings
from ..database.vector import BGE_M3_DIMENSION
from .openai_compatible import OpenAICompatibleEmbeddingProvider
from .provider import EmbeddingConfigurationError, EmbeddingProvider
from .reranker import Reranker


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider_name = settings.embedding_provider.strip().lower()
    if settings.embedding_dimension != BGE_M3_DIMENSION:
        raise EmbeddingConfigurationError(
            f"EMBEDDING_DIMENSION must match the database vector dimension ({BGE_M3_DIMENSION})",
            status_code=503,
        )
    if provider_name != "openai_compatible":
        raise EmbeddingConfigurationError(
            f"unsupported embedding provider: {provider_name}",
            status_code=503,
        )
    return OpenAICompatibleEmbeddingProvider(
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    )


def create_reranker(settings: Settings) -> Reranker | None:
    """Return the configured reranker, or None when RERANK_MODEL is unset."""
    if not settings.rerank_model.strip():
        return None
    return Reranker(
        model=settings.rerank_model,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    )


__all__ = ["EmbeddingProvider", "Reranker", "create_embedding_provider", "create_reranker"]
