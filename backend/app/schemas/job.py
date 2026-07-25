"""Job request and response schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ..core.security import MAX_UNTRUSTED_JOB_CONTENT_CHARS, limit_untrusted_job_content


class JobCreate(BaseModel):
    """Create a saved job for the current user."""

    title: str = Field(min_length=1, max_length=500)
    company: str | None = Field(default=None, max_length=300)
    description: str = Field(min_length=1, max_length=MAX_UNTRUSTED_JOB_CONTENT_CHARS)
    source_url: str | None = Field(default=None, max_length=2048)
    source_type: str = Field(default="manual", min_length=1, max_length=50)

    @field_validator("title", "company", "description", "source_url", "source_type")
    @classmethod
    def strip_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        stripped = (
            limit_untrusted_job_content(value)
            if info.field_name == "description"
            else value.strip()
        )
        if info.field_name in {"title", "description", "source_type"} and not stripped:
            raise ValueError(f"{info.field_name} must not be blank")
        return stripped


class JobRead(JobCreate):
    """Persisted saved job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class JobCreateResponse(JobRead):
    """Outcome of an idempotent saved-job create request."""

    status: Literal["created", "duplicate"]
    job_id: uuid.UUID
    message: str | None = None
