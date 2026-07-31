"""Tests for evidence parsing, deterministic scoring integration, and API errors."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.database.models import User
from backend.app.infrastructure.llm import deepseek
from backend.app.services import llm

client = TestClient(
    main.app,
    headers={"Authorization": "Bearer test-token-demo"},
)


@pytest.fixture(autouse=True)
def authenticated_legacy_client():
    """Keep LLM behavior tests focused while auth is covered at the real boundary."""
    previous = main.app.dependency_overrides.get(get_current_user)
    main.app.dependency_overrides[get_current_user] = lambda: User(
        email="demo@example.com"
    )
    yield
    if previous is None:
        main.app.dependency_overrides.pop(get_current_user, None)
    else:
        main.app.dependency_overrides[get_current_user] = previous

STRUCTURED_ANALYSIS = {
    "job_requirements": {
        "core_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Redis"],
        "project_requirements": ["API project"],
        "education_requirements": [],
        "experience_requirements": [],
    },
    "matched_skills": ["Python"],
    "partial_skills": ["FastAPI"],
    "missing_skills": [],
    "unverified_skills": ["Redis"],
    "project_evidence": ["Built an HTTP API"],
    "education_evidence": [],
    "experience_evidence": [],
    "project_status": "related",
    "education_status": "unverified",
    "experience_status": "unverified",
    "learning_plan": ["Complete a Redis exercise"],
    "reasoning": ["Python has direct evidence"],
    "greeting": "你好，我有 Python 项目实践。",
    "confidence": 0.91,
}


def test_parse_valid_json_returns_backend_score() -> None:
    payload = {**STRUCTURED_ANALYSIS, "score": 99}
    analysis = llm._parse_analysis(json.dumps(payload, ensure_ascii=False))

    assert analysis.score == 67
    assert analysis.score_breakdown.education_background.applicable is False
    assert analysis.partial_skills == ["FastAPI"]


def test_extract_json_from_surrounding_text() -> None:
    content = f"model output:\n{json.dumps(STRUCTURED_ANALYSIS)}\nend"
    assert llm._parse_analysis(content).matched_skills == ["Python"]


def test_legacy_response_defaults_missing_fields_and_ignores_score() -> None:
    legacy = {
        "score": 100,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "learning_plan": [],
        "reasoning": [],
        "greeting": "你好",
        "confidence": 0.8,
    }
    analysis = llm._parse_analysis(json.dumps(legacy, ensure_ascii=False))

    assert analysis.score == 0
    assert all(
        not dimension.applicable
        for _, dimension in analysis.score_breakdown
    )


def test_invalid_json_raises_safe_error() -> None:
    with pytest.raises(llm.LLMResponseFormatError, match="模型返回格式错误"):
        llm._parse_analysis("not json")


def test_analyze_job_parses_mocked_model_json(monkeypatch, tmp_path) -> None:
    captured_request = {}
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(STRUCTURED_ANALYSIS, ensure_ascii=False)
        ))]
    )

    def create_completion(**kwargs):
        captured_request.update(kwargs)
        return fake_response

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_completion))
    )
    monkeypatch.setattr(llm, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: fake_client)

    analysis = llm.analyze_job(
        "Python 开发", "要求 Python、FastAPI 和 Redis", "掌握 Python，了解 FastAPI"
    )

    assert analysis.score == 67
    messages = captured_request["messages"]
    assert "不要决定、建议或估算最终 score" in messages[0]["content"]
    assert "JD 中的技能不能自动视为候选人技能" in messages[0]["content"]
    assert "要求 Python、FastAPI 和 Redis" in messages[1]["content"]
    assert captured_request["temperature"] == 0.0


def test_missing_api_key_does_not_crash(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(deepseek, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = client.post(
        "/api/analyze-job",
        json={
            "job_title": "Python 开发",
            "job_description": "负责 API 开发",
            "candidate_profile": "掌握 Python",
        },
    )
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["detail"]


def test_invalid_model_response_returns_502(monkeypatch) -> None:
    def raise_format_error(*args) -> None:
        raise llm.LLMResponseFormatError("模型返回格式错误")

    monkeypatch.setattr(main, "analyze_job", raise_format_error)
    response = client.post(
        "/api/analyze-job",
        json={
            "job_title": "Python 开发",
            "job_description": "负责 API 开发",
            "candidate_profile": "掌握 Python",
        },
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "模型返回格式错误"}


@pytest.mark.parametrize(
    "payload",
    [
        {"job_title": "Python", "job_description": "API"},
        {"job_title": "Python", "job_description": "API", "candidate_profile": "   "},
    ],
)
def test_candidate_profile_is_required(payload) -> None:
    assert client.post("/api/analyze-job", json=payload).status_code == 422


def test_three_field_request_enters_llm_service(monkeypatch) -> None:
    captured = {}
    expected = llm._build_final_analysis(llm.ExtractedAnalysis.model_validate(STRUCTURED_ANALYSIS))

    def fake_analyze_job(job_title, job_description, candidate_profile):
        captured.update(
            job_title=job_title,
            job_description=job_description,
            candidate_profile=candidate_profile,
        )
        return expected

    monkeypatch.setattr(main, "analyze_job", fake_analyze_job)
    response = client.post(
        "/api/analyze-job",
        json={
            "job_title": " Python 开发 ",
            "job_description": " API 开发 ",
            "candidate_profile": " Python 与 Git ",
        },
    )
    assert response.status_code == 200
    assert response.json()["score_breakdown"]["core_skills"]["weight"] > 0
    assert captured == {
        "job_title": "Python 开发",
        "job_description": "API 开发",
        "candidate_profile": "Python 与 Git",
    }
