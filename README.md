# Claude Logistics API

Sistema de gestión de logística y optimización de rutas para botillería en Rancagua, Chile.

## Descripción

Claude Logistics es una plataforma backend desarrollada para optimizar la gestión de entregas y rutas de distribución, utilizando capacidades de geolocalización y análisis espacial a través de PostgreSQL con PostGIS.

## Stack Tecnológico

### Backend
- **Python 3.11**: Lenguaje de programación principal
- **FastAPI**: Framework web moderno y de alto rendimiento
- **Uvicorn**: Servidor ASGI para Python

### Base de Datos
- **PostgreSQL 14**: Sistema de gestión de base de datos relacional
- **PostGIS 3.3**: Extensión geoespacial para PostgreSQL
- **SQLAlchemy 2.0**: ORM para Python
- **GeoAlchemy2**: Extensión de SQLAlchemy para tipos geoespaciales
- **Alembic**: Herramienta de migración de base de datos

### Caché y Mensajería
- **Redis 7**: Sistema de almacenamiento en memoria para caché

### Validación y Configuración
- **Pydantic**: Validación de datos usando anotaciones de tipo Python
- **Pydantic Settings**: Gestión de configuración basada en variables de entorno

### Infraestructura
- **Docker**: Containerización de aplicaciones
- **Docker Compose**: Orquestación de servicios multi-contenedor

## Estructura del Proyecto

```
route_dispatch/
├── app/
│   ├── api/                 # Endpoints de la API
│   │   ├── __init__.py
│   │   └── health.py        # Endpoint de health check
│   ├── config/              # Configuración de la aplicación
│   │   ├── __init__.py
│   │   └── settings.py      # Variables de entorno y configuración
│   ├── models/              # Modelos de SQLAlchemy (vacío - FASE 1)
│   │   └── __init__.py
│   ├── schemas/             # Esquemas de Pydantic (vacío - FASE 1)
│   │   └── __init__.py
│   ├── services/            # Lógica de negocio (vacío - FASE 1)
│   │   └── __init__.py
│   ├── utils/               # Funciones utilitarias (vacío - FASE 1)
│   │   └── __init__.py
│   ├── __init__.py
│   └── main.py              # Punto de entrada de la aplicación FastAPI
├── migrations/              # Migraciones de Alembic
│   ├── versions/            # Directorio de versiones de migración
│   ├── env.py              # Configuración del entorno de Alembic
│   └── script.py.mako      # Template para nuevas migraciones
├── tests/                   # Tests (vacío - futuras fases)
│   └── __init__.py
├── .env                     # Variables de entorno (no versionado)
├── .env.example             # Ejemplo de variables de entorno
├── .env.template            # Template de variables de entorno
├── .gitignore              # Archivos ignorados por Git
├── alembic.ini             # Configuración de Alembic
├── docker-compose.yml      # Configuración de Docker Compose
├── Dockerfile              # Configuración de Docker para la app
├── requirements.txt        # Dependencias de Python
└── README.md              # Este archivo
```

## Prerequisitos

Antes de comenzar, asegúrate de tener instalado:

- **Docker** (versión 20.10 o superior)
- **Docker Compose** (versión 2.0 o superior)
- **Git** (para clonar el repositorio)

## Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd route_dispatch
```

### 2. Configurar Variables de Entorno

Copia el archivo de ejemplo y ajusta los valores según sea necesario:

```bash
cp .env.example .env
```

El archivo `.env` contiene:

```env
# Database Configuration
DATABASE_URL=postgresql://claude_user:claude_pass@postgres:5432/claude_logistics
POSTGRES_USER=claude_user
POSTGRES_PASSWORD=claude_pass
POSTGRES_DB=claude_logistics

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=dev-secret-key-change-in-production

# Application Settings
DEBUG=true

# CORS Origins
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

**IMPORTANTE**: En producción, cambia `SECRET_KEY` por una clave segura y establece `DEBUG=false`.

### 3. Levantar los Servicios

Ejecuta Docker Compose para construir y levantar todos los servicios:

