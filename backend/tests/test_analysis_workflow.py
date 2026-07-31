"""API and persistence tests for the saved-job analysis workflow."""

import json
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.dependencies import get_embedding_provider
from backend.app.application.analysis_service import AnalysisService
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Analysis, Document, DocumentChunk, User
from backend.app.infrastructure.database.session import create_session_factory, get_db_session
from backend.app.infrastructure.llm.parser import ExtractedAnalysis, build_final_analysis
from backend.app.infrastructure.llm.provider import LLMServiceError
from backend.app.main import app


class AnalysisEmbeddingProvider:
    dimension = 1024

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1023 for _ in texts]

    def embed_query(self, query: str) -> list[float]:
        return [1.0] + [0.0] * 1023


@pytest.fixture(autouse=True)
def extracted_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        AnalysisService,
        "extract_job",
        lambda *_args: ExtractedAnalysis.model_validate(
            {
                "job_requirements": {
                    "core_skills": ["Python", "FastAPI", "Redis"],
                }
            }
        ),
    )


@pytest.fixture
def workflow_database(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'workflow.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app, headers={"Authorization": "Bearer test-token-demo"}) as client:
            yield client, session_factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _create_profile_and_job(client: TestClient) -> tuple[dict, dict]:
    profile = client.post(
        "/api/v1/profiles",
        json={
            "name": "Candidate",
            "target_role": "Backend Engineer",
            "summary": "Built production APIs",
            "skills": ["Python", "FastAPI"],
        },
    ).json()
    job = client.post(
        "/api/v1/jobs",
        json={
            "title": "Backend Engineer",
            "description": "Requires Python, FastAPI and Redis",
        },
    ).json()
    return profile, job


def _completed_result():
    return build_final_analysis(
        ExtractedAnalysis.model_validate(
            {
                "job_requirements": {
                    "core_skills": ["Python", "FastAPI", "Redis"],
                    "preferred_skills": [],
                    "project_requirements": [],
                    "education_requirements": [],
                    "experience_requirements": [],
                },
                "matched_skills": ["Python", "FastAPI"],
                "missing_skills": ["Redis"],
                "reasoning": ["Python and FastAPI have direct profile evidence"],
                "greeting": "分析已完成。",
                "confidence": 0.9,
            }
        )
    )


def test_analyze_saved_job_calls_existing_service_and_returns_completed(
    workflow_database,
    monkeypatch,
) -> None:
    client, _ = workflow_database
    profile, job = _create_profile_and_job(client)
    captured: dict[str, str] = {}

    def fake_analyze(self, job_title, job_description, candidate_profile):
        captured.update(
            title=job_title,
            description=job_description,
            profile=candidate_profile,
        )
        return _completed_result()

    monkeypatch.setattr(AnalysisService, "analyze_job", fake_analyze)
    response = client.post(f"/api/v1/jobs/{job['id']}/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["score"] == 67
    assert payload["job_id"] == job["id"]
    assert payload["candidate_profile_id"] == profile["id"]
    assert payload["result_json"]["missing_skills"] == ["Redis"]
    assert payload["evidence_json"] == []
    assert captured["title"] == "Backend Engineer"
    assert captured["description"] == "Requires Python, FastAPI and Redis"
    assert json.loads(captured["profile"])["skills"] == ["Python", "FastAPI"]


def test_completed_analysis_is_persisted_in_a_new_session(
    workflow_database,
    monkeypatch,
) -> None:
    client, session_factory = workflow_database
    profile, job = _create_profile_and_job(client)
    monkeypatch.setattr(AnalysisService, "analyze_job", lambda *args: _completed_result())

    analysis_id = client.post(f"/api/v1/jobs/{job['id']}/analyze").json()["id"]

    with session_factory() as session:
        stored = session.get(Analysis, uuid.UUID(analysis_id))
        assert stored is not None
        assert stored.status == "completed"
        assert stored.score == 67
        assert stored.candidate_profile_id == uuid.UUID(profile["id"])
        assert stored.result_json["reasoning"] == [
            "Python and FastAPI have direct profile evidence"
        ]
        assert stored.scoring_version == "deterministic-v1"
        assert stored.evidence_json == []


def test_failed_analysis_is_persisted_and_error_is_returned(
    workflow_database,
    monkeypatch,
) -> None:
    client, session_factory = workflow_database
    _, job = _create_profile_and_job(client)

    def fail_analysis(*args):
        raise LLMServiceError("AI service unavailable", status_code=502)

    monkeypatch.setattr(AnalysisService, "analyze_job", fail_analysis)
    response = client.post(f"/api/v1/jobs/{job['id']}/analyze")

    assert response.status_code == 502
    assert response.json() == {"detail": "AI service unavailable"}
    with session_factory() as session:
        stored = session.scalar(select(Analysis))
        assert stored is not None
        assert stored.status == "failed"
        assert stored.score is None
        assert stored.result_json == {"error": "AI service unavailable"}
        assert stored.evidence_json == []


def test_analyze_requires_owned_job_and_profile(workflow_database, monkeypatch) -> None:
    client, _ = workflow_database
    _, job = _create_profile_and_job(client)
    called = False

    def fake_analyze(*args):
        nonlocal called
        called = True
        return _completed_result()

    monkeypatch.setattr(AnalysisService, "analyze_job", fake_analyze)
    response = client.post(
        f"/api/v1/jobs/{job['id']}/analyze",
        headers={"Authorization": "Bearer test-token-other"},
    )

    assert response.status_code == 404
    assert called is False


def test_analysis_retrieves_and_persists_owned_resume_evidence(
    workflow_database,
    monkeypatch,
) -> None:
    client, session_factory = workflow_database
    _, job = _create_profile_and_job(client)
    captured_profile: dict[str, object] = {}

    def analyze_with_evidence(_self, _title, _description, candidate_profile):
        captured_profile.update(json.loads(candidate_profile))
        return _completed_result()

    monkeypatch.setattr(AnalysisService, "analyze_job", analyze_with_evidence)
    app.dependency_overrides[get_embedding_provider] = lambda: AnalysisEmbeddingProvider()

    with session_factory() as session:
        user = session.scalar(select(User).where(User.email == "demo@example.com"))
        assert user is not None
        document = Document(
            user_id=user.id,
            filename="resume.docx",
            file_type="docx",
            storage_path="test/resume.docx",
            status="ready",
        )
        document.chunks.append(
            DocumentChunk(
                content="Built production APIs with Python and FastAPI",
                section="Projects",
                chunk_index=0,
                embedding=[1.0] + [0.0] * 1023,
            )
        )
        session.add(document)
        session.commit()
        document_id = document.id
        chunk_id = document.chunks[0].id

    response = client.post(f"/api/v1/jobs/{job['id']}/analyze")

    assert response.status_code == 200
    assert response.json()["score"] == 67
    evidence = response.json()["evidence_json"]
    assert evidence
    assert evidence[0] == {
        "chunk_id": str(chunk_id),
        "document_id": str(document_id),
        "content": "Built production APIs with Python and FastAPI",
        "section": "Projects",
        "requirement": "Python",
    }
    assert captured_profile["retrieved_resume_evidence"] == evidence
    with session_factory() as session:
        stored = session.scalar(select(Analysis))
        assert stored is not None
        assert stored.evidence_json == evidence


def test_analysis_does_not_retrieve_another_users_evidence(
    workflow_database,
    monkeypatch,
) -> None:
    client, session_factory = workflow_database
    _, job = _create_profile_and_job(client)
    monkeypatch.setattr(AnalysisService, "analyze_job", lambda *args: _completed_result())
    app.dependency_overrides[get_embedding_provider] = lambda: AnalysisEmbeddingProvider()

    with session_factory() as session:
        other = User(email="other@example.test")
        document = Document(
            user=other,
            filename="private.docx",
            file_type="docx",
            storage_path="test/private.docx",
            status="ready",
        )
        document.chunks.append(
            DocumentChunk(
                content="Private FastAPI evidence",
                section="Experience",
                chunk_index=0,
                embedding=[1.0] + [0.0] * 1023,
            )
        )
        session.add(document)
        session.commit()

    response = client.post(f"/api/v1/jobs/{job['id']}/analyze")

    assert response.status_code == 200
    assert response.json()["evidence_json"] == []
