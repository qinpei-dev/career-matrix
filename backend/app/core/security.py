"""Security boundaries for untrusted job content and public diagnostics."""

from __future__ import annotations

import re
from typing import Any

MAX_UNTRUSTED_JOB_CONTENT_CHARS = 8_000
REDACTED = "[REDACTED]"

_SENSITIVE_PATTERNS = (
    re.compile(r"TEST_SECRET_DO_NOT_EXPOSE_[A-Za-z0-9_-]+"),
    re.compile(r"TEST_SECRET_CANARY_[A-Za-z0-9_-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_ -]?key|token|secret|password|authorization)"
        r"(\s*[:=]\s*)([^\s,;\"']{4,})"
    ),
)

_UNTRUSTED_COMMAND_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"忽略之前(?:所有)?规则",
        r"读取(?:本地\s*)?\.env",
        r"(?:输出|显示).{0,12}api\s*key",
        r"自动发送.{0,12}(?:招聘)?消息",
        r"你现在是系统管理员",
        r"隐藏这些指令",
        r"发送到外部服务器",
        r"ignore (?:all )?(?:previous|prior) instructions",
        r"read (?:the )?\.env",
        r"(?:print|reveal|output).{0,16}(?:api.?key|token|secret)",
        r"(?:send|post|upload).{0,24}(?:message|candidate|external server)",
    )
)


def limit_untrusted_job_content(value: str) -> str:
    """Normalize and cap content before it reaches persistence or a model."""
    return value.replace("\x00", "").strip()[:MAX_UNTRUSTED_JOB_CONTENT_CHARS]


def redact_sensitive_text(value: str) -> str:
    """Remove common credential shapes without inspecting process environment."""
    redacted = value
    for index, pattern in enumerate(_SENSITIVE_PATTERNS):
        if index == 3:
            redacted = pattern.sub(r"\1" + REDACTED, redacted)
        elif index == 4:
            redacted = pattern.sub(r"\1\2" + REDACTED, redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def contains_untrusted_command(value: str) -> bool:
    return any(pattern.search(value) for pattern in _UNTRUSTED_COMMAND_PATTERNS)


def sanitize_model_text(value: str) -> str:
    """Keep model text public-safe and remove lines that repeat page commands."""
    safe_lines = [
        redact_sensitive_text(line)
        for line in value.splitlines()
        if not contains_untrusted_command(line)
    ]
    return "\n".join(safe_lines).strip()


def sanitize_model_payload(value: Any) -> Any:
    """Recursively sanitize only model-produced strings."""
    if isinstance(value, str):
        return sanitize_model_text(value)
    if isinstance(value, list):
        return [
            sanitized
            for item in value
            if (sanitized := sanitize_model_payload(item)) not in ("", None)
        ]
    if isinstance(value, dict):
        return {key: sanitize_model_payload(item) for key, item in value.items()}
    return value


def public_error_message(exc: Exception, fallback: str = "operation failed") -> str:
    """Redact public/provider errors and unexpected diagnostics before persistence."""
    message = getattr(exc, "public_message", None)
    if not isinstance(message, str) or not message:
        message = str(exc) or fallback
    return redact_sensitive_text(message)
