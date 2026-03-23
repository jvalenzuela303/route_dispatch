"""
SQLAlchemy models for the Route Dispatch System

This module defines all database tables and their relationships for managing
logistics operations including orders, invoices, routes, users, and audit logs.

All models use:
- UUID primary keys for security and scalability
- Timestamp tracking (created_at, updated_at)
- PostGIS Geography types for spatial data
- Proper foreign key constraints and relationships
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Boolean, Text, Enum as SQLEnum, Date, Integer,
    Numeric, ForeignKey, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.models.base import BaseModel, Base, UUIDMixin
from app.models.enums import (
    OrderStatus, SourceChannel, GeocodingConfidence,
    InvoiceType, RouteStatus, AuditResult,
    NotificationChannel, NotificationStatus,
    VehicleStatus, AlertType, GeofenceType, EvidenceType
)


class Role(BaseModel):
    """
    User roles and permissions

    Defines different user types in the system with their associated permissions.
    Permissions are stored as JSONB for flexibility.

    Business Roles:
    - Administrador: Full system access + override capabilities
    - Encargado de Bodega: Generate routes, approve deliveries
    - Vendedor: Create orders, create invoices
    - Repartidor: View assigned routes, update delivery status
    """
    __tablename__ = "roles"

    role_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Role name (e.g., 'Administrador', 'Vendedor')"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of role responsibilities"
    )
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Flexible permissions structure as JSON"
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.role_name}')>"


class User(BaseModel):
    """
    System users

    Represents all users who interact with the system, from administrators
    to delivery drivers. Each user has exactly one role that determines
    their permissions.
    """
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Unique username for login"
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="User email address (also used for login)"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="BCrypt/Argon2 hashed password"
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key to roles table"
    )
    active_status: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether user account is active"
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="users"
    )
    created_orders: Mapped[List["Order"]] = relationship(
        "Order",
        foreign_keys="Order.created_by_user_id",
        back_populates="created_by"
    )
    assigned_routes: Mapped[List["Route"]] = relationship(
        "Route",
        foreign_keys="Route.assigned_driver_id",
        back_populates="assigned_driver"
    )
    created_invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        foreign_keys="Invoice.created_by_user_id",
        back_populates="created_by"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_role_id", "role_id"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class Order(BaseModel):
    """
    Customer orders

    Tracks the complete lifecycle of a customer order from creation to delivery.
    Key features:
    - PostGIS geography type for precise location tracking
    - Geocoding confidence tracking for data quality
    - State machine for order status progression
    - Relationship to invoice (required before routing)

    CRITICAL BUSINESS RULES:
    - Cannot transition to EN_RUTA without invoice_id
    - Auto-transitions to DOCUMENTADO when invoice is linked
    - Cut-off time logic determines delivery_date
    """
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Auto-generated order number (ORD-YYYYMMDD-NNNN)"
    )
    customer_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Customer full name"
    )
    customer_phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Customer phone number for contact"
    )
    customer_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer email for notifications"
    )
    address_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original address as text provided by customer"
    )
    address_coordinates: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        comment="PostGIS geography point (latitude, longitude) in WGS84"
    )
    geocoding_confidence: Mapped[Optional[GeocodingConfidence]] = mapped_column(
        SQLEnum(GeocodingConfidence, name="geocoding_confidence_enum"),
        nullable=True,
        comment="Confidence level of geocoded coordinates"
    )
    order_status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus, name="order_status_enum"),
        nullable=False,
        default=OrderStatus.PENDIENTE,
        comment="Current status in order lifecycle"
    )
    source_channel: Mapped[SourceChannel] = mapped_column(
        SQLEnum(SourceChannel, name="source_channel_enum"),
        nullable=False,
        comment="Channel where order was received (WEB, RRSS, PRESENCIAL)"
    )
    delivery_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Assigned delivery date (determined by cut-off rules)"
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who created this order"
    )
    assigned_route_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Route this order is assigned to (null if not yet routed)"
    )
    document_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default='',
        comment="Número de boleta o factura del comprador"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or special instructions"
    )

    # Relationships
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        back_populates="created_orders"
    )
    invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )
    assigned_route: Mapped[Optional["Route"]] = relationship(
        "Route",
        foreign_keys=[assigned_route_id],
        back_populates="orders"
    )
    notification_logs: Mapped[List["NotificationLog"]] = relationship(
        "NotificationLog",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_orders_order_number", "order_number"),
        Index("ix_orders_order_status", "order_status"),
        Index("ix_orders_delivery_date", "delivery_date"),
        Index("ix_orders_created_by_user_id", "created_by_user_id"),
        Index("ix_orders_assigned_route_id", "assigned_route_id"),
        # Spatial index for geographic queries (distance calculations)
        Index(
            "ix_orders_address_coordinates",
            "address_coordinates",
            postgresql_using="gist"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Order(id={self.id}, order_number='{self.order_number}', "
            f"status={self.order_status.value}, customer='{self.customer_name}')>"
        )


class Invoice(BaseModel):
    """
    Fiscal documents (invoices/receipts)

    One-to-one relationship with Order. An invoice must be linked before
    an order can be included in a delivery route.

    Chilean fiscal document types:
    - FACTURA: Tax invoice for businesses
    - BOLETA: Receipt for individual customers

    CRITICAL: Linking an invoice triggers order state transition to DOCUMENTADO
    """
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="Unique fiscal document number"
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Foreign key to orders (one invoice per order)"
    )
    invoice_type: Mapped[InvoiceType] = mapped_column(
        SQLEnum(InvoiceType, name="invoice_type_enum"),
        nullable=False,
        comment="Type of fiscal document (FACTURA or BOLETA)"
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total invoice amount in Chilean pesos"
    )
    issued_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Timestamp when invoice was issued"
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who created this invoice"
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="invoice"
    )
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        back_populates="created_invoices"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_invoices_invoice_number", "invoice_number"),
        Index("ix_invoices_order_id", "order_id"),
        CheckConstraint("total_amount > 0", name="ck_invoices_positive_amount"),
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, invoice_number='{self.invoice_number}', "
            f"type={self.invoice_type.value}, amount={self.total_amount})>"
        )


class Route(BaseModel):
    """
    Delivery routes

    Represents an optimized delivery route for a specific date and driver.
    Contains the sequence of orders to be delivered and tracking metrics.

    The stop_sequence JSONB field stores the optimized order of deliveries
    as an array of order UUIDs: ["uuid1", "uuid2", ...]

    Route lifecycle:
    - DRAFT: Being planned, not yet assigned
    - ACTIVE: Assigned to driver and in progress
    - COMPLETED: All deliveries finished
    """
    __tablename__ = "routes"

    route_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable route name (e.g., 'Ruta 2026-01-21 #1')"
    )
    route_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date when this route will be/was executed"
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Driver assigned to this route (null if unassigned)"
    )
    status: Mapped[RouteStatus] = mapped_column(
        SQLEnum(RouteStatus, name="route_status_enum"),
        nullable=False,
        default=RouteStatus.DRAFT,
        comment="Current route status (DRAFT, ACTIVE, COMPLETED)"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp when route execution started"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp when route was completed"
    )
    total_distance_km: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Total route distance in kilometers"
    )
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated duration in minutes (from route optimizer)"
    )
    actual_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Actual duration in minutes (for model retraining)"
    )
    stop_sequence: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Optimized sequence of order UUIDs: ['uuid1', 'uuid2', ...]"
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        comment="Vehicle assigned to execute this route"
    )
    assigned_load_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Total load weight assigned to this route in kg"
    )

    # Relationships
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_driver_id],
        back_populates="assigned_routes"
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle",
        foreign_keys=[vehicle_id],
        back_populates="routes"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        foreign_keys="Order.assigned_route_id",
        back_populates="assigned_route"
    )
    gps_positions: Mapped[List["GPSPosition"]] = relationship(
        "GPSPosition",
        back_populates="route",
        cascade="all, delete-orphan"
    )
    delivery_evidences: Mapped[List["DeliveryEvidence"]] = relationship(
        "DeliveryEvidence",
        back_populates="route",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_routes_route_date", "route_date"),
        Index("ix_routes_status", "status"),
        Index("ix_routes_assigned_driver_id", "assigned_driver_id"),
        Index("ix_routes_vehicle_id", "vehicle_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Route(id={self.id}, name='{self.route_name}', "
            f"date={self.route_date}, status={self.status.value})>"
        )


class RefreshToken(BaseModel):
    """
    Refresh tokens for JWT authentication

    Stores refresh tokens issued to users for obtaining new access tokens.
    Each refresh token has an expiration date and can be revoked.

    Security features:
    - Token rotation: optionally generate new refresh token on each use
    - Revocation: tokens can be invalidated (is_revoked flag)
    - Expiration tracking: expires_at timestamp
    - User association: tracks which user owns the token
    """
    __tablename__ = "refresh_tokens"

    token: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        comment="JWT refresh token string"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who owns this refresh token"
    )
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Timestamp when this refresh token expires"
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this token has been revoked (logout)"
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="refresh_tokens"
    )

    # Indexes
    __table_args__ = (
        Index("ix_refresh_tokens_token", "token"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken(id={self.id}, user_id={self.user_id}, "
            f"revoked={self.is_revoked}, expires={self.expires_at})>"
        )


class AuditLog(BaseModel):
    """
    Audit trail for system actions

    Tracks all critical actions in the system, especially:
    - State transitions
    - Business rule overrides
    - Permission-denied actions
    - Data modifications

    Used for:
    - Compliance and auditing
    - Security investigation
    - Debugging business logic issues
    - Performance analysis
    """
    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        comment="When the action occurred"
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed the action (null for system actions)"
    )
    action: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Action type (e.g., 'CREATE_ORDER', 'FORCE_DELIVERY_DATE')"
    )
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of entity affected (ORDER, INVOICE, ROUTE, USER)"
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of the affected entity"
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Action-specific details as JSON"
    )
    result: Mapped[AuditResult] = mapped_column(
        SQLEnum(AuditResult, name="audit_result_enum"),
        nullable=False,
        comment="Result of the action (SUCCESS, DENIED, ERROR)"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        comment="IP address of the client that initiated the action"
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs"
    )

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"entity={self.entity_type}, result={self.result.value})>"
        )


class NotificationLog(BaseModel):
    """
    Log of all notifications sent to customers

    Tracks notification delivery status, channel used, and any errors encountered.
    Used for debugging, compliance tracking, and customer service support.

    Key features:
    - Multi-channel support (EMAIL, SMS, WhatsApp, Push)
    - Delivery status tracking (PENDING, SENT, FAILED)
    - Error logging for troubleshooting
    - Timestamp tracking for audit trail

    Business value:
    - Prove notification delivery for customer service disputes
    - Debug failed notifications
    - Track notification delivery metrics
    - Compliance with communication regulations
    """
    __tablename__ = "notification_logs"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="Order this notification is about"
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel, name="notification_channel_enum"),
        nullable=False,
        comment="Channel used: EMAIL, SMS, WHATSAPP, PUSH"
    )
    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Recipient email address or phone number"
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus, name="notification_status_enum"),
        nullable=False,
        default=NotificationStatus.PENDING,
        comment="Notification status: PENDING, SENT, FAILED"
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp when notification was successfully sent"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if notification failed (for debugging)"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts made"
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="notification_logs"
    )

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_notification_logs_order_id", "order_id"),
        Index("ix_notification_logs_status", "status"),
        Index("ix_notification_logs_channel", "channel"),
        Index("ix_notification_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, order_id={self.order_id}, "
            f"channel={self.channel.value}, status={self.status.value})>"
        )


# ─────────────────────────────────────────────────────────────────
# TMS / GPS MODELS (Phase 2 — vehicle management and GPS tracking)
# ─────────────────────────────────────────────────────────────────

class Vehicle(BaseModel):
    """
    Delivery vehicles (trucks) in the fleet

    Tracks vehicle capacity, assignment status and links to the GPS
    device installed on the vehicle so that telemetry from external
    providers (e.g. Wialon) can be mapped back to a DB record.
    """
    __tablename__ = "vehicles"

    plate_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        comment="Chilean vehicle license plate (e.g. BCDF-12)"
    )
    alias: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Human-friendly name (e.g. 'Camión 1')"
    )
    brand: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Vehicle brand (e.g. Mercedes-Benz)"
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Vehicle model name"
    )
    year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Manufacturing year"
    )
    max_load_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Maximum cargo capacity in kilograms"
    )
    max_volume_m3: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 3),
        nullable=True,
        comment="Maximum cargo volume in cubic metres"
    )
    status: Mapped[VehicleStatus] = mapped_column(
        SQLEnum(VehicleStatus, name="vehicle_status_enum"),
        nullable=False,
        default=VehicleStatus.AVAILABLE,
        comment="Current operational status"
    )
    assigned_driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Driver currently assigned to this vehicle"
    )
    gps_device_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="External GPS device / Wialon unit ID for telemetry mapping"
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Soft-delete flag; False = vehicle removed from fleet"
    )

    # Relationships
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_driver_id]
    )
    routes: Mapped[List["Route"]] = relationship(
        "Route",
        foreign_keys="Route.vehicle_id",
        back_populates="vehicle"
    )
    gps_positions: Mapped[List["GPSPosition"]] = relationship(
        "GPSPosition",
        back_populates="vehicle",
        cascade="all, delete-orphan"
    )
    gps_alerts: Mapped[List["GPSAlert"]] = relationship(
        "GPSAlert",
        back_populates="vehicle",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_vehicles_plate_number", "plate_number"),
        Index("ix_vehicles_status", "status"),
        Index("ix_vehicles_assigned_driver_id", "assigned_driver_id"),
    )

    def __repr__(self) -> str:
        return f"<Vehicle(id={self.id}, plate='{self.plate_number}', status={self.status.value})>"


class GPSPosition(Base, UUIDMixin):
    """
    Time-series GPS telemetry positions for each vehicle

    Intentionally omits updated_at — positions are immutable once recorded.
    Supports two source channels:
    - BROWSER: Geolocation API pushed by the driver's mobile browser/APK
    - WIALON / MQTT: Hardware GPS device telemetry via webhook or broker
    """
    __tablename__ = "gps_positions"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        comment="Vehicle this position belongs to"
    )
    route_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Active route at time of position recording (if any)"
    )
    coordinates: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=False,
        comment="WGS84 geographic point (PostGIS Geography)"
    )
    speed_kmh: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 1),
        nullable=True,
        comment="Vehicle speed in km/h at time of recording"
    )
    heading_degrees: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 1),
        nullable=True,
        comment="Compass heading in degrees (0-360)"
    )
    altitude_m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 2),
        nullable=True,
        comment="Altitude above sea level in metres"
    )
    accuracy_m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 1),
        nullable=True,
        comment="GPS accuracy radius in metres"
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="BROWSER",
        comment="Origin of position: BROWSER | WIALON | MQTT"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Timestamp from device (may differ from server created_at)"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        comment="Server receipt timestamp"
    )

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="gps_positions"
    )
    route: Mapped[Optional["Route"]] = relationship(
        "Route",
        back_populates="gps_positions"
    )

    __table_args__ = (
        Index("ix_gps_positions_vehicle_id", "vehicle_id"),
        Index("ix_gps_positions_route_id", "route_id"),
        Index("ix_gps_positions_recorded_at", "recorded_at"),
        Index(
            "ix_gps_positions_coordinates",
            "coordinates",
            postgresql_using="gist"
        ),
        # Critical composite index for "latest position per vehicle" queries
        Index("ix_gps_positions_vehicle_recorded", "vehicle_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return f"<GPSPosition(vehicle_id={self.vehicle_id}, recorded_at={self.recorded_at}, source='{self.source}')>"


class Geofence(BaseModel):
    """
    Geographic alert zones

    Supports two geometry types:
    - CIRCULAR: center_point + radius_meters (uses ST_DWithin)
    - POLYGON: polygon_area (uses ST_Within)

    When a vehicle enters or exits an active geofence a GPSAlert is created.
    """
    __tablename__ = "geofences"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable geofence name (e.g. 'Zona Centro Rancagua')"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the zone's purpose"
    )
    geofence_type: Mapped[GeofenceType] = mapped_column(
        SQLEnum(GeofenceType, name="geofence_type_enum"),
        nullable=False,
        comment="Geometry type: CIRCULAR or POLYGON"
    )
    center_point: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
        comment="Center of circular geofence (CIRCULAR type only)"
    )
    radius_meters: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Radius in metres for CIRCULAR geofences"
    )
    polygon_area: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326),
        nullable=True,
        comment="Polygon boundary for POLYGON geofences"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Only active geofences trigger alerts"
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Admin user who created this geofence"
    )

    # Relationships
    created_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by_user_id]
    )
    alerts: Mapped[List["GPSAlert"]] = relationship(
        "GPSAlert",
        back_populates="geofence"
    )

    __table_args__ = (
        Index("ix_geofences_is_active", "is_active"),
        Index(
            "ix_geofences_center_point",
            "center_point",
            postgresql_using="gist"
        ),
        Index(
            "ix_geofences_polygon_area",
            "polygon_area",
            postgresql_using="gist"
        ),
    )

    def __repr__(self) -> str:
        return f"<Geofence(id={self.id}, name='{self.name}', type={self.geofence_type.value})>"


class GPSAlert(BaseModel):
    """
    Alerts generated by GPS event detection

    Created automatically by gps_service when:
    - Vehicle enters/exits a geofence
    - Vehicle deviates from its planned route
    - Vehicle exceeds speed threshold
    - Vehicle stops for an unusually long period

    Alerts are broadcast via WebSocket to the logistics dashboard and
    must be acknowledged by a supervisor.
    """
    __tablename__ = "gps_alerts"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        comment="Vehicle that triggered this alert"
    )
    route_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="SET NULL"),
        nullable=True,
        comment="Active route when alert was generated"
    )
    geofence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geofences.id", ondelete="SET NULL"),
        nullable=True,
        comment="Geofence that triggered this alert (if applicable)"
    )
    alert_type: Mapped[AlertType] = mapped_column(
        SQLEnum(AlertType, name="alert_type_enum"),
        nullable=False,
        comment="Category of GPS alert"
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable alert description"
    )
    position_lat: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        comment="Latitude snapshot when alert was triggered"
    )
    position_lon: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        comment="Longitude snapshot when alert was triggered"
    )
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True once a supervisor has reviewed this alert"
    )
    acknowledged_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Supervisor who acknowledged the alert"
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When the alert was acknowledged"
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extra context (e.g. speed value, geofence name)"
    )

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="gps_alerts"
    )
    geofence: Mapped[Optional["Geofence"]] = relationship(
        "Geofence",
        back_populates="alerts"
    )

    __table_args__ = (
        Index("ix_gps_alerts_vehicle_id", "vehicle_id"),
        Index("ix_gps_alerts_alert_type", "alert_type"),
        Index("ix_gps_alerts_is_acknowledged", "is_acknowledged"),
        Index("ix_gps_alerts_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<GPSAlert(id={self.id}, vehicle_id={self.vehicle_id}, "
            f"type={self.alert_type.value}, ack={self.is_acknowledged})>"
        )


class DeliveryEvidence(BaseModel):
    """
    Photographic and signature evidence captured by the driver's APK

    Stored on the local filesystem (or object storage in production) and
    linked to a specific order within a route.  The APK uploads evidence
    at the moment of confirming each delivery stop.

    file_path: relative path inside UPLOAD_DIR volume
    file_url:  public URL served via /uploads/ static route
    """
    __tablename__ = "delivery_evidences"

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Route during which this evidence was captured"
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="Order this evidence belongs to"
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        SQLEnum(EvidenceType, name="evidence_type_enum"),
        nullable=False,
        comment="Media type: PHOTO or SIGNATURE"
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative filesystem path inside upload volume"
    )
    file_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Public URL for browser access via /uploads/"
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes"
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type (e.g. image/jpeg, image/png)"
    )
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Device timestamp when evidence was captured"
    )
    gps_lat: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        comment="GPS latitude at moment of capture"
    )
    gps_lon: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
        comment="GPS longitude at moment of capture"
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Driver (user) who uploaded this evidence"
    )

    # Relationships
    route: Mapped["Route"] = relationship(
        "Route",
        back_populates="delivery_evidences"
    )
    order: Mapped["Order"] = relationship(
        "Order",
        foreign_keys=[order_id]
    )
    uploaded_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by_user_id]
    )

    __table_args__ = (
        Index("ix_delivery_evidences_route_id", "route_id"),
        Index("ix_delivery_evidences_order_id", "order_id"),
        Index("ix_delivery_evidences_evidence_type", "evidence_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<DeliveryEvidence(id={self.id}, order_id={self.order_id}, "
            f"type={self.evidence_type.value})>"
        )
