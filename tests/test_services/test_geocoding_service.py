"""
Tests for GeocodingService

Tests cover:
- Address normalization
- Cache hit/miss behavior
- Rate limiting enforcement
- Nominatim API response parsing
- Confidence level calculation
- Bounding box validation
- Address quality validation
- Error handling
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import Timeout, RequestException

from app.services.geocoding_service import GeocodingService, GeocodingResult
from app.services.geocoding_cache import InMemoryGeocodingCache
from app.models.enums import GeocodingConfidence
from app.exceptions import GeocodingServiceError


@pytest.fixture
def in_memory_cache():
    """Provide fresh in-memory cache for each test"""
    return InMemoryGeocodingCache(max_size=100)


@pytest.fixture
def geocoding_service(in_memory_cache):
    """Provide GeocodingService with in-memory cache"""
    return GeocodingService(cache_backend=in_memory_cache)


@pytest.fixture
def mock_nominatim_response_high_confidence():
    """
    Mock Nominatim response for high-confidence address
    (exact house number match)
    """
    return [{
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
        "importance": 0.5
    }]


@pytest.fixture
def mock_nominatim_response_medium_confidence():
    """
    Mock Nominatim response for medium-confidence address
    (street-level, no exact house number)
    """
    return [{
        "place_id": 123457,
        "lat": "-34.1710",
        "lon": "-70.7410",
        "display_name": "Calle Astorga, Rancagua, Chile",
        "address": {
            "road": "Calle Astorga",
            "city": "Rancagua",
            "state": "Región del Libertador General Bernardo O'Higgins",
            "country": "Chile",
            "country_code": "cl"
        },
        "type": "street",
        "importance": 0.25
    }]


@pytest.fixture
def mock_nominatim_response_low_confidence():
    """
    Mock Nominatim response for low-confidence address
    (neighbourhood level only)
    """
    return [{
        "place_id": 123458,
        "lat": "-34.1700",
        "lon": "-70.7400",
        "display_name": "Centro, Rancagua, Chile",
        "address": {
            "suburb": "Centro",
            "city": "Rancagua",
            "state": "Región del Libertador General Bernardo O'Higgins",
            "country": "Chile",
            "country_code": "cl"
        },
        "type": "suburb",
        "importance": 0.15
    }]


@pytest.fixture
def mock_nominatim_response_outside_bbox():
    """
    Mock Nominatim response for address outside Rancagua bounding box
    (Santiago coordinates)
    """
    return [{
        "place_id": 999999,
        "lat": "-33.4489",  # Santiago latitude
        "lon": "-70.6693",  # Santiago longitude
        "display_name": "Av O'Higgins 123, Santiago, Chile",
        "address": {
            "house_number": "123",
            "road": "Avenida O'Higgins",
            "city": "Santiago",
            "country": "Chile"
        },
        "type": "house",
        "importance": 0.6
    }]


# ============================================================================
# Address Normalization Tests
# ============================================================================

def test_normalize_address_adds_rancagua(geocoding_service):
    """Address without 'Rancagua' gets it added"""
    result = geocoding_service._normalize_address("Av O'Higgins 123")
    assert "Rancagua" in result
    assert "Chile" in result


def test_normalize_address_adds_chile(geocoding_service):
    """Address without 'Chile' gets it added"""
    result = geocoding_service._normalize_address("Av O'Higgins 123, Rancagua")
    assert "Chile" in result


def test_normalize_address_preserves_existing_context(geocoding_service):
    """Address with Rancagua and Chile is not duplicated"""
    original = "Av O'Higgins 123, Rancagua, Chile"
    result = geocoding_service._normalize_address(original)
    # Should not have duplicate "Rancagua" or "Chile"
    assert result.count("Rancagua") == 1
    assert result.count("Chile") == 1


# ============================================================================
# Address Component Validation Tests
# ============================================================================

def test_validate_address_components_valid_address(geocoding_service):
    """Valid address with street number passes validation"""
    error = geocoding_service._validate_address_components("Av O'Higgins 123")
    assert error is None


def test_validate_address_components_too_short(geocoding_service):
    """Address shorter than 10 characters is rejected"""
    error = geocoding_service._validate_address_components("Calle 1")
    assert error is not None
    assert "demasiado corta" in error.lower()


def test_validate_address_components_no_number(geocoding_service):
    """Address without street number is rejected"""
    error = geocoding_service._validate_address_components("Avenida O'Higgins sin numero")
    assert error is not None
    assert "número de calle" in error.lower()


def test_validate_address_components_generic_location(geocoding_service):
    """Generic locations like 'Centro' are rejected"""
    error = geocoding_service._validate_address_components("Centro")
    assert error is not None
    assert "demasiado genérico" in error.lower()


def test_validate_address_components_relative_reference(geocoding_service):
    """Relative references like 'cerca de' are rejected"""
    error = geocoding_service._validate_address_components("cerca de la plaza")
    assert error is not None
    assert "demasiado genérico" in error.lower()


# ============================================================================
# Coordinate Validation Tests
# ============================================================================

def test_validate_coordinates_inside_bbox(geocoding_service):
    """Coordinates inside Rancagua bounding box are valid"""
    # Center of Rancagua
    assert geocoding_service._validate_coordinates(-34.1706, -70.7406) is True


def test_validate_coordinates_outside_bbox_north(geocoding_service):
    """Coordinates north of bounding box are invalid"""
    assert geocoding_service._validate_coordinates(-34.0, -70.7406) is False


def test_validate_coordinates_outside_bbox_south(geocoding_service):
    """Coordinates south of bounding box are invalid"""
    assert geocoding_service._validate_coordinates(-34.3, -70.7406) is False


def test_validate_coordinates_outside_bbox_east(geocoding_service):
    """Coordinates east of bounding box are invalid"""
    assert geocoding_service._validate_coordinates(-34.1706, -70.6) is False


def test_validate_coordinates_outside_bbox_west(geocoding_service):
    """Coordinates west of bounding box are invalid"""
    assert geocoding_service._validate_coordinates(-34.1706, -70.9) is False


# ============================================================================
# Confidence Level Calculation Tests
# ============================================================================

def test_calculate_confidence_high_with_house_number(geocoding_service):
    """House with number and high importance = HIGH confidence"""
    result = {
        "type": "house",
        "importance": 0.5,
        "address": {
            "house_number": "123",
            "road": "Av O'Higgins"
        }
    }
    confidence = geocoding_service._calculate_confidence(result)
    assert confidence == GeocodingConfidence.HIGH


def test_calculate_confidence_medium_street_level(geocoding_service):
    """Street-level match without house number = MEDIUM confidence"""
    result = {
        "type": "street",
        "importance": 0.25,
        "address": {
            "road": "Calle Astorga"
        }
    }
    confidence = geocoding_service._calculate_confidence(result)
    assert confidence == GeocodingConfidence.MEDIUM


def test_calculate_confidence_low_neighbourhood(geocoding_service):
    """Neighbourhood-level match = LOW confidence"""
    result = {
        "type": "suburb",
        "importance": 0.15,
        "address": {
            "suburb": "Centro"
        }
    }
    confidence = geocoding_service._calculate_confidence(result)
    assert confidence == GeocodingConfidence.LOW


def test_calculate_confidence_invalid_country_level(geocoding_service):
    """Country-level match = INVALID"""
    result = {
        "type": "country",
        "importance": 0.1,
        "address": {
            "country": "Chile"
        }
    }
    confidence = geocoding_service._calculate_confidence(result)
    assert confidence == GeocodingConfidence.INVALID


# ============================================================================
# Geocoding Full Flow Tests
# ============================================================================

def test_geocode_address_high_confidence_success(
    geocoding_service,
    mock_nominatim_response_high_confidence
):
    """Successful geocoding of high-confidence address"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = geocoding_service.geocode_address("Av O'Higgins 123")

        assert result.success is True
        assert result.confidence == GeocodingConfidence.HIGH
        assert result.latitude is not None
        assert result.longitude is not None
        assert -34.20 < result.latitude < -34.10
        assert -70.80 < result.longitude < -70.70
        assert result.display_name is not None


