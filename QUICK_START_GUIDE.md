# Claude Logistics API - Quick Start Guide

## Inicio Rápido

### 1. Instalación de Dependencias

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración de Base de Datos

```bash
# Crear base de datos PostgreSQL con PostGIS
createdb claude_logistics

# Habilitar extensión PostGIS
psql claude_logistics -c "CREATE EXTENSION postgis;"

# Ejecutar migraciones (si existen)
# o crear tablas directamente con SQLAlchemy
python -c "from app.config.database import engine, Base; from app.models.models import *; Base.metadata.create_all(engine)"
```

### 3. Variables de Entorno

Crear archivo `.env`:

```env
# App
APP_NAME="Claude Logistics API"
APP_VERSION="1.0.0"
DEBUG=True

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/claude_logistics

# JWT
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]

# Geocoding (Nominatim)
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
NOMINATIM_USER_AGENT=ClaudeBotilleria/1.0

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@botilleria.cl
SMTP_FROM_NAME=Botillería Rancagua

# Route Optimization
DEPOT_LATITUDE=-34.1706
DEPOT_LONGITUDE=-70.7407
AVERAGE_SPEED_KMH=30
SERVICE_TIME_PER_STOP_MINUTES=5
ROUTE_OPTIMIZATION_TIMEOUT_SECONDS=10
```

### 4. Seed Data (Opcional)

```bash
# Crear roles y usuarios iniciales
python app/scripts/seed_data.py
```

### 5. Ejecutar Servidor

```bash
# Desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Verificar Instalación

```bash
# Health check
curl http://localhost:8000/health

# OpenAPI docs
open http://localhost:8000/docs
```

---

## Flujo de Trabajo Típico

### Escenario 1: Procesar Pedido Completo

#### Paso 1: Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'

# Guardar token
export TOKEN="eyJ..."
```

#### Paso 2: Crear Pedido
```bash
curl -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Juan Pérez",
    "customer_phone": "+56912345678",
    "customer_email": "juan@example.cl",
    "address_text": "Av. Brasil 1234, Rancagua",
    "source_channel": "WEB"
  }'

# Guardar order_id
export ORDER_ID="uuid-from-response"
```

#### Paso 3: Transicionar a EN_PREPARACION
```bash
curl -X PUT http://localhost:8000/api/orders/$ORDER_ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "EN_PREPARACION"
  }'
```

#### Paso 4: Crear Factura (auto-transición a DOCUMENTADO)
```bash
curl -X POST http://localhost:8000/api/invoices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "'$ORDER_ID'",
    "invoice_number": "FAC-001",
    "invoice_type": "FACTURA",
    "total_amount": 50000
  }'
```

#### Paso 5: Generar Ruta
```bash
curl -X POST http://localhost:8000/api/routes/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "delivery_date": "2026-01-23"
  }'

# Guardar route_id
export ROUTE_ID="uuid-from-response"
```

#### Paso 6: Activar Ruta
```bash
curl -X POST http://localhost:8000/api/routes/$ROUTE_ID/activate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "driver-uuid"
  }'
```

#### Paso 7: Ver Datos de Mapa
```bash
curl http://localhost:8000/api/routes/$ROUTE_ID/map-data \
  -H "Authorization: Bearer $TOKEN"
```

---

### Escenario 2: Generar Reportes

#### Reporte de Compliance
```bash
curl "http://localhost:8000/api/reports/compliance?start_date=2026-01-15&end_date=2026-01-22" \
  -H "Authorization: Bearer $TOKEN"
```

#### Reporte Diario
```bash
curl "http://localhost:8000/api/reports/daily-operations?report_date=2026-01-22" \
  -H "Authorization: Bearer $TOKEN"
```

#### Resumen Ejecutivo
```bash
curl http://localhost:8000/api/reports/summary \
  -H "Authorization: Bearer $TOKEN"
```

---

## Tests

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests específicos
pytest tests/test_api/test_orders_endpoints.py

# Con coverage
pytest --cov=app --cov-report=html

# Ver coverage
open htmlcov/index.html
```

---

## Documentación Interactiva

### Swagger UI
Ir a: http://localhost:8000/docs

**Features:**
- Probar endpoints directamente
- Ver schemas de request/response
- Autenticación JWT integrada (botón "Authorize")

### ReDoc
Ir a: http://localhost:8000/redoc

**Features:**
- Documentación más legible
- Búsqueda de endpoints
- Descarga de OpenAPI spec

---

## Estructura de Permisos (RBAC)

### Administrador
- Acceso completo a todos los endpoints
- Puede eliminar órdenes y facturas
- Puede sobrescribir cutoff times

### Encargado de Bodega
- Gestión de órdenes y facturas
- Generación y activación de rutas
- Acceso a reportes

### Vendedor
- Crear órdenes
- Ver solo sus propias órdenes
- Crear facturas para sus órdenes

### Repartidor
- Ver rutas asignadas
- Actualizar estados de entrega
- Completar rutas

---

## Troubleshooting

### Error: "Database connection failed"
```bash
# Verificar PostgreSQL está corriendo
pg_isready

# Verificar credenciales en .env
echo $DATABASE_URL

# Recrear base de datos
dropdb claude_logistics
createdb claude_logistics
psql claude_logistics -c "CREATE EXTENSION postgis;"
```

### Error: "Module not found"
```bash
# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

### Error: "Geocoding service timeout"
```bash
# Verificar conectividad con Nominatim
curl "https://nominatim.openstreetmap.org/search?q=Rancagua&format=json"

# Ajustar timeout en settings.py
```

### Error: "JWT token expired"
```bash
# Hacer login nuevamente
curl -X POST http://localhost:8000/api/auth/login ...
```

---

## Docker Deployment

### Desarrollo
```bash
docker-compose up -d
```

### Producción
```bash
docker build -t claude-logistics:latest .
docker run -d -p 8000:8000 --env-file .env.prod claude-logistics:latest
```

---

## Monitoreo

### Health Check Endpoint
```bash
curl http://localhost:8000/health
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-01-22T14:30:00Z"
}
```

### Logs
```bash
# Development (console)
uvicorn app.main:app --reload --log-level debug

# Production (file)
uvicorn app.main:app --log-config logging.conf
```

---

## Recursos Adicionales

- **Documentación completa:** `/docs` o `/redoc`
- **Especificación OpenAPI:** `/openapi.json`
- **Resumen de FASE 7:** `FASE_7_IMPLEMENTATION_SUMMARY.md`
- **Especificación de IA:** `CLAUDE_IA_SPEC.md`

---

## Soporte

Para reportar bugs o solicitar features:
1. Revisar documentación en `/docs`
2. Verificar logs de errores
3. Contactar al equipo de desarrollo

**API Version:** 1.0.0
**Última actualización:** 22 de Enero, 2026
