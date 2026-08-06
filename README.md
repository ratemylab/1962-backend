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

## Admin Authentication

Admin endpoints use JWT instead of client API keys. Client endpoints are unaffected and keep using `X-Client-Id` / `X-Api-Token`.

Log in to obtain a token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "Admin@123"}'
```

The response contains `accessToken`, `refreshToken`, `tokenType`, `expiresIn` and `refreshExpiresIn`. Send the access token on admin calls:

```bash
curl -X POST http://localhost:8000/api/v1/admin/clients \
  -H "Authorization: Bearer <accessToken>" \
  -H 'Content-Type: application/json' \
  -d '{"clientId": "client_up_001", "clientName": "Field App - Uttar Pradesh"}'
```

`get_current_admin()` from `app.api.deps` verifies the signature and expiry, reloads the admin, and rejects deactivated accounts. Every failure returns `401`.

### Refresh and logout

The refresh token is an opaque random string rather than a JWT, so it can be revoked. Only its hash is stored, using the same `hash_token()` / `verify_token()` helpers as client API tokens, and the plaintext is returned exactly once at login.

Exchange it for a new access token without resending credentials:

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refreshToken": "<refreshToken>"}'
```

Refreshing does not rotate the refresh token. Revoke it explicitly:

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <accessToken>"
```

Each admin has at most one active refresh token, enforced by a unique constraint on `refresh_tokens.admin_id`. Logging in again replaces the stored row, so the previous refresh token stops working. After logout or expiry, `/auth/refresh` returns `401`. Access tokens are stateless and stay valid until they expire, so keep `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` short if immediate revocation matters.

Relevant settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `JWT_SECRET_KEY` | development placeholder | Signing key; **must** be overridden outside local development |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime, reported as `expiresIn` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime, reported as `refreshExpiresIn` |
| `REFRESH_TOKEN_BYTES` | `32` | Entropy of the generated refresh token |
| `SEED_ADMIN_ENABLED` | `true` | Seed the default admin on startup |
| `SEED_ADMIN_USERNAME` | `admin` | Default admin username |
| `SEED_ADMIN_PASSWORD` | `Admin@123` | Default admin password, stored only as a bcrypt hash |

The startup seeder creates the default admin once and never overwrites an existing one. Change the seeded password before exposing a deployment, and always set a unique `JWT_SECRET_KEY` (for example `openssl rand -hex 32`), otherwise admin tokens are forgeable.

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

Follow-up migrations create:

- `admins`
- `refresh_tokens`

The app uses async SQLAlchemy sessions at runtime and Alembic with a synchronous PostgreSQL driver for migrations.

## Tests

```bash
poetry run pytest
```
