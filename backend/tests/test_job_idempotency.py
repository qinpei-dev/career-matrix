"""Tests for user-scoped idempotent Job creation."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.crud_service import CrudService
from backend.app.application.job_fingerprint import (
    generate_job_fingerprint,
    normalize_job_source_url,
)
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Job
from backend.app.infrastructure.database.session import (
    create_session_factory,
    get_db_session,
)
from backend.app.main import app
from backend.app.schemas import JobCreate


@pytest.fixture
def job_api(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'job-idempotency.db').as_posix()}",
        connect_args={"timeout": 10},
    )
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


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Backend Engineer",
        "company": "Example Co",
        "description": "Build reliable APIs",
        "source_url": "https://jobs.example.test/detail/42",
    }
    payload.update(overrides)
    return payload


def test_same_job_saved_twice_returns_created_then_duplicate(job_api) -> None:
    client, session_factory = job_api

    created = client.post("/api/v1/jobs", json=_payload())
    duplicate = client.post("/api/v1/jobs", json=_payload())

    assert created.status_code == 201
    assert created.json()["status"] == "created"
    assert created.json()["job_id"] == created.json()["id"]
    assert duplicate.status_code == 200
    assert duplicate.json() == {
        **created.json(),
        "status": "duplicate",
        "message": "该岗位已保存",
    }
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_different_users_can_save_the_same_job(job_api) -> None:
    client, session_factory = job_api

    first = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer test-token-first"},
        json=_payload(),
    )
    second = client.post(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer test-token-second"},
        json=_payload(),
    )

    assert first.json()["status"] == second.json()["status"] == "created"
    assert first.json()["job_id"] != second.json()["job_id"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 2


def test_same_stable_source_url_is_duplicate(job_api) -> None:
    client, _ = job_api
    first = client.post(
        "/api/v1/jobs",
        json=_payload(
            source_url="HTTPS://JOBS.EXAMPLE.TEST:443/detail/42/?securityId=one&utm_source=a"
        ),
    )
    second = client.post(
        "/api/v1/jobs",
        json=_payload(
            title="A changed title",
            description="Changed copy",
            source_url="https://jobs.example.test/detail/42?utm_medium=b&securityId=two",
        ),
    )

    assert first.json()["status"] == "created"
    assert second.json()["status"] == "duplicate"
    assert second.json()["job_id"] == first.json()["job_id"]


def test_normalized_content_is_duplicate_without_source_url(job_api) -> None:
    client, _ = job_api
    first = client.post(
        "/api/v1/jobs",
        json=_payload(source_url=None, title=" Backend   Engineer "),
    )
    second = client.post(
        "/api/v1/jobs",
        json=_payload(
            source_url=None,
            title="backend engineer",
            company=" example co ",
            description="  build reliable\n APIs  ",
        ),
    )

    assert first.json()["status"] == "created"
    assert second.json()["status"] == "duplicate"


def test_concurrent_creation_persists_only_one_job(job_api) -> None:
    _, session_factory = job_api
    payload = JobCreate(**_payload())

    def create() -> tuple[str, str]:
        with session_factory() as session:
            result = CrudService(session, "concurrent@example.test").create_job(payload)
            return result.status, str(result.job.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: create(), range(2)))

    assert sorted(status for status, _ in results) == ["created", "duplicate"]
    assert len({job_id for _, job_id in results}) == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 1


def test_fingerprint_helpers_return_stable_sha256_values() -> None:
    assert normalize_job_source_url(
        "https://Example.test/jobs/1/?b=2&securityId=abc&a=1#apply"
    ) == "https://example.test/jobs/1?a=1&b=2"
    fingerprint = generate_job_fingerprint(
        source_url=None,
        title=" Engineer ",
        company=" Example ",
        description="Build\nAPIs",
    )
    assert len(fingerprint) == 64
    assert fingerprint == generate_job_fingerprint(
        source_url=None,
        title="engineer",
        company="example",
        description=" build APIs ",
    )
