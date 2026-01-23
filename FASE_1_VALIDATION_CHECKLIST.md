# FASE 1: Validation Checklist

Use este checklist para validar que FASE 1 está completamente implementada y funcionando correctamente.

## Pre-requisitos

- [ ] Docker instalado y ejecutándose
- [ ] Docker Compose disponible
- [ ] Python 3.11+ instalado
- [ ] Virtual environment activado
- [ ] Puerto 5432 disponible (PostgreSQL)

## 1. Instalación de Dependencias

```bash
pip install -r requirements.txt
```

**Verificar:**
- [ ] SQLAlchemy 2.0.23 instalado
- [ ] Alembic 1.12.1 instalado
- [ ] GeoAlchemy2 0.14.2 instalado
- [ ] psycopg2-binary 2.9.9 instalado
- [ ] bcrypt 4.1.2 instalado
- [ ] eralchemy2 1.3.8 instalado
- [ ] pytest 7.4.3 instalado
- [ ] FastAPI 0.104.1 instalado

**Comando de verificación:**
```bash
pip freeze | grep -E "(sqlalchemy|alembic|geoalchemy2|psycopg2|bcrypt|eralchemy2|pytest|fastapi)"
```

## 2. Estructura de Archivos

**Verificar que existen los siguientes archivos:**

### Models
- [ ] `/home/juan/Desarrollo/route_dispatch/app/models/__init__.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/models/base.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/models/enums.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/models/models.py`

### Config
- [ ] `/home/juan/Desarrollo/route_dispatch/app/config/database.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/config/settings.py`

### Scripts
- [ ] `/home/juan/Desarrollo/route_dispatch/app/scripts/__init__.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/scripts/seed_data.py`
- [ ] `/home/juan/Desarrollo/route_dispatch/app/scripts/generate_erd.py`

### Migrations
- [ ] `/home/juan/Desarrollo/route_dispatch/migrations/env.py` (actualizado)
- [ ] `/home/juan/Desarrollo/route_dispatch/migrations/versions/001_initial_schema.py`

### Tests
- [ ] `/home/juan/Desarrollo/route_dispatch/tests/test_models.py`

### Documentation
- [ ] `/home/juan/Desarrollo/route_dispatch/docs/DATABASE_SCHEMA.md`
- [ ] `/home/juan/Desarrollo/route_dispatch/docs/FASE_1_INSTRUCTIONS.md`
- [ ] `/home/juan/Desarrollo/route_dispatch/FASE_1_SUMMARY.md`

**Comando de verificación:**
```bash
find /home/juan/Desarrollo/route_dispatch -type f -name "*.py" | grep -E "(models|config|scripts|migrations|tests)" | wc -l
# Debe mostrar al menos 13 archivos
```

## 3. Database Setup

### 3.1 Iniciar PostgreSQL

```bash
cd /home/juan/Desarrollo/route_dispatch
docker compose up -d postgres
```

**Verificar:**
- [ ] Contenedor postgres está corriendo
- [ ] Puerto 5432 está escuchando
- [ ] Logs no muestran errores

**Comandos de verificación:**
```bash
docker compose ps | grep postgres
# Debe mostrar: Up

docker compose logs postgres | tail -20
# No debe mostrar errores críticos
```

### 3.2 Verificar PostGIS

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT PostGIS_Version();"
```

**Verificar:**
- [ ] PostGIS versión 3.x se muestra
- [ ] No hay errores de "extension not found"

**Output esperado:**
```
           postgis_version
----------------------------------------
 3.x USE_GEOS=1 USE_PROJ=1 USE_STATS=1
```

## 4. Database Migration

### 4.1 Aplicar Migración

```bash
alembic upgrade head
```

**Verificar:**
- [ ] Comando ejecuta sin errores
- [ ] Se muestra "Running upgrade -> 001_initial_schema"
- [ ] Se muestra "SUCCESS"

### 4.2 Verificar Estado de Migración

```bash
alembic current
```

**Verificar:**
- [ ] Muestra: `001_initial_schema (head)`

### 4.3 Verificar Tablas Creadas

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "\dt"
```

