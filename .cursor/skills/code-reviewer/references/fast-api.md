# FastAPI — Review Checklist

Use with `python.md` for Python-specific concerns. Focus on HTTP API design and FastAPI conventions.

## App and routing

- **Routers**: logical `prefix`/`tags`; avoid duplicate path/param names across included routers.
- **HTTP methods and status codes**: match semantics (e.g. `201` for create, `204` for empty success).
- **`response_model`**: set where it clarifies the contract and strips extra fields.

## Dependencies

- **`Depends`**: inject DB sessions, auth, settings; keep dependency functions **small and testable**.
- **Scopes**: understand request-scoped vs app-scoped dependencies; avoid leaking request state globally.

## Request/response models (Pydantic)

- **Validation**: field constraints (`ge`, `max_length`, etc.) at the boundary.
- **V2 models**: use current Pydantic v2 patterns consistent with the project.
- **Sensitive fields**: never return secrets in response models.

## Async and I/O

- **Async routes**: use async DB/HTTP clients; don’t block the event loop.
- **Lifespan**: open/close pools and clients in lifespan handlers, not at import time when avoidable.

## OpenAPI and docs

- **Descriptions** on paths and models where behavior is non-obvious.
- **Examples** in schema when enums or formats need clarification.

## Errors

- **Consistent error shape** (e.g. HTTPException or custom handlers); avoid leaking stack traces in production responses.
- **Exception handlers**: map domain errors to correct status codes.

## Security

- **Auth**: dependency order (auth before business logic); check **authorization** not only authentication.
- **CORS**: explicit origins in production; avoid `*` with credentials.

## Testing

- **`TestClient`** or async client: cover auth, validation failures, and happy paths.
- Override dependencies in tests instead of patching internals when possible.
