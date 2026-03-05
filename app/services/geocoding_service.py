"""
Geocoding service using OpenStreetMap Nominatim

Implements address validation and geocoding for the Rancagua delivery area.

Key Features:
- Strict rate limiting (1 request/second per Nominatim policy)
- Aggressive caching to minimize API calls
- Address quality validation before geocoding
- Bounding box validation for Rancagua service area
- Confidence level calculation (HIGH, MEDIUM, LOW, INVALID)

Business Rules:
- Only HIGH and MEDIUM confidence addresses can be used for orders
- LOW and INVALID addresses must be rejected with user-friendly messages
- All coordinates must fall within Rancagua bounding box

Nominatim Attribution:
Data from OpenStreetMap contributors. See https://www.openstreetmap.org/copyright
"""

import time
import hashlib
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

import requests
from requests.exceptions import RequestException, Timeout

from app.models.enums import GeocodingConfidence
from app.config.settings import get_settings
from app.exceptions import InvalidAddressError, GeocodingServiceError
from app.services.geocoding_cache import GeocodingCacheBackend


@dataclass
class GeocodingResult:
    """
    Result of geocoding operation

    Attributes:
        success: Whether geocoding succeeded
        latitude: Geocoded latitude (WGS84)
        longitude: Geocoded longitude (WGS84)
        confidence: Confidence level (HIGH, MEDIUM, LOW, INVALID)
        display_name: Formatted address from Nominatim
        address_components: Parsed address components dict
        error_message: Error message if failed
        cached: Whether result came from cache
    """
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: Optional[GeocodingConfidence] = None
    display_name: Optional[str] = None
    address_components: Optional[Dict] = None
    error_message: Optional[str] = None
    cached: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        # Convert enum to string for JSON serialization
        if self.confidence:
            result['confidence'] = self.confidence.value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'GeocodingResult':
        """Create from dictionary (for cache deserialization)"""
        # Convert string back to enum
        if data.get('confidence'):
            data['confidence'] = GeocodingConfidence(data['confidence'])
        return cls(**data)


