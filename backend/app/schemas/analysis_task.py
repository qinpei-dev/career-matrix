"""API schemas for persistent analysis tasks."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from ..infrastructure.database.models.analysis_task import AnalysisTaskStatus


class AnalysisTaskCreate(BaseModel):
    job_id: uuid.UUID


class AnalysisTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    status: AnalysisTaskStatus
    current_step: str
    progress: int
    retry_count: int
    max_retries: int
    error_code: str | None
    error_message: str | None
    result_id: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_running: bool
    claimed_at: datetime | None
    lease_expires_at: datetime | None


class AnalysisTaskStarted(BaseModel):
    task_id: uuid.UUID
    status: AnalysisTaskStatus
    current_step: str
    progress: int
