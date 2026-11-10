"""Offline retrieval evaluation against the labelled resume/requirement set.

Run from the repository root (needs the embedding provider configured)::

    python -m backend.eval.run_retrieval_eval
    python -m backend.eval.run_retrieval_eval --output eval-baseline.json

Each resume in ``data/resumes`` is chunked with the production chunker, embedded
with the configured provider and stored for its own user in an in-memory SQLite
database. Every query in ``data/queries.jsonl`` then goes through
``RetrievalService`` like the analysis workflow does: vector search, then
reranking when ``RERANK_MODEL`` is configured (``--no-rerank`` skips it).

Label format (one JSON object per line)::

    {"id": "be-01", "resume": "backend_engineer.txt", "query": "熟悉 FastAPI",
     "evidence": ["verbatim snippet of a correct chunk", "..."]}

A chunk is relevant when it contains any ``evidence`` snippet. An empty
``evidence`` list marks a negative query: the resume has no supporting evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.application.document_processing import chunk_resume_text
from backend.app.application.retrieval_service import (
    EVIDENCE_MIN_SCORE,
    EVIDENCE_TOP_K,
    RERANK_CANDIDATES,
    RERANK_MIN_SCORE,
    RetrievalService,
)
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Document, DocumentChunk, User
from backend.app.infrastructure.embedding.provider import EmbeddingProvider
from backend.app.infrastructure.embedding.reranker import Reranker

DATA_DIR = Path(__file__).resolve().parent / "data"
SEARCH_DEPTH = RERANK_CANDIDATES
RECALL_KS = (1, 2, 5)
SWEEP_KS = (1, 2, 3, 5)
COSINE_THRESHOLDS = tuple(round(0.30 + 0.05 * step, 2) for step in range(9))
RERANK_THRESHOLDS = (0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50)
EMBED_BATCH_SIZE = 16


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _user_email(resume: str) -> str:
    return f"eval-{Path(resume).stem}@example.com"


def load_queries(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def ingest_resumes(session: Session, provider: EmbeddingProvider, resumes_dir: Path) -> int:
    """Chunk and embed every resume the same way DocumentService does."""
    total = 0
    for path in sorted(resumes_dir.glob("*.txt")):
        user = User(email=_user_email(path.name))
        session.add(user)
        session.flush()
        document = Document(
            user_id=user.id,
            filename=path.name,
            file_type="txt",
            storage_path=str(path),
            status="ready",
        )
        session.add(document)
        session.flush()
        chunks = chunk_resume_text(path.read_text(encoding="utf-8"))
        contents = [chunk.content for chunk in chunks]
        embeddings: list[list[float]] = []
        for start in range(0, len(contents), EMBED_BATCH_SIZE):
            embeddings.extend(
                provider.embed_texts(contents[start : start + EMBED_BATCH_SIZE])
            )
        session.add_all(
            DocumentChunk(
                document_id=document.id,
                content=chunk.content,
                section=chunk.section,
                chunk_index=index,
                embedding=embeddings[index],
            )
            for index, chunk in enumerate(chunks)
        )
        total += len(chunks)
    session.commit()
    return total


def check_labels(queries: list[dict], resumes_dir: Path) -> None:
    """Fail fast when an evidence snippet no longer matches any chunk."""
    chunk_texts: dict[str, list[str]] = {}
    problems: list[str] = []
    for query in queries:
        resume = query["resume"]
        if resume not in chunk_texts:
            text = (resumes_dir / resume).read_text(encoding="utf-8")
            chunk_texts[resume] = [
                _normalize(chunk.content) for chunk in chunk_resume_text(text)
            ]
        for snippet in query["evidence"]:
            if not any(_normalize(snippet) in chunk for chunk in chunk_texts[resume]):
                problems.append(f"{query['id']}: snippet not found in {resume}: {snippet}")
    if problems:
        raise SystemExit("Invalid labels:\n" + "\n".join(problems))


def run_queries(
    session: Session,
    provider: EmbeddingProvider,
    queries: list[dict],
    reranker: Reranker | None = None,
) -> list[dict]:
    """Return per-query ranked results as (score, is_relevant) pairs."""
    records: list[dict] = []
    for query in queries:
        service = RetrievalService(
            session, _user_email(query["resume"]), provider, reranker=reranker
        )
        snippets = [_normalize(snippet) for snippet in query["evidence"]]
        matches = service.rerank(
            query["query"], service.search(query["query"], SEARCH_DEPTH)
        )
        records.append(
            {
                "id": query["id"],
                "query": query["query"],
                "negative": not snippets,
                "results": [
                    {
                        "score": round(match.score, 4),
                        "relevant": any(
                            snippet in _normalize(match.content) for snippet in snippets
                        ),
                        "section": match.section,
                        "content": match.content,
                    }
                    for match in matches
                ],
            }
        )
    return records


def compute_metrics(records: list[dict], thresholds: tuple[float, ...]) -> dict:
    positives = [record for record in records if not record["negative"]]
    negatives = [record for record in records if record["negative"]]

    def first_relevant_rank(record: dict) -> int | None:
        for rank, result in enumerate(record["results"], start=1):
            if result["relevant"]:
                return rank
        return None

    ranks = [first_relevant_rank(record) for record in positives]
    recall = {
        f"recall@{k}": sum(rank is not None and rank <= k for rank in ranks) / len(positives)
        for k in RECALL_KS
    }
    mrr = sum(1 / rank for rank in ranks if rank is not None) / len(positives)

    sweep: list[dict] = []
    for k in SWEEP_KS:
        for threshold in thresholds:
            kept = [
                [r for r in record["results"][:k] if r["score"] >= threshold]
                for record in positives
            ]
            kept_total = sum(len(items) for items in kept)
            kept_relevant = sum(r["relevant"] for items in kept for r in items)
            false_hits = sum(
                any(r["score"] >= threshold for r in record["results"][:k])
                for record in negatives
            )
            sweep.append(
                {
                    "top_k": k,
                    "min_score": threshold,
                    # share of positive queries that keep at least one correct chunk
                    "evidence_recall": sum(
                        any(r["relevant"] for r in items) for items in kept
                    )
                    / len(positives),
                    # share of kept chunks (positive queries) that are correct
                    "evidence_precision": kept_relevant / kept_total if kept_total else 0.0,
                    # share of negative queries that still produce "evidence"
                    "false_recall": false_hits / len(negatives) if negatives else 0.0,
                }
            )
    return {
        "positive_queries": len(positives),
        "negative_queries": len(negatives),
        **recall,
        "mrr": mrr,
        "sweep": sweep,
    }


def print_report(
    metrics: dict, records: list[dict], chunk_count: int, min_score: float
) -> None:
    print(
        f"Chunks: {chunk_count}  Positive queries: {metrics['positive_queries']}  "
        f"Negative queries: {metrics['negative_queries']}"
    )
    print()
    print("| Metric | Value |")
    print("| --- | --- |")
    for k in RECALL_KS:
        print(f"| Recall@{k} | {metrics[f'recall@{k}']:.3f} |")
    print(f"| MRR@{SEARCH_DEPTH} | {metrics['mrr']:.3f} |")
    print()
    print("Threshold sweep (* = current top_k / min_score used by the workflow):")
    print()
    print("| top_k | min_score | evidence recall | evidence precision | false recall |")
    print("| --- | --- | --- | --- | --- |")
    for row in metrics["sweep"]:
        current = (
            row["top_k"] == EVIDENCE_TOP_K
            and abs(row["min_score"] - min_score) < 1e-9
        )
        print(
            f"| {row['top_k']}{'*' if current else ''} | {row['min_score']:.2f} | "
            f"{row['evidence_recall']:.3f} | {row['evidence_precision']:.3f} | "
            f"{row['false_recall']:.3f} |"
        )
    print()
    print(f"Positive queries missed at top {EVIDENCE_TOP_K}:")
    for record in records:
        if record["negative"]:
            continue
        if not any(r["relevant"] for r in record["results"][:EVIDENCE_TOP_K]):
            top = record["results"][0] if record["results"] else None
            got = f"{top['score']:.3f} {top['content'][:40]}" if top else "no result"
            print(f"- {record['id']} {record['query']} -> {got}")
    print()
    print("Top score of each negative query:")
    for record in records:
        if record["negative"] and record["results"]:
            top = record["results"][0]
            print(f"- {record['id']} {record['query']} -> {top['score']:.3f} {top['content'][:40]}")


def evaluate(
    provider: EmbeddingProvider,
    data_dir: Path = DATA_DIR,
    reranker: Reranker | None = None,
) -> tuple[dict, list[dict], int]:
    queries = load_queries(data_dir / "queries.jsonl")
    resumes_dir = data_dir / "resumes"
    check_labels(queries, resumes_dir)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            chunk_count = ingest_resumes(session, provider, resumes_dir)
            records = run_queries(session, provider, queries, reranker)
    finally:
        engine.dispose()
    thresholds = RERANK_THRESHOLDS if reranker else COSINE_THRESHOLDS
    return compute_metrics(records, thresholds), records, chunk_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, help="write metrics and per-query results as JSON")
    parser.add_argument(
        "--no-rerank", action="store_true", help="ignore RERANK_MODEL and score by cosine only"
    )
    args = parser.parse_args()

    from backend.app.core.config import get_settings
    from backend.app.infrastructure.embedding import create_embedding_provider, create_reranker

    settings = get_settings()
    provider = create_embedding_provider(settings)
    reranker = None if args.no_rerank else create_reranker(settings)
    metrics, records, chunk_count = evaluate(provider, args.data_dir, reranker)
    print(f"Embedding model: {settings.embedding_model}")
    print(f"Rerank model: {reranker.model if reranker else 'none (cosine only)'}")
    print_report(
        metrics, records, chunk_count, RERANK_MIN_SCORE if reranker else EVIDENCE_MIN_SCORE
    )
    if args.output:
        args.output.write_text(
            json.dumps(
                {
                    "model": settings.embedding_model,
                    "rerank_model": reranker.model if reranker else None,
                    "metrics": metrics,
                    "records": records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
