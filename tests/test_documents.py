from io import BytesIO
from pathlib import Path
from uuid import UUID

import fitz
import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from app.api.documents import (
    delete_document,
    get_document,
    list_document_pages,
    list_documents,
    process_document,
    upload_document,
)
from app.core.config import Settings
from app.db.database import Base


@pytest.fixture
def database() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield database
    database.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="sqlite://",
        document_storage_path=tmp_path / "documents",
        max_upload_size_bytes=1024,
    )


def uploaded_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_upload_list_get_and_delete_document(database: Session, settings: Settings) -> None:
    document = upload_document(
        uploaded_file("agreement.pdf", b"%PDF-1.7\nexample", "application/pdf"),
        database,
        settings,
    )

    assert document.original_filename == "agreement.pdf"
    assert document.status == "uploaded"
    assert document.file_size_bytes == len(b"%PDF-1.7\nexample")

    listed = list_documents(database, limit=50, offset=0)
    assert listed.total == 1

    fetched = get_document(UUID(document.id), database)
    assert fetched.id == document.id

    delete_document(UUID(document.id), database)
    with pytest.raises(HTTPException, match="Document not found"):
        get_document(UUID(document.id), database)


def test_upload_rejects_non_pdf_file(database: Session, settings: Settings) -> None:
    with pytest.raises(HTTPException, match="Only PDF files are supported") as error:
        upload_document(
            uploaded_file("notes.txt", b"not a PDF", "text/plain"), database, settings
        )

    assert error.value.status_code == 415


def test_processes_pdf_and_retains_page_numbers(database: Session, settings: Settings) -> None:
    pdf = fitz.open()
    first_page = pdf.new_page()
    first_page.insert_text((72, 72), "Termination requires 30 days notice.")
    pdf.new_page()  # Empty pages are retained for citations.
    pdf_bytes = pdf.tobytes()
    pdf.close()

    document = upload_document(
        uploaded_file("contract.pdf", pdf_bytes, "application/pdf"), database, settings
    )
    processed = process_document(UUID(document.id), database)

    assert processed.pages_processed == 2
    assert processed.document.status == "processed"
    assert processed.document.page_count == 2

    pages = list_document_pages(UUID(document.id), database, limit=50, offset=0)
    assert pages.total == 2
    assert pages.items[0].page_number == 1
    assert "30 days notice" in pages.items[0].text
    assert pages.items[1].page_number == 2
    assert pages.items[1].text == ""
