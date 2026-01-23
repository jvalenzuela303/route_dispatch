"""
Geocoding cache implementations

Provides both Redis and in-memory caching backends for geocoding results
to minimize API calls to Nominatim and improve performance.

Cache key format: "geocoding:{normalized_address}"
Cache value: JSON serialized GeocodingResult
"""

import json
from typing import Optional, Protocol
from collections import OrderedDict
from datetime import timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class GeocodingCacheBackend(Protocol):
    """Protocol defining cache backend interface"""

    def get(self, key: str) -> Optional[dict]:
        """Retrieve cached geocoding result"""
        ...

    def set(self, key: str, value: dict) -> None:
        """Store geocoding result in cache"""
        ...

    def delete(self, key: str) -> None:
        """Remove cached geocoding result"""
        ...

    def clear(self) -> None:
        """Clear all cached geocoding results"""
        ...


class InMemoryGeocodingCache:
    """
    In-memory LRU cache for geocoding results

    Uses OrderedDict to implement LRU eviction when max_size is reached.
    Suitable for development and testing environments.

    Features:
    - LRU eviction policy
    - Configurable max size
    - No external dependencies
    - Thread-safe for single-process use

    Limitations:
    - Not shared across multiple processes
    - Lost on application restart
    - Memory usage grows with cache size
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize in-memory cache

        Args:
            max_size: Maximum number of entries to store (default 1000)
        """
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> Optional[dict]:
        """
        Retrieve cached geocoding result

        Args:
            key: Normalized address to lookup

        Returns:
            Cached geocoding result dict or None if not found
        """
        if key in self.cache:
            # Move to end (mark as recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: dict) -> None:
        """
        Store geocoding result in cache

        Implements LRU eviction: if cache is full, removes oldest entry.

        Args:
            key: Normalized address
            value: Geocoding result dict
        """
        # If already exists, update and move to end
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = value
            return

        # Check if cache is full
        if len(self.cache) >= self.max_size:
            # Remove oldest entry (first item)
            self.cache.popitem(last=False)

        # Add new entry
        self.cache[key] = value

    def delete(self, key: str) -> None:
        """
        Remove specific cached result

        Args:
            key: Normalized address to remove
        """
        self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries"""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)


class RedisGeocodingCache:
    """
    Redis-backed cache for geocoding results

    Suitable for production environments with multiple workers.
    Provides shared cache across processes and persistent storage.

    Features:
    - Shared across multiple processes/servers
    - Configurable TTL (time-to-live)
    - Automatic expiration
    - Survives application restarts

    Requirements:
    - Redis server running
    - redis-py library installed
    """

    def __init__(
        self,
        redis_client: 'redis.Redis',
        ttl_seconds: int = 60 * 60 * 24 * 30,  # 30 days default
        key_prefix: str = "geocoding"
    ):
        """
        Initialize Redis cache

        Args:
            redis_client: Connected Redis client instance
            ttl_seconds: Time-to-live for cached entries (default 30 days)
            key_prefix: Prefix for all cache keys (default "geocoding")
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis library not available. "
                "Install with: pip install redis"
            )

        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def _make_key(self, address: str) -> str:
        """
        Create full Redis key with prefix

        Args:
            address: Normalized address

        Returns:
            Full Redis key (e.g., "geocoding:av o'higgins 123, rancagua, chile")
        """
        return f"{self.key_prefix}:{address.lower()}"

    def get(self, key: str) -> Optional[dict]:
        """
        Retrieve cached geocoding result from Redis

        Args:
            key: Normalized address to lookup

        Returns:
            Cached geocoding result dict or None if not found or expired
        """
        redis_key = self._make_key(key)
        data = self.redis.get(redis_key)

        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                # Corrupted cache entry - delete it
                self.redis.delete(redis_key)
                return None

        return None

    def set(self, key: str, value: dict) -> None:
        """
        Store geocoding result in Redis with TTL

        Args:
            key: Normalized address
            value: Geocoding result dict
        """
        redis_key = self._make_key(key)
        serialized = json.dumps(value)

        # Store with expiration
        self.redis.setex(
            redis_key,
            timedelta(seconds=self.ttl_seconds),
            serialized
        )

    def delete(self, key: str) -> None:
        """
        Remove specific cached result from Redis

        Args:
            key: Normalized address to remove
        """
        redis_key = self._make_key(key)
        self.redis.delete(redis_key)

    def clear(self) -> None:
        """
        Clear all geocoding cache entries

        WARNING: This uses SCAN to find all keys with the prefix,
        which can be slow for large datasets.
        """
        pattern = f"{self.key_prefix}:*"
        cursor = 0

        while True:
            cursor, keys = self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )

            if keys:
                self.redis.delete(*keys)

            if cursor == 0:
                break

    def size(self) -> int:
        """
        Get approximate cache size

        WARNING: This uses SCAN which can be slow.
        For monitoring, consider tracking size separately.

        Returns:
            Approximate number of cached entries
        """
        pattern = f"{self.key_prefix}:*"
        count = 0
        cursor = 0

        while True:
            cursor, keys = self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            count += len(keys)

            if cursor == 0:
                break

        return count


def create_geocoding_cache(
    cache_type: str = "memory",
    redis_url: Optional[str] = None,
    **kwargs
) -> GeocodingCacheBackend:
    """
    Factory function to create appropriate cache backend

    Args:
        cache_type: "memory" or "redis"
        redis_url: Redis connection URL (required if cache_type="redis")
        **kwargs: Additional arguments passed to cache constructor

    Returns:
        GeocodingCacheBackend instance

    Raises:
        ValueError: If cache_type is invalid or Redis URL missing

    Examples:
        >>> # In-memory cache for development
        >>> cache = create_geocoding_cache("memory", max_size=500)

        >>> # Redis cache for production
        >>> cache = create_geocoding_cache(
        ...     "redis",
        ...     redis_url="redis://localhost:6379/0",
        ...     ttl_seconds=86400
        ... )
    """
    if cache_type == "memory":
        max_size = kwargs.get("max_size", 1000)
        return InMemoryGeocodingCache(max_size=max_size)

    elif cache_type == "redis":
        if not redis_url:
            raise ValueError("redis_url is required for Redis cache")

        if not REDIS_AVAILABLE:
            raise ImportError(
                "Redis library not available. "
                "Install with: pip install redis"
            )

        redis_client = redis.from_url(redis_url, decode_responses=True)
        ttl_seconds = kwargs.get("ttl_seconds", 60 * 60 * 24 * 30)
        key_prefix = kwargs.get("key_prefix", "geocoding")

        return RedisGeocodingCache(
            redis_client=redis_client,
            ttl_seconds=ttl_seconds,
            key_prefix=key_prefix
        )

    else:
        raise ValueError(
            f"Invalid cache_type '{cache_type}'. "
            f"Must be 'memory' or 'redis'"
        )
