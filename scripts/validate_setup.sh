#!/bin/bash
# Script para validar que el proyecto está correctamente configurado

set -e

echo "=========================================="
echo "Validando configuración del proyecto..."
echo "=========================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Verificar Docker
echo "1. Verificando Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_status 0 "Docker instalado: $DOCKER_VERSION"
else
    print_status 1 "Docker NO está instalado"
    echo -e "${YELLOW}   → Ejecuta: ./scripts/install_docker.sh${NC}"
    echo -e "${YELLOW}   → O consulta: DOCKER_SETUP.md${NC}"
fi
echo ""

# Verificar Docker Compose
echo "2. Verificando Docker Compose..."
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version)
    print_status 0 "Docker Compose instalado: $COMPOSE_VERSION"
else
    print_status 1 "Docker Compose NO está disponible"
fi
echo ""

# Verificar archivo .env
echo "3. Verificando archivo de configuración..."
if [ -f ".env" ]; then
    print_status 0 "Archivo .env existe"
else
    print_status 1 "Archivo .env NO existe"
    echo -e "${YELLOW}   → Ejecuta: cp .env.example .env${NC}"
fi
echo ""

# Verificar estructura de directorios
echo "4. Verificando estructura de directorios..."
REQUIRED_DIRS=(
    "app/api"
    "app/config"
    "app/models"
    "app/schemas"
    "app/services"
    "app/utils"
    "migrations/versions"
    "tests"
)

all_dirs_ok=true
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_status 0 "Directorio $dir existe"
    else
        print_status 1 "Directorio $dir NO existe"
        all_dirs_ok=false
    fi
done
echo ""

# Verificar archivos principales
echo "5. Verificando archivos principales..."
REQUIRED_FILES=(
    "app/main.py"
    "app/config/settings.py"
    "app/api/health.py"
    "docker-compose.yml"
    "Dockerfile"
    "requirements.txt"
    "alembic.ini"
)

all_files_ok=true
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_status 0 "Archivo $file existe"
    else
        print_status 1 "Archivo $file NO existe"
        all_files_ok=false
    fi
done
echo ""

# Verificar que Docker daemon está corriendo
echo "6. Verificando Docker daemon..."
if docker info &> /dev/null; then
    print_status 0 "Docker daemon está corriendo"
else
    print_status 1 "Docker daemon NO está corriendo"
    echo -e "${YELLOW}   → Ejecuta: sudo systemctl start docker${NC}"
fi
echo ""

# Resumen
echo "=========================================="
echo "Resumen de Validación"
echo "=========================================="

if command -v docker &> /dev/null && docker compose version &> /dev/null && [ -f ".env" ] && $all_dirs_ok && $all_files_ok && docker info &> /dev/null; then
    echo -e "${GREEN}✓ Todo está configurado correctamente!${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "1. Levantar los servicios:"
    echo "   docker compose up -d --build"
    echo ""
    echo "2. Verificar el estado:"
    echo "   docker compose ps"
    echo ""
    echo "3. Ver los logs:"
    echo "   docker compose logs -f"
    echo ""
    echo "4. Probar el health endpoint:"
    echo "   curl http://localhost:8000/health"
    echo ""
else
    echo -e "${RED}✗ Hay problemas con la configuración${NC}"
    echo ""
    echo "Por favor, revisa los errores arriba y corrígelos."
    echo ""
    exit 1
fi
