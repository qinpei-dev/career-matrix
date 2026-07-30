"""Endpoints for constrained Career Copilot runs."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from ...agents.career_copilot.schemas import AgentRunCreate, AgentRunRead, AgentRunStarted
from ...application.agent_service import AgentRunService
from ..dependencies import get_agent_run_service

router = APIRouter(prefix="/agent/runs", tags=["agent"])


@router.post("", response_model=AgentRunStarted, status_code=status.HTTP_202_ACCEPTED)
def create_agent_run(
    payload: AgentRunCreate,
    background_tasks: BackgroundTasks,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunStarted:
    started = service.create_run(payload.job_id)
    background_tasks.add_task(service.execute, started.run_id)
    return started


@router.get("/active", response_model=AgentRunRead)
def get_active_agent_run(
    job_id: uuid.UUID,
    service: AgentRunService = Depends(get_agent_run_service),
) -> object:
    run = service.find_active_run(job_id)
    return run if run is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{run_id}", response_model=AgentRunRead)
def get_agent_run(
    run_id: uuid.UUID,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    return service.get_run(run_id)