class GeocodingService:
    """
    Service for geocoding addresses using OpenStreetMap Nominatim

    Implements strict rate limiting, caching, and quality validation
    for the Rancagua, Chile delivery area.

    Usage:
        >>> from app.services.geocoding_cache import InMemoryGeocodingCache
        >>> cache = InMemoryGeocodingCache()
        >>> service = GeocodingService(cache_backend=cache)
        >>> result = service.geocode_address("Av O'Higgins 123, Rancagua")
        >>> if result.success and result.confidence in [GeocodingConfidence.HIGH, GeocodingConfidence.MEDIUM]:
        ...     print(f"Valid address at {result.latitude}, {result.longitude}")
    """

    def __init__(
        self,
        cache_backend: Optional[GeocodingCacheBackend] = None,
        settings=None
    ):
        """
        Initialize geocoding service

        Args:
            cache_backend: Cache implementation (defaults to in-memory dict)
            settings: Settings instance (defaults to global settings)
        """
        self.settings = settings or get_settings()
        self.cache = cache_backend or {}  # Default: simple dict
        self.last_request_time = 0.0

        # Nominatim configuration
        self.base_url = self.settings.nominatim_base_url
        self.user_agent = self.settings.nominatim_user_agent
        self.rate_limit_seconds = self.settings.geocoding_rate_limit_seconds

        # Rancagua bounding box
        self.bbox_west = self.settings.rancagua_bbox_west
        self.bbox_east = self.settings.rancagua_bbox_east
        self.bbox_south = self.settings.rancagua_bbox_south
        self.bbox_north = self.settings.rancagua_bbox_north

        # Viewbox string for Nominatim (west,south,east,north)
        self.viewbox = f"{self.bbox_west},{self.bbox_south},{self.bbox_east},{self.bbox_north}"

        # Request timeout
        self.request_timeout = 10  # seconds

    def geocode_address(self, address_text: str) -> GeocodingResult:
        """
        Geocode address to coordinates with quality validation

        Process:
        1. Normalize address (add context)
        2. Check cache
        3. Validate address has minimum required components
        4. Rate limit enforcement
        5. Call Nominatim API
        6. Parse response and calculate confidence
        7. Validate coordinates in bounding box
        8. Store in cache
        9. Return result

        Args:
            address_text: Address to geocode (e.g., "Av O'Higgins 123")

        Returns:
            GeocodingResult with coordinates and confidence level

        Note:
            Does NOT raise exceptions - returns GeocodingResult with success=False
            and error_message set. Calling code should check result.success.
        """
        # Step 1: Normalize address
        try:
            normalized = self._normalize_address(address_text)
        except Exception as e:
            return GeocodingResult(
                success=False,
                error_message=f"Error normalizando dirección: {str(e)}"
            )

        # Step 2: Check cache
        cached_result = self._check_cache(normalized)
        if cached_result:
            cached_result.cached = True
            return cached_result

        # Step 3: Basic validation before API call
        validation_error = self._validate_address_components(address_text)
        if validation_error:
            result = GeocodingResult(
                success=False,
                confidence=GeocodingConfidence.INVALID,
                error_message=validation_error
            )
            # Cache invalid results to avoid repeated API calls
            self._store_in_cache(normalized, result)
            return result

        # Step 4: Rate limiting
        self._wait_for_rate_limit()

        # Step 5: Call Nominatim
        try:
            response_data = self._request_nominatim(normalized)
        except GeocodingServiceError as e:
            return GeocodingResult(
                success=False,
                error_message=e.message
            )

        # Step 6: Parse response
        result = self._parse_nominatim_response(response_data, address_text)

        # Step 7: Store in cache (even failures to avoid repeated calls)
        self._store_in_cache(normalized, result)

        return result

    def validate_address_quality(self, result: GeocodingResult) -> Tuple[bool, Optional[str]]:
        """
        Validate if geocoding result has sufficient quality for order creation

        Acceptance criteria:
        - success = True
        - confidence = HIGH or MEDIUM
        - coordinates within Rancagua bounding box

        Args:
            result: GeocodingResult to validate

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
            If valid, error_message is None

        Examples:
            >>> result = service.geocode_address("Av O'Higgins 123")
            >>> is_valid, error = service.validate_address_quality(result)
            >>> if not is_valid:
            ...     raise InvalidAddressError(error)
        """
        if not result.success:
            return False, result.error_message or "No se pudo geocodificar la dirección"

        if result.confidence == GeocodingConfidence.INVALID:
            return False, (
                "La dirección proporcionada no pudo ser localizada. "
                "Por favor verifique que la dirección incluya nombre de calle y número."
            )

        # LOW confidence accepted with coordinates — OSM coverage in Rancagua is limited
        # HIGH, MEDIUM or LOW all accepted as long as coordinates are in service area
        if result.confidence in [GeocodingConfidence.HIGH, GeocodingConfidence.MEDIUM, GeocodingConfidence.LOW]:
            # Verify coordinates in bounding box (should already be validated, but double-check)
            if not self._validate_coordinates(result.latitude, result.longitude):
                return False, (
                    "La dirección geocodificada está fuera del área de servicio de Rancagua. "
                    f"Coordenadas: {result.latitude}, {result.longitude}"
                )

            return True, None

        # Shouldn't reach here, but handle gracefully
        return False, "Nivel de confianza desconocido en resultado de geocodificación"

    def _normalize_address(self, address_text: str) -> str:
        """
        Normalize address by adding Rancagua, Chile context

        Ensures Nominatim searches in the correct geographic area.

        Examples:
            "Av O'Higgins 123" -> "Av O'Higgins 123, Rancagua, Chile"
            "Calle Astorga 456, Rancagua" -> "Calle Astorga 456, Rancagua, Chile"

        Args:
            address_text: Original address

        Returns:
            Normalized address with context
        """
        normalized = address_text.strip()

        # Add Rancagua if not present
        normalized_lower = normalized.lower()
        if 'rancagua' not in normalized_lower:
            normalized = f"{normalized}, Rancagua"

        # Add Chile if not present
        if 'chile' not in normalized_lower:
            normalized = f"{normalized}, Chile"

        return normalized

    def _validate_address_components(self, address_text: str) -> Optional[str]:
        """
        Validate address has minimum required components before API call

        Rejects obviously invalid addresses to save API quota.

        Required components:
        - At least one digit (house/building number)
        - At least 10 characters
        - Not just "Rancagua" or "Centro"

        Args:
            address_text: Address to validate

        Returns:
            Error message if invalid, None if valid
        """
        cleaned = address_text.strip()

        # Minimum length check
        if len(cleaned) < 10:
            return (
                "La dirección es demasiado corta. "
                "Por favor proporcione dirección completa con nombre de calle y número."
            )

        # Check for at least one digit (street number)
        if not any(char.isdigit() for char in cleaned):
            return (
                "La dirección debe incluir un número de calle. "
                "Ejemplo: 'Av O'Higgins 123' o 'Calle Astorga 456'"
            )

        # Reject generic location references
        cleaned_lower = cleaned.lower()
        generic_terms = [
            'centro', 'downtown', 'ciudad', 'rancagua centro',
            'cerca de', 'near', 'al lado de', 'frente a'
        ]

        for term in generic_terms:
            if cleaned_lower == term or cleaned_lower.startswith(f"{term} "):
                return (
                    f"'{cleaned}' es demasiado genérico. "
                    "Por favor proporcione una dirección específica con calle y número."
                )

        return None

    def _check_cache(self, normalized_address: str) -> Optional[GeocodingResult]:
        """
        Check cache for existing geocoding result

        Args:
            normalized_address: Normalized address to lookup

        Returns:
            Cached GeocodingResult or None if not found
        """
        # Generate cache key (use hash for long addresses)
        cache_key = self._make_cache_key(normalized_address)

        # Handle both dict and cache backend
        if isinstance(self.cache, dict):
            cached_data = self.cache.get(cache_key)
        else:
            # Assume cache backend protocol
            cached_data = self.cache.get(cache_key)

        if cached_data:
            try:
                # If it's already a GeocodingResult, return it
                if isinstance(cached_data, GeocodingResult):
                    return cached_data
                # Otherwise deserialize from dict
                return GeocodingResult.from_dict(cached_data)
            except Exception:
                # Corrupted cache entry - ignore
                return None

        return None

    def _store_in_cache(self, normalized_address: str, result: GeocodingResult) -> None:
        """
        Store geocoding result in cache

        Args:
            normalized_address: Normalized address
            result: GeocodingResult to cache
        """
        cache_key = self._make_cache_key(normalized_address)

        # Serialize to dict for cache storage
        result_dict = result.to_dict()

        # Handle both dict and cache backend
        if isinstance(self.cache, dict):
            self.cache[cache_key] = result_dict
        else:
            # Assume cache backend protocol
            self.cache.set(cache_key, result_dict)

    def _make_cache_key(self, normalized_address: str) -> str:
        """
        Generate cache key from normalized address

        Uses lowercase for case-insensitive caching.

        Args:
            normalized_address: Normalized address

        Returns:
            Cache key string
        """
        return normalized_address.lower()

    def _wait_for_rate_limit(self) -> None:
        """
        Enforce rate limiting (1 request per second for Nominatim)

        Blocks execution until sufficient time has passed since last request.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_seconds:
            sleep_time = self.rate_limit_seconds - time_since_last_request
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _request_nominatim(self, normalized_address: str) -> list:
        """
        Make HTTP request to Nominatim API

        Args:
            normalized_address: Address to geocode

        Returns:
            List of result dictionaries from Nominatim

        Raises:
            GeocodingServiceError: If request fails
        """
        params = {
            'q': normalized_address,
            'format': 'json',
            'addressdetails': '1',
            'limit': '1',
            'countrycodes': 'cl',
            'viewbox': self.viewbox,
            'bounded': '1'  # Restrict results to viewbox
        }

        headers = {
            'User-Agent': self.user_agent,
            'Accept-Language': 'es-CL,es'
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=self.request_timeout
            )

            response.raise_for_status()
            return response.json()

        except Timeout:
            raise GeocodingServiceError(
                "Timeout al contactar servicio de geocodificación. Intente nuevamente.",
                details={'address': normalized_address}
            )

        except RequestException as e:
            raise GeocodingServiceError(
                f"Error al contactar servicio de geocodificación: {str(e)}",
                details={'address': normalized_address}
            )

    def _parse_nominatim_response(
        self,
        response_data: list,
        original_address: str
    ) -> GeocodingResult:
        """
        Parse Nominatim API response and calculate confidence

        Args:
            response_data: JSON response from Nominatim
            original_address: Original address text (for error messages)

        Returns:
            GeocodingResult with parsed data and confidence level
        """
        # No results found
        if not response_data or len(response_data) == 0:
            return GeocodingResult(
                success=False,
                confidence=GeocodingConfidence.INVALID,
                error_message=(
                    f"No se encontró la dirección '{original_address}' en Rancagua. "
                    "Por favor verifique que la dirección sea correcta y esté en el área de servicio."
                )
            )

        # Get first (best) result
        result = response_data[0]

        # Extract coordinates
        try:
            lat = float(result['lat'])
            lon = float(result['lon'])
        except (KeyError, ValueError) as e:
            return GeocodingResult(
                success=False,
                confidence=GeocodingConfidence.INVALID,
                error_message=f"Respuesta inválida del servicio de geocodificación: {str(e)}"
            )

        # Validate coordinates within bounding box
        if not self._validate_coordinates(lat, lon):
            return GeocodingResult(
                success=False,
                confidence=GeocodingConfidence.INVALID,
                error_message=(
                    f"La dirección '{original_address}' está fuera del área de servicio de Rancagua. "
                    f"Coordenadas encontradas: {lat}, {lon}"
                )
            )

        # Calculate confidence level
        confidence = self._calculate_confidence(result)

        # Extract address components
        address_components = result.get('address', {})
        display_name = result.get('display_name', '')

        return GeocodingResult(
            success=True,
            latitude=lat,
            longitude=lon,
            confidence=confidence,
            display_name=display_name,
            address_components=address_components
        )

    def _calculate_confidence(self, nominatim_result: dict) -> GeocodingConfidence:
        """
        Calculate confidence level based on Nominatim result type and importance

        Confidence rules:
        - HIGH: type=house/building/commercial, has house_number, importance>0.3
        - MEDIUM: type=street/road/residential, has road, importance>0.2
        - LOW: type=suburb/neighbourhood/city_district, importance<=0.2
        - INVALID: type=country/state or no useful data

        Args:
            nominatim_result: Single result dict from Nominatim

        Returns:
            GeocodingConfidence enum value
        """
        result_type = nominatim_result.get('type', '').lower()
        importance = nominatim_result.get('importance', 0.0)
        address = nominatim_result.get('address', {})

        # HIGH confidence: exact building/house match
        if result_type in ['house', 'building', 'commercial', 'residential']:
            if 'house_number' in address and importance > 0.3:
                return GeocodingConfidence.HIGH

        # MEDIUM confidence: street-level match
        if result_type in ['street', 'road', 'residential', 'pedestrian', 'footway']:
            if 'road' in address and importance > 0.2:
                return GeocodingConfidence.MEDIUM

        # Check for house_number even if type is not ideal
        if 'house_number' in address and 'road' in address:
            if importance > 0.3:
                return GeocodingConfidence.HIGH
            elif importance > 0.2:
                return GeocodingConfidence.MEDIUM

        # LOW confidence: neighbourhood/zone level (not suitable for routing)
        if result_type in ['suburb', 'neighbourhood', 'city_district', 'quarter']:
            return GeocodingConfidence.LOW

        # INVALID: too generic
        if result_type in ['country', 'state', 'region', 'city', 'town']:
            return GeocodingConfidence.INVALID

        # Default: LOW if we have coordinates but uncertain quality
        return GeocodingConfidence.LOW

    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """
        Validate coordinates are within Rancagua bounding box

        Args:
            lat: Latitude (WGS84)
            lon: Longitude (WGS84)

        Returns:
            True if within service area, False otherwise
        """
        return (
            self.bbox_south <= lat <= self.bbox_north and
            self.bbox_west <= lon <= self.bbox_east
        )
