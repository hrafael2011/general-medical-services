#!/bin/bash
set -e

echo "=== Running database migrations ==="
alembic upgrade head

echo "=== Starting uvicorn ==="
exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
