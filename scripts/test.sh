#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-unit}"
PHASE="${2:-}"

# PostgreSQL descartable para tests y E2E (scripts/test-db.sh, puerto 5434, sin volumen)
TEST_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test"

# La suite backend corre contra PostgreSQL — el mismo motor que producción, sin
# SQLite. Si el postgres-test no responde, se levanta solo: sin él no hay tests.
ensure_test_db() {
  if TEST_DB_URL="$TEST_DB_URL" ./.venv/bin/python - <<'PY' 2>/dev/null
import os, sys
from sqlalchemy import create_engine, text
try:
    engine = create_engine(os.environ["TEST_DB_URL"], connect_args={"connect_timeout": 2})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()
except Exception:
    sys.exit(1)
PY
  then
    return 0
  fi
  echo "postgres-test (5434) no responde; levantándolo..."
  ./scripts/test-db.sh up
}

run_backend_unit() {
  ensure_test_db
  ./.venv/bin/python -m pytest backend/tests -q
}

run_backend_checks() {
  ./.venv/bin/python -m ruff check backend
}

run_frontend_unit() {
  npm --prefix frontend run test -- --run
}

run_frontend_checks() {
  npm --prefix frontend run lint
}

# PostgreSQL descartable para E2E (scripts/test-db.sh, puerto 5434, sin volumen)
run_e2e() {
  # El trap garantiza que postgres-test se elimine aunque pytest falle.
  trap './scripts/test-db.sh down' EXIT
  ./scripts/test-db.sh reset
  DATABASE_URL="$TEST_DB_URL" ./.venv/bin/alembic upgrade head
  DATABASE_URL="$TEST_DB_URL" ./.venv/bin/python -m backend.scripts.seed_e2e
  DATABASE_URL="$TEST_DB_URL" ./.venv/bin/python -m pytest backend/tests/e2e -m e2e -q --tb=short
}

case "$TARGET" in
  unit)
    run_backend_unit
    run_frontend_unit
    ;;
  api|backend)
    run_backend_checks
    run_backend_unit
    ;;
  frontend)
    run_frontend_checks
    run_frontend_unit
    ;;
  e2e)
    run_e2e
    ;;
  scheduling)
    run_backend_unit
    ;;
  telegram)
    run_backend_unit
    ;;
  phase)
    case "$PHASE" in
      0|1|2)
        run_backend_checks
        run_backend_unit
        run_frontend_checks
        run_frontend_unit
        ;;
      *)
        echo "Phase test target '$PHASE' is not implemented yet."
        exit 1
        ;;
    esac
    ;;
  all)
    run_backend_checks
    run_backend_unit
    run_frontend_checks
    run_frontend_unit
    ;;
  *)
    echo "Unknown test target: $TARGET"
    echo "Usage: ./scripts/test.sh {unit|api|backend|frontend|e2e|scheduling|telegram|phase <number>|all}"
    exit 1
    ;;
esac
