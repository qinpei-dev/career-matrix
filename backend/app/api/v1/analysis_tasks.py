"""Persistent analysis-task endpoints."""

import uuid

from fastapi import APIRouter, Depends, status

from ...application.analysis_task_service import AnalysisTaskService
from ...schemas.analysis_task import (
    AnalysisTaskCreate,
    AnalysisTaskRead,
    AnalysisTaskStarted,
)
from ..dependencies import get_analysis_task_service

router = APIRouter(prefix="/analysis-tasks", tags=["analysis-tasks"])


@router.post(
    "",
    response_model=AnalysisTaskStarted,
    status_code=status.HTTP_201_CREATED,
)
def create_analysis_task(
    payload: AnalysisTaskCreate,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> AnalysisTaskStarted:
    return service.create(payload.job_id)


@router.get("/active", response_model=AnalysisTaskRead)
def get_active_analysis_task(
    job_id: uuid.UUID,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> object:
    return service.get_current_for_job(job_id)


@router.get("/{task_id}", response_model=AnalysisTaskRead)
def get_analysis_task(
    task_id: uuid.UUID,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> object:
    return service.get(task_id)


@router.post("/{task_id}/run", response_model=AnalysisTaskRead)
def run_analysis_task(
    task_id: uuid.UUID,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> object:
    return service.run(task_id)


@router.post("/{task_id}/retry", response_model=AnalysisTaskRead)
def retry_analysis_task(
    task_id: uuid.UUID,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> object:
    return service.retry(task_id)


@router.post("/{task_id}/complete", response_model=AnalysisTaskRead)
def complete_analysis_task(
    task_id: uuid.UUID,
    service: AnalysisTaskService = Depends(get_analysis_task_service),
) -> object:
    return service.complete(task_id)
