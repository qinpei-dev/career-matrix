"""End-to-end tests for the versioned persistence API."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (
    Analysis,
    AnalysisTask,
    CandidateProfile,
    Job,
    User,
)
from backend.app.infrastructure.database.session import create_session_factory, get_db_session
from backend.app.main import app


@pytest.fixture
def api_database(tmp_path: Path) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'api.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, session_factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_profile_create_read_patch_and_conflict(api_database) -> None:
    client, _ = api_database

    assert client.get("/api/v1/profiles/me").status_code == 404

    created = client.post(
        "/api/v1/profiles",
        json={
            "name": " Candidate ",
            "target_role": "Backend Engineer",
            "summary": "API builder",
            "skills": ["Python", "FastAPI"],
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]
    assert created.json()["name"] == "Candidate"

    fetched = client.get("/api/v1/profiles/me")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == profile_id

    patched = client.patch(
        "/api/v1/profiles/me",
        json={"target_role": "Platform Engineer", "skills": ["Python", "SQL"]},
    )
    assert patched.status_code == 200
    assert patched.json()["target_role"] == "Platform Engineer"
    assert patched.json()["summary"] == "API builder"
    assert patched.json()["skills"] == ["Python", "SQL"]

    duplicate = client.post(
        "/api/v1/profiles",
        json={"name": "Duplicate", "skills": []},
    )
    assert duplicate.status_code == 409


def test_job_create_list_get_and_user_isolation(api_database) -> None:
    client, _ = api_database
    headers = {"X-User-Email": "owner@example.test"}

    created = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": " Backend Engineer ",
            "company": "Example Co",
            "description": "Build reliable APIs",
            "source_url": "https://example.test/jobs/1",
        },
    )
    assert created.status_code == 201
    job_id = created.json()["id"]
    assert created.json()["title"] == "Backend Engineer"
    assert created.json()["source_type"] == "manual"

    listed = client.get("/api/v1/jobs", headers=headers)
    assert listed.status_code == 200
    assert [job["id"] for job in listed.json()] == [job_id]

    fetched = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["description"] == "Build reliable APIs"

    other_headers = {"X-User-Email": "other@example.test"}
    assert client.get(f"/api/v1/jobs/{job_id}", headers=other_headers).status_code == 404
    assert client.get("/api/v1/jobs", headers=other_headers).json() == []


def test_job_search_filter_sort_and_pagination(api_database) -> None:
    client, _ = api_database
    jobs = [
        {
            "title": "Python Engineer",
            "company": "Beta",
            "description": "Build Python APIs",
            "source_type": "manual",
        },
        {
            "title": "Frontend Engineer",
            "company": "Alpha",
            "description": "Build interfaces",
            "source_type": "extension",
        },
        {
            "title": "Data Engineer",
            "company": "Gamma",
            "description": "Build pipelines",
            "source_type": "manual",
        },
    ]
    created_jobs = []
    for payload in jobs:
        response = client.post("/api/v1/jobs", json=payload)
        assert response.status_code == 201
        created_jobs.append(response.json())

    searched = client.get("/api/v1/jobs", params={"query": "alpha"})
    assert [job["title"] for job in searched.json()] == ["Frontend Engineer"]

    filtered = client.get(
        "/api/v1/jobs",
        params={"source_type": "manual", "sort": "title_asc"},
    )
    assert [job["title"] for job in filtered.json()] == [
        "Data Engineer",
        "Python Engineer",
    ]

    first_page = client.get(
        "/api/v1/jobs",
        params={"sort": "company_asc", "offset": 0, "limit": 2},
    )
    second_page = client.get(
        "/api/v1/jobs",
        params={"sort": "company_asc", "offset": 2, "limit": 2},
    )
    assert [job["company"] for job in first_page.json()] == ["Alpha", "Beta"]
    assert [job["company"] for job in second_page.json()] == ["Gamma"]

    profile = client.post(
        "/api/v1/profiles",
        json={"name": "Search Candidate", "skills": ["Python"]},
    ).json()
    assert client.post(
        "/api/v1/analyses",
        json={
            "job_id": created_jobs[0]["id"],
            "candidate_profile_id": profile["id"],
            "status": "completed",
            "score": 90,
            "result_json": {},
        },
    ).status_code == 201
    analyzed = client.get(
        "/api/v1/jobs",
        params={"analysis_status": "analyzed"},
    )
    pending = client.get(
        "/api/v1/jobs",
        params={"analysis_status": "pending", "sort": "title_asc"},
    )
    assert [job["title"] for job in analyzed.json()] == ["Python Engineer"]
    assert [job["title"] for job in pending.json()] == [
        "Data Engineer",
        "Frontend Engineer",
    ]


def test_job_patch_recomputes_fingerprint_and_enforces_user_isolation(
    api_database,
) -> None:
    client, _ = api_database
    owner = {"X-User-Email": "owner@example.test"}
    other = {"X-User-Email": "other@example.test"}
    first = client.post(
        "/api/v1/jobs",
        headers=owner,
        json={"title": "First", "description": "Original"},
    ).json()
    second = client.post(
        "/api/v1/jobs",
        headers=owner,
        json={"title": "Second", "description": "Different"},
    ).json()

    updated = client.patch(
        f"/api/v1/jobs/{first['id']}",
        headers=owner,
        json={"title": "Updated", "company": " Example ", "description": "New JD"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert updated.json()["company"] == "Example"

    duplicate = client.patch(
        f"/api/v1/jobs/{second['id']}",
        headers=owner,
        json={"title": "Updated", "company": "Example", "description": "New JD"},
    )
    assert duplicate.status_code == 409
    assert client.get(f"/api/v1/jobs/{second['id']}", headers=owner).json()["title"] == "Second"
    assert client.patch(
        f"/api/v1/jobs/{first['id']}",
        headers=other,
        json={"title": "Stolen"},
    ).status_code == 404


def test_job_delete_rejects_active_work_then_cascades_terminal_records(
    api_database,
) -> None:
    client, session_factory = api_database
    profile = client.post(
        "/api/v1/profiles",
        json={"name": "Candidate", "skills": ["Python"]},
    ).json()
    job = client.post(
        "/api/v1/jobs",
        json={"title": "Delete Me", "description": "Temporary"},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={
            "job_id": job["id"],
            "candidate_profile_id": profile["id"],
            "status": "completed",
            "score": 80,
            "result_json": {},
        },
    ).json()
    with session_factory() as session:
        user_id = session.scalar(select(User.id))
        session.add(
            AnalysisTask(
                user_id=user_id,
                job_id=uuid.UUID(job["id"]),
                status="WAITING_FOR_REVIEW",
                current_step="WAITING_FOR_REVIEW",
                progress=90,
                result_id=uuid.UUID(analysis["id"]),
            )
        )
        session.commit()

    blocked = client.delete(f"/api/v1/jobs/{job['id']}")
    assert blocked.status_code == 409
    assert "分析任务" in blocked.json()["detail"]

    with session_factory() as session:
        task = session.scalar(select(AnalysisTask))
        assert task is not None
        task.status = "COMPLETED"
        task.current_step = "COMPLETED"
        task.progress = 100
        session.commit()

    deleted = client.delete(f"/api/v1/jobs/{job['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        assert session.scalar(select(func.count()).select_from(Analysis)) == 0
        assert session.scalar(select(func.count()).select_from(AnalysisTask)) == 0


def test_job_delete_is_user_scoped(api_database) -> None:
    client, _ = api_database
    job = client.post(
        "/api/v1/jobs",
        headers={"X-User-Email": "owner@example.test"},
        json={"title": "Owned", "description": "Private"},
    ).json()
    assert client.delete(
        f"/api/v1/jobs/{job['id']}",
        headers={"X-User-Email": "other@example.test"},
    ).status_code == 404
    assert client.get(
        f"/api/v1/jobs/{job['id']}",
        headers={"X-User-Email": "owner@example.test"},
    ).status_code == 200


def test_analysis_create_list_and_relationship_validation(api_database) -> None:
    client, _ = api_database
    profile = client.post(
        "/api/v1/profiles",
        json={"name": "Candidate", "skills": ["Python"]},
    ).json()
    job = client.post(
        "/api/v1/jobs",
        json={"title": "Engineer", "description": "Build APIs"},
    ).json()
    payload = {
        "job_id": job["id"],
        "candidate_profile_id": profile["id"],
        "status": "completed",
        "score": 91,
        "result_json": {"summary": "strong match"},
        "scoring_version": "v1",
        "model_provider": "deepseek",
        "model_name": "deepseek-chat",
    }

    created = client.post("/api/v1/analyses", json=payload)
    assert created.status_code == 201
    analysis_id = created.json()["id"]
    assert created.json()["score"] == 91

    listed = client.get("/api/v1/analyses")
    assert listed.status_code == 200
    assert [analysis["id"] for analysis in listed.json()] == [analysis_id]

    foreign_attempt = client.post(
        "/api/v1/analyses",
        headers={"X-User-Email": "other@example.test"},
        json=payload,
    )
    assert foreign_attempt.status_code == 404


def test_api_writes_are_persisted_in_new_database_session(api_database) -> None:
    client, session_factory = api_database
    profile = client.post(
        "/api/v1/profiles",
        json={"name": "Persistent Candidate", "skills": ["SQLAlchemy"]},
    ).json()
    job = client.post(
        "/api/v1/jobs",
        json={"title": "Persistent Job", "description": "Stored in SQLite"},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={
            "job_id": job["id"],
            "candidate_profile_id": profile["id"],
            "status": "completed",
            "score": 84,
            "result_json": {"persisted": True},
        },
    ).json()

    with session_factory() as verification_session:
        assert verification_session.scalar(select(func.count()).select_from(User)) == 1
        assert verification_session.scalar(select(func.count()).select_from(CandidateProfile)) == 1
        assert verification_session.scalar(select(func.count()).select_from(Job)) == 1
        assert verification_session.scalar(select(func.count()).select_from(Analysis)) == 1
        stored = verification_session.get(Analysis, uuid.UUID(analysis["id"]))
        assert stored is not None
        assert stored.result_json == {"persisted": True}
        assert stored.job.title == "Persistent Job"
