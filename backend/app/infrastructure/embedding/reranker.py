"""Cross-encoder reranking through the embedding provider's ``/rerank`` endpoint."""

from __future__ import annotations

import httpx

from .provider import EmbeddingResponseError, EmbeddingServiceError


class Reranker:
    """Score (query, document) pairs with a hosted reranking model."""

    def __init__(self, *, model: str, base_url: str, api_key: str) -> None:
        self.model = model.strip()
        self.url = base_url.strip().rstrip("/") + "/rerank"
        self.api_key = api_key.strip()

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one relevance score in [0, 1] per document, in input order."""
        try:
            response = httpx.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "query": query, "documents": documents},
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EmbeddingServiceError("rerank request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingServiceError("rerank service is unavailable", status_code=502) from exc

        try:
            scores = {
                int(item["index"]): float(item["relevance_score"])
                for item in response.json()["results"]
            }
            return [scores[index] for index in range(len(documents))]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingResponseError("rerank response format is invalid") from exc
