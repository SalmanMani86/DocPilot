from dataclasses import dataclass
from pathlib import Path

import fitz


class PDFExtractionError(Exception):
    """Raised when a PDF cannot safely yield page text."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


def extract_pages(pdf_path: Path) -> list[ExtractedPage]:
    """Extract text from every PDF page while retaining its one-based page number."""
    if not pdf_path.is_file():
        raise PDFExtractionError("The stored PDF file no longer exists")

    try:
        with fitz.open(pdf_path) as pdf:
            if pdf.needs_pass:
                raise PDFExtractionError("Password-protected PDFs are not supported")

            return [
                ExtractedPage(page_number=index, text=page.get_text("text"))
                for index, page in enumerate(pdf, start=1)
            ]
    except PDFExtractionError:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError) as error:
        raise PDFExtractionError("The uploaded file could not be read as a PDF") from error
