"""
Ejemplos de uso del servicio de geocodificacion

Este archivo demuestra como usar el GeocodingService y sus componentes
en diferentes escenarios del sistema de logistica.
"""

from app.services.geocoding_service import GeocodingService, GeocodingResult
from app.services.geocoding_cache import (
    InMemoryGeocodingCache,
    RedisGeocodingCache,
    create_geocoding_cache
)
from app.models.enums import GeocodingConfidence
from app.exceptions import InvalidAddressError


# ============================================================================
# EJEMPLO 1: Uso Basico - Geocodificar una direccion
# ============================================================================

def ejemplo_basico():
    """Geocodificacion simple de una direccion"""
    print("\n=== EJEMPLO 1: Uso Basico ===\n")

    # Crear servicio (usa cache en memoria por defecto)
    service = GeocodingService()

    # Geocodificar direccion
    result = service.geocode_address("Av O'Higgins 123, Rancagua")

    # Verificar resultado
    if result.success:
        print(f"✓ Geocodificacion exitosa")
        print(f"  Latitud: {result.latitude}")
        print(f"  Longitud: {result.longitude}")
        print(f"  Confianza: {result.confidence.value}")
        print(f"  Direccion formateada: {result.display_name}")
        print(f"  En cache: {result.cached}")
    else:
        print(f"✗ Error: {result.error_message}")


# ============================================================================
# EJEMPLO 2: Validacion de Calidad de Direccion
# ============================================================================

def ejemplo_validacion_calidad():
    """Validar si una direccion tiene calidad suficiente para pedidos"""
    print("\n=== EJEMPLO 2: Validacion de Calidad ===\n")

    service = GeocodingService()

    # Probar diferentes direcciones
    direcciones = [
        "Av O'Higgins 123, Rancagua",      # HIGH - aceptada
        "Calle Astorga 456, Rancagua",     # MEDIUM - aceptada
        "Centro, Rancagua",                # LOW - rechazada
        "Rancagua"                         # INVALID - rechazada
    ]

    for direccion in direcciones:
        print(f"\nDireccion: {direccion}")

        result = service.geocode_address(direccion)
        is_valid, error = service.validate_address_quality(result)

        if is_valid:
            print(f"  ✓ ACEPTADA (Confianza: {result.confidence.value})")
        else:
            print(f"  ✗ RECHAZADA")
            print(f"     Razon: {error}")


# ============================================================================
# EJEMPLO 3: Uso con Cache en Memoria
# ============================================================================

def ejemplo_cache_memoria():
    """Demostrar cache LRU en memoria"""
    print("\n=== EJEMPLO 3: Cache en Memoria ===\n")

    # Crear cache con maximo 100 entradas
    cache = InMemoryGeocodingCache(max_size=100)
    service = GeocodingService(cache_backend=cache)

    # Primera llamada - cache miss
    print("Primera llamada (cache miss):")
    result1 = service.geocode_address("Av O'Higgins 123, Rancagua")
    print(f"  Cached: {result1.cached}")

    # Segunda llamada - cache hit
    print("\nSegunda llamada (cache hit):")
    result2 = service.geocode_address("Av O'Higgins 123, Rancagua")
    print(f"  Cached: {result2.cached}")

    # Verificar tamaño de cache
    print(f"\nEntradas en cache: {cache.size()}")


# ============================================================================
# EJEMPLO 4: Uso con Cache Redis (Produccion)
# ============================================================================

def ejemplo_cache_redis():
    """Demostrar cache Redis para produccion"""
    print("\n=== EJEMPLO 4: Cache Redis ===\n")

    try:
        # Usar factory para crear cache Redis
        cache = create_geocoding_cache(
            cache_type="redis",
            redis_url="redis://localhost:6379/0",
            ttl_seconds=60 * 60 * 24 * 30  # 30 dias
        )

        service = GeocodingService(cache_backend=cache)

        # Geocodificar
        result = service.geocode_address("Av Brasil 1025, Rancagua")

        if result.success:
            print(f"✓ Geocodificacion exitosa")
            print(f"  Cached: {result.cached}")
            print(f"  Confianza: {result.confidence.value}")
        else:
            print(f"✗ Error: {result.error_message}")

    except ImportError:
        print("Redis no disponible. Instalar con: pip install redis")
    except Exception as e:
        print(f"Error conectando a Redis: {e}")


# ============================================================================
# EJEMPLO 5: Manejo de Errores
# ============================================================================

def ejemplo_manejo_errores():
    """Demostrar manejo de diferentes tipos de errores"""
    print("\n=== EJEMPLO 5: Manejo de Errores ===\n")

    service = GeocodingService()

    # Casos de error comunes
    test_cases = [
        ("Calle", "Direccion muy corta"),
        ("Centro", "Direccion muy generica"),
        ("Av O'Higgins sin numero", "Falta numero de calle"),
        ("Calle Inexistente 99999, Rancagua", "Direccion no encontrada"),
        ("Av O'Higgins 123, Santiago", "Fuera del area de servicio")
    ]

    for direccion, caso in test_cases:
        print(f"\nCaso: {caso}")
        print(f"  Direccion: {direccion}")

        result = service.geocode_address(direccion)

        if result.success:
            print(f"  ✓ Geocodificada (Confianza: {result.confidence.value})")
        else:
            print(f"  ✗ Error: {result.error_message[:80]}...")


# ============================================================================
# EJEMPLO 6: Integracion con OrderService
# ============================================================================