**Verificar que existen las siguientes tablas:**
- [ ] alembic_version
- [ ] audit_logs
- [ ] invoices
- [ ] orders
- [ ] roles
- [ ] routes
- [ ] users

**Total esperado:** 7 tablas

### 4.4 Verificar Enums Creados

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "\dT"
```

**Verificar que existen los siguientes enums:**
- [ ] audit_result_enum
- [ ] geocoding_confidence_enum
- [ ] invoice_type_enum
- [ ] order_status_enum
- [ ] route_status_enum
- [ ] source_channel_enum

**Total esperado:** 6 enums

### 4.5 Verificar Índices

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "\di"
```

**Verificar índices clave:**
- [ ] ix_orders_address_coordinates (GIST - índice espacial)
- [ ] ix_orders_order_status
- [ ] ix_orders_delivery_date
- [ ] ix_users_email
- [ ] ix_users_username
- [ ] ix_invoices_order_id
- [ ] ix_routes_route_date

**Total esperado:** 17+ índices

## 5. Seed Data

### 5.1 Ejecutar Script de Seed

```bash
python -m app.scripts.seed_data
```

**Verificar output:**
- [ ] "Creating roles..." - 4 roles creados
- [ ] "Creating test users..." - 4 usuarios creados
- [ ] "Creating sample orders..." - 10 pedidos creados
- [ ] "Creating sample invoices..." - 5 facturas creadas
- [ ] "Creating sample routes..." - 3 rutas creadas
- [ ] "Database seeding completed successfully!"

### 5.2 Verificar Roles

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT role_name FROM roles;"
```

**Verificar que existen:**
- [ ] Administrador
- [ ] Encargado de Bodega
- [ ] Vendedor
- [ ] Repartidor

### 5.3 Verificar Usuarios

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT username, email FROM users;"
```

**Verificar que existen:**
- [ ] admin (admin@botilleria.cl)
- [ ] bodega (bodega@botilleria.cl)
- [ ] vendedor (vendedor@botilleria.cl)
- [ ] repartidor (repartidor@botilleria.cl)

### 5.4 Verificar Pedidos

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT order_number, order_status FROM orders;"
```

**Verificar:**
- [ ] 10 pedidos creados
- [ ] Diferentes estados (PENDIENTE, EN_PREPARACION, DOCUMENTADO, EN_RUTA, ENTREGADO, INCIDENCIA)
- [ ] Order numbers en formato ORD-YYYYMMDD-NNNN

### 5.5 Verificar Facturas

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT invoice_number, invoice_type FROM invoices;"
```

**Verificar:**
- [ ] 5 facturas creadas
- [ ] Tipos FACTURA y BOLETA presentes
- [ ] Números de factura únicos

### 5.6 Verificar Rutas

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT route_name, status FROM routes;"
```

**Verificar:**
- [ ] 3 rutas creadas
- [ ] Estados: DRAFT, ACTIVE, COMPLETED

## 6. PostGIS Functionality

### 6.1 Test Spatial Query - Distance

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
SELECT
    o1.order_number as order1,
    o2.order_number as order2,
    ST_Distance(o1.address_coordinates, o2.address_coordinates) as distance_meters
FROM orders o1, orders o2
WHERE o1.id != o2.id
  AND o1.address_coordinates IS NOT NULL
  AND o2.address_coordinates IS NOT NULL
LIMIT 3;
EOF
```

**Verificar:**
- [ ] Query ejecuta sin errores
- [ ] Distancias calculadas en metros
- [ ] Valores razonables (< 50,000 metros para Rancagua)

### 6.2 Test Spatial Query - Radius

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
SELECT
    order_number,
    customer_name,
    ST_Distance(
        address_coordinates,
        ST_GeographyFromText('POINT(-70.7407 -34.1704)')
    ) as distance_meters