```bash
docker-compose up --build
```

Para ejecutar en segundo plano:

```bash
docker-compose up -d --build
```

### 4. Verificar el Estado del Sistema

Una vez que los servicios estén corriendo, verifica el estado:

```bash
curl http://localhost:8000/health
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

## Uso

### Acceder a la Documentación de la API

FastAPI genera automáticamente documentación interactiva:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Endpoints Disponibles

#### GET /
Información básica de la API

```bash
curl http://localhost:8000/
```

#### GET /health
Health check del sistema y sus dependencias

```bash
curl http://localhost:8000/health
```

### Comandos Docker Compose Útiles

```bash
# Ver logs de todos los servicios
docker-compose logs -f

# Ver logs de un servicio específico
docker-compose logs -f app

# Detener todos los servicios
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: elimina datos de la BD)
docker-compose down -v

# Reconstruir la imagen de la aplicación
docker-compose build app

# Acceder al contenedor de la aplicación
docker-compose exec app bash

# Acceder a PostgreSQL
docker-compose exec postgres psql -U claude_user -d claude_logistics
```

### Gestión de Migraciones con Alembic

#### Crear una nueva migración

```bash
# Dentro del contenedor de la app
docker-compose exec app alembic revision -m "descripción de la migración"
```

#### Aplicar migraciones

```bash
docker-compose exec app alembic upgrade head
```

#### Revertir migraciones

```bash
docker-compose exec app alembic downgrade -1
```

#### Ver historial de migraciones

```bash
docker-compose exec app alembic history
```

## Desarrollo

### Configuración del Entorno de Desarrollo Local

Si prefieres desarrollar sin Docker:

1. Crear un entorno virtual:

```bash
python3.11 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Asegúrate de que PostgreSQL y Redis estén corriendo localmente o ajusta las URLs en `.env`:

```env
DATABASE_URL=postgresql://claude_user:claude_pass@localhost:5432/claude_logistics
REDIS_URL=redis://localhost:6379/0
```

4. Ejecutar la aplicación:

```bash
uvicorn app.main:app --reload
```

### Hot Reload

El contenedor de Docker está configurado con volúmenes montados, por lo que los cambios en el código se reflejarán automáticamente sin necesidad de reconstruir la imagen.

## Arquitectura

### Servicios Docker

1. **postgres**: Base de datos PostgreSQL con extensión PostGIS
   - Puerto: 5432
   - Volumen persistente: `postgres_data`
   - Health check automático

2. **redis**: Caché en memoria
   - Puerto: 6379
   - Volumen persistente: `redis_data`
   - Health check automático

3. **app**: Aplicación FastAPI
   - Puerto: 8000
   - Depende de postgres y redis
   - Hot reload habilitado en desarrollo

### Flujo de Conexiones

```
Cliente → FastAPI (puerto 8000)
           ↓
           ├─→ PostgreSQL + PostGIS (puerto 5432)
           └─→ Redis (puerto 6379)
```

## Seguridad

### Variables de Entorno Sensibles

- Nunca commits el archivo `.env` al repositorio
- Usa `.env.template` como referencia para nuevos desarrolladores
- En producción, utiliza sistemas de gestión de secretos (AWS Secrets Manager, HashiCorp Vault, etc.)

### CORS

La configuración de CORS está establecida en `app/config/settings.py`. Ajusta `CORS_ORIGINS` según tus necesidades:

```python
CORS_ORIGINS=http://localhost:3000,https://tu-dominio.com
```

## Testing

Los tests se agregarán en fases posteriores. El directorio `tests/` está preparado con `conftest.py` para configuración de pytest.

## Roadmap

### FASE 0 (Actual): Inicialización y Fundación
- [x] Configuración de Docker Compose
- [x] Setup de PostgreSQL + PostGIS
- [x] Configuración de Redis
- [x] Estructura base de FastAPI
- [x] Endpoint de health check
- [x] Setup de Alembic para migraciones

