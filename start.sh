#!/usr/bin/env bash
# ===========================================================================
# start.sh — Arranca todos los servicios del Sistema de Turnos Médicos
#
# Uso:   ./start.sh
#        ./start.sh --build   (reconstruye frontend antes de arrancar)
#
# Detener: Ctrl+C  (detiene todos los servicios gracefulmente)
# ===========================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ── Colores ────────────────────────────────────────────────────────────────
RED='\033[0;31m';    GREEN='\033[0;32m';   YELLOW='\033[1;33m'
CYAN='\033[0;36m';   BOLD='\033[1m';       NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }

# ── Trap: limpieza al salir ───────────────────────────────────────────────
CLEANUP_PIDS=()
cleanup() {
  local exit_code=$?
  echo
  warn "Deteniendo servicios..."
  for pid in "${CLEANUP_PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  ok "Todos los servicios detenidos."
  exit "$exit_code"
}
trap cleanup SIGINT SIGTERM EXIT

# ── 1. Verificar prerequisitos ────────────────────────────────────────────
info "Verificando prerequisitos..."

PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  warn "Virtualenv no encontrado en .venv. Usando python del sistema..."
  PYTHON="python3"
fi

if ! command -v docker &>/dev/null; then
  fail "Docker no está instalado. Instálalo primero: https://docs.docker.com/engine/install/"
  exit 1
fi

if ! command -v node &>/dev/null; then
  fail "Node.js no está instalado."
  exit 1
fi

ok "Prerequisitos listos."

# ── 2. Arrancar PostgreSQL ─────────────────────────────────────────────────
info "Iniciando PostgreSQL (Docker Compose)..."
docker compose up -d --wait 2>&1 | sed 's/^/       /'
ok "PostgreSQL listo en localhost:5433"

# ── 3. Migraciones ────────────────────────────────────────────────────────
info "Ejecutando migraciones de base de datos..."
if "$PYTHON" -m alembic upgrade head 2>&1 | sed 's/^/       /'; then
  ok "Migraciones aplicadas."
else
  warn "Migraciones fallaron. ¿Ya están aplicadas?"
fi

# ── 4. Backend ─────────────────────────────────────────────────────────────
info "Iniciando backend (uvicorn)..."
"$PYTHON" -m uvicorn backend.app.main:app \
  --reload \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" &
BACKEND_PID=$!
CLEANUP_PIDS+=("$BACKEND_PID")
ok "Backend corriendo (PID $BACKEND_PID)"

# ── 5. Frontend ────────────────────────────────────────────────────────────
info "Iniciando frontend (Vite)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
CLEANUP_PIDS+=("$FRONTEND_PID")
cd "$ROOT_DIR"
ok "Frontend corriendo (PID $FRONTEND_PID)"

# ── 6. URLs ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}  🚀  Servicios activos${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}Backend:${NC}  http://localhost:${PORT:-8000}"
echo -e "  ${GREEN}API Docs:${NC} http://localhost:${PORT:-8000}/docs"
echo -e "  ${GREEN}Frontend:${NC} http://localhost:5173"
echo -e "  ${GREEN}DB:${NC}       postgresql://postgres:postgres@localhost:5433/medical_shifts"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${YELLOW}Pulsa Ctrl+C para detener todos los servicios${NC}"
echo ""

# ── Esperar ────────────────────────────────────────────────────────────────
wait