def test_geocode_address_medium_confidence_success(
    geocoding_service,
    mock_nominatim_response_medium_confidence
):
    """Successful geocoding of medium-confidence address"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_medium_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = geocoding_service.geocode_address("Calle Astorga")

        assert result.success is True
        assert result.confidence == GeocodingConfidence.MEDIUM


def test_geocode_address_no_results(geocoding_service):
    """Geocoding with no results returns INVALID"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = []  # Empty results
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = geocoding_service.geocode_address("Calle Inexistente 99999")

        assert result.success is False
        assert result.confidence == GeocodingConfidence.INVALID
        assert "No se encontró" in result.error_message


def test_geocode_address_outside_bounding_box(
    geocoding_service,
    mock_nominatim_response_outside_bbox
):
    """Address outside Rancagua bounding box is rejected"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_outside_bbox
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = geocoding_service.geocode_address("Av O'Higgins 123, Santiago")

        assert result.success is False
        assert result.confidence == GeocodingConfidence.INVALID
        assert "fuera del área de servicio" in result.error_message


def test_geocode_address_invalid_no_number(geocoding_service):
    """Address without number fails validation before API call"""
    result = geocoding_service.geocode_address("Avenida O'Higgins sin numero")

    assert result.success is False
    assert result.confidence == GeocodingConfidence.INVALID
    # Should not have called API (validated locally)
    assert result.error_message is not None


# ============================================================================
# Cache Tests
# ============================================================================

def test_geocode_address_cache_hit(
    geocoding_service,
    mock_nominatim_response_high_confidence
):
    """Second call to same address uses cache, not API"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call - should hit API
        result1 = geocoding_service.geocode_address("Av O'Higgins 123")
        assert result1.success is True
        assert mock_get.call_count == 1

        # Second call - should use cache
        result2 = geocoding_service.geocode_address("Av O'Higgins 123")
        assert result2.success is True
        assert result2.cached is True
        assert mock_get.call_count == 1  # No additional API call


