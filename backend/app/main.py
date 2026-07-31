"""FastAPI entry point for AI Job Copilot."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .application.analysis_service import analyze_job
from .application.agent_service import recover_stale_agent_runs
from .application.analysis_task_service import recover_interrupted_analysis_tasks
from .application.crud_service import ResourceConflictError, ResourceNotFoundError
from .api.dependencies import get_current_user, get_db_session
from .api.v1.router import router as v1_router
from .core.config import get_settings
from .infrastructure.database.models import User
from .infrastructure.database.session import (
    DatabaseConfigurationError,
    get_default_session_factory,
)
from .infrastructure.llm.parser import JobAnalysis
from .infrastructure.llm.provider import LLMServiceError
from sqlalchemy.exc import SQLAlchemyError

APP_NAME = "AI Job Copilot API"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Recover abandoned Agent Runs before accepting production traffic."""
    # Database-backed API tests provide their own request session and test recovery directly.
    if get_db_session not in application.dependency_overrides:
        try:
            with get_default_session_factory()() as session:
                recover_stale_agent_runs(
                    session,
                    get_settings().agent_run_timeout_seconds,
                )
                recover_interrupted_analysis_tasks(session)
        except (DatabaseConfigurationError, SQLAlchemyError) as exc:
            logger.warning("Agent Run startup recovery skipped: %s", exc)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://.*)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.exception_handler(ResourceNotFoundError)
def handle_not_found(_request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ResourceConflictError)
def handle_conflict(_request: Request, exc: ResourceConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
def read_root() -> dict[str, str]:
    """Return basic service information."""
    return {"name": APP_NAME, "status": "running"}


@app.get("/health")
def read_health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "ok"}


class JobAnalysisRequest(BaseModel):
    """Input accepted by the job analysis endpoint."""

    job_title: str = Field(min_length=1, max_length=500)
    job_description: str = Field(min_length=1, max_length=8000)
    candidate_profile: str = Field(min_length=1, max_length=8000)

    @field_validator("job_title", "job_description", "candidate_profile")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("字段不能为空")
        return stripped


@app.post("/api/analyze-job", response_model=JobAnalysis)
def analyze_job_endpoint(
    payload: JobAnalysisRequest,
    _current_user: User = Depends(get_current_user),
) -> JobAnalysis:
    """Analyze a job description through the configured LLM service."""
    try:
        return analyze_job(
            payload.job_title,
            payload.job_description,
            payload.candidate_profile,
        )
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.public_message,
        ) from exc
