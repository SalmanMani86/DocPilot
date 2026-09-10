import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db
from app.db.models import Document, DocumentPage
from app.schemas.documents import (
    DocumentListResponse,
    DocumentPageListResponse,
    DocumentProcessResponse,
    DocumentResponse,
)
from app.services.pdf_service import PDFExtractionError, extract_pages

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
CHUNK_SIZE_BYTES = 1024 * 1024


def get_document_or_404(database: Session, document_id: UUID) -> Document:
    document = database.get(Document, str(document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: UploadFile = File(...),
    database: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Document:
    """Validate and persist a PDF plus its metadata. Processing occurs in a later phase."""
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Only PDF files are supported")
    if file.content_type and file.content_type.lower() not in PDF_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    document = Document(
        id=str(uuid4()),
        original_filename=Path(filename).name,
        storage_path="",  # Set after an ID is generated.
        content_type="application/pdf",
        file_size_bytes=0,
        status="uploaded",
    )
    document_id = document.id
    storage_directory = settings.document_storage_path
    storage_directory.mkdir(parents=True, exist_ok=True)
    destination = storage_directory / f"{document_id}.pdf"
    bytes_written = 0

    try:
        with destination.open("xb") as stored_file:
            first_chunk = file.file.read(CHUNK_SIZE_BYTES)
            if not first_chunk.startswith(b"%PDF-"):
                raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF")

            while True:
                chunk = first_chunk if bytes_written == 0 else file.file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"PDF exceeds the {settings.max_upload_size_bytes} byte upload limit",
                    )
                stored_file.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError as error:
        destination.unlink(missing_ok=True)
        logger.exception("Unable to store uploaded document")
        raise HTTPException(status_code=500, detail="Unable to store uploaded document") from error
    finally:
        file.file.close()

    document.storage_path = str(destination)
    document.file_size_bytes = bytes_written
    try:
        database.add(document)
        database.commit()
        database.refresh(document)
    except Exception:
        database.rollback()
        destination.unlink(missing_ok=True)
        logger.exception("Unable to persist document metadata")
        raise HTTPException(status_code=500, detail="Unable to persist document metadata") from None

    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    database: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    total = database.scalar(select(func.count()).select_from(Document)) or 0
    documents = database.scalars(
        select(Document).order_by(Document.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return DocumentListResponse(items=documents, total=total)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, database: Session = Depends(get_db)) -> Document:
    return get_document_or_404(database, document_id)


@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(document_id: UUID, database: Session = Depends(get_db)) -> DocumentProcessResponse:
    """Extract page-aware text synchronously. A background worker will replace this later."""
    document = get_document_or_404(database, document_id)
    document.status = "processing"
    database.commit()

    try:
        extracted_pages = extract_pages(Path(document.storage_path))
        database.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        database.add_all(
            [
                DocumentPage(
                    id=str(uuid4()),
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                )
                for page in extracted_pages
            ]
        )
        document.status = "processed"
        document.page_count = len(extracted_pages)
        database.commit()
        database.refresh(document)
    except PDFExtractionError as error:
        database.rollback()
        document.status = "failed"
        database.commit()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception:
        database.rollback()
        document.status = "failed"
        database.commit()
        logger.exception("Unable to process document", extra={"document_id": document.id})
        raise HTTPException(status_code=500, detail="Unable to process document") from None

    return DocumentProcessResponse(document=document, pages_processed=len(extracted_pages))


@router.get("/{document_id}/pages", response_model=DocumentPageListResponse)
def list_document_pages(
    document_id: UUID,
    database: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentPageListResponse:
    document = get_document_or_404(database, document_id)
    total = database.scalar(
        select(func.count()).select_from(DocumentPage).where(DocumentPage.document_id == document.id)
    ) or 0
    pages = database.scalars(
        select(DocumentPage)
        .where(DocumentPage.document_id == document.id)
        .order_by(DocumentPage.page_number)
        .offset(offset)
        .limit(limit)
    ).all()
    return DocumentPageListResponse(items=pages, total=total)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, database: Session = Depends(get_db)) -> None:
    document = get_document_or_404(database, document_id)
    stored_file = Path(document.storage_path)
    database.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
    database.delete(document)
    database.commit()
    stored_file.unlink(missing_ok=True)
