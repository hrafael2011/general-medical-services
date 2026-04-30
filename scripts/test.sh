#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-unit}"
PHASE="${2:-}"

run_backend_unit() {
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
    echo "E2E suite is not implemented yet."
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
