"""Shared test configuration for Demo Auth credentials."""

import json

import pytest

from backend.app.core.config import get_settings


TEST_DEMO_AUTH_TOKENS = {
    "test-token-demo": "demo@example.com",
    "test-token-owner": "owner@example.test",
    "test-token-other": "other@example.test",
    "test-token-first": "first@example.test",
    "test-token-second": "second@example.test",
    "test-token-intruder": "intruder@example.test",
    "test-token-many-jobs": "many-jobs@example.test",
}


@pytest.fixture(autouse=True)
def configure_demo_auth(monkeypatch: pytest.MonkeyPatch):
    """Install fake per-test credentials without relying on a developer .env file."""
    monkeypatch.setenv("DEMO_AUTH_TOKENS", json.dumps(TEST_DEMO_AUTH_TOKENS))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
