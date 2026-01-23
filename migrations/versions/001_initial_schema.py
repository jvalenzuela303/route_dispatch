"""Initial schema with all models

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-01-20 21:30:00.000000

This migration creates the complete database schema for the Route Dispatch System:
- Roles and Users for authentication and authorization
- Orders with PostGIS geographic coordinates
- Invoices (one-to-one with Orders)
- Routes with optimized stop sequences
- Audit logs for compliance and debugging

Key features:
- UUID primary keys for all tables
- PostGIS Geography type for spatial queries
- PostgreSQL enums for type safety
- Comprehensive indexes including spatial (GIST) indexes
- Foreign key constraints with proper cascade rules
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create all tables and indexes for the Route Dispatch System
    """

    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Create custom enum types
    op.execute("""
        CREATE TYPE order_status_enum AS ENUM (
            'PENDIENTE', 'EN_PREPARACION', 'DOCUMENTADO',
            'EN_RUTA', 'ENTREGADO', 'INCIDENCIA'
        )
    """)

    op.execute("""
        CREATE TYPE source_channel_enum AS ENUM ('WEB', 'RRSS', 'PRESENCIAL')
    """)

    op.execute("""
        CREATE TYPE geocoding_confidence_enum AS ENUM ('HIGH', 'MEDIUM', 'LOW', 'INVALID')
    """)

    op.execute("""
        CREATE TYPE invoice_type_enum AS ENUM ('FACTURA', 'BOLETA')
    """)

    op.execute("""
        CREATE TYPE route_status_enum AS ENUM ('DRAFT', 'ACTIVE', 'COMPLETED')
    """)

    op.execute("""
        CREATE TYPE audit_result_enum AS ENUM ('SUCCESS', 'DENIED', 'ERROR')
    """)

    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('role_name', sa.String(length=100), nullable=False, comment="Role name (e.g., 'Administrador', 'Vendedor')"),
        sa.Column('description', sa.Text(), nullable=True, comment='Description of role responsibilities'),
        sa.Column('permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Flexible permissions structure as JSON'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('role_name', name=op.f('uq_roles_role_name'))
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('username', sa.String(length=100), nullable=False, comment='Unique username for login'),
        sa.Column('email', sa.String(length=255), nullable=False, comment='User email address (also used for login)'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='BCrypt/Argon2 hashed password'),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Foreign key to roles table'),
        sa.Column('active_status', sa.Boolean(), nullable=False, server_default='true', comment='Whether user account is active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_users_role_id_roles'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_role_id'), 'users', ['role_id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)

    # Create routes table
    op.create_table(
        'routes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('route_name', sa.String(length=255), nullable=False, comment="Human-readable route name (e.g., 'Ruta 2026-01-21 #1')"),
        sa.Column('route_date', sa.Date(), nullable=False, comment='Date when this route will be/was executed'),
        sa.Column('assigned_driver_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Driver assigned to this route (null if unassigned)'),
        sa.Column('status', postgresql.ENUM('DRAFT', 'ACTIVE', 'COMPLETED', name='route_status_enum', create_type=False), nullable=False, comment='Current route status (DRAFT, ACTIVE, COMPLETED)'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when route execution started'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when route was completed'),
        sa.Column('total_distance_km', sa.Numeric(precision=8, scale=2), nullable=True, comment='Total route distance in kilometers'),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True, comment='Estimated duration in minutes (from route optimizer)'),
        sa.Column('actual_duration_minutes', sa.Integer(), nullable=True, comment='Actual duration in minutes (for model retraining)'),
        sa.Column('stop_sequence', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment="Optimized sequence of order UUIDs: ['uuid1', 'uuid2', ...]"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.ForeignKeyConstraint(['assigned_driver_id'], ['users.id'], name=op.f('fk_routes_assigned_driver_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_routes'))
    )
    op.create_index(op.f('ix_routes_assigned_driver_id'), 'routes', ['assigned_driver_id'], unique=False)
    op.create_index(op.f('ix_routes_route_date'), 'routes', ['route_date'], unique=False)
    op.create_index(op.f('ix_routes_status'), 'routes', ['status'], unique=False)

    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('order_number', sa.String(length=50), nullable=False, comment='Auto-generated order number (ORD-YYYYMMDD-NNNN)'),
        sa.Column('customer_name', sa.String(length=255), nullable=False, comment='Customer full name'),
        sa.Column('customer_phone', sa.String(length=50), nullable=False, comment='Customer phone number for contact'),
        sa.Column('customer_email', sa.String(length=255), nullable=True, comment='Customer email for notifications'),
        sa.Column('address_text', sa.Text(), nullable=False, comment='Original address as text provided by customer'),
        sa.Column('address_coordinates', geoalchemy2.types.Geography(
            geometry_type='POINT',
            srid=4326,
            spatial_index=False
        ), nullable=True, comment='PostGIS geography point (latitude, longitude) in WGS84'),
        sa.Column('geocoding_confidence', postgresql.ENUM('HIGH', 'MEDIUM', 'LOW', 'INVALID', name='geocoding_confidence_enum', create_type=False), nullable=True, comment='Confidence level of geocoded coordinates'),
        sa.Column('order_status', postgresql.ENUM('PENDIENTE', 'EN_PREPARACION', 'DOCUMENTADO', 'EN_RUTA', 'ENTREGADO', 'INCIDENCIA', name='order_status_enum', create_type=False), nullable=False, comment='Current status in order lifecycle'),
        sa.Column('source_channel', postgresql.ENUM('WEB', 'RRSS', 'PRESENCIAL', name='source_channel_enum', create_type=False), nullable=False, comment='Channel where order was received (WEB, RRSS, PRESENCIAL)'),
        sa.Column('delivery_date', sa.Date(), nullable=True, comment='Assigned delivery date (determined by cut-off rules)'),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who created this order'),
        sa.Column('assigned_route_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Route this order is assigned to (null if not yet routed)'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Additional notes or special instructions'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.ForeignKeyConstraint(['assigned_route_id'], ['routes.id'], name=op.f('fk_orders_assigned_route_id_routes'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_orders_created_by_user_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_orders')),
        sa.UniqueConstraint('order_number', name=op.f('uq_orders_order_number'))
    )
    op.create_index(op.f('ix_orders_assigned_route_id'), 'orders', ['assigned_route_id'], unique=False)
    op.create_index(op.f('ix_orders_created_by_user_id'), 'orders', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_orders_delivery_date'), 'orders', ['delivery_date'], unique=False)
    op.create_index(op.f('ix_orders_order_number'), 'orders', ['order_number'], unique=False)
    op.create_index(op.f('ix_orders_order_status'), 'orders', ['order_status'], unique=False)

    # Create spatial index for address_coordinates using GIST
    op.execute("""
        CREATE INDEX ix_orders_address_coordinates
        ON orders
        USING GIST (address_coordinates)
    """)

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('invoice_number', sa.String(length=100), nullable=False, comment='Unique fiscal document number'),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Foreign key to orders (one invoice per order)'),
        sa.Column('invoice_type', postgresql.ENUM('FACTURA', 'BOLETA', name='invoice_type_enum', create_type=False), nullable=False, comment='Type of fiscal document (FACTURA or BOLETA)'),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total invoice amount in Chilean pesos'),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False, comment='Timestamp when invoice was issued'),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who created this invoice'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.CheckConstraint('total_amount > 0', name=op.f('ck_invoices_positive_amount')),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_invoices_created_by_user_id_users'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_invoices_order_id_orders'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
        sa.UniqueConstraint('invoice_number', name=op.f('uq_invoices_invoice_number')),
        sa.UniqueConstraint('order_id', name=op.f('uq_invoices_order_id'))
    )
    op.create_index(op.f('ix_invoices_invoice_number'), 'invoices', ['invoice_number'], unique=False)
    op.create_index(op.f('ix_invoices_order_id'), 'invoices', ['order_id'], unique=False)

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Unique identifier for this record'),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='When the action occurred'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True, comment='User who performed the action (null for system actions)'),
        sa.Column('action', sa.String(length=255), nullable=False, comment="Action type (e.g., 'CREATE_ORDER', 'FORCE_DELIVERY_DATE')"),
        sa.Column('entity_type', sa.String(length=100), nullable=False, comment='Type of entity affected (ORDER, INVOICE, ROUTE, USER)'),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True, comment='ID of the affected entity'),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Action-specific details as JSON'),
        sa.Column('result', postgresql.ENUM('SUCCESS', 'DENIED', 'ERROR', name='audit_result_enum', create_type=False), nullable=False, comment='Result of the action (SUCCESS, DENIED, ERROR)'),
        sa.Column('ip_address', postgresql.INET(), nullable=True, comment='IP address of the client that initiated the action'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was created'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp when record was last updated'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_logs_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_entity_type_entity_id'), 'audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """
    Drop all tables and enums
    """
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('audit_logs')
    op.drop_table('invoices')
    op.drop_table('orders')
    op.drop_table('routes')
    op.drop_table('users')
    op.drop_table('roles')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS audit_result_enum")
    op.execute("DROP TYPE IF EXISTS route_status_enum")
    op.execute("DROP TYPE IF EXISTS invoice_type_enum")
    op.execute("DROP TYPE IF EXISTS geocoding_confidence_enum")
    op.execute("DROP TYPE IF EXISTS source_channel_enum")
    op.execute("DROP TYPE IF EXISTS order_status_enum")
