"""API-level tests for the lightweight Demo Auth boundary."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app import main
from backend.app.application.security_test_service import TEST_SECRET_CANARY
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.session import (
    create_session_factory,
    get_db_session,
)
from backend.app.infrastructure.llm.parser import ExtractedAnalysis, build_final_analysis

app = main.app

LEGACY_ANALYSIS_PAYLOAD = {
    "job_title": "Backend Engineer",
    "job_description": "Build reliable APIs",
    "candidate_profile": "Python and FastAPI experience",
}


@pytest.fixture
def auth_api(tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'auth.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic test-token-demo"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer unknown-token"},
    ],
)
def test_missing_malformed_and_unknown_credentials_return_401(
    auth_api: TestClient,
    headers: dict[str, str],
) -> None:
    response = auth_api.get("/api/v1/jobs", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "token" not in response.text.casefold()


def test_valid_token_maps_to_database_user_and_ignores_spoofed_email(
    auth_api: TestClient,
) -> None:
    response = auth_api.get(
        "/api/v1/workspace/settings",
        headers={
            "Authorization": "Bearer test-token-demo",
            "X-User-Email": "owner@example.test",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "demo@example.com"


def test_untrusted_content_security_test_requires_demo_auth(
    auth_api: TestClient,
) -> None:
    response = auth_api.post("/api/v1/security-tests/untrusted-content")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_untrusted_content_security_test_runs_for_valid_token(
    auth_api: TestClient,
) -> None:
    response = auth_api.post(
        "/api/v1/security-tests/untrusted-content",
        headers={"Authorization": "Bearer test-token-demo"},
    )

    assert response.status_code == 200
    assert response.json()["overall_status"] == "PASS"
    assert TEST_SECRET_CANARY not in response.text


def test_different_tokens_preserve_user_isolation(auth_api: TestClient) -> None:
    owner = {"Authorization": "Bearer test-token-owner"}
    other = {"Authorization": "Bearer test-token-other"}
    created = auth_api.post(
        "/api/v1/jobs",
        headers=owner,
        json={"title": "Private role", "description": "Owner-only job"},
    )

    assert created.status_code == 201
    job_id = created.json()["id"]
    assert auth_api.get(f"/api/v1/jobs/{job_id}", headers=other).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer unknown-token"},
    ],
)
def test_legacy_analysis_requires_valid_demo_auth(
    auth_api: TestClient,
    headers: dict[str, str],
) -> None:
    response = auth_api.post(
        "/api/analyze-job",
        headers=headers,
        json=LEGACY_ANALYSIS_PAYLOAD,
    )

    assert response.status_code == 401


def test_legacy_analysis_preserves_behavior_for_valid_token(
    auth_api: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    expected = build_final_analysis(
        ExtractedAnalysis(greeting="Authenticated demo analysis")
    )

    def fake_analyze_job(
        job_title: str,
        job_description: str,
        candidate_profile: str,
    ):
        captured.update(
            job_title=job_title,
            job_description=job_description,
            candidate_profile=candidate_profile,
        )
        return expected

    monkeypatch.setattr(main, "analyze_job", fake_analyze_job)
    response = auth_api.post(
        "/api/analyze-job",
        headers={"Authorization": "Bearer test-token-demo"},
        json=LEGACY_ANALYSIS_PAYLOAD,
    )

    assert response.status_code == 200
    assert response.json()["greeting"] == "Authenticated demo analysis"
    assert captured == LEGACY_ANALYSIS_PAYLOAD


def test_pdf_export_requires_demo_auth(auth_api: TestClient) -> None:
    path = f"/api/v1/tailored-resumes/{uuid.uuid4()}/export.pdf"

    assert auth_api.get(path).status_code == 401
    authenticated = auth_api.get(
        path,
        headers={"Authorization": "Bearer test-token-demo"},
    )
    assert authenticated.status_code == 501
    assert authenticated.json()["detail"] == (
        "PDF export is NOT VERIFIED; use the real DOCX export."
    )