def test_geocode_address_cache_miss_different_address(
    geocoding_service,
    mock_nominatim_response_high_confidence
):
    """Different addresses don't share cache entries"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First address
        result1 = geocoding_service.geocode_address("Av O'Higgins 123")
        assert mock_get.call_count == 1

        # Different address - should make new API call
        result2 = geocoding_service.geocode_address("Av O'Higgins 456")
        assert mock_get.call_count == 2


def test_geocode_address_caches_failures(geocoding_service):
    """Failed geocoding results are also cached"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = []  # No results
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call
        result1 = geocoding_service.geocode_address("Calle Inexistente 99999")
        assert result1.success is False
        assert mock_get.call_count == 1

        # Second call - should use cached failure
        result2 = geocoding_service.geocode_address("Calle Inexistente 99999")
        assert result2.success is False
        assert result2.cached is True
        assert mock_get.call_count == 1


# ============================================================================
# Rate Limiting Tests
# ============================================================================

def test_rate_limiting_enforced(geocoding_service, mock_nominatim_response_high_confidence):
    """Rate limiting ensures minimum 1 second between requests"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Make two requests to different addresses (to avoid cache)
        start_time = time.time()

        geocoding_service.geocode_address("Av O'Higgins 123")
        geocoding_service.geocode_address("Av O'Higgins 456")

        elapsed_time = time.time() - start_time

        # Should take at least 1 second due to rate limiting
        assert elapsed_time >= 1.0


def test_rate_limiting_not_applied_to_cache_hits(
    geocoding_service,
    mock_nominatim_response_high_confidence
):
    """Cache hits don't trigger rate limiting"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # First call
        geocoding_service.geocode_address("Av O'Higgins 123")

        # Second call (cache hit) should be instant
        start_time = time.time()
        result = geocoding_service.geocode_address("Av O'Higgins 123")
        elapsed_time = time.time() - start_time

        assert result.cached is True
        assert elapsed_time < 0.1  # Should be nearly instant


# ============================================================================
# Address Quality Validation Tests
# ============================================================================

def test_validate_address_quality_high_confidence_valid(geocoding_service):
    """HIGH confidence result passes quality validation"""
    result = GeocodingResult(
        success=True,
        latitude=-34.1706,
        longitude=-70.7406,
        confidence=GeocodingConfidence.HIGH,
        display_name="Test Address"
    )

    is_valid, error = geocoding_service.validate_address_quality(result)
    assert is_valid is True
    assert error is None


def test_validate_address_quality_medium_confidence_valid(geocoding_service):
    """MEDIUM confidence result passes quality validation"""
    result = GeocodingResult(
        success=True,
        latitude=-34.1706,
        longitude=-70.7406,
        confidence=GeocodingConfidence.MEDIUM,
        display_name="Test Address"
    )

    is_valid, error = geocoding_service.validate_address_quality(result)
    assert is_valid is True
    assert error is None


