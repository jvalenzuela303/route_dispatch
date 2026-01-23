#!/bin/bash
# Script para instalar Docker y Docker Compose en Fedora/RHEL

set -e

echo "Instalando Docker en Fedora..."

# Remover versiones antiguas si existen
sudo dnf remove -y docker \
    docker-client \
    docker-client-latest \
    docker-common \
    docker-latest \
    docker-latest-logrotate \
    docker-logrotate \
    docker-selinux \
    docker-engine-selinux \
    docker-engine || true

# Instalar dnf-plugins-core
sudo dnf -y install dnf-plugins-core

# Agregar el repositorio oficial de Docker
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo

# Instalar Docker Engine, CLI y containerd
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Iniciar y habilitar Docker
sudo systemctl start docker
sudo systemctl enable docker

# Agregar el usuario actual al grupo docker (para usar docker sin sudo)
sudo usermod -aG docker $USER

echo ""
echo "=========================================="
echo "Docker instalado exitosamente!"
echo "=========================================="
echo ""
echo "IMPORTANTE: Debes cerrar sesión y volver a iniciar sesión"
echo "para que los cambios de grupo surtan efecto."
echo ""
echo "Después de reiniciar sesión, ejecuta:"
echo "  docker --version"
echo "  docker compose version"
echo ""
echo "Para verificar que Docker está funcionando correctamente:"
echo "  docker run hello-world"
echo ""
