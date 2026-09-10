# DocPilot

Evidence-first document intelligence built with local, open-source AI components.

## Current scope

The service provides a health check, PDF upload/document-management API, and page-aware PDF text extraction. Uploaded PDFs are stored locally, while their metadata and extracted pages are stored in PostgreSQL. Qdrant, local embeddings, and Ollama are introduced in later incremental phases.

### Run locally

Requires Python 3.12 or newer.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for API documentation. Current endpoints are `GET /health`, `POST /documents/upload`, `GET /documents`, `GET /documents/{document_id}`, `POST /documents/{document_id}/process`, `GET /documents/{document_id}/pages`, and `DELETE /documents/{document_id}`.

### Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

### Checks

```bash
pytest
ruff check .
```

## Layout

`app/api` holds HTTP endpoints, `app/core` contains cross-cutting configuration and logging, and future pipeline services will live under `app/services`. This keeps API contracts separate from RAG and persistence concerns as the application grows.
