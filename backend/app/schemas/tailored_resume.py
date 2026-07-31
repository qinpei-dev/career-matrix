"""Tailored resume request and response contracts."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TailoredStatus = Literal["DRAFT", "GENERATED", "EDITING", "FINALIZED", "FAILED"]


class TailoredResumeCreate(BaseModel):
    job_id: uuid.UUID
    source_document_id: uuid.UUID


class TailoredResumeStarted(BaseModel):
    tailored_resume_id: uuid.UUID
    status: TailoredStatus


class TailoredItem(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    action: Literal["保留", "改写", "调整顺序", "删除冗余", "缺失", "风险"] = "保留"

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class TailoredResumeUpdate(BaseModel):
    summary: str | None = Field(default=None, max_length=12000)
    skills: list[str] | None = Field(default=None, max_length=100)
    experience: list[TailoredItem] | None = Field(default=None, max_length=100)
    projects: list[TailoredItem] | None = Field(default=None, max_length=100)
    education: list[TailoredItem] | None = Field(default=None, max_length=50)

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]


class TailoredResumeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    source_document_id: uuid.UUID
    title: str
    status: TailoredStatus
    summary: str
    skills_json: list[str]
    experience_json: list[dict[str, Any]]
    projects_json: list[dict[str, Any]]
    education_json: list[dict[str, Any]]
    evidence_json: list[dict[str, Any]]
    warnings_json: list[dict[str, Any]]
    generated_content_json: dict[str, Any]
    user_edited_content_json: dict[str, Any]
    error_message: str | None
    is_generating: bool
    version: int
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TailoredResumeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    source_document_id: uuid.UUID
    title: str
    status: TailoredStatus
    warnings_json: list[dict[str, Any]]
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime
