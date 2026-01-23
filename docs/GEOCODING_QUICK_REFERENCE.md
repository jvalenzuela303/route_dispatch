# Geocoding Quick Reference

Referencia rapida para desarrolladores que usan el servicio de geocodificacion.

## Importaciones

```python
from app.services.geocoding_service import GeocodingService, GeocodingResult
from app.services.geocoding_cache import (
    InMemoryGeocodingCache,
    RedisGeocodingCache,
    create_geocoding_cache
)
from app.models.enums import GeocodingConfidence
from app.exceptions import InvalidAddressError, GeocodingServiceError
```

## Uso Basico

```python
# Crear servicio
service = GeocodingService()

# Geocodificar direccion
result = service.geocode_address("Av O'Higgins 123, Rancagua")

# Verificar resultado
if result.success:
    print(f"Lat: {result.latitude}, Lon: {result.longitude}")
    print(f"Confianza: {result.confidence.value}")
else:
    print(f"Error: {result.error_message}")
```

## Validar Calidad de Direccion

```python
# Geocodificar
result = service.geocode_address("Av O'Higgins 123")

# Validar calidad (HIGH o MEDIUM requerido)
is_valid, error = service.validate_address_quality(result)

if not is_valid:
    raise InvalidAddressError(error)
```

## Cache en Memoria (Desarrollo)

```python
cache = InMemoryGeocodingCache(max_size=1000)
service = GeocodingService(cache_backend=cache)
```

## Cache Redis (Produccion)

```python
import redis

redis_client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
cache = RedisGeocodingCache(
    redis_client=redis_client,
    ttl_seconds=60 * 60 * 24 * 30  # 30 dias
)
service = GeocodingService(cache_backend=cache)
```

## Factory de Cache

```python
# In-memory
cache = create_geocoding_cache("memory", max_size=500)

# Redis
cache = create_geocoding_cache(
    "redis",
    redis_url="redis://localhost:6379/0",
    ttl_seconds=86400
)
```

## Niveles de Confianza

| Nivel | Criterio | Accion |
|-------|----------|--------|
| `HIGH` | Casa/edificio con numero | Aceptado |
| `MEDIUM` | Nivel de calle | Aceptado |
| `LOW` | Barrio/vecindario | Rechazado |
| `INVALID` | Sin resultados, fuera de bbox | Rechazado |

## GeocodingResult Attributes

```python
result.success          # bool
result.latitude         # float | None
result.longitude        # float | None
result.confidence       # GeocodingConfidence | None
result.display_name     # str | None
result.address_components  # dict | None
result.error_message    # str | None
result.cached           # bool
```

## Integracion OrderService

```python
from app.services.order_service import OrderService
from app.models.enums import SourceChannel

try:
    order = order_service.create_order(
        customer_name="Juan Perez",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123",
        source_channel=SourceChannel.WEB,
        user=current_user
    )
except InvalidAddressError as e:
    # Direccion rechazada
    return {"error": e.message}
```

## Excepciones

```python
# Direccion invalida (400)
raise InvalidAddressError(
    message="La direccion es muy corta",
    details={"address": "Calle"}
)

# Error de servicio (503)
raise GeocodingServiceError(
    message="Timeout al contactar Nominatim",
    details={"address": "Av O'Higgins 123"}
)
```

## Configuracion (.env)

```bash
GEOCODING_CACHE_TTL=2592000
GEOCODING_RATE_LIMIT_SECONDS=1.0
NOMINATIM_USER_AGENT="ClaudeBotilleria/1.0 (contact@botilleria.cl)"
NOMINATIM_BASE_URL="https://nominatim.openstreetmap.org/search"

RANCAGUA_BBOX_WEST=-70.85
RANCAGUA_BBOX_EAST=-70.65
RANCAGUA_BBOX_SOUTH=-34.25
RANCAGUA_BBOX_NORTH=-34.05
```

## Bounding Box Rancagua

```python
service.bbox_north  # -34.05
service.bbox_south  # -34.25
service.bbox_east   # -70.65
service.bbox_west   # -70.85

# Validar coordenadas
is_inside = service._validate_coordinates(lat, lon)
```

## Rate Limiting

- **Politica:** 1 request/segundo (Nominatim requirement)
- **Cache hits:** No afectados por rate limiting
- **Implementacion:** Sleep automatico entre requests

## Mensajes de Error Comunes

```python
# Direccion muy corta
"La direccion es demasiado corta. Por favor proporcione direccion completa..."

# Falta numero
"La direccion debe incluir un numero de calle. Ejemplo: 'Av O'Higgins 123'"

# Muy generica
"'Centro' es demasiado generico. Por favor proporcione una direccion especifica..."

# Baja confianza
"La direccion proporcionada es demasiado ambigua para entregas precisas..."

# No encontrada
"No se encontro la direccion 'Calle Inexistente' en Rancagua..."

# Fuera de area
"La direccion geocodificada esta fuera del area de servicio de Rancagua."
```

## Testing

```bash
# Todos los tests
pytest tests/test_services/test_geocoding_service.py -v

# Test especifico
pytest tests/test_services/test_geocoding_service.py::test_name -v

# Test de integracion (manual)
pytest tests/test_services/test_geocoding_service.py::test_geocode_real_address_rancagua -v -s
```

## Patrones Comunes

### Pattern 1: Geocodificar con Validacion

```python
def geocode_and_validate(address: str) -> tuple[float, float]:
    """Geocodificar y validar, o lanzar excepcion"""
    service = GeocodingService()
    result = service.geocode_address(address)

    is_valid, error = service.validate_address_quality(result)
    if not is_valid:
        raise InvalidAddressError(error)

    return result.latitude, result.longitude
```

### Pattern 2: Batch Geocoding con Cache

```python
def geocode_batch(addresses: list[str]) -> dict[str, GeocodingResult]:
    """Geocodificar multiples direcciones con cache"""
    cache = InMemoryGeocodingCache(max_size=len(addresses))
    service = GeocodingService(cache_backend=cache)

    results = {}
    for address in addresses:
        results[address] = service.geocode_address(address)

    return results
```

### Pattern 3: Geocoding con Fallback

```python
def geocode_with_fallback(address: str) -> GeocodingResult:
    """Intentar geocodificar, usar default si falla"""
    service = GeocodingService()
    result = service.geocode_address(address)

    if not result.success:
        # Usar coordenadas del centro de Rancagua
        return GeocodingResult(
            success=True,
            latitude=-34.1706,
            longitude=-70.7406,
            confidence=GeocodingConfidence.LOW,
            display_name="Rancagua Centro (fallback)"
        )

    return result
```

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| Lento | Verificar cache hit rate |
| Rate limit errors | Usar Redis cache compartido |
| Muchas rechazadas | Mejorar validacion frontend |
| Cache no funciona | Verificar backend initialization |

## Recursos

- [Documentacion Completa](./GEOCODING_INTEGRATION.md)
- [Ejemplos de Uso](../examples/geocoding_usage_example.py)
- [Nominatim API Docs](https://nominatim.org/release-docs/latest/)
