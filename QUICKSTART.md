# QUICKSTART - Claude Logistics API

Guía de inicio rápido para poner el sistema en funcionamiento en 5 minutos.

## FASE 0: COMPLETADA

Todos los archivos de infraestructura han sido creados exitosamente.

## Inicio Rápido (3 pasos)

### 1. Instalar Docker (si no está instalado)

```bash
./scripts/install_docker.sh
```

Cierra sesión y vuelve a iniciar sesión después de la instalación.

### 2. Validar la configuración

```bash
./scripts/validate_setup.sh
```

### 3. Levantar los servicios

```bash
docker compose up -d --build
```

## Verificación

Espera unos 30 segundos y luego verifica:

```bash
# Ver estado de los servicios
docker compose ps

# Probar el health endpoint
curl http://localhost:8000/health
```

Deberías recibir:

```json
{
  "status": "healthy",
  "service": "claude-logistics",
  "database": "connected",
  "redis": "connected"
}
```

## Acceder a la Documentación

Abre en tu navegador:

- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)
- http://localhost:8000/ (API Info)

## Servicios Levantados

1. **FastAPI Application** - http://localhost:8000
   - Framework: Python 3.11 + FastAPI
   - Endpoints: /, /health, /docs, /redoc

2. **PostgreSQL + PostGIS** - localhost:5432
   - Database: claude_logistics
   - User: claude_user
   - Password: claude_pass

3. **Redis** - localhost:6379
   - Database: 0
   - Cache para optimización

## Comandos Útiles

```bash
# Ver logs en tiempo real
docker compose logs -f

# Detener servicios
docker compose down

# Reiniciar servicios
docker compose restart

# Acceder a la base de datos
docker compose exec postgres psql -U claude_user -d claude_logistics

# Acceder al contenedor de la app
docker compose exec app bash

# Ver logs de un servicio específico
docker compose logs -f app
docker compose logs -f postgres
docker compose logs -f redis
```

## Estructura de Archivos Creados

```
route_dispatch/
├── app/                        # Código de la aplicación
│   ├── api/                    # Endpoints REST
│   │   ├── health.py          # Health check endpoint
│   │   └── __init__.py
│   ├── config/                 # Configuración
│   │   ├── settings.py        # Variables de entorno
│   │   └── __init__.py
│   ├── models/                 # Modelos SQLAlchemy (vacío - FASE 1)
│   ├── schemas/                # Esquemas Pydantic (vacío - FASE 1)
│   ├── services/               # Lógica de negocio (vacío - FASE 1)
│   ├── utils/                  # Utilidades (vacío - FASE 1)
│   └── main.py                 # Entrada principal de FastAPI
│
├── migrations/                 # Migraciones de base de datos
│   ├── versions/               # Versiones de migraciones
│   ├── env.py                 # Configuración de Alembic
│   └── script.py.mako         # Template de migración
│
├── scripts/                    # Scripts de automatización
│   ├── install_docker.sh      # Instalador de Docker
│   └── validate_setup.sh      # Validador de configuración
│
├── tests/                      # Tests (vacío - futuras fases)
│   ├── conftest.py            # Configuración de pytest
│   └── __init__.py
│
├── .env                        # Variables de entorno (local)
├── .env.example                # Ejemplo de configuración
├── .env.template               # Plantilla de configuración
├── .gitignore                  # Archivos ignorados por Git
├── alembic.ini                 # Configuración de Alembic
├── docker-compose.yml          # Configuración de Docker Compose
├── Dockerfile                  # Imagen de la aplicación
├── requirements.txt            # Dependencias de Python
│
└── Documentación
    ├── README.md               # Documentación principal
    ├── DEPLOYMENT_GUIDE.md     # Guía de despliegue
    ├── DOCKER_SETUP.md         # Guía de instalación de Docker
    └── QUICKSTART.md           # Esta guía
```

## Archivos de Configuración Principales

### docker-compose.yml
Orquesta 3 servicios:
- PostgreSQL 14 + PostGIS 3.3
- Redis 7 Alpine
- FastAPI App (Python 3.11)

### Dockerfile
Multi-stage build para optimizar imagen:
- Base: Python 3.11 slim
- Dependencias del sistema (gcc, postgresql-client, libpq-dev)
- Dependencias de Python
- Health check incluido

### requirements.txt
Dependencias principales:
- fastapi==0.104.1
- uvicorn[standard]==0.24.0
- sqlalchemy==2.0.23
- alembic==1.12.1
- psycopg2-binary==2.9.9
- geoalchemy2==0.14.2
- redis==5.0.1
- pydantic==2.5.0
- pydantic-settings==2.1.0

### app/main.py
Aplicación FastAPI principal con:
- CORS middleware
- Exception handlers
- Root endpoint
- Health router incluido
- Startup/shutdown events

### app/api/health.py
Endpoint de health check que verifica:
- Estado de la API
- Conexión a PostgreSQL
- Conexión a Redis

### app/config/settings.py
Configuración usando Pydantic Settings:
- DATABASE_URL
- REDIS_URL
- SECRET_KEY
- DEBUG mode
- CORS_ORIGINS

## Próximos Pasos (FASE 1)

Una vez que FASE 0 esté funcionando:

1. Crear modelos SQLAlchemy para entidades principales
2. Crear esquemas Pydantic para validación de datos
3. Generar migraciones iniciales con Alembic
4. Implementar CRUD básico para entidades

## Solución de Problemas Rápida

### Docker no está instalado
```bash
./scripts/install_docker.sh
# Luego cierra sesión y vuelve a iniciar
```

### Error de permisos con Docker
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Puerto 8000 ya en uso
Edita `docker-compose.yml` y cambia el puerto en la sección `app`:
```yaml
ports:
  - "8001:8000"
```

### Servicios no levantan
```bash
# Ver logs de todos los servicios
docker compose logs

# Ver logs de un servicio específico
docker compose logs postgres
docker compose logs redis
docker compose logs app
```

## Documentación Completa

Para información más detallada, consulta:

- **README.md** - Documentación principal del proyecto
- **DEPLOYMENT_GUIDE.md** - Guía completa de despliegue
- **DOCKER_SETUP.md** - Instalación detallada de Docker

## Stack Tecnológico

- **Backend**: Python 3.11 + FastAPI
- **Base de Datos**: PostgreSQL 14 + PostGIS 3.3
- **Caché**: Redis 7
- **ORM**: SQLAlchemy 2.0 + GeoAlchemy2
- **Migraciones**: Alembic 1.12
- **Validación**: Pydantic 2.5
- **Servidor**: Uvicorn
- **Infraestructura**: Docker + Docker Compose

## Estado del Proyecto

FASE 0: INICIALIZACIÓN - COMPLETADA

- [x] Estructura de proyecto creada
- [x] Docker Compose configurado
- [x] Dockerfile multi-stage optimizado
- [x] FastAPI app funcionando
- [x] Health endpoint implementado
- [x] PostgreSQL + PostGIS configurado
- [x] Redis configurado
- [x] Alembic setup para migraciones
- [x] Configuración de entornos
- [x] Documentación completa

Listo para comenzar FASE 1: Implementación de Modelos de Datos.
