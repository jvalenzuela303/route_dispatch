#!/usr/bin/env bash
# =============================================================================
# start.sh — Script de arranque del sistema Route Dispatch
# =============================================================================
set -euo pipefail

# ── Colores ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Directorio raíz del proyecto ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Modo de arranque (por defecto: docker) ────────────────────────────────────
MODE="${1:-docker}"   # opciones: docker | dev | infra

# ── Funciones de log ──────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}${BLUE}==> $*${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
banner() {
  echo -e "${BOLD}${BLUE}"
  echo "  ┌─────────────────────────────────────────┐"
  echo "  │        Route Dispatch — Start System     │"
  echo "  │   Backend: FastAPI  |  Frontend: Vue 3   │"
  echo "  └─────────────────────────────────────────┘"
  echo -e "${NC}"
  echo -e "  Modo: ${BOLD}${MODE}${NC}  |  Directorio: ${SCRIPT_DIR}\n"
}

# ── Verificar dependencias ────────────────────────────────────────────────────
check_deps() {
  header "Verificando dependencias"
  local missing=0

  for cmd in docker docker-compose curl; do
    if command -v "$cmd" &>/dev/null; then
      success "$cmd encontrado"
    else
      error "$cmd NO encontrado"
      missing=$((missing + 1))
    fi
  done

  if [[ "$MODE" == "dev" ]]; then
    for cmd in python3 node npm; do
      if command -v "$cmd" &>/dev/null; then
        success "$cmd encontrado"
      else
        warn "$cmd no encontrado (requerido para modo dev)"
      fi
    done
  fi

  [[ $missing -gt 0 ]] && { error "Instala las dependencias faltantes y reintenta."; exit 1; }
}

# ── Verificar .env ────────────────────────────────────────────────────────────
check_env() {
  header "Verificando archivo de entorno"
  if [[ ! -f ".env" ]]; then
    warn ".env no encontrado — creando desde .env.example si existe"
    if [[ -f ".env.example" ]]; then
      cp .env.example .env
      success ".env creado desde .env.example"
    else
      warn "Usando variables de entorno por defecto del docker-compose.yml"
    fi
  else
    success ".env encontrado"
  fi
}

# ── Modo: solo infraestructura (postgres + redis) ─────────────────────────────
start_infra() {
  header "Levantando infraestructura (PostgreSQL + Redis)"
  docker-compose up -d postgres redis
  info "Esperando que la base de datos esté lista..."
  local retries=0
  until docker-compose exec -T postgres pg_isready -U "${POSTGRES_USER:-claude_user}" &>/dev/null; do
    retries=$((retries + 1))
    [[ $retries -ge 20 ]] && { error "PostgreSQL no respondió a tiempo."; exit 1; }
    sleep 2
  done
  success "PostgreSQL listo"

  until docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
    retries=$((retries + 1))
    [[ $retries -ge 20 ]] && { error "Redis no respondió a tiempo."; exit 1; }
    sleep 2
  done
  success "Redis listo"
}

# ── Modo: Docker completo ─────────────────────────────────────────────────────
start_docker() {
  header "Construyendo y levantando todos los servicios (Docker)"
  docker-compose up -d --build
  echo ""
  info "Esperando que los servicios respondan..."
  sleep 5

  local retries=0
  until curl -sf http://localhost:8000/health &>/dev/null; do
    retries=$((retries + 1))
    [[ $retries -ge 15 ]] && { warn "API aún no responde — revisa: docker-compose logs app"; break; }
    sleep 3
  done

  echo ""
  success "Sistema levantado"
  echo -e "\n${BOLD}URLs disponibles:${NC}"
  echo -e "  ${GREEN}API Backend${NC}   →  http://localhost:8000"
  echo -e "  ${GREEN}API Docs${NC}      →  http://localhost:8000/docs"
  echo -e "  ${GREEN}Frontend${NC}      →  http://localhost:3000"
  echo -e "  ${GREEN}Health check${NC}  →  http://localhost:8000/health"
}

# ── Modo: desarrollo local (sin contenedor app/frontend) ─────────────────────
start_dev() {
  header "Modo desarrollo — infraestructura en Docker, app local"

  # Infraestructura
  start_infra

  # Backend
  header "Iniciando backend (uvicorn)"
  if [[ ! -d "venv" ]]; then
    info "Creando entorno virtual..."
    python3 -m venv venv
  fi
  source venv/bin/activate
  pip install -q -r requirements.txt
  info "Ejecutando migraciones..."
  alembic upgrade head 2>/dev/null || warn "Migraciones omitidas (alembic no disponible o sin cambios)"

  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
  BACKEND_PID=$!
  info "Backend PID: $BACKEND_PID"

  # Frontend
  header "Iniciando frontend (Vite dev server)"
  pushd frontend > /dev/null
  npm install --silent
  npm run dev &
  FRONTEND_PID=$!
  info "Frontend PID: $FRONTEND_PID"
  popd > /dev/null

  # Guardar PIDs para stop.sh
  echo "$BACKEND_PID"  > /tmp/route_dispatch_backend.pid
  echo "$FRONTEND_PID" > /tmp/route_dispatch_frontend.pid

  echo ""
  success "Servicios de desarrollo en ejecución"
  echo -e "\n${BOLD}URLs disponibles:${NC}"
  echo -e "  ${GREEN}API Backend${NC}   →  http://localhost:8000"
  echo -e "  ${GREEN}API Docs${NC}      →  http://localhost:8000/docs"
  echo -e "  ${GREEN}Frontend${NC}      →  http://localhost:5173"
  echo ""
  info "Presiona Ctrl+C para detener todos los servicios"

  # Esperar y limpiar al salir
  trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; info "Servicios detenidos."' INT TERM
  wait
}

# ── Estado del sistema ────────────────────────────────────────────────────────
show_status() {
  header "Estado de los contenedores"
  docker-compose ps
}

# ── Uso ───────────────────────────────────────────────────────────────────────
usage() {
  echo -e "${BOLD}Uso:${NC} $0 [modo]"
  echo ""
  echo -e "  ${CYAN}docker${NC}  (default)  Levanta todos los servicios con Docker Compose"
  echo -e "  ${CYAN}dev${NC}               Infraestructura en Docker, backend/frontend en local"
  echo -e "  ${CYAN}infra${NC}             Solo PostgreSQL y Redis"
  echo -e "  ${CYAN}status${NC}            Muestra el estado de los contenedores"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
banner

case "$MODE" in
  docker)
    check_deps
    check_env
    start_docker
    show_status
    ;;
  dev)
    check_deps
    check_env
    start_dev
    ;;
  infra)
    check_deps
    check_env
    start_infra
    show_status
    ;;
  status)
    show_status
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    error "Modo desconocido: '$MODE'"
    usage
    exit 1
    ;;
esac
