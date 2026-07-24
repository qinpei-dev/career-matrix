"""Persistent analysis-task state machine, recovery, and API tests."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, Lock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.dependencies import get_embedding_provider
from backend.app.application.analysis_service import AnalysisService
from backend.app.application.analysis_task_service import (
    AnalysisTaskService,
    recover_interrupted_analysis_tasks,
    transition_analysis_task,
)
from backend.app.application.crud_service import ResourceConflictError
from backend.app.application.retrieval_service import RetrievalService
from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import (
    Analysis,
    AnalysisTask,
    AnalysisTaskStatus,
    CandidateProfile,
    Job,
    User,
)
from backend.app.infrastructure.database.repositories import AnalysisTaskRepository
from backend.app.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    get_db_session,
)
from backend.app.infrastructure.llm.parser import (
    ExtractedAnalysis,
    build_final_analysis,
)
from backend.app.main import app


class EmptyEmbeddingProvider:
    dimension = 1024

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, query: str) -> list[float]:
        return [0.0] * self.dimension


def extracted_result() -> ExtractedAnalysis:
    return ExtractedAnalysis.model_validate({
        "job_requirements": {"core_skills": ["Python", "Redis"]},
        "matched_skills": ["Python"],
        "missing_skills": ["Redis"],
        "reasoning": ["Python is supported by the candidate profile"],
        "confidence": 0.9,
    })


@pytest.fixture(autouse=True)
def deterministic_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AnalysisService, "extract_job", lambda *_args: extracted_result())
    monkeypatch.setattr(
        AnalysisService,
        "analyze_job",
        lambda *_args: build_final_analysis(extracted_result()),
    )


@pytest.fixture
def task_database(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_database_engine(
        f"sqlite+pysqlite:///{(tmp_path / 'tasks.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_embedding_provider] = lambda: EmptyEmbeddingProvider()
    try:
        with TestClient(app) as client:
            yield client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_profile_and_job(
    client: TestClient, headers: dict[str, str] | None = None
) -> dict:
    client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
            "name": "Candidate",
            "target_role": "Backend Engineer",
            "summary": "Production API experience",
            "skills": ["Python"],
        },
    )
    response = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "title": "Backend Engineer",
            "description": "Requires Python and Redis",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_task(client: TestClient, job: dict, headers=None) -> dict:
    response = client.post(
        "/api/v1/analysis-tasks",
        headers=headers,
        json={"job_id": job["id"]},
    )
    assert response.status_code == 201
    return response.json()


def test_pending_creation_and_duplicate_click_returns_same_active_task(
    task_database,
) -> None:
    client, factory = task_database
    job = create_profile_and_job(client)
    first = create_task(client, job)
    second = create_task(client, job)

    assert first == second
    assert first["status"] == "PENDING"
    assert first["current_step"] == "PENDING"
    assert first["progress"] == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisTask)) == 1


def test_complete_flow_waits_for_review_then_confirms(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    transitions: list[AnalysisTaskStatus] = []
    original = AnalysisTaskService._transition_claimed

    def recording_transition(self, stored, target, claim_token, **kwargs):
        transitions.append(target)
        return original(self, stored, target, claim_token, **kwargs)

    monkeypatch.setattr(
        AnalysisTaskService, "_transition_claimed", recording_transition
    )

    waiting = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run")
    assert waiting.status_code == 200
    assert waiting.json()["status"] == "WAITING_FOR_REVIEW"
    assert waiting.json()["progress"] == 90
    assert waiting.json()["result_id"]
    assert transitions == [
        AnalysisTaskStatus.FETCHING_JOB,
        AnalysisTaskStatus.ANALYZING,
        AnalysisTaskStatus.WAITING_FOR_REVIEW,
    ]

    completed = client.post(
        f"/api/v1/analysis-tasks/{task['task_id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["progress"] == 100
    assert completed.json()["completed_at"]
    assert client.post(
        f"/api/v1/analysis-tasks/{task['task_id']}/run"
    ).status_code == 409
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Analysis)) == 1


def test_illegal_state_transitions_are_rejected() -> None:
    task = AnalysisTask(
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        status=AnalysisTaskStatus.PENDING.value,
    )
    with pytest.raises(
        ResourceConflictError,
        match="PENDING -> COMPLETED",
    ):
        transition_analysis_task(task, AnalysisTaskStatus.COMPLETED)
    task.status = AnalysisTaskStatus.COMPLETED.value
    with pytest.raises(
        ResourceConflictError,
        match="COMPLETED -> ANALYZING",
    ):
        transition_analysis_task(task, AnalysisTaskStatus.ANALYZING)
    task.status = AnalysisTaskStatus.FAILED.value
    with pytest.raises(
        ResourceConflictError,
        match="FAILED -> COMPLETED",
    ):
        transition_analysis_task(task, AnalysisTaskStatus.COMPLETED)


def test_analyzing_failure_is_persisted_and_retry_resumes(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    calls = 0

    def fail_once(*_args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("secret token must not be exposed")
        return extracted_result()

    monkeypatch.setattr(AnalysisService, "extract_job", fail_once)
    failed = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run").json()
    assert failed["status"] == "FAILED"
    assert failed["current_step"] == "ANALYZING"
    assert failed["retry_count"] == 0
    assert failed["error_code"] == "RuntimeError"
    assert failed["error_message"] == "analysis task failed"

    with factory() as session:
        stored = session.get(AnalysisTask, uuid.UUID(task["task_id"]))
        assert stored is not None
        assert stored.status == "FAILED"
        assert stored.error_message == "analysis task failed"

    recovered = client.post(
        f"/api/v1/analysis-tasks/{task['task_id']}/retry"
    ).json()
    assert recovered["status"] == "WAITING_FOR_REVIEW"
    assert recovered["retry_count"] == 1
    assert calls == 2


def test_retry_limit_is_enforced(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    task_id = uuid.UUID(task["task_id"])
    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        assert stored is not None
        stored.status = "FAILED"
        stored.current_step = "ANALYZING"
        stored.retry_count = stored.max_retries
        session.commit()

    response = client.post(f"/api/v1/analysis-tasks/{task_id}/retry")
    assert response.status_code == 409
    assert response.json()["detail"] == "analysis task retry limit exceeded"


def test_duplicate_run_does_not_duplicate_result(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    path = f"/api/v1/analysis-tasks/{task['task_id']}/run"
    first = client.post(path)
    second = client.post(path)
    assert first.json()["result_id"] == second.json()["result_id"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Analysis)) == 1


def test_saving_failure_retries_without_reanalyzing_or_duplicate_result(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    analysis_calls = 0
    save_calls = 0
    original_analyze = AnalysisService.analyze_job
    original_save = AnalysisTaskService._save_result

    def count_analysis(self, *args):
        nonlocal analysis_calls
        analysis_calls += 1
        return original_analyze(self, *args)

    def fail_save_once(self, stored, claim_token):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 1:
            raise RuntimeError("temporary database failure")
        return original_save(self, stored, claim_token)

    monkeypatch.setattr(AnalysisService, "analyze_job", count_analysis)
    monkeypatch.setattr(AnalysisTaskService, "_save_result", fail_save_once)
    failed = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run").json()
    assert failed["status"] == "FAILED"
    assert failed["current_step"] == "SAVING_RESULT"
    assert analysis_calls == 1

    waiting = client.post(
        f"/api/v1/analysis-tasks/{task['task_id']}/retry"
    ).json()
    assert waiting["status"] == "WAITING_FOR_REVIEW"
    assert analysis_calls == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Analysis)) == 1


def test_atomic_claim_prevents_a_second_executor(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    task_id = uuid.UUID(task["task_id"])
    with factory() as first, factory() as second:
        first_service = AnalysisTaskService(
            first,
            "demo@example.com",
            AnalysisService(object()),
            RetrievalService(first, "demo@example.com", EmptyEmbeddingProvider()),
        )
        second_service = AnalysisTaskService(
            second,
            "demo@example.com",
            AnalysisService(object()),
            RetrievalService(second, "demo@example.com", EmptyEmbeddingProvider()),
        )
        owned = first_service.get(task_id)
        now = datetime.now(timezone.utc)
        assert first_service.tasks.claim(
            task_id,
            owned.user_id,
            expected_status=owned.status,
            expected_version=owned.version,
            claim_token="first-token",
            claimed_at=now,
            lease_expires_at=now + timedelta(minutes=5),
        ) is True
        current = second_service.run(task_id)
        assert current.status == "PENDING"
        assert current.is_running is True
        assert second_service.tasks.claim(
            task_id,
            owned.user_id,
            expected_status=owned.status,
            expected_version=owned.version,
            claim_token="second-token",
            claimed_at=now,
            lease_expires_at=now + timedelta(minutes=5),
        ) is False
        assert first_service.tasks.release(task_id, "first-token") is True


def test_new_session_can_query_and_continue_interrupted_task(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    task_id = uuid.UUID(task["task_id"])
    with factory() as before_restart:
        stored = before_restart.get(AnalysisTask, task_id)
        assert stored is not None
        stored.status = "FETCHING_JOB"
        stored.current_step = "FETCHING_JOB"
        stored.progress = 10
        stored.is_running = True
        stored.claim_token = "expired-token"
        stored.claimed_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        stored.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        before_restart.commit()

    with factory() as startup_session:
        assert recover_interrupted_analysis_tasks(startup_session) == 1

    persisted = client.get(f"/api/v1/analysis-tasks/{task_id}")
    assert persisted.status_code == 200
    assert persisted.json()["status"] == "FETCHING_JOB"
    resumed = client.post(f"/api/v1/analysis-tasks/{task_id}/run")
    assert resumed.json()["status"] == "WAITING_FOR_REVIEW"


def test_missing_and_other_users_tasks_are_404(task_database) -> None:
    client, _ = task_database
    owner = {"X-User-Email": "owner@example.test"}
    task = create_task(client, create_profile_and_job(client, owner), owner)
    other = {"X-User-Email": "other@example.test"}

    assert client.get(
        f"/api/v1/analysis-tasks/{task['task_id']}", headers=other
    ).status_code == 404
    assert client.get(
        f"/api/v1/analysis-tasks/{uuid.uuid4()}"
    ).status_code == 404


def test_stale_version_cannot_update_claimed_task(task_database) -> None:
    client, factory = task_database
    task_id = uuid.UUID(create_task(client, create_profile_and_job(client))["task_id"])
    now = datetime.now(timezone.utc)
    with factory() as first, factory() as stale:
        current = first.get(AnalysisTask, task_id)
        stale_task = stale.get(AnalysisTask, task_id)
        assert current is not None and stale_task is not None
        assert AnalysisTaskRepository(first).claim(
            task_id,
            current.user_id,
            expected_status="PENDING",
            expected_version=current.version,
            claim_token="cas-owner",
            claimed_at=now,
            lease_expires_at=now + timedelta(minutes=5),
        )
        assert AnalysisTaskRepository(stale).compare_and_set(
            task_id,
            stale_task.user_id,
            expected_status="PENDING",
            expected_version=stale_task.version,
            values={
                "status": "FETCHING_JOB",
                "current_step": "FETCHING_JOB",
                "progress": 10,
            },
        ) is False
        assert AnalysisTaskRepository(first).release(task_id, "cas-owner")


def test_claim_token_and_lease_ownership(task_database) -> None:
    client, factory = task_database
    task_id = uuid.UUID(create_task(client, create_profile_and_job(client))["task_id"])
    now = datetime.now(timezone.utc)
    with factory() as session:
        task = session.get(AnalysisTask, task_id)
        assert task is not None
        repository = AnalysisTaskRepository(session)
        assert repository.claim(
            task.id,
            task.user_id,
            expected_status=task.status,
            expected_version=task.version,
            claim_token="old-owner",
            claimed_at=now,
            lease_expires_at=now + timedelta(minutes=5),
        )
        assert repository.release(task.id, "wrong-owner") is False
        assert repository.release_expired(now + timedelta(minutes=1)) == 0
        assert repository.release_expired(now + timedelta(minutes=6)) == 1
        session.expire_all()
        task = session.get(AnalysisTask, task_id)
        assert task is not None
        assert repository.claim(
            task.id,
            task.user_id,
            expected_status=task.status,
            expected_version=task.version,
            claim_token="new-owner",
            claimed_at=now + timedelta(minutes=6),
            lease_expires_at=now + timedelta(minutes=11),
        )
        assert repository.release(task.id, "old-owner") is False
        session.expire_all()
        assert session.get(AnalysisTask, task_id).claim_token == "new-owner"
        assert repository.release(task.id, "new-owner") is True


def test_analyzing_payload_is_reused_and_saving_without_payload_recovers(
    task_database,
) -> None:
    client, factory = task_database
    first_job = create_profile_and_job(client)
    first_id = uuid.UUID(create_task(client, first_job)["task_id"])
    calls = 0

    class CountingAnalyzer:
        def extract_job(self, *_args):
            nonlocal calls
            calls += 1
            return extracted_result()

        def analyze_job(self, *_args):
            nonlocal calls
            calls += 1
            return build_final_analysis(extracted_result())

    with factory() as session:
        task = session.get(AnalysisTask, first_id)
        profile = session.scalar(select(CandidateProfile))
        assert task is not None and profile is not None
        task.status = task.current_step = "ANALYZING"
        task.progress = 30
        task.result_payload = {
            "candidate_profile_id": str(profile.id),
            "analysis": build_final_analysis(extracted_result()).model_dump(mode="json"),
            "evidence": [],
        }
        session.commit()
        service = AnalysisTaskService(
            session,
            "demo@example.com",
            CountingAnalyzer(),
            RetrievalService(session, "demo@example.com", EmptyEmbeddingProvider()),
        )
        assert service.run(first_id).status == "WAITING_FOR_REVIEW"
        assert calls == 0

    second_job = client.post(
        "/api/v1/jobs",
        json={"title": "Second Engineer", "description": "Python recovery"},
    ).json()
    second_id = uuid.UUID(create_task(client, second_job)["task_id"])
    with factory() as session:
        task = session.get(AnalysisTask, second_id)
        assert task is not None
        task.status = task.current_step = "SAVING_RESULT"
        task.progress = 80
        task.result_payload = {}
        session.commit()
        service = AnalysisTaskService(
            session,
            "demo@example.com",
            CountingAnalyzer(),
            RetrievalService(session, "demo@example.com", EmptyEmbeddingProvider()),
        )
        assert service.run(second_id).status == "WAITING_FOR_REVIEW"
        assert calls == 2


def test_waiting_cannot_transition_back_to_analyzing() -> None:
    task = AnalysisTask(
        user_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        status="WAITING_FOR_REVIEW",
    )
    with pytest.raises(ResourceConflictError, match="WAITING_FOR_REVIEW -> ANALYZING"):
        transition_analysis_task(task, AnalysisTaskStatus.ANALYZING)


def test_complete_requires_owned_result_and_is_atomic(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    waiting = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run").json()
    task_id = uuid.UUID(task["task_id"])
    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        assert stored is not None
        stored.result_id = None
        session.commit()
    missing = client.post(f"/api/v1/analysis-tasks/{task_id}/complete")
    assert missing.status_code == 409

    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        owner = session.scalar(select(User).where(User.email == "demo@example.com"))
        profile = session.scalar(select(CandidateProfile))
        assert stored is not None and owner is not None and profile is not None
        other = User(email="other-result@example.test")
        other_job = Job(
            user=other, title="Other", description="Other", source_type="manual"
        )
        other_profile = CandidateProfile(user=other, name="Other", skills=[])
        analysis = Analysis(
            user=other,
            job=other_job,
            candidate_profile=other_profile,
            status="completed",
            result_json={},
        )
        session.add(analysis)
        session.flush()
        stored.result_id = analysis.id
        session.commit()
    invalid = client.post(f"/api/v1/analysis-tasks/{task_id}/complete")
    assert invalid.status_code == 409

    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        assert stored is not None
        stored.result_id = uuid.UUID(waiting["result_id"])
        session.commit()
    completed = client.post(f"/api/v1/analysis-tasks/{task_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    assert completed.json()["progress"] == 100


def test_result_cannot_be_deleted_while_task_references_it(task_database) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    waiting = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run").json()
    with factory() as session:
        analysis = session.get(Analysis, uuid.UUID(waiting["result_id"]))
        assert analysis is not None
        session.delete(analysis)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_database_partial_index_rejects_second_active_task(task_database) -> None:
    client, factory = task_database
    job = create_profile_and_job(client)
    create_task(client, job)
    with factory() as session:
        user = session.scalar(select(User).where(User.email == "demo@example.com"))
        assert user is not None
        session.add(AnalysisTask(user_id=user.id, job_id=uuid.UUID(job["id"])))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_active_api_and_mutations_are_user_isolated(task_database) -> None:
    client, _ = task_database
    owner = {"X-User-Email": "owner@example.test"}
    other = {"X-User-Email": "intruder@example.test"}
    job = create_profile_and_job(client, owner)
    task = create_task(client, job, owner)
    active = client.get(
        f"/api/v1/analysis-tasks/active?job_id={job['id']}", headers=owner
    )
    assert active.status_code == 200
    assert active.json()["id"] == task["task_id"]
    assert client.get(
        f"/api/v1/analysis-tasks/active?job_id={job['id']}", headers=other
    ).status_code == 404
    for action in ("run", "retry", "complete"):
        assert client.post(
            f"/api/v1/analysis-tasks/{task['task_id']}/{action}", headers=other
        ).status_code == 404


def test_two_concurrent_runs_execute_analysis_once(task_database) -> None:
    client, factory = task_database
    task_id = uuid.UUID(create_task(client, create_profile_and_job(client))["task_id"])
    barrier = Barrier(2)
    lock = Lock()
    calls = 0

    class CountingAnalyzer:
        def extract_job(self, *_args):
            nonlocal calls
            with lock:
                calls += 1
            return extracted_result()

        def analyze_job(self, *_args):
            return build_final_analysis(extracted_result())

    def execute() -> str:
        with factory() as session:
            service = AnalysisTaskService(
                session,
                "demo@example.com",
                CountingAnalyzer(),
                RetrievalService(session, "demo@example.com", EmptyEmbeddingProvider()),
            )
            barrier.wait()
            return service.run(task_id).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: execute(), range(2)))
    assert calls == 1
    assert "WAITING_FOR_REVIEW" in statuses


def test_two_concurrent_retries_only_one_claims_and_advances(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    monkeypatch.setattr(
        AnalysisService,
        "extract_job",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("fail first")),
    )
    failed = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run").json()
    assert failed["status"] == "FAILED"
    task_id = uuid.UUID(task["task_id"])
    barrier = Barrier(2)
    calls = 0
    lock = Lock()
    original_claim = AnalysisTaskService._claim

    def synchronized_claim(self, stored, *, increment_retry):
        if increment_retry:
            barrier.wait()
        return original_claim(self, stored, increment_retry=increment_retry)

    monkeypatch.setattr(AnalysisTaskService, "_claim", synchronized_claim)

    class FixedAnalyzer:
        def extract_job(self, *_args):
            nonlocal calls
            with lock:
                calls += 1
            return extracted_result()

        def analyze_job(self, *_args):
            return build_final_analysis(extracted_result())

    def retry() -> str:
        with factory() as session:
            service = AnalysisTaskService(
                session,
                "demo@example.com",
                FixedAnalyzer(),
                RetrievalService(session, "demo@example.com", EmptyEmbeddingProvider()),
            )
            return service.retry(task_id).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: retry(), range(2)))
    assert calls == 1
    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        assert stored is not None
        assert stored.retry_count == 1
        assert stored.status == "WAITING_FOR_REVIEW"
    assert set(statuses) <= {
        "FAILED", "ANALYZING", "SAVING_RESULT", "WAITING_FOR_REVIEW"
    }


def test_payload_and_saving_transition_share_one_cas(task_database, monkeypatch) -> None:
    client, _ = task_database
    task = create_task(client, create_profile_and_job(client))
    captured: list[dict[str, object]] = []
    original = AnalysisTaskRepository.compare_and_set

    def capture(self, task_id, user_id, **kwargs):
        if kwargs["expected_status"] == "ANALYZING":
            captured.append(dict(kwargs["values"]))
        return original(self, task_id, user_id, **kwargs)

    monkeypatch.setattr(AnalysisTaskRepository, "compare_and_set", capture)
    response = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run")
    assert response.json()["status"] == "WAITING_FOR_REVIEW"
    assert len(captured) == 1
    assert captured[0]["status"] == "SAVING_RESULT"
    assert captured[0]["current_step"] == "SAVING_RESULT"
    assert captured[0]["progress"] == 80
    assert captured[0]["result_payload"]


def test_two_concurrent_completes_only_one_commits(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = task_database
    task = create_task(client, create_profile_and_job(client))
    client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run")
    task_id = uuid.UUID(task["task_id"])
    barrier = Barrier(2)
    original = AnalysisTaskRepository.compare_and_set

    def synchronize_complete(self, selected_id, user_id, **kwargs):
        if kwargs["expected_status"] == "WAITING_FOR_REVIEW":
            barrier.wait()
        return original(self, selected_id, user_id, **kwargs)

    monkeypatch.setattr(
        AnalysisTaskRepository, "compare_and_set", synchronize_complete
    )

    def complete() -> str:
        with factory() as session:
            service = AnalysisTaskService(
                session,
                "demo@example.com",
                AnalysisService(object()),
                RetrievalService(session, "demo@example.com", EmptyEmbeddingProvider()),
            )
            try:
                return service.complete(task_id).status
            except ResourceConflictError:
                return "CONFLICT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: complete(), range(2)))
    assert sorted(statuses) == ["COMPLETED", "CONFLICT"]
    with factory() as session:
        stored = session.get(AnalysisTask, task_id)
        assert stored is not None
        assert stored.status == "COMPLETED"
        assert stored.completed_at is not None
        assert stored.progress == 100


def test_release_failure_does_not_mask_success(
    task_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = task_database
    task = create_task(client, create_profile_and_job(client))

    def fail_release(*_args, **_kwargs):
        raise IntegrityError("release", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(AnalysisTaskRepository, "release", fail_release)
    response = client.post(f"/api/v1/analysis-tasks/{task['task_id']}/run")
    assert response.status_code == 200
    assert response.json()["status"] == "WAITING_FOR_REVIEW"
