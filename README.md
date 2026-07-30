# Ticket Management Backend

FastAPI backend foundation for the Ticket Management System assignment.

Phase 2 prepares infrastructure only: database models, Alembic migration, static client-token authentication dependency, seed tooling, Docker wiring, and foundation tests. Ticket API endpoints and ticket business logic are intentionally not implemented yet.

## Prerequisites

- Python 3.12+
- Poetry 2.x
- Docker and Docker Compose

## Setup

Create `.env` from `.env.example` if needed. The application builds sync and async SQLAlchemy URLs from `DB_*` settings.

```bash
poetry install
poetry run alembic upgrade head
poetry run python scripts/seed_clients.py
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8085
```

Health check: http://localhost:8085/health

## Docker

```bash
docker compose up --build
```

The Compose stack starts the API and PostgreSQL. The API container runs Alembic migrations, seeds missing sample clients, and mounts an audio upload volume at `/app/uploads/audio`.

## Authentication Foundation

Protected Phase 3 endpoints should depend on `get_current_client()` from `app.api.deps`.

The dependency reads:

- `X-Client-Id`
- `X-Api-Token`

It looks up the client, verifies the hashed token, checks `is_active`, and returns the authenticated `ClientDB`. Invalid credentials return `401`.

## Client Management

Seed clients:

```bash
poetry run python scripts/seed_clients.py
```

Create one client:

```bash
poetry run python create_client.py --client-name "Partner Clinic"
```

Plaintext API tokens are printed only when a client is created. Store them securely; only token hashes are persisted.

## Database

The foundation migration creates:

- `clients`
- `tickets`
- `animals`
- `audio_files`

The app uses async SQLAlchemy sessions at runtime and Alembic with a synchronous PostgreSQL driver for migrations.

## Tests

```bash
poetry run pytest
```
