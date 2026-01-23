# Instalación de Docker en Fedora

Esta guía te ayudará a instalar Docker y Docker Compose en tu sistema Fedora Linux.

## Opción 1: Instalación Automática con Script

Hemos incluido un script de instalación automática:

```bash
./scripts/install_docker.sh
```

**IMPORTANTE**: Después de ejecutar el script, debes cerrar sesión y volver a iniciar para que los cambios de grupo surtan efecto.

## Opción 2: Instalación Manual

### Paso 1: Remover versiones antiguas (si existen)

```bash
sudo dnf remove -y docker \
    docker-client \
    docker-client-latest \
    docker-common \
    docker-latest \
    docker-latest-logrotate \
    docker-logrotate \
    docker-selinux \
    docker-engine-selinux \
    docker-engine
```

### Paso 2: Instalar repositorio de Docker

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
```

### Paso 3: Instalar Docker Engine

```bash
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Paso 4: Iniciar Docker

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Paso 5: Agregar tu usuario al grupo docker

Para usar Docker sin sudo:

```bash
sudo usermod -aG docker $USER
```

**IMPORTANTE**: Cierra sesión y vuelve a iniciar sesión para que este cambio surta efecto.

### Paso 6: Verificar la instalación

Después de reiniciar sesión:

```bash
# Verificar versión de Docker
docker --version

# Verificar versión de Docker Compose
docker compose version

# Probar Docker con un contenedor de prueba
docker run hello-world
```

## Verificación de la Instalación

Si todo está correcto, deberías ver:

```bash
$ docker --version
Docker version 24.0.x, build xxxxx

$ docker compose version
Docker Compose version v2.x.x
```

## Solución de Problemas

### Error: "permission denied while trying to connect to the Docker daemon socket"

Esto significa que no se aplicaron los cambios de grupo. Soluciones:

1. Cierra sesión completamente y vuelve a iniciar sesión
2. O ejecuta: `newgrp docker` (temporal para la sesión actual)
3. O ejecuta Docker con sudo temporalmente: `sudo docker ...`

### Error: "Cannot connect to the Docker daemon"

El servicio Docker no está corriendo:

```bash
sudo systemctl start docker
sudo systemctl status docker
```

### Docker Compose no funciona con docker-compose

En versiones modernas de Docker, usa `docker compose` (sin guión) en lugar de `docker-compose`:

```bash
# Antiguo (v1)
docker-compose up

# Nuevo (v2)
docker compose up
```

## Recursos Adicionales

- [Documentación oficial de Docker](https://docs.docker.com/engine/install/fedora/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
