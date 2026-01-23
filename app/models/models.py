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

from app.models.base import BaseModel
from app.models.enums import (
    OrderStatus, SourceChannel, GeocodingConfidence,
    InvoiceType, RouteStatus, AuditResult,
    NotificationChannel, NotificationStatus
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

    # Relationships
    assigned_driver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_driver_id],
        back_populates="assigned_routes"
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        foreign_keys="Order.assigned_route_id",
        back_populates="assigned_route"
    )

    # Indexes
    __table_args__ = (
        Index("ix_routes_route_date", "route_date"),
        Index("ix_routes_status", "status"),
        Index("ix_routes_assigned_driver_id", "assigned_driver_id"),
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
