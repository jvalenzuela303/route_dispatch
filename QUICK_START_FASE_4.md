# Quick Start - FASE 4: Route Optimization

Guía rápida para comenzar a usar el motor de optimización de rutas.

## Prerequisitos

FASE 4 requiere:
- ✅ FASE 0: Infraestructura (PostgreSQL + PostGIS)
- ✅ FASE 1: Base de datos (tablas creadas)
- ✅ FASE 2: Lógica de negocio (OrderService, InvoiceService)
- ✅ FASE 3: Geocodificación (GeocodingService)

## Instalación Rápida

### 1. Instalar Dependencias

```bash
cd /home/juan/Desarrollo/route_dispatch
pip install -r requirements.txt
```

Esto instalará:
- `ortools==9.8.3296` (Google OR-Tools)
- `numpy==1.26.2` (Matrices numéricas)

### 2. Configurar Variables de Entorno

Editar `.env`:

```bash
# Depot (Bodega) - ACTUALIZAR CON UBICACIÓN REAL
DEPOT_LATITUDE=-34.1706
DEPOT_LONGITUDE=-70.7406
DEPOT_NAME="Bodega Principal - Botillería Rancagua"

# Parámetros de Optimización
AVERAGE_SPEED_KMH=30.0
SERVICE_TIME_PER_STOP_MINUTES=5
ROUTE_OPTIMIZATION_TIMEOUT_SECONDS=30
```

### 3. Verificar Instalación

```bash
# Verificar OR-Tools
python -c "from ortools.constraint_solver import pywrapcp; print('OR-Tools: OK')"

# Verificar servicio
python -c "from app.services.route_optimization_service import RouteOptimizationService; print('Service: OK')"
```

## Uso Básico (5 Pasos)

### Paso 1: Preparar Pedidos

Crear pedidos con `OrderService` (FASE 2):

```python
from app.services.order_service import OrderService
from datetime import date, timedelta

order_service = OrderService(db_session)
tomorrow = date.today() + timedelta(days=1)

# Crear pedido
order = order_service.create_order(
    customer_name="Juan Pérez",
    customer_phone="+56912345678",
    address_text="Av. Libertador Bernardo O'Higgins 123, Rancagua",
    source_channel=SourceChannel.WEB,
    user=current_user
)
```

### Paso 2: Geocodificar Direcciones

Usar `GeocodingService` (FASE 3):

```python
from app.services.geocoding_service import GeocodingService

geo_service = GeocodingService()

# Geocodificar pedido
result = geo_service.geocode_order(order.id, db_session)
print(f"Coordenadas: {result.latitude}, {result.longitude}")
```

### Paso 3: Crear Factura

Usar `InvoiceService` (FASE 2):

```python
from app.services.invoice_service import InvoiceService
from decimal import Decimal

invoice_service = InvoiceService(db_session)

# Crear factura (esto transiciona el pedido a DOCUMENTADO)
invoice = invoice_service.create_invoice(
    order_id=order.id,
    invoice_number="F-001-00001",
    invoice_type=InvoiceType.BOLETA,
    total_amount=Decimal("45000.00"),
    user=current_user
)
```

Ahora el pedido está en estado `DOCUMENTADO` y listo para routing.

### Paso 4: Generar Ruta Optimizada

```python
from app.services.route_optimization_service import RouteOptimizationService

route_service = RouteOptimizationService(db_session)

# Generar ruta para mañana
route = route_service.generate_route_for_date(
    delivery_date=tomorrow,
    user=current_user  # Debe ser Encargado o Admin
)

print(f"Ruta generada: {route.route_name}")
print(f"Distancia total: {route.total_distance_km} km")
print(f"Duración estimada: {route.estimated_duration_minutes} min")
print(f"Número de paradas: {len(route.stop_sequence)}")
```

### Paso 5: Activar Ruta y Asignar Repartidor

