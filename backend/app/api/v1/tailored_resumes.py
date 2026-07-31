"""Evidence-backed tailored resume endpoints."""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ...application.tailored_resume_service import (
    TailoredResumeService,
    UnsupportedTailoredContentError,
)
from ...infrastructure.embedding.provider import EmbeddingServiceError
from ...infrastructure.llm.provider import LLMServiceError
from ...schemas import (
    TailoredResumeCreate,
    TailoredResumeListItem,
    TailoredResumeRead,
    TailoredResumeStarted,
    TailoredResumeUpdate,
)
from ..dependencies import get_tailored_resume_service

router = APIRouter(prefix="/tailored-resumes", tags=["tailored-resumes"])


@router.post("", response_model=TailoredResumeStarted, status_code=status.HTTP_201_CREATED)
def create_tailored_resume(
    payload: TailoredResumeCreate,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> TailoredResumeStarted:
    resume = service.create(payload.job_id, payload.source_document_id)
    return TailoredResumeStarted(
        tailored_resume_id=resume.id,
        status=resume.status,
    )


@router.get("", response_model=list[TailoredResumeListItem])
def list_tailored_resumes(
    job_id: uuid.UUID | None = Query(default=None),
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> object:
    return service.list(job_id)


@router.get("/{resume_id}", response_model=TailoredResumeRead)
def get_tailored_resume(
    resume_id: uuid.UUID,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> object:
    return service.get(resume_id)


@router.post("/{resume_id}/generate", response_model=TailoredResumeRead)
def generate_tailored_resume(
    resume_id: uuid.UUID,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> object:
    try:
        return service.generate(resume_id)
    except (LLMServiceError, EmbeddingServiceError) as exc:
        raise HTTPException(
            status_code=getattr(exc, "status_code", 502),
            detail=getattr(exc, "public_message", "定制生成失败"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="模型结果未通过结构校验") from exc


@router.patch("/{resume_id}", response_model=TailoredResumeRead)
def update_tailored_resume(
    resume_id: uuid.UUID,
    payload: TailoredResumeUpdate,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> object:
    try:
        return service.update(resume_id, payload)
    except UnsupportedTailoredContentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{resume_id}/finalize", response_model=TailoredResumeRead)
def finalize_tailored_resume(
    resume_id: uuid.UUID,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> object:
    return service.finalize(resume_id)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tailored_resume(
    resume_id: uuid.UUID,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> Response:
    service.delete(resume_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{resume_id}/export.docx")
def export_tailored_resume_docx(
    resume_id: uuid.UUID,
    service: TailoredResumeService = Depends(get_tailored_resume_service),
) -> Response:
    filename, content = service.export_docx(resume_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                "attachment; filename=tailored-resume.docx; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.get("/{resume_id}/export.pdf")
def export_tailored_resume_pdf(resume_id: uuid.UUID) -> None:
    del resume_id
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF export is NOT VERIFIED; use the real DOCX export.",
    )
