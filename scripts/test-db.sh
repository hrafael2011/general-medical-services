#!/usr/bin/env bash
# Gestión del PostgreSQL descartable para tests E2E (puerto 5434, sin volumen).
#
# Uso: ./scripts/test-db.sh {up|down|reset}
#   up    — levanta postgres-test y espera a que pg_isready responda
#   down  — detiene y elimina el contenedor (los datos se pierden)
#   reset — down + up (base recién creada, vacía)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

wait_until_ready() {
  echo "Esperando a que postgres-test quede listo..."
  for _ in $(seq 1 30); do
    # psql valida la conexión y la existencia de la base (pg_isready no
    # comprueba el nombre de la DB y puede pasar durante el init del contenedor).
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T postgres-test \
        psql -U postgres -d medical_shifts_test -tAc "SELECT 1" 2>/dev/null | grep -q 1; then
      echo "postgres-test listo."
      return 0
    fi
    sleep 2
  done
  echo "ERROR: postgres-test no quedó listo en 60s." >&2
  return 1
}

start_test_db() {
  docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d postgres-test
  wait_until_ready
}

stop_test_db() {
  docker compose -f "$PROJECT_DIR/docker-compose.yml" rm -sf postgres-test >/dev/null 2>&1 || true
  echo "postgres-test eliminado."
}

case "${1:-}" in
  up)
    start_test_db
    ;;
  down)
    stop_test_db
    ;;
  reset)
    stop_test_db
    start_test_db
    ;;
  *)
    echo "Uso: $0 {up|down|reset}" >&2
    exit 1
    ;;
esac
