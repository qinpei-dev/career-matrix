"""Candidate profile endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from ...application.crud_service import CrudService
from ...application.profile_draft_service import (
    ProfileDraftEvidenceError,
    ProfileDraftExtractionError,
    ProfileDraftService,
)
from ...infrastructure.llm.provider import LLMServiceError
from ...schemas import (
    ProfileCreate,
    ProfileDraftFromDocumentRequest,
    ProfileDraftRead,
    ProfileRead,
    ProfileUpdate,
)
from ..dependencies import get_crud_service, get_profile_draft_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("/draft-from-document", response_model=ProfileDraftRead)
def draft_from_document(
    payload: ProfileDraftFromDocumentRequest,
    service: ProfileDraftService = Depends(get_profile_draft_service),
) -> ProfileDraftRead:
    """Generate an evidence-bounded draft without persisting profile data."""
    try:
        return service.generate(payload.document_id)
    except ProfileDraftEvidenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ProfileDraftExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc


@router.get("/me", response_model=ProfileRead)
def get_my_profile(service: CrudService = Depends(get_crud_service)) -> object:
    return service.get_profile()


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ProfileCreate,
    service: CrudService = Depends(get_crud_service),
) -> object:
    return service.create_profile(payload)


@router.patch("/me", response_model=ProfileRead)
def update_my_profile(
    payload: ProfileUpdate,
    service: CrudService = Depends(get_crud_service),
) -> object:
    return service.update_profile(payload)
