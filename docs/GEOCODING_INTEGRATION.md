# Geocoding Integration Documentation

## Overview

This document describes the implementation of FASE 3: Address Validation and Geocoding using OpenStreetMap Nominatim API for the Claude Logistics system serving Rancagua, Chile.

## Table of Contents

- [Architecture](#architecture)
- [Components](#components)
- [Nominatim API Integration](#nominatim-api-integration)
- [Confidence Levels](#confidence-levels)
- [Rancagua Bounding Box](#rancagua-bounding-box)
- [Caching Strategy](#caching-strategy)
- [Rate Limiting](#rate-limiting)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Architecture

### Components

The geocoding system consists of three main components:

1. **GeocodingService** (`app/services/geocoding_service.py`)
   - Core service for address validation and geocoding
   - Integrates with Nominatim API
   - Implements rate limiting and quality validation

2. **GeocodingCache** (`app/services/geocoding_cache.py`)
   - Provides caching backends (Redis and in-memory)
   - Implements LRU eviction for in-memory cache
   - Supports TTL-based expiration for Redis

3. **OrderService Integration** (`app/services/order_service.py`)
   - Geocodes addresses during order creation
   - Validates address quality before allowing order
   - Stores coordinates in PostGIS format

### Data Flow

```
User creates order
    |
    v
OrderService.create_order()
    |
    v
GeocodingService.geocode_address()
    |
    +---> Check cache
    |     |
    |     +---> Cache hit? Return cached result
    |     |
    |     +---> Cache miss? Continue...
    |
    +---> Validate address components (local)
    |     |
    |     +---> Invalid? Return error result
    |     |
    |     +---> Valid? Continue...
    |
    +---> Rate limiting (1 req/s)
    |
    +---> Call Nominatim API
    |
    +---> Parse response
    |
    +---> Calculate confidence (HIGH/MEDIUM/LOW/INVALID)
    |
    +---> Validate coordinates in bounding box
    |
    +---> Store in cache
    |
    v
GeocodingResult
    |
    v
OrderService validates quality
    |
    +---> HIGH or MEDIUM? Accept order
    |
    +---> LOW or INVALID? Reject with user-friendly message
```

---

## Nominatim API Integration

### Endpoint

```
https://nominatim.openstreetmap.org/search
```

### Request Parameters

```python
params = {
    'q': 'Av O\'Higgins 123, Rancagua, Chile',  # Normalized address
    'format': 'json',
    'addressdetails': '1',          # Include address components
    'limit': '1',                   # Only best result
    'countrycodes': 'cl',           # Restrict to Chile
    'viewbox': '-70.85,-34.25,-70.65,-34.05',  # Rancagua bounding box
    'bounded': '1'                  # Restrict to viewbox
}

headers = {
    'User-Agent': 'ClaudeBotilleria/1.0 (contact@botilleria.cl)',
    'Accept-Language': 'es-CL,es'
}
```

### Response Example

```json
[
  {
    "place_id": 123456,
    "lat": "-34.1706",
    "lon": "-70.7406",
    "display_name": "123, Avenida Libertador Bernardo O'Higgins, Rancagua, Chile",
    "address": {
      "house_number": "123",
      "road": "Avenida Libertador Bernardo O'Higgins",
      "city": "Rancagua",
      "state": "Región del Libertador General Bernardo O'Higgins",
      "country": "Chile",
      "country_code": "cl"
    },
    "type": "house",
    "importance": 0.5,
    "boundingbox": ["-34.1711", "-34.1701", "-70.7411", "-70.7401"]
  }
]
```

### Attribution

Data from OpenStreetMap contributors.
License: Open Database License (ODbL)
See: https://www.openstreetmap.org/copyright

---

## Confidence Levels

The system calculates four confidence levels based on Nominatim response:

### HIGH Confidence

**Criteria:**
- `type` = "house", "building", "commercial"
- Has `house_number` in address components
- `importance` > 0.3
- Coordinates within Rancagua bounding box

**Business Impact:**
- Accepted for order creation
- Suitable for precise routing
- High delivery success probability

**Example:**
```
Address: "Av O'Higgins 123, Rancagua"
→ Geocodes to exact building location
→ Confidence: HIGH
→ Result: Order accepted
```

### MEDIUM Confidence

**Criteria:**
- `type` = "street", "road", "residential"
- Has `road` in address components
- `importance` > 0.2
- Coordinates within Rancagua bounding box

**Business Impact:**
- Accepted for order creation
- Street-level accuracy (interpolated)
- Acceptable delivery precision

**Example:**
```
Address: "Calle Astorga 456, Rancagua"
→ Geocodes to street segment
→ Confidence: MEDIUM
→ Result: Order accepted
```

### LOW Confidence

**Criteria:**
- `type` = "suburb", "neighbourhood", "city_district"
- Only has `suburb` or `city` in address
- `importance` ≤ 0.2

**Business Impact:**
- **REJECTED** for order creation
- Too ambiguous for routing
- Requires customer to provide specific address

**Example:**
```
Address: "Centro, Rancagua"
→ Geocodes to neighborhood center
→ Confidence: LOW
→ Result: Order REJECTED with message:
   "La dirección proporcionada es demasiado ambigua para entregas precisas.
    Por favor incluya el número de calle específico."
```

### INVALID Confidence

**Criteria:**
- No results from Nominatim
- `type` = "country", "state" (too generic)
- Coordinates outside Rancagua bounding box
- Missing required address components

**Business Impact:**
- **REJECTED** for order creation
- Address cannot be geocoded
- Requires customer to verify address

**Example:**
```
Address: "Rancagua"
→ Too generic, no street information
→ Confidence: INVALID
→ Result: Order REJECTED with message:
   "La dirección proporcionada no pudo ser localizada.
    Por favor verifique que la dirección incluya nombre de calle y número."
```

---

## Rancagua Bounding Box

### Service Area Coordinates

```python
RANCAGUA_BOUNDING_BOX = {
    "west": -70.85,   # Longitud oeste
    "south": -34.25,  # Latitud sur
    "east": -70.65,   # Longitud este
    "north": -34.05   # Latitud norte
}

RANCAGUA_CENTER = {
    "lat": -34.1706,
    "lon": -70.7406
}
```

### Coverage Area

The bounding box includes:
- Rancagua city center
- Machalí
- Graneros
- Peripheral sectors within delivery range

### Validation

All geocoded coordinates MUST fall within this bounding box:

```python
def _validate_coordinates(lat: float, lon: float) -> bool:
    return (
        -34.25 <= lat <= -34.05 and
        -70.85 <= lon <= -70.65
    )
```

Addresses outside the bounding box are rejected:

```
Address: "Av O'Higgins 123, Santiago"
→ Geocodes to Santiago (-33.4489, -70.6693)
→ Outside bounding box
→ Result: REJECTED with message:
   "La dirección geocodificada está fuera del área de servicio de Rancagua."
```

---

## Caching Strategy

### Why Cache?

1. **Minimize API Calls**: Nominatim has strict rate limits (1 req/s)
2. **Improve Performance**: Cache hits are instant (< 1ms vs ~500ms API call)
3. **Reduce Load**: Same addresses geocoded repeatedly (e.g., business addresses)
4. **Cost Savings**: Free tier has usage limits

### Cache Backends

#### In-Memory Cache (Development)

```python
from app.services.geocoding_cache import InMemoryGeocodingCache

cache = InMemoryGeocodingCache(max_size=1000)
service = GeocodingService(cache_backend=cache)
```

**Features:**
- LRU eviction when max_size reached
- Thread-safe for single process
- No external dependencies
- Lost on application restart

**Use Case:** Development, testing, single-worker deployments

#### Redis Cache (Production)

```python
from app.services.geocoding_cache import RedisGeocodingCache
import redis

redis_client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
cache = RedisGeocodingCache(
    redis_client=redis_client,
    ttl_seconds=60 * 60 * 24 * 30,  # 30 days
    key_prefix="geocoding"
)
service = GeocodingService(cache_backend=cache)
```

**Features:**
- Shared across multiple processes/servers
- TTL-based automatic expiration
- Survives application restarts
- Scalable for high-traffic

**Use Case:** Production, multi-worker deployments

### Cache Key Strategy

```python
# Normalized address (lowercase)
cache_key = "av o'higgins 123, rancagua, chile"

# Redis key format
redis_key = "geocoding:av o'higgins 123, rancagua, chile"
```

### Cache Hit Rate Optimization

**Expected Hit Rates:**
- Business addresses: ~90% (frequently ordered)
- Residential addresses: ~60% (repeat customers)
- New addresses: 0% (first time)

**Cache Failures:**
Invalid addresses are also cached to prevent repeated API calls:

```python
# Failed geocoding cached for 30 days
result = GeocodingResult(
    success=False,
    confidence=GeocodingConfidence.INVALID,
    error_message="No se encontró la dirección"
)
cache.set(normalized_address, result.to_dict())
```

---

## Rate Limiting

### Nominatim Policy

**Maximum:** 1 request per second
**Enforcement:** Strict - violators may be blocked

### Implementation

```python
def _wait_for_rate_limit(self) -> None:
    """Enforce 1 request per second"""
    current_time = time.time()
    time_since_last_request = current_time - self.last_request_time

    if time_since_last_request < self.rate_limit_seconds:
        sleep_time = self.rate_limit_seconds - time_since_last_request
        time.sleep(sleep_time)

    self.last_request_time = time.time()
```

### Behavior

- **First request:** Immediate
- **Second request < 1s later:** Sleeps until 1s has passed
- **Cache hits:** No rate limiting (instant)

### Performance Impact

**Without Cache:**
- 100 addresses = ~100 seconds (1 req/s)

**With Cache (60% hit rate):**
- 100 addresses = ~40 seconds (40 API calls)

**Best Practice:**
- Pre-geocode known business addresses
- Use aggressive caching
- Implement address autocomplete to reduce typos

---

## Usage Examples

### Basic Geocoding

```python
from app.services.geocoding_service import GeocodingService

service = GeocodingService()

# Geocode address
result = service.geocode_address("Av O'Higgins 123, Rancagua")

if result.success:
    print(f"Latitude: {result.latitude}")
    print(f"Longitude: {result.longitude}")
    print(f"Confidence: {result.confidence}")
    print(f"Display Name: {result.display_name}")
else:
    print(f"Error: {result.error_message}")
```

### Order Creation with Geocoding

```python
from app.services.order_service import OrderService
from app.exceptions import InvalidAddressError

order_service = OrderService(db)

try:
    order = order_service.create_order(
        customer_name="Juan Pérez",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123",
        source_channel=SourceChannel.WEB,
        user=current_user
    )
    print(f"Order created: {order.order_number}")

except InvalidAddressError as e:
    # User-friendly error message
    print(f"Invalid address: {e.message}")
    # Example: "La dirección proporcionada es demasiado ambigua.
    #           Por favor incluya el número de calle específico."
```

### Validating Address Quality

```python
# Geocode address
result = service.geocode_address("Centro, Rancagua")

# Validate quality
is_valid, error = service.validate_address_quality(result)

if not is_valid:
    raise InvalidAddressError(error)
```

### With Custom Cache

```python
from app.services.geocoding_cache import create_geocoding_cache

# Redis cache
cache = create_geocoding_cache(
    cache_type="redis",
    redis_url="redis://localhost:6379/0",
    ttl_seconds=86400  # 1 day
)

service = GeocodingService(cache_backend=cache)
```

---

## Error Handling

### Exception Hierarchy

```
InvalidAddressError (400)
├─ Address too short
├─ No street number
├─ Too generic (e.g., "Centro")
├─ LOW confidence
└─ INVALID confidence

GeocodingServiceError (503)
├─ Network timeout
├─ API unavailable
└─ Malformed response
```

### User-Friendly Messages

All error messages are in Spanish and provide actionable guidance:

#### Address Too Short
```
"La dirección es demasiado corta.
 Por favor proporcione dirección completa con nombre de calle y número."
```

#### Missing Street Number
```
"La dirección debe incluir un número de calle.
 Ejemplo: 'Av O'Higgins 123' o 'Calle Astorga 456'"
```

#### Too Generic
```
"'Centro' es demasiado genérico.
 Por favor proporcione una dirección específica con calle y número."
```

#### Low Confidence
```
"La dirección proporcionada es demasiado ambigua para entregas precisas.
 Por favor incluya el número de calle específico.
 Dirección detectada: Centro, Rancagua, Chile"
```

#### Not Found
```
"No se encontró la dirección 'Calle Inexistente 99999' en Rancagua.
 Por favor verifique que la dirección sea correcta y esté en el área de servicio."
```

#### Outside Service Area
```
"La dirección geocodificada está fuera del área de servicio de Rancagua.
 Coordenadas: -33.4489, -70.6693"
```

#### Network Error
```
"Timeout al contactar servicio de geocodificación. Intente nuevamente."
```

---

## Testing

### Unit Tests

Run all geocoding tests:

```bash
pytest tests/test_services/test_geocoding_service.py -v
```

### Test Coverage

- Address normalization
- Address component validation
- Coordinate validation (bounding box)
- Confidence level calculation
- Cache hit/miss behavior
- Rate limiting enforcement
- Error handling (network, malformed responses)
- Quality validation

### Integration Test (Manual)

Test with real Nominatim API:

```bash
pytest tests/test_services/test_geocoding_service.py::test_geocode_real_address_rancagua -v -s
```

**Warning:** Only run occasionally to avoid rate limiting.

### Mock Testing

Most tests use mocked Nominatim responses:

```python
@pytest.fixture
def mock_nominatim_response_high_confidence():
    return [{
        "lat": "-34.1706",
        "lon": "-70.7406",
        "display_name": "123, Av O'Higgins, Rancagua, Chile",
        "address": {
            "house_number": "123",
            "road": "Avenida Libertador Bernardo O'Higgins",
            "city": "Rancagua"
        },
        "type": "house",
        "importance": 0.5
    }]

def test_geocode_address_high_confidence(geocoding_service, mock_response):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_response

        result = geocoding_service.geocode_address("Av O'Higgins 123")

        assert result.success is True
        assert result.confidence == GeocodingConfidence.HIGH
```

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Geocoding Settings
GEOCODING_CACHE_TTL=2592000              # 30 days in seconds
GEOCODING_RATE_LIMIT_SECONDS=1.0
NOMINATIM_USER_AGENT="ClaudeBotilleria/1.0 (contact@botilleria.cl)"
NOMINATIM_BASE_URL="https://nominatim.openstreetmap.org/search"

# Rancagua Bounding Box
RANCAGUA_BBOX_WEST=-70.85
RANCAGUA_BBOX_EAST=-70.65
RANCAGUA_BBOX_SOUTH=-34.25
RANCAGUA_BBOX_NORTH=-34.05
```

### Settings Class

Configuration loaded in `app/config/settings.py`:

```python
class Settings(BaseSettings):
    # Geocoding
    geocoding_cache_ttl: int = Field(default=60 * 60 * 24 * 30)
    geocoding_rate_limit_seconds: float = Field(default=1.0)
    nominatim_user_agent: str = Field(default="ClaudeBotilleria/1.0")
    nominatim_base_url: str = Field(default="https://nominatim.openstreetmap.org/search")

    # Rancagua Bounding Box
    rancagua_bbox_west: float = Field(default=-70.85)
    rancagua_bbox_east: float = Field(default=-70.65)
    rancagua_bbox_south: float = Field(default=-34.25)
    rancagua_bbox_north: float = Field(default=-34.05)
```

---

## Troubleshooting

### Issue: Geocoding is slow

**Symptoms:** Requests taking > 2 seconds

**Diagnosis:**
1. Check cache hit rate (should be > 50%)
2. Verify network latency to Nominatim
3. Check rate limiting enforcement

**Solutions:**
- Implement Redis cache for production
- Pre-geocode known business addresses
- Consider address autocomplete to reduce typos

### Issue: Rate limit errors

**Symptoms:** HTTP 429 from Nominatim

**Diagnosis:**
- Multiple workers making simultaneous requests
- Rate limiting not enforced

**Solutions:**
- Use shared Redis cache across workers
- Implement distributed rate limiting (Redis-based)
- Reduce request frequency

### Issue: Many addresses rejected

**Symptoms:** High percentage of LOW/INVALID confidence

**Diagnosis:**
- Customer addresses lack street numbers
- Generic location references ("cerca de", "al frente")

**Solutions:**
- Improve address input validation on frontend
- Implement address autocomplete with Google Places
- Show address validation feedback in real-time

### Issue: Addresses outside bounding box

**Symptoms:** Valid Chilean addresses rejected

**Diagnosis:**
- Bounding box too restrictive
- Customer in peripheral area (Codegua, Doñihue)

**Solutions:**
- Review and expand bounding box if needed
- Add multiple service zones
- Manual override for edge cases

### Issue: Cache not working

**Symptoms:** Every request hits API

**Diagnosis:**
1. Check cache backend initialization
2. Verify cache key generation
3. Check Redis connectivity (if using Redis)

**Solutions:**
- Verify `cache_backend` passed to GeocodingService
- Check Redis connection string
- Review cache logs for errors

### Issue: Foreign addresses accepted

**Symptoms:** Addresses outside Chile geocoded

**Diagnosis:**
- `bounded=1` parameter not enforced
- Bounding box too large

**Solutions:**
- Verify Nominatim request parameters
- Add country code validation (`countrycodes=cl`)
- Validate address components include "Chile"

---

## Future Enhancements

### Phase 4: Distance Calculation
- Use PostGIS ST_Distance for route optimization
- Calculate delivery zones based on distance from warehouse
- Estimate delivery time based on distance

### Phase 5: Address Autocomplete
- Integrate Google Places Autocomplete API
- Pre-validate addresses before submission
- Reduce geocoding errors

### Phase 6: Bulk Geocoding
- Batch geocode historical orders
- Pre-populate cache with common addresses
- Optimize for route planning

### Phase 7: Machine Learning
- Learn from delivery success/failure
- Improve confidence scoring
- Detect address patterns

---

## References

- [OpenStreetMap Nominatim Documentation](https://nominatim.org/release-docs/latest/)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [PostGIS Geography Type](https://postgis.net/docs/geography.html)
- [GeoAlchemy2 Documentation](https://geoalchemy-2.readthedocs.io/)

---

## Change Log

### FASE 3 (2026-01-21)
- Initial implementation
- OpenStreetMap Nominatim integration
- Rate limiting (1 req/s)
- Redis and in-memory caching
- Rancagua bounding box validation
- Confidence level calculation
- Integration with OrderService
- Comprehensive test suite
