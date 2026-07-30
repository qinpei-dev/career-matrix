"""Resume document management endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from ...application.document_service import (
    DocumentProcessingError,
    DocumentService,
    DocumentTooLargeError,
    MAX_DOCUMENT_SIZE,
    UnsupportedDocumentTypeError,
)
from ...infrastructure.embedding.provider import EmbeddingServiceError
from ...schemas import (
    DocumentChunkPublic,
    DocumentDetailRead,
    DocumentListItem,
    DocumentRead,
    DocumentUploadRead,
)
from ..dependencies import get_document_service

router = APIRouter(prefix="/documents", tags=["documents"])


async def _read_limited(file: UploadFile) -> bytes:
    contents = bytearray()
    while chunk := await file.read(1024 * 1024):
        contents.extend(chunk)
        if len(contents) > MAX_DOCUMENT_SIZE:
            raise DocumentTooLargeError("document must not exceed 10 MB")
    return bytes(contents)


@router.post(
    "/upload",
    response_model=DocumentUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
) -> object:
    """Store, extract, structure, and persist a PDF or DOCX resume."""
    try:
        contents = await _read_limited(file)
        result = service.upload(file.filename or "", contents)
        if not result.created:
            response.status_code = status.HTTP_200_OK
        is_duplicate = not result.created
        document_payload = DocumentRead.model_validate(result.document).model_dump()
        return DocumentUploadRead.model_validate({
            **document_payload,
            "upload_status": "duplicate" if is_duplicate else "created",
            "is_duplicate": is_duplicate,
            "message": (
                "该简历版本已存在，无需重新解析"
                if is_duplicate
                else "简历上传并解析完成"
            ),
        })
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except EmbeddingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
    finally:
        await file.close()


@router.get("", response_model=list[DocumentListItem])
def list_documents(service: DocumentService = Depends(get_document_service)) -> object:
    return service.list_documents()


@router.get("/{document_id}", response_model=DocumentDetailRead)
def get_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
) -> object:
    return service.get_document(document_id)


@router.post("/{document_id}/retry", response_model=DocumentDetailRead)
def retry_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
) -> object:
    """Retry parsing and embedding a failed user-owned document."""
    try:
        return service.retry(document_id)
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT
            if "only failed" in str(exc)
            else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except EmbeddingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkPublic])
def list_document_chunks(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
) -> object:
    return service.list_chunks(document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
) -> Response:
    service.delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