FROM orders
WHERE address_coordinates IS NOT NULL
  AND ST_DWithin(
      address_coordinates,
      ST_GeographyFromText('POINT(-70.7407 -34.1704)'),
      10000
  )
ORDER BY distance_meters;
EOF
```

**Verificar:**
- [ ] Query ejecuta sin errores
- [ ] Ordena por distancia correctamente
- [ ] Solo muestra pedidos dentro de 10km

### 6.3 Test Spatial Index

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
EXPLAIN ANALYZE
SELECT *
FROM orders
WHERE ST_DWithin(
    address_coordinates,
    ST_GeographyFromText('POINT(-70.7407 -34.1704)'),
    5000
);
EOF
```

**Verificar:**
- [ ] Plan usa "Index Scan using ix_orders_address_coordinates"
- [ ] No usa "Seq Scan" (tabla completa)

## 7. Model Tests

### 7.1 Ejecutar Tests

```bash
pytest tests/test_models.py -v
```

**Verificar:**
- [ ] 16 tests ejecutados
- [ ] 16 tests PASSED
- [ ] 0 tests FAILED
- [ ] 0 tests SKIPPED

### 7.2 Tests Individuales

**Role Model:**
- [ ] test_create_role - PASSED
- [ ] test_role_unique_name - PASSED

**User Model:**
- [ ] test_create_user - PASSED
- [ ] test_user_unique_email - PASSED
- [ ] test_user_role_relationship - PASSED

**Order Model:**
- [ ] test_create_order - PASSED
- [ ] test_order_status_enum - PASSED
- [ ] test_order_unique_order_number - PASSED

**Invoice Model:**
- [ ] test_create_invoice - PASSED
- [ ] test_invoice_one_to_one_with_order - PASSED

**Route Model:**
- [ ] test_create_route - PASSED
- [ ] test_route_driver_relationship - PASSED

**AuditLog Model:**
- [ ] test_create_audit_log - PASSED
- [ ] test_audit_log_system_action - PASSED

**Relationships:**
- [ ] test_order_invoice_relationship - PASSED
- [ ] test_cascade_delete_invoice_with_order - PASSED

### 7.3 Coverage (Opcional)

```bash
pytest tests/test_models.py --cov=app.models --cov-report=term-missing
```

**Verificar:**
- [ ] Coverage > 80% en app.models

## 8. ERD Generation

### 8.1 Generar ERD

```bash
python -m app.scripts.generate_erd
```

**Verificar:**
- [ ] Script ejecuta sin errores
- [ ] Muestra "ERD successfully generated!"
- [ ] Archivo creado: `docs/erd.png`
- [ ] Archivo creado: `docs/erd.pdf`

### 8.2 Validar ERD

```bash
ls -lh /home/juan/Desarrollo/route_dispatch/docs/erd.*
```

**Verificar:**
- [ ] erd.png existe y tiene tamaño > 10KB
- [ ] erd.pdf existe y tiene tamaño > 10KB

**Abrir y verificar visualmente:**
- [ ] Todas las 6 tablas están presentes
- [ ] Relaciones (flechas) se muestran correctamente
- [ ] Primary keys marcados
- [ ] Foreign keys marcados

## 9. Data Integrity

### 9.1 Foreign Key Constraints

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
-- Intentar insertar un usuario con role_id inválido (debe fallar)
INSERT INTO users (id, username, email, password_hash, role_id, active_status)
VALUES (
    gen_random_uuid(),
    'test_invalid',
    'invalid@test.com',
    'hash',
    gen_random_uuid(),  -- UUID inexistente
    true
);
EOF
```

**Verificar:**
- [ ] Query FALLA con error de foreign key
- [ ] Mensaje: "violates foreign key constraint"

### 9.2 Unique Constraints

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
-- Intentar insertar orden con order_number duplicado (debe fallar)
INSERT INTO orders (id, order_number, customer_name, customer_phone, address_text, order_status, source_channel, created_by_user_id)
SELECT
    gen_random_uuid(),
    'ORD-20260120-0001',  -- Número duplicado
    'Test Customer',
    '+56912345678',
    'Test Address',
    'PENDIENTE',
    'WEB',
    id
FROM users LIMIT 1;
EOF
```