def ejemplo_order_service_integration(db_session, user):
    """Demostrar como se usa en OrderService"""
    print("\n=== EJEMPLO 6: Integracion OrderService ===\n")

    from app.services.order_service import OrderService
    from app.models.enums import SourceChannel

    # Crear OrderService (integra GeocodingService automaticamente)
    order_service = OrderService(db=db_session)

    try:
        # Crear pedido - geocodificacion automatica
        order = order_service.create_order(
            customer_name="Juan Perez",
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=user
        )

        print(f"✓ Pedido creado: {order.order_number}")
        print(f"  Coordenadas: {order.address_coordinates}")
        print(f"  Confianza: {order.geocoding_confidence.value}")

    except InvalidAddressError as e:
        # Direccion rechazada - mensaje user-friendly
        print(f"✗ Direccion invalida: {e.message}")
        print(f"  Detalles: {e.details}")


# ============================================================================
# EJEMPLO 7: Verificar Bounding Box de Rancagua
# ============================================================================

def ejemplo_bounding_box():
    """Verificar si coordenadas estan en el area de servicio"""
    print("\n=== EJEMPLO 7: Validacion Bounding Box ===\n")

    service = GeocodingService()

    # Coordenadas de prueba
    test_coords = [
        (-34.1706, -70.7406, "Centro Rancagua"),
        (-34.15, -70.75, "Dentro de Rancagua"),
        (-33.4489, -70.6693, "Santiago (fuera)"),
        (-34.30, -70.90, "Fuera del area")
    ]

    print(f"Bounding Box Rancagua:")
    print(f"  Norte: {service.bbox_north}")
    print(f"  Sur: {service.bbox_south}")
    print(f"  Este: {service.bbox_east}")
    print(f"  Oeste: {service.bbox_west}")
    print()

    for lat, lon, descripcion in test_coords:
        is_valid = service._validate_coordinates(lat, lon)
        status = "✓ DENTRO" if is_valid else "✗ FUERA"
        print(f"{status} - {descripcion} ({lat}, {lon})")


# ============================================================================
# EJEMPLO 8: Calculo de Confianza
# ============================================================================

def ejemplo_calculo_confianza():
    """Demostrar como se calcula el nivel de confianza"""
    print("\n=== EJEMPLO 8: Calculo de Confianza ===\n")

    service = GeocodingService()

    # Simular respuestas de Nominatim
    test_results = [
        {
            "type": "house",
            "importance": 0.5,
            "address": {"house_number": "123", "road": "Av O'Higgins"},
            "descripcion": "Casa con numero"
        },
        {
            "type": "street",
            "importance": 0.25,
            "address": {"road": "Calle Astorga"},
            "descripcion": "Nivel de calle"
        },
        {
            "type": "suburb",
            "importance": 0.15,
            "address": {"suburb": "Centro"},
            "descripcion": "Nivel de barrio"
        },
        {
            "type": "country",
            "importance": 0.1,
            "address": {"country": "Chile"},
            "descripcion": "Nivel de pais"
        }
    ]

    for result in test_results:
        confidence = service._calculate_confidence(result)
        print(f"{confidence.value:8} - {result['descripcion']}")


# ============================================================================
# EJEMPLO 9: Normalizacion de Direcciones
# ============================================================================

def ejemplo_normalizacion():
    """Demostrar normalizacion automatica de direcciones"""
    print("\n=== EJEMPLO 9: Normalizacion de Direcciones ===\n")

    service = GeocodingService()

    # Direcciones sin contexto completo
    test_addresses = [
        "Av O'Higgins 123",
        "Calle Astorga 456, Rancagua",
        "Av Brasil 1025, Rancagua, Chile"
    ]

    print("Normalizacion automatica (añade Rancagua, Chile):\n")

    for address in test_addresses:
        normalized = service._normalize_address(address)
        print(f"Original:    {address}")
        print(f"Normalizada: {normalized}")
        print()


# ============================================================================
# EJEMPLO 10: Performance y Rate Limiting
# ============================================================================

def ejemplo_performance():
    """Demostrar impacto de cache y rate limiting"""
    print("\n=== EJEMPLO 10: Performance ===\n")

    import time

    service = GeocodingService()

    direcciones = [
        "Av O'Higgins 123, Rancagua",
        "Calle Astorga 456, Rancagua",
        "Av O'Higgins 123, Rancagua",  # Repetida - cache hit
    ]

    print("Geocodificando 3 direcciones (1 repetida)...")
    print("Rate limit: 1 request/segundo\n")

    start_time = time.time()

    for i, direccion in enumerate(direcciones, 1):
        request_start = time.time()
        result = service.geocode_address(direccion)
        request_time = time.time() - request_start

        cache_status = "CACHE HIT" if result.cached else "API CALL"
        print(f"{i}. {cache_status:10} - {request_time:.3f}s - {direccion[:30]}...")

    total_time = time.time() - start_time
    print(f"\nTiempo total: {total_time:.2f}s")
    print(f"Sin cache: ~{len(direcciones)}s (rate limiting)")


# ============================================================================
# Ejecutar ejemplos
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EJEMPLOS DE USO - SERVICIO DE GEOCODIFICACION")
    print("=" * 80)

    # Ejecutar ejemplos que no requieren DB
    ejemplo_basico()
    ejemplo_validacion_calidad()
    ejemplo_cache_memoria()
    # ejemplo_cache_redis()  # Descomentar si Redis disponible
    ejemplo_manejo_errores()
    ejemplo_bounding_box()
    ejemplo_calculo_confianza()
    ejemplo_normalizacion()
    # ejemplo_performance()  # Descomentar para test de performance

    # Ejemplos que requieren DB session
    # ejemplo_order_service_integration(db_session, user)

    print("\n" + "=" * 80)
    print("FIN DE EJEMPLOS")
    print("=" * 80)
