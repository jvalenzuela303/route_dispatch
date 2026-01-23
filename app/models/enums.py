"""
Business enums for the Route Dispatch System

This module defines all enumeration types used across the application
to ensure data consistency and type safety.
"""

from enum import Enum as PyEnum


class OrderStatus(str, PyEnum):
    """
    Order lifecycle states

    PENDIENTE: Order just created, awaiting preparation
    EN_PREPARACION: Order being prepared in warehouse (picking)
    DOCUMENTADO: Invoice linked - CRITICAL state that enables routing
    EN_RUTA: Assigned to vehicle and in transit (triggers customer notification)
    ENTREGADO: Delivery confirmed by driver
    INCIDENCIA: Delivery could not be completed
    """
    PENDIENTE = "PENDIENTE"
    EN_PREPARACION = "EN_PREPARACION"
    DOCUMENTADO = "DOCUMENTADO"
    EN_RUTA = "EN_RUTA"
    ENTREGADO = "ENTREGADO"
    INCIDENCIA = "INCIDENCIA"


class SourceChannel(str, PyEnum):
    """
    Sales channels where orders originate

    WEB: Online web platform orders
    RRSS: Social media orders (WhatsApp, Instagram, Facebook)
    PRESENCIAL: In-person orders at physical location
    """
    WEB = "WEB"
    RRSS = "RRSS"
    PRESENCIAL = "PRESENCIAL"


class GeocodingConfidence(str, PyEnum):
    """
    Geocoding quality levels for address validation

    HIGH: Precise coordinates with high confidence (exact address match)
    MEDIUM: Good coordinates but some ambiguity (street-level accuracy)
    LOW: Low confidence coordinates (neighborhood/zone level)
    INVALID: Could not geocode address - requires manual intervention
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INVALID = "INVALID"


class InvoiceType(str, PyEnum):
    """
    Chilean fiscal document types

    FACTURA: Tax invoice (for businesses with RUT)
    BOLETA: Receipt (for individual customers)
    """
    FACTURA = "FACTURA"
    BOLETA = "BOLETA"


class RouteStatus(str, PyEnum):
    """
    Route lifecycle states

    DRAFT: Route being planned, not yet active
    ACTIVE: Route assigned to driver and in progress
    COMPLETED: All deliveries on route completed
    """
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class AuditResult(str, PyEnum):
    """
    Audit log entry results

    SUCCESS: Action completed successfully
    DENIED: Action was denied due to business rules or permissions
    ERROR: Action failed due to technical error
    """
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    ERROR = "ERROR"


class NotificationChannel(str, PyEnum):
    """
    Notification delivery channels

    EMAIL: Email notification via SMTP
    SMS: SMS notification (future implementation)
    WHATSAPP: WhatsApp notification (future implementation)
    PUSH: Push notification for mobile apps (future implementation)
    """
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    PUSH = "PUSH"


class NotificationStatus(str, PyEnum):
    """
    Notification delivery status tracking

    PENDING: Notification queued but not yet sent
    SENT: Successfully delivered to recipient
    FAILED: Failed to deliver after all retry attempts
    """
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
