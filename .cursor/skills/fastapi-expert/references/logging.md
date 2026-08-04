# Logging (Template `AppLogger`)

Use the project’s existing logging utility. **Do not add new logging frameworks, handlers, or `basicConfig()` calls in generated code.**

## Canonical import + usage (MUST)

In any new module (router/service/repo), obtain a logger like this:

```python
from app.core.logging import AppLogger

logger = AppLogger().get_logger()
```

Then log with:

- `logger.info(...)`
- `logger.warning(...)`
- `logger.error(...)`
- `logger.exception(...)` (when handling exceptions)

Avoid `print()`.

## Structured fields with `extra={...}` (SHOULD)

Your template logger uses `python-json-logger`, so you should attach structured fields via `extra` so they become JSON attributes.

Recommended standard keys:

- `request_id`
- `user_id`
- `resource_id`
- `operation`
- `path`, `method`
- `status_code`
- `duration_ms`
- `component` (when helpful)

Examples:

```python
logger.info(
    "user_created",
    extra={"user_id": user.id, "operation": "create_user"},
)

logger.warning(
    "auth_denied",
    extra={"user_id": user_id, "operation": "delete_user"},
)

try:
    await repo.save(obj)
except Exception:
    logger.exception(
        "db_write_failed",
        extra={"resource_id": obj.id, "operation": "save_object"},
    )
    raise
```

## Where to add logs in generated FastAPI code

- **Routers (HTTP layer)**:
  - Log key domain events (create/update/delete) at **INFO**.
  - Log authorization/validation denials at **WARNING** (do not log secrets).
  - Include identifiers in `extra` (IDs, operation name, request_id if available).

- **Middleware**:
  - Add a request summary log (start/end) including `method`, `path`, `status_code`, `duration_ms`, and `request_id`.

- **Global exception handler**:
  - Use `logger.exception("unhandled_exception", extra={"request_id": request_id, ...})`.
  - Return a generic error message to clients; include `request_id` in the response body so support can correlate.
  - Do not leak internal exception details in production responses.

- **Service / DB layer**:
  - Log failures with `logger.exception(...)` and include entity IDs / operation names.
  - Avoid logging full payloads unless explicitly required; prefer IDs and counts.

## Security rules (MUST NOT)

- Never log passwords, access/refresh tokens, API keys, or the raw `Authorization` header.
- Avoid PII unless explicitly required; prefer stable identifiers (e.g., `user_id`).
- If you must log a user-provided string, consider logging only length or a redacted form.

## Notes about the template logger

- `AppLogger` configures handlers/formatting centrally. Generated code should only **use** the logger it provides.
- If you see duplicate log lines in an app, it’s usually due to handlers being added multiple times elsewhere. The fix is to keep handler setup centralized in `AppLogger` and avoid adding handlers outside it.
# >>Logging (Structured) and Request IDs

## Goals

- Emit **structured**, parseable logs (ideally JSON) with consistent fields.
- Include a **request/correlation ID** on every request, log line, and error response.
- Avoid common production pitfalls: duplicate handlers, noisy access logs, leaking secrets.

This reference complements `references/production-checklist.md` (global exception handler + request_id).

## Baseline: stdlib `logging` with consistent fields

If you don’t want extra dependencies, standard library logging is fine. Prefer a format that’s easy for log shippers to parse.

```python
import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format=(
        '%(asctime)s %(levelname)s %(name)s '
        'request_id=%(request_id)s '
        'msg="%(message)s"'
    ),
)

logger = logging.getLogger("app")
```

### Passing structured fields with `extra`

Use `extra={...}` to attach fields. This is especially useful in exception paths.

```python
logger.info("user_created", extra={"request_id": request_id, "user_id": user.id})
logger.exception("db_error", extra={"request_id": request_id})
```

To avoid `KeyError` when `request_id` is missing from `extra`, add a filter (shown below) that always injects it.

## Request ID middleware (header in, header out)

Use a middleware that:

- Accepts `X-Request-Id` if present (from an upstream gateway).
- Generates a new ID if missing.
- Stores it on `request.state.request_id`.
- Returns it in the response header (and optionally in JSON error bodies).

```python
from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
```

Register it early (typically right after app creation) so all routes and exception handlers can use it.

## Context propagation with `contextvars` (recommended)

Middleware-only access to `request.state` is inconvenient in deeper layers (services/repos). Use a `contextvar` so any code can read the current request ID without threading it through every function signature.

```python
from __future__ import annotations

import contextvars
from typing import Optional

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)

def get_request_id() -> str:
    return request_id_ctx.get() or ""
```

Set/reset the contextvar in your middleware:

```python
token = request_id_ctx.set(request_id)
try:
    response = await call_next(request)
finally:
    request_id_ctx.reset(token)
```

## Always include `request_id` in log records

Add a filter that injects `request_id` onto every `LogRecord` so your formatter can always refer to `%(request_id)s`.

```python
import logging

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True

root = logging.getLogger()
root.addFilter(RequestIdFilter())
```

If you configure multiple loggers/handlers, prefer adding the filter to the handler(s) you control instead of the root logger.

## Uvicorn / Gunicorn notes

- **Avoid duplicate handlers**: if you call `logging.basicConfig()` and also supply Uvicorn’s `--log-config`, you can end up with duplicates. Pick one approach.\n- **Access logs**: Uvicorn access logs are useful, but often too noisy. Consider disabling them (`--access-log false`) or routing them to a separate handler.\n- **Log level**: drive log level via env (`LOG_LEVEL`) and keep defaults sane (`INFO` in prod, `DEBUG` locally).\n

## Exception logging and error responses

In production:

- Log the full exception server-side with `logger.exception(...)`.
- Return a generic error message to clients (don’t leak internal details).
- Include `request_id` in the JSON error body so support can correlate.

This aligns with the guidance in `references/production-checklist.md`’s global exception handler example.

## Optional: `structlog` (when already in the stack)

If the project already uses `structlog`, prefer JSON rendering and make `request_id` a first-class field.

```python
import structlog

log = structlog.get_logger()

log.info("user_created", request_id=get_request_id(), user_id=user.id)
log.exception("unhandled_exception", request_id=get_request_id())
```

Don’t introduce `structlog` just for this skill unless the project already wants it; stdlib logging is sufficient.

## Quick reference


| Concern             | Recommendation                                                          |
| ------------------- | ----------------------------------------------------------------------- |
| Correlation header  | `X-Request-Id` (accept if present, always return)                       |
| Where to store      | `request.state.request_id` + `contextvars` for deeper layers            |
| Formatter           | JSON if possible; otherwise key-value fields like `request_id=...`      |
| Exceptions          | `logger.exception(...)` + generic client message + include `request_id` |
| Secrets             | Never log tokens/passwords; redact auth headers and PII                 |
| Uvicorn access logs | Disable or separate handler when too noisy                              |


