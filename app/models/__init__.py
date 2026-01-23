"""
Database models package

Exports all models and base classes for easy import throughout the application.
"""

from app.models.base import Base, BaseModel, UUIDMixin, TimestampMixin
from app.models.enums import (
    OrderStatus,
    SourceChannel,
    GeocodingConfidence,
    InvoiceType,
    RouteStatus,
    AuditResult,
)
from app.models.models import (
    Role,
    User,
    Order,
    Invoice,
    Route,
    AuditLog,
)

__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "UUIDMixin",
    "TimestampMixin",
    # Enums
    "OrderStatus",
    "SourceChannel",
    "GeocodingConfidence",
    "InvoiceType",
    "RouteStatus",
    "AuditResult",
    # Models
    "Role",
    "User",
    "Order",
    "Invoice",
    "Route",
    "AuditLog",
]
