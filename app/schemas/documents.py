from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    status: str
    page_count: int
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_number: int
    text: str
    created_at: datetime


class DocumentPageListResponse(BaseModel):
    items: list[DocumentPageResponse]
    total: int


class DocumentProcessResponse(BaseModel):
    document: DocumentResponse
    pages_processed: int
