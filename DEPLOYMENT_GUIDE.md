# Guía de Despliegue - Claude Logistics API

Esta guía te llevará paso a paso desde cero hasta tener el sistema completamente funcional.

## Estado del Proyecto: FASE 0 COMPLETADA

Todos los archivos de infraestructura y configuración han sido creados exitosamente.

## Checklist de Verificación

### Archivos Creados

- [x] docker-compose.yml - Configuración de servicios (PostgreSQL, Redis, App)
- [x] Dockerfile - Imagen de la aplicación FastAPI
- [x] requirements.txt - Dependencias de Python
- [x] .env - Variables de entorno
- [x] .env.example - Plantilla de variables de entorno
- [x] .env.template - Template para nuevos entornos
- [x] .gitignore - Archivos a ignorar en Git
- [x] alembic.ini - Configuración de migraciones
- [x] README.md - Documentación principal
- [x] app/main.py - Aplicación FastAPI principal
- [x] app/config/settings.py - Configuración de la aplicación
- [x] app/api/health.py - Endpoint de health check
- [x] migrations/env.py - Configuración de Alembic
- [x] tests/conftest.py - Configuración de pytest
- [x] scripts/install_docker.sh - Script de instalación de Docker
- [x] scripts/validate_setup.sh - Script de validación de setup

### Estructura de Directorios

```
route_dispatch/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── health.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   ├── __init__.py
│   └── main.py
├── migrations/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── scripts/
│   ├── install_docker.sh
│   └── validate_setup.sh
├── tests/
│   ├── __init__.py
│   └── conftest.py
├── .env
├── .env.example
├── .env.template
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── README.md
├── DOCKER_SETUP.md
└── requirements.txt
```

## Pasos para Desplegar

### Paso 1: Verificar que tienes Git y el repositorio

```bash
cd /home/juan/Desarrollo/route_dispatch
git status
```

### Paso 2: Instalar Docker (si no está instalado)

#### Opción A: Instalación Automática

```bash
./scripts/install_docker.sh
```

#### Opción B: Instalación Manual

Sigue las instrucciones en `DOCKER_SETUP.md`.

**IMPORTANTE**: Después de instalar Docker, debes cerrar sesión y volver a iniciar sesión para que los cambios de grupo surtan efecto.

### Paso 3: Validar la Configuración

Después de instalar Docker y reiniciar sesión:

```bash
./scripts/validate_setup.sh
```

Este script verificará:
- Docker instalado y funcionando
- Docker Compose disponible
- Archivo .env configurado
- Estructura de directorios completa
- Archivos principales presentes

### Paso 4: Levantar los Servicios

```bash
# Construir y levantar todos los servicios
docker compose up -d --build
```

Este comando:
- Construye la imagen de la aplicación FastAPI
- Descarga las imágenes de PostgreSQL + PostGIS y Redis
- Crea la red bridge para comunicación entre servicios
- Levanta los tres servicios en segundo plano

### Paso 5: Verificar el Estado de los Servicios

```bash
# Ver el estado de los contenedores
docker compose ps
```

Deberías ver 3 servicios corriendo:
- claude_logistics_db (PostgreSQL + PostGIS)
- claude_logistics_redis (Redis)
- claude_logistics_app (FastAPI)

### Paso 6: Ver los Logs

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs solo de la aplicación
docker compose logs -f app

# Ver logs solo de la base de datos
docker compose logs -f postgres
```

### Paso 7: Probar el Health Endpoint

```bash
# Usando curl
curl http://localhost:8000/health

# O usando HTTPie (si está instalado)
http GET http://localhost:8000/health

