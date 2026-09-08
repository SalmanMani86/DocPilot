# DocPilot

Evidence-first document intelligence built with local, open-source AI components.

## Phase 1: API foundation

The service currently exposes a health check and automatic OpenAPI documentation. Document ingestion, PostgreSQL, Qdrant, local embeddings, and Ollama are introduced in later incremental phases.

### Run locally

Requires Python 3.12 or newer.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for API documentation, or call `GET /health`.

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
