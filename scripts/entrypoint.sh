#!/bin/bash
set -e

# Worker (Railway cron) pasa su comando como argumento: ejecutarlo y salir.
# El API corre sin argumentos y sigue el flujo de abajo (migraciones + uvicorn).
if [ $# -gt 0 ]; then
  exec "$@"
fi

echo "=== Running database migrations ==="
python -m alembic upgrade head

echo "=== Starting uvicorn ==="
exec uvicorn backend.app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${UVICORN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips '*'