```python
# Obtener repartidor
driver = db_session.query(User).filter(
    User.role.role_name == "Repartidor"
).first()

# Activar ruta
activated_route = route_service.activate_route(
    route_id=route.id,
    driver_id=driver.id,
    user=current_user
)

print(f"Ruta activada: {activated_route.status}")
print(f"Repartidor: {activated_route.assigned_driver.username}")
print(f"Iniciada: {activated_route.started_at}")
```

Ahora todos los pedidos en la ruta están en estado `EN_RUTA`.

## Ejemplo Completo

```python
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.enums import SourceChannel, InvoiceType
from app.services.order_service import OrderService
from app.services.geocoding_service import GeocodingService
from app.services.invoice_service import InvoiceService
from app.services.route_optimization_service import RouteOptimizationService

def generate_route_example(db_session: Session, user, driver):
    """Ejemplo completo: crear pedidos y generar ruta"""

    tomorrow = date.today() + timedelta(days=1)

    # 1. Crear servicios
    order_service = OrderService(db_session)
    geo_service = GeocodingService()
    invoice_service = InvoiceService(db_session)
    route_service = RouteOptimizationService(db_session)

    # 2. Crear pedidos
    addresses = [
        "Av. Libertador Bernardo O'Higgins 123, Rancagua",
        "Calle Estado 456, Rancagua",
        "Av. Cachapoal 789, Rancagua"
    ]

    orders = []
    for idx, address in enumerate(addresses, start=1):
        # Crear pedido
        order = order_service.create_order(
            customer_name=f"Cliente {idx}",
            customer_phone=f"+56912345{idx:03d}",
            address_text=address,
            source_channel=SourceChannel.WEB,
            user=user
        )

        # Geocodificar
        geo_service.geocode_order(order.id, db_session)

        # Crear factura
        invoice_service.create_invoice(
            order_id=order.id,
            invoice_number=f"F-001-{idx:05d}",
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("45000.00"),
            user=user
        )

        orders.append(order)

    print(f"Creados {len(orders)} pedidos")

    # 3. Generar ruta
    route = route_service.generate_route_for_date(tomorrow, user)

    print(f"\nRuta: {route.route_name}")
    print(f"Distancia: {route.total_distance_km} km")
    print(f"Duración: {route.estimated_duration_minutes} min")

    # 4. Activar ruta
    activated = route_service.activate_route(route.id, driver.id, user)

    print(f"\nRuta activada para {activated.assigned_driver.username}")

    return route
```

## Verificar Resultados

### Ver Detalles de Ruta

```python
details = route_service.get_route_details(route.id)

print(f"\n{details['route_name']}")
print("=" * 50)
print(f"Fecha: {details['route_date']}")
print(f"Estado: {details['status']}")
print(f"Distancia: {details['total_distance_km']} km")
print(f"Duración: {details['estimated_duration_minutes']} min")
print(f"\nParadas:")

for stop in details['stops']:
    print(f"  {stop['stop_number']}. {stop['customer_name']}")
    print(f"     {stop['address_text']}")
    print(f"     Tel: {stop['customer_phone']}")
```

### Ver Pedidos en Ruta

```python
from app.models.models import Order
from app.models.enums import OrderStatus

orders_en_ruta = db_session.query(Order).filter(
    Order.assigned_route_id == route.id,
    Order.order_status == OrderStatus.EN_RUTA
).all()

print(f"\nPedidos en ruta: {len(orders_en_ruta)}")
for order in orders_en_ruta:
    print(f"  - {order.order_number}: {order.customer_name}")
```

## Tests

### Ejecutar Tests

```bash
# Todos los tests de route optimization
pytest tests/test_services/test_route_optimization_service.py -v

# Test específico de performance
pytest tests/test_services/test_route_optimization_service.py::TestPerformance::test_route_generation_performance_50_orders -v
```

### Output Esperado

```
tests/test_services/test_route_optimization_service.py::TestRouteGeneration::test_generate_route_basic PASSED
tests/test_services/test_route_optimization_service.py::TestPerformance::test_route_generation_performance_50_orders PASSED
...
==================== 16 passed in 12.34s ====================
```