**Verificar:**
- [ ] Query FALLA con error de unique constraint
- [ ] Mensaje: "duplicate key value violates unique constraint"

### 9.3 Check Constraints

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
-- Intentar insertar factura con monto negativo (debe fallar)
INSERT INTO invoices (id, invoice_number, order_id, invoice_type, total_amount, issued_at, created_by_user_id)
SELECT
    gen_random_uuid(),
    'TEST-INVALID-001',
    id,
    'BOLETA',
    -100,  -- Monto negativo
    NOW(),
    created_by_user_id
FROM orders LIMIT 1;
EOF
```

**Verificar:**
- [ ] Query FALLA con error de check constraint
- [ ] Mensaje: "violates check constraint"

## 10. Relationships

### 10.1 One-to-One (Order-Invoice)

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT o.order_number, i.invoice_number FROM orders o LEFT JOIN invoices i ON o.id = i.order_id WHERE i.id IS NOT NULL LIMIT 5;"
```

**Verificar:**
- [ ] Solo pedidos con facturas se muestran
- [ ] Cada pedido tiene máximo 1 factura

### 10.2 Many-to-One (Order-User)

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT u.username, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id = o.created_by_user_id GROUP BY u.username;"
```

**Verificar:**
- [ ] Usuarios mostrados con sus conteos de pedidos
- [ ] Usuario "vendedor" tiene la mayoría de pedidos

### 10.3 Many-to-One (User-Role)

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT r.role_name, COUNT(u.id) as user_count FROM roles r LEFT JOIN users u ON r.id = u.role_id GROUP BY r.role_name;"
```

**Verificar:**
- [ ] Todos los roles se muestran
- [ ] Cada rol tiene 1 usuario

## 11. Business Logic Validation

### 11.1 Order Status Progression

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT order_status, COUNT(*) FROM orders GROUP BY order_status ORDER BY order_status;"
```

**Verificar:**
- [ ] Todos los 6 estados presentes
- [ ] Distribución razonable

### 11.2 Invoiced Orders

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
SELECT
    o.order_number,
    o.order_status,
    i.invoice_number
FROM orders o
LEFT JOIN invoices i ON o.id = i.order_id
WHERE o.order_status IN ('DOCUMENTADO', 'EN_RUTA', 'ENTREGADO')
ORDER BY o.order_status;
EOF
```

**Verificar:**
- [ ] Todos los pedidos DOCUMENTADO/EN_RUTA/ENTREGADO tienen factura
- [ ] Ninguna factura NULL en estos estados

### 11.3 Route Assignments

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
SELECT
    r.route_name,
    r.status,
    COUNT(o.id) as order_count
