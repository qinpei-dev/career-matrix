"""User-isolated workspace dashboard, search, notifications, and settings."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (
    AnalysisTask,
    Document,
    User,
    UserSettings,
)
from backend.app.infrastructure.database.session import create_session_factory, get_db_session
from backend.app.main import app


@pytest.fixture
def workspace_database(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'workspace.db').as_posix()}")
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


def _create_analysis_data(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    profile = client.post(
        "/api/v1/profiles",
        headers=headers,
        json={"name": "搜索候选人", "skills": ["Python"]},
    ).json()
    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Platform Engineer",
            "company": "Acme Search",
            "description": "Build reliable search APIs",
        },
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        headers=headers,
        json={
            "job_id": job["id"],
            "candidate_profile_id": profile["id"],
            "status": "completed",
            "score": 88,
            "result_json": {"summary": "Strong distributed systems match"},
        },
    ).json()
    return job["id"], analysis["id"]


def test_settings_are_persisted_and_isolated(workspace_database) -> None:
    client, session_factory = workspace_database
    owner = {"Authorization": "Bearer test-token-owner"}
    other = {"Authorization": "Bearer test-token-other"}

    initial = client.get("/api/v1/workspace/settings", headers=owner)
    assert initial.status_code == 200
    assert initial.json()["page_size"] == 20
    assert initial.json()["email"] == "owner@example.test"

    updated = client.patch(
        "/api/v1/workspace/settings",
        headers=owner,
        json={
            "display_name": "Local Candidate",
            "target_role": "Platform Engineer",
            "page_size": 50,
            "show_technical_details": True,
            "default_analysis_options": {
                "auto_run": True,
                "require_review": True,
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Local Candidate"
    assert updated.json()["page_size"] == 50

    assert client.get("/api/v1/workspace/settings", headers=other).json()["page_size"] == 20
    with session_factory() as session:
        owner_user = session.scalar(select(User).where(User.email == "owner@example.test"))
        assert owner_user is not None
        stored = session.get(UserSettings, owner_user.id)
        assert stored is not None
        assert stored.display_name == "Local Candidate"


def test_dashboard_search_and_notifications_use_real_owned_data(
    workspace_database,
) -> None:
    client, session_factory = workspace_database
    headers = {"Authorization": "Bearer test-token-owner"}
    job_id, analysis_id = _create_analysis_data(client, headers)

    with session_factory() as session:
        user = session.scalar(select(User).where(User.email == "owner@example.test"))
        assert user is not None
        document = Document(
            user_id=user.id,
            filename="platform-resume.pdf",
            file_type="pdf",
            storage_path="/redacted/platform-resume.pdf",
            file_hash="a" * 64,
            status="ready",
        )
        task = AnalysisTask(
            user_id=user.id,
            job_id=uuid.UUID(job_id),
            status="FAILED",
            current_step="ANALYZING",
            progress=45,
            error_code="provider_unavailable",
            error_message="AI 服务暂时不可用",
        )
        session.add_all((document, task))
        session.commit()

    dashboard = client.get("/api/v1/workspace/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["stats"] == {
        "jobs": 1,
        "analyses": 1,
        "analyzed_jobs": 1,
        "pending_jobs": 0,
        "average_score": 88,
        "high_matches": 1,
        "documents": 1,
        "ready_documents": 1,
        "active_tasks": 0,
        "failed_tasks": 1,
    }
    assert dashboard.json()["recent_analyses"][0]["id"] == analysis_id
    assert dashboard.json()["recent_jobs"][0]["analysis_status"] == "completed"
    assert dashboard.json()["recent_jobs"][0]["analysis_score"] == 88
    assert dashboard.json()["recent_tasks"][0]["status"] == "FAILED"

    job_search = client.get("/api/v1/workspace/search?q=Acme", headers=headers).json()
    assert [item["type"] for item in job_search["results"]] == ["job"]
    resume_search = client.get(
        "/api/v1/workspace/search?q=platform-resume", headers=headers
    ).json()
    assert resume_search["results"][0]["type"] == "resume"
    analysis_search = client.get(
        "/api/v1/workspace/search?q=distributed", headers=headers
    ).json()
    assert analysis_search["results"][0]["type"] == "analysis"
    assert analysis_search["results"][0]["href"] == f"/jobs/{job_id}"

    notifications = client.get(
        "/api/v1/workspace/notifications", headers=headers
    ).json()
    assert {item["title"] for item in notifications} == {
        "分析失败",
        "简历处理完成",
    }
    assert client.get(
        "/api/v1/workspace/search?q=Acme",
        headers={"Authorization": "Bearer test-token-other"},
    ).json()["total"] == 0


def test_provider_status_never_returns_credentials(
    workspace_database, monkeypatch,
) -> None:
    client, _ = workspace_database
    monkeypatch.setenv("LLM_API_KEY", "do-not-return-this-value")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example.test")

    response = client.get("/api/v1/workspace/providers")

    assert response.status_code == 200
    assert response.json()["llm"]["credential"] == "已配置（已脱敏）"
    assert "do-not-return-this-value" not in response.text


def test_dashboard_and_search_are_not_limited_to_job_list_page_size(
    workspace_database,
) -> None:
    client, _ = workspace_database
    headers = {"Authorization": "Bearer test-token-many-jobs"}
    for index in range(21):
        created = client.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": f"Role {index}",
                "company": "Pagination Corp",
                "description": f"Unique role description {index}",
            },
        )
        assert created.status_code == 201

    dashboard = client.get("/api/v1/workspace/dashboard", headers=headers).json()
    search = client.get(
        "/api/v1/workspace/search?q=Pagination",
        headers=headers,
    ).json()

    assert dashboard["stats"]["jobs"] == 21
    assert search["total"] == 21
