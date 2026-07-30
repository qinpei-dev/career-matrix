"""Saved job endpoints."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ...application.analysis_service import ApplicationAnalysisService
from ...application.crud_service import CrudService
from ...infrastructure.llm.provider import LLMServiceError
from ...schemas import JobAnalysisRead, JobCreate, JobCreateResponse, JobRead
from ...schemas.job import JobUpdate
from ..dependencies import get_application_analysis_service, get_crud_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    payload: JobCreate,
    response: Response,
    service: CrudService = Depends(get_crud_service),
) -> object:
    result = service.create_job(payload)
    if result.status == "duplicate":
        response.status_code = status.HTTP_200_OK
    job_data = JobRead.model_validate(result.job).model_dump()
    return {
        **job_data,
        "status": result.status,
        "job_id": result.job.id,
        "message": result.message,
    }


@router.get("", response_model=list[JobRead])
def list_jobs(
    query: str | None = Query(default=None, min_length=1, max_length=200),
    source_type: str | None = Query(default=None, min_length=1, max_length=50),
    analysis_status: Literal["analyzed", "pending"] | None = None,
    sort: Literal[
        "updated_desc", "created_desc", "title_asc", "company_asc"
    ] = "updated_desc",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: CrudService = Depends(get_crud_service),
) -> object:
    return service.list_jobs(
        query=query.strip() if query else None,
        source_type=source_type,
        analysis_status=analysis_status,
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    service: CrudService = Depends(get_crud_service),
) -> object:
    return service.get_job(job_id)


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    service: CrudService = Depends(get_crud_service),
) -> object:
    return service.update_job(job_id, payload)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    service: CrudService = Depends(get_crud_service),
) -> Response:
    service.delete_job(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/analyze", response_model=JobAnalysisRead)
def analyze_saved_job(
    job_id: uuid.UUID,
    service: ApplicationAnalysisService = Depends(get_application_analysis_service),
) -> object:
    try:
        return service.analyze_job(job_id)
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
