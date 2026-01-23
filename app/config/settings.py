"""
Application settings using Pydantic Settings
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Claude Logistics API"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, validation_alias="DEBUG")

    # Database
    database_url: str = Field(
        default="postgresql://claude_user:claude_pass@postgres:5432/claude_logistics",
        validation_alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias="REDIS_URL",
    )

    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        validation_alias="SECRET_KEY",
    )

    # JWT Settings
    jwt_secret_key: str = Field(
        default="dev-jwt-secret-key-change-in-production-use-strong-random-key",
        validation_alias="JWT_SECRET_KEY",
        description="Secret key for JWT token signing (must be kept secure)"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
        description="JWT signing algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        description="Access token expiration time in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        validation_alias="REFRESH_TOKEN_EXPIRE_DAYS",
        description="Refresh token expiration time in days"
    )

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        validation_alias="CORS_ORIGINS",
    )

    # Geocoding Settings
    geocoding_cache_ttl: int = Field(
        default=60 * 60 * 24 * 30,  # 30 days
        validation_alias="GEOCODING_CACHE_TTL",
        description="Geocoding cache TTL in seconds"
    )
    geocoding_rate_limit_seconds: float = Field(
        default=1.0,
        validation_alias="GEOCODING_RATE_LIMIT_SECONDS",
        description="Rate limit for Nominatim API (1 req/second)"
    )
    nominatim_user_agent: str = Field(
        default="ClaudeBotilleria/1.0 (contact@botilleria.cl)",
        validation_alias="NOMINATIM_USER_AGENT",
        description="User-Agent header for Nominatim requests"
    )
    nominatim_base_url: str = Field(
        default="https://nominatim.openstreetmap.org/search",
        validation_alias="NOMINATIM_BASE_URL",
        description="Nominatim API base URL"
    )

    # Rancagua Bounding Box (service area)
    rancagua_bbox_west: float = Field(
        default=-70.85,
        validation_alias="RANCAGUA_BBOX_WEST",
        description="Rancagua bounding box - west longitude"
    )
    rancagua_bbox_east: float = Field(
        default=-70.65,
        validation_alias="RANCAGUA_BBOX_EAST",
        description="Rancagua bounding box - east longitude"
    )
    rancagua_bbox_south: float = Field(
        default=-34.25,
        validation_alias="RANCAGUA_BBOX_SOUTH",
        description="Rancagua bounding box - south latitude"
    )
    rancagua_bbox_north: float = Field(
        default=-34.05,
        validation_alias="RANCAGUA_BBOX_NORTH",
        description="Rancagua bounding box - north latitude"
    )

    # Depot (Warehouse) Location
    depot_latitude: float = Field(
        default=-34.1706,
        validation_alias="DEPOT_LATITUDE",
        description="Depot (bodega) latitude - Rancagua centro"
    )
    depot_longitude: float = Field(
        default=-70.7406,
        validation_alias="DEPOT_LONGITUDE",
        description="Depot (bodega) longitude - Rancagua centro"
    )
    depot_name: str = Field(
        default="Bodega Principal - Botillería Rancagua",
        validation_alias="DEPOT_NAME",
        description="Name of the warehouse/depot"
    )

    # Route Optimization Parameters
    average_speed_kmh: float = Field(
        default=30.0,
        validation_alias="AVERAGE_SPEED_KMH",
        description="Average urban speed in Rancagua for route time estimation"
    )
    service_time_per_stop_minutes: int = Field(
        default=5,
        validation_alias="SERVICE_TIME_PER_STOP_MINUTES",
        description="Average time spent per delivery stop in minutes"
    )
    route_optimization_timeout_seconds: int = Field(
        default=30,
        validation_alias="ROUTE_OPTIMIZATION_TIMEOUT_SECONDS",
        description="Maximum time for OR-Tools solver to find solution"
    )

    # SMTP Email Notification Settings
    smtp_host: str = Field(
        default="smtp.gmail.com",
        validation_alias="SMTP_HOST",
        description="SMTP server hostname (e.g., smtp.gmail.com, smtp-mail.outlook.com)"
    )
    smtp_port: int = Field(
        default=587,
        validation_alias="SMTP_PORT",
        description="SMTP server port (587 for TLS/STARTTLS, 465 for SSL)"
    )
    smtp_user: str = Field(
        default="",
        validation_alias="SMTP_USER",
        description="SMTP username (typically your email address)"
    )
    smtp_password: str = Field(
        default="",
        validation_alias="SMTP_PASSWORD",
        description="SMTP password or app-specific password for Gmail/Outlook"
    )
    smtp_from_email: str = Field(
        default="noreply@botilleria-rancagua.cl",
        validation_alias="SMTP_FROM_EMAIL",
        description="From email address displayed in sent emails"
    )
    smtp_from_name: str = Field(
        default="Botillería Rancagua",
        validation_alias="SMTP_FROM_NAME",
        description="From name displayed in sent emails"
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias="SMTP_USE_TLS",
        description="Use TLS encryption (True for port 587, False for port 465 SSL)"
    )
    smtp_timeout: int = Field(
        default=10,
        validation_alias="SMTP_TIMEOUT",
        description="SMTP connection timeout in seconds"
    )

    # Model configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance
    Using lru_cache ensures we only create one instance
    """
    return Settings()