FROM routes r
LEFT JOIN orders o ON r.id = o.assigned_route_id
GROUP BY r.id, r.route_name, r.status
ORDER BY r.status;
EOF
```

**Verificar:**
- [ ] Rutas tienen pedidos asignados
- [ ] Conteos razonables (1-3 pedidos por ruta)

## 12. Documentation

### 12.1 Archivos de Documentación

**Verificar que existen y tienen contenido:**
- [ ] `docs/DATABASE_SCHEMA.md` (> 500 líneas)
- [ ] `docs/FASE_1_INSTRUCTIONS.md` (> 400 líneas)
- [ ] `FASE_1_SUMMARY.md` (> 300 líneas)
- [ ] `FASE_1_VALIDATION_CHECKLIST.md` (este archivo)

```bash
wc -l /home/juan/Desarrollo/route_dispatch/docs/*.md /home/juan/Desarrollo/route_dispatch/FASE_1*.md
```

### 12.2 Documentación Inline

**Verificar docstrings en código:**
```bash
grep -c '"""' /home/juan/Desarrollo/route_dispatch/app/models/models.py
# Debe mostrar > 30 (docstrings abundantes)
```

## 13. Code Quality

### 13.1 No Syntax Errors

```bash
python -m py_compile /home/juan/Desarrollo/route_dispatch/app/models/*.py
python -m py_compile /home/juan/Desarrollo/route_dispatch/app/config/*.py
python -m py_compile /home/juan/Desarrollo/route_dispatch/app/scripts/*.py
```

**Verificar:**
- [ ] No errores de sintaxis
- [ ] Todos los archivos compilan

### 13.2 Import Tests

```bash
python -c "from app.models import Role, User, Order, Invoice, Route, AuditLog; print('✅ All imports successful')"
```

**Verificar:**
- [ ] Muestra "✅ All imports successful"
- [ ] No errores de import

## 14. Performance

### 14.1 Connection Pool

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'claude_logistics';"
```

**Verificar:**
- [ ] Conexiones activas < 10
- [ ] Pool funcionando correctamente

### 14.2 Query Performance (Spatial)

```bash
docker compose exec postgres psql -U claude_user -d claude_logistics <<EOF
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM orders
WHERE ST_DWithin(
    address_coordinates,
    ST_GeographyFromText('POINT(-70.7407 -34.1704)'),
    5000
);
EOF
```

**Verificar:**
- [ ] Execution time < 10ms (con 10 registros)
- [ ] Usa índice GIST
- [ ] No usa Seq Scan

## Final Checklist Summary

### Database
- [ ] PostgreSQL corriendo con PostGIS
- [ ] 7 tablas creadas
- [ ] 6 enums creados
- [ ] 17+ índices creados (incluyendo 1 GIST)
- [ ] Constraints funcionando (FK, UNIQUE, CHECK)

### Data
- [ ] 4 roles insertados
- [ ] 4 usuarios insertados
- [ ] 10 pedidos insertados
- [ ] 5 facturas insertadas
- [ ] 3 rutas insertadas

### Code
- [ ] 6 modelos SQLAlchemy implementados
- [ ] Database session management configurado
- [ ] Seed data script funcional
- [ ] ERD generator funcional
- [ ] 16 tests pasando

### Documentation
- [ ] Schema documentado completamente
- [ ] Instrucciones de ejecución claras
- [ ] ERD generado (PNG y PDF)
- [ ] Resumen de FASE 1 completo

### Business Rules
- [ ] Order lifecycle definido
- [ ] Cut-off time framework listo
- [ ] Invoice requirement enforcement preparado
- [ ] Audit logging framework implementado
- [ ] Role-based permissions estructurados

## Resultado Final

**Si todos los checkboxes están marcados (✅), FASE 1 está COMPLETA y VALIDADA.**

**Siguiente paso:** Proceder a FASE 2 - Business Logic Layer & API Endpoints

---

**Fecha de validación:** _____________
**Validado por:** _____________
**Status:** [ ] APROBADO  [ ] REQUIERE CORRECCIONES

---

## Troubleshooting

### Si algún check falla:

1. **Migración no aplicada:**
   ```bash
   alembic downgrade base
   alembic upgrade head
   ```

2. **Datos faltantes:**
   ```bash
   python -m app.scripts.seed_data
   ```

3. **Tests fallando:**
   ```bash
   pip install -r requirements.txt --force-reinstall
   pytest tests/test_models.py -v
   ```

4. **ERD no generado:**
   ```bash
   pip install eralchemy2
   python -m app.scripts.generate_erd
   ```

5. **PostGIS no disponible:**
   ```bash
   docker compose down
   docker compose up -d postgres
   docker compose exec postgres psql -U claude_user -d claude_logistics -c "CREATE EXTENSION IF NOT EXISTS postgis;"
   ```