### FASE 1 (Próxima): Modelos de Datos
- [ ] Modelos SQLAlchemy para entidades principales
- [ ] Esquemas Pydantic para validación
- [ ] Migraciones iniciales de base de datos
- [ ] CRUD básico para entidades

### FASE 2: Lógica de Negocio
- [ ] Servicios de optimización de rutas
- [ ] Integración con APIs externas
- [ ] Implementación de algoritmos de routing

### FASE 3: Autenticación y Autorización
- [ ] Sistema de autenticación JWT
- [ ] Gestión de usuarios y roles
- [ ] Middleware de seguridad

## Solución de Problemas

### El contenedor de la app no inicia

Verifica los logs:

```bash
docker-compose logs app
```

Asegúrate de que postgres y redis estén saludables:

```bash
docker-compose ps
```

### Error de conexión a la base de datos

Verifica que el servicio de postgres esté corriendo y saludable:

```bash
docker-compose exec postgres pg_isready -U claude_user
```

### Puerto 8000 ya en uso

Cambia el puerto en `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Usa puerto 8001 en el host
```

## Contribución

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/amazing-feature`)
3. Commit tus cambios (`git commit -m 'Add some amazing feature'`)
4. Push a la rama (`git push origin feature/amazing-feature`)
5. Abre un Pull Request

## Licencia

[Especificar licencia]

## Contacto

[Información de contacto del equipo]

## Agradecimientos

Este proyecto utiliza Claude AI para asistencia en desarrollo y optimización de código.

---

## FASE 7 - Capa API y Orquestación de Workflows ✅

**Estado: COMPLETADO**
**Fecha: 22 de Enero, 2026**

### Resumen de Implementación

FASE 7 completa la arquitectura del sistema con una capa REST API completa y un sistema de orquestación de workflows multi-paso.

#### Componentes Implementados

1. **WorkflowOrchestrator** - Servicio central de orquestación
   - Order creation workflow
   - Invoice linking workflow
   - Route generation and activation workflow
   - Compliance reporting

2. **REST API Endpoints** - 24 endpoints implementados
   - Orders API: 8 endpoints
   - Invoices API: 5 endpoints
   - Routes API: 8 endpoints
   - Reports API: 4 endpoints

3. **Error Handling Middleware**
   - 20+ exception handlers
   - Consistent error responses
   - Automatic logging

4. **Pydantic Schemas**
   - Route schemas (6 schemas)
   - Report schemas (7 schemas)
   - Full validation

5. **Integration Tests**
   - 30+ test cases
   - E2E workflow testing
   - RBAC verification

#### Métricas

- **Archivos creados:** 15
- **Líneas de código:** ~3,282 en archivos principales
- **Total Python files:** 79
- **Total líneas en app/:** ~12,260
- **Endpoints:** 24 nuevos
- **Tests:** 30+ casos

#### Documentación

- [FASE_7_IMPLEMENTATION_SUMMARY.md](FASE_7_IMPLEMENTATION_SUMMARY.md) - Resumen detallado
- [QUICK_START_GUIDE.md](QUICK_START_GUIDE.md) - Guía de inicio rápido
- [API_ENDPOINTS_REFERENCE.md](API_ENDPOINTS_REFERENCE.md) - Referencia de endpoints
- OpenAPI/Swagger: `http://localhost:8000/docs`

#### Próximos Pasos

El sistema está listo para:
1. Deployment a producción
2. Integración con frontend (React/Vue/Angular)
3. Desarrollo de mobile app para repartidores
4. Monitoreo y analytics avanzados

---

## Fases Completadas

- [x] **FASE 0:** Infraestructura Docker
- [x] **FASE 1:** Base de datos y modelos
- [x] **FASE 2:** Lógica de negocio (Services)
- [x] **FASE 3:** Geocodificación con OpenStreetMap
- [x] **FASE 4:** Optimización de rutas con OR-Tools
- [x] **FASE 5:** Autenticación JWT y RBAC
- [x] **FASE 6:** Sistema de notificaciones Email
- [x] **FASE 7:** Capa API y Orquestación de Workflows

**Sistema 100% funcional y listo para producción**

