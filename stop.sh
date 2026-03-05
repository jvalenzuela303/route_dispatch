#!/usr/bin/env bash
# =============================================================================
# stop.sh — Script para detener el sistema Route Dispatch
# =============================================================================
set -euo pipefail

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-docker}"   # opciones: docker | dev | volumes

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}${BLUE}==> $*${NC}"; }

banner() {
  echo -e "${BOLD}${RED}"
  echo "  ┌─────────────────────────────────────────┐"
  echo "  │        Route Dispatch — Stop System      │"
  echo "  └─────────────────────────────────────────┘"
  echo -e "${NC}"
  echo -e "  Modo: ${BOLD}${MODE}${NC}\n"
}

# ── Detener servicios Docker ──────────────────────────────────────────────────
stop_docker() {
  header "Deteniendo contenedores"
  docker-compose stop
  success "Contenedores detenidos"
}

# ── Detener y eliminar contenedores (sin borrar volúmenes) ────────────────────
down_docker() {
  header "Bajando contenedores (datos preservados)"
  docker-compose down
  success "Contenedores eliminados — volúmenes intactos"
}

# ── Detener y eliminar todo, incluyendo volúmenes ────────────────────────────
down_volumes() {
  header "Bajando contenedores y eliminando volúmenes"
  warn "Esto eliminará TODOS los datos de PostgreSQL y Redis"
  read -rp "  ¿Confirmar? [s/N] " confirm
  if [[ "${confirm,,}" == "s" ]]; then
    docker-compose down -v
    success "Contenedores y volúmenes eliminados"
  else
    info "Operación cancelada"
    exit 0
  fi
}

# ── Detener procesos locales de modo dev ──────────────────────────────────────
stop_dev() {
  header "Deteniendo procesos de desarrollo local"

  for pidfile in /tmp/route_dispatch_backend.pid /tmp/route_dispatch_frontend.pid; do
    if [[ -f "$pidfile" ]]; then
      pid=$(cat "$pidfile")
      label=$(basename "$pidfile" .pid | sed 's/route_dispatch_//')
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" && success "Proceso $label (PID $pid) detenido"
      else
        warn "Proceso $label (PID $pid) ya no estaba en ejecución"
      fi
      rm -f "$pidfile"
    else
      warn "No se encontró PID para $(basename "$pidfile" .pid)"
    fi
  done

  # También bajar la infraestructura Docker
  header "Deteniendo infraestructura Docker"
  docker-compose stop postgres redis
  success "PostgreSQL y Redis detenidos"
}

# ── Estado final ──────────────────────────────────────────────────────────────
show_status() {
  echo ""
  header "Estado final"
  docker-compose ps 2>/dev/null || true
}

usage() {
  echo -e "${BOLD}Uso:${NC} $0 [modo]"
  echo ""
  echo -e "  ${CYAN}docker${NC}   (default)  Detiene los contenedores (datos preservados)"
  echo -e "  ${CYAN}down${NC}               Elimina los contenedores (datos preservados)"
  echo -e "  ${CYAN}volumes${NC}            Elimina contenedores Y volúmenes (borra datos)"
  echo -e "  ${CYAN}dev${NC}                Detiene procesos locales + infraestructura Docker"
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
banner

case "$MODE" in
  docker)
    stop_docker
    show_status
    ;;
  down)
    down_docker
    show_status
    ;;
  volumes)
    down_volumes
    show_status
    ;;
  dev)
    stop_dev
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