def test_validate_address_quality_low_confidence_invalid(geocoding_service):
    """LOW confidence result fails quality validation"""
    result = GeocodingResult(
        success=True,
        latitude=-34.1706,
        longitude=-70.7406,
        confidence=GeocodingConfidence.LOW,
        display_name="Centro, Rancagua"
    )

    is_valid, error = geocoding_service.validate_address_quality(result)
    assert is_valid is False
    assert error is not None
    assert "demasiado ambigua" in error.lower()


def test_validate_address_quality_invalid_confidence(geocoding_service):
    """INVALID confidence result fails quality validation"""
    result = GeocodingResult(
        success=False,
        confidence=GeocodingConfidence.INVALID,
        error_message="No se encontró la dirección"
    )

    is_valid, error = geocoding_service.validate_address_quality(result)
    assert is_valid is False
    assert error is not None


def test_validate_address_quality_failed_geocoding(geocoding_service):
    """Failed geocoding result fails quality validation"""
    result = GeocodingResult(
        success=False,
        error_message="Error de red"
    )

    is_valid, error = geocoding_service.validate_address_quality(result)
    assert is_valid is False
    assert error == "Error de red"


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_geocode_address_network_timeout(geocoding_service):
    """Network timeout returns error result, not exception"""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Timeout("Connection timeout")

        result = geocoding_service.geocode_address("Av O'Higgins 123")

        assert result.success is False
        assert result.error_message is not None
        # Should not raise exception, return error result instead


def test_geocode_address_network_error(geocoding_service):
    """Network error returns error result, not exception"""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = RequestException("Connection failed")

        result = geocoding_service.geocode_address("Av O'Higgins 123")

        assert result.success is False
        assert result.error_message is not None


def test_geocode_address_malformed_response(geocoding_service):
    """Malformed API response is handled gracefully"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        # Missing required fields
        mock_response.json.return_value = [{"invalid": "data"}]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = geocoding_service.geocode_address("Av O'Higgins 123")

        assert result.success is False
        assert result.error_message is not None


# ============================================================================
# Nominatim Request Tests
# ============================================================================

def test_nominatim_request_correct_parameters(
    geocoding_service,
    mock_nominatim_response_high_confidence
):
    """Nominatim request includes all required parameters"""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_nominatim_response_high_confidence
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        geocoding_service.geocode_address("Av O'Higgins 123")

        # Verify request was made with correct parameters
        assert mock_get.called
        call_kwargs = mock_get.call_args[1]

        # Check params
        params = call_kwargs['params']
        assert params['format'] == 'json'
        assert params['addressdetails'] == '1'
        assert params['countrycodes'] == 'cl'
        assert params['bounded'] == '1'
        assert 'viewbox' in params

        # Check headers
        headers = call_kwargs['headers']
        assert 'User-Agent' in headers
        assert 'ClaudeBotilleria' in headers['User-Agent']
        assert headers['Accept-Language'] == 'es-CL,es'


# ============================================================================
# Integration Test (Manual - requires real API)
# ============================================================================

@pytest.mark.skip(reason="Manual test - requires real Nominatim API")
def test_geocode_real_address_rancagua():
    """
    Integration test with real Nominatim API

    Run manually with:
    pytest tests/test_services/test_geocoding_service.py::test_geocode_real_address_rancagua -v -s
    """
    service = GeocodingService()

    # Known address in Rancagua
    result = service.geocode_address("Avenida Brasil 1025, Rancagua")

    print(f"\n--- Real API Test Results ---")
    print(f"Success: {result.success}")
    print(f"Latitude: {result.latitude}")
    print(f"Longitude: {result.longitude}")
    print(f"Confidence: {result.confidence}")
    print(f"Display Name: {result.display_name}")
    print(f"Cached: {result.cached}")

    assert result.success is True
    assert result.latitude is not None

    # Verify coordinates are approximately in Rancagua
    assert -34.20 < result.latitude < -34.10
    assert -70.80 < result.longitude < -70.70

    # Second call should use cache
    result2 = service.geocode_address("Avenida Brasil 1025, Rancagua")
    assert result2.cached is True
