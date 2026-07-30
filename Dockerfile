# --- builder ---
FROM python:3.12-slim AS builder

ENV POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN poetry install --only main

# --- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic

COPY scripts ./scripts
COPY create_client.py ./create_client.py
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Create the audio upload directory and give it to the non-root runtime user.
# A fresh named volume mounted here inherits this ownership on first use, so the
# app (running as appuser) can write uploaded files.
RUN mkdir -p /app/uploads/audio && chown -R appuser:appuser /app/uploads

USER appuser

EXPOSE 8085

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8085/health')" || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]
