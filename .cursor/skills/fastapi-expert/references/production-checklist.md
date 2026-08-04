# Production Checklist

When generating or reviewing a FastAPI API for production, ensure the following are in place.

## Configuration

- **Use pydantic-settings (or equivalent)** for all configuration; no hardcoded secrets or URLs.
- Load `SECRET_KEY`, `DATABASE_URL`, and similar from environment; validate at startup so the app fails fast if required vars are missing.
- See `references/pydantic-v2.md` for `BaseSettings` and `SettingsConfigDict`.

## CORS

- Configure CORS explicitly via `CORSMiddleware` with allowed origins from settings (e.g. `settings.CORS_ORIGINS`).
- Do not use `allow_origins=["*"]` in production unless intentional.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Rate Limiting

- Apply rate limiting to auth endpoints (e.g. `/auth/token`) and to public or expensive endpoints.
- Use a middleware or dependency (e.g. slowapi, or custom dependency with in-memory/Redis store) and return 429 when exceeded.

```python
# Example: dependency-based rate limit (conceptual)
from fastapi import Request, HTTPException

async def rate_limit_auth(request: Request) -> None:
    key = f"auth:{request.client.host}"
    if await is_rate_limited(key, max_calls=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests")
```

## Health and Readiness

- Implement **`/health`** (and optionally **`/ready`**) so orchestrators and load balancers can check liveness and readiness.
- **`/health`**: simple 200 (e.g. "ok"); no DB required.
- **`/ready`** (optional): 200 only if the app can serve traffic (e.g. DB connection or migration state OK); 503 otherwise.

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/ready")
async def ready(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    from sqlalchemy import text
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
```

## Global Exception Handler

- Register a global exception handler that returns a **consistent JSON error schema** (e.g. `detail`, `code`, `request_id`) for all unhandled exceptions.
- Log the full exception server-side; do not expose internal details in the response body in production.

```python
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    logger.exception("Unhandled exception", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
    )
```

## Logging and Request ID

- Use structured logging; attach a **request_id** (from header or generated) to each request and include it in log records and in error responses so traces can be followed.

## Checklist Summary

| Item | Required |
|------|----------|
| Configuration via pydantic-settings (no hardcoded secrets) | Yes |
| CORS configured explicitly from settings | Yes |
| Rate limiting on auth and public endpoints | Yes |
| `/health` endpoint | Yes |
| `/ready` endpoint (optional, with DB check) | Recommended |
| Global exception handler with consistent error schema | Yes |
| Request/correlation ID in logs and error responses | Yes |
