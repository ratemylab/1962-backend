# Logging and Configuration

Production-ready applications use structured logging and load configuration from the environment with validation at startup.

## Configuration from Environment

- Load all configuration and secrets from environment variables (or a validated `.env`); validate at application startup so misconfiguration fails fast.
- Use a single entry point (e.g. a settings module or `pydantic-settings`) so the rest of the code imports config from one place.
- Never hardcode secrets; never log secrets or full config.

```python
# config.py or settings.py - validate at import/startup
import os

def get_required(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value

def get_optional(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

# Or use pydantic-settings for typed, validated settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    DATABASE_URL: str
    SECRET_KEY: str
    LOG_LEVEL: str = "INFO"

settings = Settings()  # Fails at startup if required vars missing
```

## Structured Logging

- Prefer structured fields (e.g. key-value or JSON) so log aggregators can filter and search.
- Include a request or correlation ID in log records when handling requests so traces can be followed across services.

```python
import logging
import json
from typing import Any

# Structured formatter (JSON or key=value)
class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        # Merge extra dict into log object
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj.update(record.extra)
        return json.dumps(log_obj)

logger = logging.getLogger(__name__)

def log_request(request_id: str, message: str, **kwargs: Any) -> None:
    logger.info(message, extra={"request_id": request_id, **kwargs})
```

## Correlation ID

- For request-scoped work, attach a correlation (request) ID early (e.g. from header or generate one) and pass it through the call chain; include it in every log line for that request.

```python
import uuid
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

def set_request_id(rid: str | None = None) -> str:
    rid = rid or str(uuid.uuid4())
    request_id_ctx.set(rid)
    return rid

def get_request_id() -> str:
    return request_id_ctx.get()

# In request handler
def handle_request():
    rid = set_request_id(request.headers.get("X-Request-ID"))
    logger.info("Request started", extra={"request_id": rid})
    # ... pass rid or use get_request_id() in callees
```

## Quick Reference

| Concern | Practice |
|--------|----------|
| Config | Load from env; validate at startup; single settings entry point |
| Secrets | Never hardcode; never log |
| Logging | Structured (JSON or key=value); include level, logger, message |
| Correlation | Request/correlation ID in logs for request-scoped flows |
