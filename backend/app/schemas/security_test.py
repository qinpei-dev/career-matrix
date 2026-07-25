"""Public, secret-free result contract for prompt-injection regressions."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RegressionStatus = Literal["PASS", "FAIL", "NOT_VERIFIED"]


class SecurityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    status: RegressionStatus
    detail: str


class SecurityTestReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str
    scope: str
    malicious_input_summary: str
    analysis_result: dict[str, Any]
    evidence: list[dict[str, Any]]
    checks: list[SecurityCheck]
    overall_status: RegressionStatus
    tool_names: list[str]
    trace: list[str]
