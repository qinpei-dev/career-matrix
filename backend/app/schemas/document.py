"""Resume document API response schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    chunk_count: int
    embedding_status: Literal["processing", "ready", "failed"]
    rag_available: bool
    can_retry: bool
    created_at: datetime


class DocumentDetailRead(DocumentListItem):
    updated_at: datetime


class DocumentChunkPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID = Field(validation_alias="id")
    section: str
    chunk_index: int
    content: str


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    section: str
    chunk_index: int
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    file_type: str
    storage_path: str
    status: str
    created_at: datetime
    updated_at: datetime
    chunks: list[DocumentChunkRead]


class DocumentUploadRead(DocumentRead):
    """Upload outcome while preserving the persisted document payload."""

    upload_status: Literal["created", "duplicate"]
    is_duplicate: bool
    message: str
