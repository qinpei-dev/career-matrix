"""Schemas for dashboard, global search, notifications, and user settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .job import JobRead


class DefaultAnalysisOptions(BaseModel):
    auto_run: bool = True
    require_review: Literal[True] = True


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    display_name: str
    target_role: str | None
    default_analysis_options: DefaultAnalysisOptions
    page_size: Literal[10, 20, 50, 100]
    show_technical_details: bool
    updated_at: datetime


class UserSettingsUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    target_role: str | None = Field(default=None, max_length=200)
    default_analysis_options: DefaultAnalysisOptions | None = None
    page_size: Literal[10, 20, 50, 100] | None = None
    show_technical_details: bool | None = None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped

    @field_validator("target_role")
    @classmethod
    def strip_target_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ProviderStatus(BaseModel):
    provider: str
    model: str
    configured: bool
    credential: Literal["已配置（已脱敏）", "未配置"]


class ProviderStatuses(BaseModel):
    llm: ProviderStatus
    embedding: ProviderStatus


class DashboardStats(BaseModel):
    jobs: int
    analyses: int
    analyzed_jobs: int
    pending_jobs: int
    average_score: int | None
    high_matches: int
    documents: int
    ready_documents: int
    active_tasks: int
    failed_tasks: int


class RecentAnalysis(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company: str | None
    status: str
    score: int | None
    updated_at: datetime


class RecentJob(JobRead):
    analysis_status: str | None
    analysis_score: int | None


class RecentTask(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    status: str
    progress: int
    error_message: str | None
    updated_at: datetime


class DashboardRead(BaseModel):
    stats: DashboardStats
    recent_jobs: list[RecentJob]
    recent_analyses: list[RecentAnalysis]
    recent_tasks: list[RecentTask]


class SearchResult(BaseModel):
    type: Literal["job", "resume", "analysis"]
    id: uuid.UUID
    title: str
    subtitle: str
    excerpt: str
    href: str
    updated_at: datetime


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


class NotificationRead(BaseModel):
    id: str
    level: Literal["success", "error", "info"]
    title: str
    detail: str
    href: str
    created_at: datetime
