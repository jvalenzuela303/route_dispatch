# Quick Start - FASE 3: Geocodificacion

Guia rapida para empezar a usar el sistema de geocodificacion.

## 1. Instalar Dependencias

```bash
cd /home/juan/Desarrollo/route_dispatch
pip install -r requirements.txt
```

## 2. Configuracion (Opcional)

El sistema funciona con configuracion por defecto. Para personalizar, añadir a `.env`:

```bash
# Geocoding (opcional - usa defaults)
GEOCODING_CACHE_TTL=2592000
NOMINATIM_USER_AGENT="ClaudeBotilleria/1.0 (contact@botilleria.cl)"

# Bounding Box Rancagua (opcional - ya configurado)
RANCAGUA_BBOX_WEST=-70.85
RANCAGUA_BBOX_EAST=-70.65
RANCAGUA_BBOX_SOUTH=-34.25
RANCAGUA_BBOX_NORTH=-34.05
```

## 3. Uso Basico

```python
from app.services.geocoding_service import GeocodingService

# Crear servicio
service = GeocodingService()

# Geocodificar direccion
result = service.geocode_address("Av O'Higgins 123, Rancagua")

# Verificar resultado
if result.success:
    print(f"Coordenadas: {result.latitude}, {result.longitude}")
    print(f"Confianza: {result.confidence.value}")
else:
    print(f"Error: {result.error_message}")
```

## 4. En OrderService (Automatico)

```python
from app.services.order_service import OrderService
from app.exceptions import InvalidAddressError

try:
    order = order_service.create_order(
        customer_name="Juan Perez",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123",  # Geocodificacion automatica
        source_channel=SourceChannel.WEB,
        user=current_user
    )
    # Coordenadas almacenadas en order.address_coordinates
except InvalidAddressError as e:
    # Direccion rechazada por baja calidad
    return {"error": e.message}
```

## 5. Ejecutar Tests

```bash
# Todos los tests
pytest tests/test_services/test_geocoding_service.py -v

# Test especifico
pytest tests/test_services/test_geocoding_service.py::test_geocode_address_high_confidence_success -v
```

## 6. Ver Ejemplos

```bash
python examples/geocoding_usage_example.py
```

## 7. Niveles de Confianza

| Nivel | ¿Se acepta? | Ejemplo |
|-------|-------------|---------|
| HIGH | Si | "Av O'Higgins 123, Rancagua" |
| MEDIUM | Si | "Calle Astorga 456, Rancagua" |
| LOW | No | "Centro, Rancagua" |
| INVALID | No | "Rancagua" |

## 8. Cache (Produccion)

Para usar Redis en produccion:

```python
from app.services.geocoding_cache import create_geocoding_cache
from app.services.geocoding_service import GeocodingService

cache = create_geocoding_cache(
    "redis",
    redis_url="redis://localhost:6379/0"
)
service = GeocodingService(cache_backend=cache)
```

## 9. Documentacion

- **Completa:** `docs/GEOCODING_INTEGRATION.md` (794 lineas)
- **Quick Reference:** `docs/GEOCODING_QUICK_REFERENCE.md`
- **Ejemplos:** `examples/geocoding_usage_example.py`
- **Resumen:** `FASE_3_COMPLETED.md`

## 10. Troubleshooting

### Problema: Direcciones rechazadas

**Solucion:** Verificar que direccion incluya numero de calle.

```python
# ✗ Rechazada
"Centro, Rancagua"

# ✓ Aceptada  
"Av O'Higgins 123, Rancagua"
```

### Problema: Lento

**Solucion:** Verificar cache hit rate. Usar Redis en produccion.

### Problema: Rate limit

**Solucion:** Verificar que rate limiting este activo (1 req/s).

---

**Listo para usar!** Ver documentacion completa para casos avanzados.