## Ejemplos Interactivos

### Ejecutar Ejemplos

```bash
python examples/route_optimization_example.py
```

Menú:
```
1. Generate Route
2. Activate Route
3. Get Route Details
4. Performance Test
5. Error Handling
0. Run all examples
```

## Troubleshooting

### Error: "No hay pedidos documentados"

**Solución**: Verificar que hay pedidos con:
- Estado: `DOCUMENTADO`
- `delivery_date` = fecha objetivo
- `invoice_id` IS NOT NULL
- `address_coordinates` IS NOT NULL

```python
# Verificar pedidos elegibles
eligible = db_session.query(Order).filter(
    Order.order_status == OrderStatus.DOCUMENTADO,
    Order.delivery_date == tomorrow,
    Order.address_coordinates.isnot(None)
).count()

print(f"Pedidos elegibles: {eligible}")
```

### Error: "OR-Tools not found"

**Solución**:
```bash
pip install ortools==9.8.3296
```

### Error: "PostGIS function not found"

**Solución**: Verificar PostGIS instalado:
```sql
SELECT PostGIS_Version();
```

Crear extensión si necesario:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Performance Lento

**Solución**: Crear índice espacial:
```sql
CREATE INDEX IF NOT EXISTS ix_orders_address_coordinates
ON orders USING GIST (address_coordinates);
```

## Configuración Avanzada

### Ajustar Velocidad Promedio

Para área más congestionada:
```bash
AVERAGE_SPEED_KMH=25.0
```

Para área menos congestionada:
```bash
AVERAGE_SPEED_KMH=35.0
```

### Ajustar Tiempo por Parada

Para entregas más rápidas:
```bash
SERVICE_TIME_PER_STOP_MINUTES=3
```

Para entregas más lentas:
```bash
SERVICE_TIME_PER_STOP_MINUTES=7
```

### Ajustar Timeout

Para rutas muy grandes:
```bash
ROUTE_OPTIMIZATION_TIMEOUT_SECONDS=60
```

## Flujo Completo de Trabajo

```
1. CREAR PEDIDOS (OrderService)
   ↓
2. GEOCODIFICAR (GeocodingService)
   ↓
3. CREAR FACTURAS (InvoiceService)
   → Pedidos ahora en DOCUMENTADO
   ↓
4. GENERAR RUTA (RouteOptimizationService)
   → Ruta en DRAFT
   ↓
5. ACTIVAR RUTA (RouteOptimizationService)
   → Ruta en ACTIVE
   → Pedidos en EN_RUTA
   ↓
6. ENTREGAR PEDIDOS (FASE 5)
   → Pedidos en ENTREGADO
   → Ruta en COMPLETED
```

## Recursos

### Documentación
- `docs/ROUTE_OPTIMIZATION.md` - Documentación técnica completa
- `FASE_4_COMPLETED.md` - Resumen de implementación
- `FASE_4_FILES_INVENTORY.md` - Inventario de archivos

### Código
- `app/services/route_optimization_service.py` - Servicio principal
- `tests/test_services/test_route_optimization_service.py` - Tests
- `examples/route_optimization_example.py` - Ejemplos

### External Links
- [Google OR-Tools](https://developers.google.com/optimization)
- [PostGIS ST_Distance](https://postgis.net/docs/ST_Distance.html)

## Próximos Pasos

Después de dominar FASE 4, continuar con:

### FASE 5: Gestión de Entregas
- Actualización de estado de entregas
- Confirmación de entrega
- Manejo de incidencias

### FASE 6: Notificaciones
- Notificaciones a clientes
- Alertas a repartidores

### FASE 7: Tracking
- GPS en tiempo real
- Visualización de rutas

---

**¿Preguntas?** Consulta `docs/ROUTE_OPTIMIZATION.md` para detalles técnicos completos.
