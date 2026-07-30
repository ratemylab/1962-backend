#!/bin/sh
set -e

echo "Running database migrations..."
i=1
until alembic upgrade head; do
  if [ "$i" -ge 10 ]; then
    echo "Alembic migrate failed after ${i} attempts" >&2
    exit 1
  fi
  echo "Alembic migrate attempt ${i} failed; retrying in 2s..."
  i=$((i + 1))
  sleep 2
done
echo "Database migrations complete."

if [ "${SEED_CLIENTS_ENABLED:-true}" = "true" ]; then
  echo "Seeding API clients..."
  python scripts/seed_clients.py
fi

exec "$@"