# O abre en el navegador
# http://localhost:8000/health
```

Deberías recibir una respuesta como:

```json
{
  "status": "healthy",
  "service": "claude-logistics",
  "database": "connected",
  "redis": "connected"
}
```

### Paso 8: Acceder a la Documentación de la API

Abre en tu navegador:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Root endpoint**: http://localhost:8000/

## Verificación de Criterios de Éxito

### Checklist de Funcionamiento

- [ ] `docker compose up` ejecuta sin errores
- [ ] PostgreSQL + PostGIS accesible en localhost:5432
- [ ] Redis accesible en localhost:6379
- [ ] FastAPI ejecutándose en localhost:8000
- [ ] GET /health retorna status 200
- [ ] Database status = "connected"
- [ ] Redis status = "connected"
- [ ] Documentación Swagger accesible en /docs

### Comandos de Verificación Rápida

```bash
# 1. Verificar que todos los servicios están UP
docker compose ps

# 2. Verificar conectividad a PostgreSQL
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT version();"

# 3. Verificar conectividad a Redis
docker compose exec redis redis-cli ping

# 4. Verificar la aplicación
curl http://localhost:8000/health
```

## Gestión de Servicios

### Comandos Útiles

```bash
# Iniciar servicios
docker compose up -d

# Detener servicios
docker compose down

# Reiniciar servicios
docker compose restart

# Ver logs en tiempo real
docker compose logs -f

# Reconstruir la imagen de la app
docker compose build app

# Reiniciar solo la app
docker compose restart app

# Entrar al contenedor de la app
docker compose exec app bash

# Entrar a PostgreSQL
docker compose exec postgres psql -U claude_user -d claude_logistics

# Ejecutar migraciones de Alembic
docker compose exec app alembic upgrade head
```

### Detener y Limpiar

```bash
# Detener todos los servicios
docker compose down

# Detener y eliminar volúmenes (CUIDADO: elimina datos de BD)
docker compose down -v

# Limpiar todo (contenedores, volúmenes, imágenes)
docker compose down -v --rmi all
```

## Siguientes Pasos

Una vez que FASE 0 esté funcionando correctamente, los próximos pasos son:

### FASE 1: Modelos de Datos
1. Crear modelos SQLAlchemy para entidades
2. Crear esquemas Pydantic para validación
3. Generar migraciones con Alembic
4. Implementar CRUD básico

### FASE 2: Lógica de Negocio
1. Servicios de optimización de rutas
2. Integración con APIs de geocodificación
3. Algoritmos de routing

### FASE 3: Autenticación y Seguridad
1. Implementar JWT authentication
2. Sistema de usuarios y roles
3. Middleware de seguridad

## Solución de Problemas

### Docker no está instalado

```bash
./scripts/install_docker.sh
# Luego cierra sesión y vuelve a iniciar
```

### Error: permission denied while trying to connect to Docker

```bash
# Agregar tu usuario al grupo docker
sudo usermod -aG docker $USER

# Luego cierra sesión y vuelve a iniciar
# O temporalmente:
newgrp docker
```

### Puerto 8000 ya en uso

Edita `docker-compose.yml` y cambia el puerto:

```yaml
app:
  ports:
    - "8001:8000"  # Cambia 8000 por otro puerto
```

### Base de datos no se conecta

```bash
# Verificar logs de PostgreSQL
docker compose logs postgres

# Verificar que el servicio está healthy
docker compose ps

# Verificar variables de entorno
docker compose exec app env | grep DATABASE
```

### Redis no se conecta

```bash
# Verificar logs de Redis
docker compose logs redis

# Verificar conectividad
docker compose exec redis redis-cli ping
```

## Contacto y Soporte

Para problemas o preguntas sobre el deployment, consulta:
- README.md - Documentación principal
- DOCKER_SETUP.md - Guía de instalación de Docker
- Logs de los servicios con `docker compose logs`

## Referencias

- [Documentación de Docker](https://docs.docker.com/)
- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Documentación de PostgreSQL](https://www.postgresql.org/docs/)
- [Documentación de PostGIS](https://postgis.net/documentation/)
- [Documentación de Alembic](https://alembic.sqlalchemy.org/)
