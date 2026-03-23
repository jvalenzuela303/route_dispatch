"""Add TMS/GPS models: vehicles, gps_positions, geofences, gps_alerts, delivery_evidences

Revision ID: 006_add_tms_gps_models
Revises: 005_fix_user_passwords
Create Date: 2026-03-14

Adds the vehicle fleet management and GPS tracking tables required for
the driver APK and the real-time logistics dashboard:

- vehicles               : fleet registry with capacity and GPS device mapping
- gps_positions          : time-series position telemetry (PostGIS GIST indexed)
- geofences              : circular and polygon alert zones
- gps_alerts             : automated alerts from GPS event detection
- delivery_evidences     : photos and signatures captured by the driver APK

Also extends routes with:
- vehicle_id             : FK to assigned vehicle
- assigned_load_kg       : calculated cargo weight for the route
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = '006_add_tms_gps_models'
down_revision: Union[str, None] = '005_fix_user_passwords'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. New enum types ────────────────────────────────────────────
    op.execute("""
        CREATE TYPE vehicle_status_enum AS ENUM (
            'AVAILABLE', 'IN_ROUTE', 'MAINTENANCE'
        )
    """)
    op.execute("""
        CREATE TYPE alert_type_enum AS ENUM (
            'GEOFENCE_ENTRY', 'GEOFENCE_EXIT',
            'ROUTE_DEVIATION', 'SPEEDING', 'LONG_STOP'
        )
    """)
    op.execute("""
        CREATE TYPE geofence_type_enum AS ENUM ('CIRCULAR', 'POLYGON')
    """)
    op.execute("""
        CREATE TYPE evidence_type_enum AS ENUM ('PHOTO', 'SIGNATURE')
    """)

    # ── 2. vehicles ──────────────────────────────────────────────────
    op.create_table(
        'vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Unique identifier for this record'),
        sa.Column('plate_number', sa.String(20), nullable=False,
                  comment='Chilean vehicle license plate (e.g. BCDF-12)'),
        sa.Column('alias', sa.String(100), nullable=True,
                  comment="Human-friendly name (e.g. 'Camión 1')"),
        sa.Column('brand', sa.String(100), nullable=True,
                  comment='Vehicle brand'),
        sa.Column('model_name', sa.String(100), nullable=True,
                  comment='Vehicle model name'),
        sa.Column('year', sa.Integer(), nullable=True,
                  comment='Manufacturing year'),
        sa.Column('max_load_kg', sa.Numeric(8, 2), nullable=True,
                  comment='Maximum cargo capacity in kilograms'),
        sa.Column('max_volume_m3', sa.Numeric(6, 3), nullable=True,
                  comment='Maximum cargo volume in cubic metres'),
        sa.Column('status',
                  postgresql.ENUM(
                      'AVAILABLE', 'IN_ROUTE', 'MAINTENANCE',
                      name='vehicle_status_enum', create_type=False
                  ),
                  nullable=False, server_default='AVAILABLE',
                  comment='Current operational status'),
        sa.Column('assigned_driver_id', postgresql.UUID(as_uuid=True),
                  nullable=True,
                  comment='Driver currently assigned to this vehicle'),
        sa.Column('gps_device_id', sa.String(100), nullable=True,
                  comment='External GPS device / Wialon unit ID'),
        sa.Column('active', sa.Boolean(), nullable=False,
                  server_default='true',
                  comment='Soft-delete flag'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['assigned_driver_id'], ['users.id'],
            name=op.f('fk_vehicles_assigned_driver_id_users'),
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vehicles')),
        sa.UniqueConstraint('plate_number', name=op.f('uq_vehicles_plate_number')),
    )
    op.create_index(op.f('ix_vehicles_plate_number'), 'vehicles', ['plate_number'])
    op.create_index(op.f('ix_vehicles_status'), 'vehicles', ['status'])
    op.create_index(op.f('ix_vehicles_assigned_driver_id'),
                    'vehicles', ['assigned_driver_id'])

    # ── 3. Extend routes with vehicle_id and assigned_load_kg ────────
    op.add_column('routes',
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Vehicle assigned to execute this route'))
    op.add_column('routes',
        sa.Column('assigned_load_kg', sa.Numeric(8, 2), nullable=True,
                  comment='Total load weight assigned to this route in kg'))
    op.create_foreign_key(
        op.f('fk_routes_vehicle_id_vehicles'),
        'routes', 'vehicles',
        ['vehicle_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index(op.f('ix_routes_vehicle_id'), 'routes', ['vehicle_id'])

    # ── 4. gps_positions ─────────────────────────────────────────────
    op.create_table(
        'gps_positions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Unique identifier for this record'),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Vehicle this position belongs to'),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Active route at time of recording (if any)'),
        sa.Column('coordinates',
                  geoalchemy2.types.Geography(
                      geometry_type='POINT', srid=4326, spatial_index=False
                  ),
                  nullable=False,
                  comment='WGS84 geographic point (PostGIS Geography)'),
        sa.Column('speed_kmh', sa.Numeric(5, 1), nullable=True,
                  comment='Vehicle speed in km/h'),
        sa.Column('heading_degrees', sa.Numeric(5, 1), nullable=True,
                  comment='Compass heading in degrees'),
        sa.Column('altitude_m', sa.Numeric(7, 2), nullable=True,
                  comment='Altitude above sea level in metres'),
        sa.Column('accuracy_m', sa.Numeric(6, 1), nullable=True,
                  comment='GPS accuracy radius in metres'),
        sa.Column('source', sa.String(20), nullable=False,
                  server_default='BROWSER',
                  comment='Origin: BROWSER | WIALON | MQTT'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False,
                  comment='Device timestamp'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False,
                  comment='Server receipt timestamp'),
        sa.ForeignKeyConstraint(
            ['vehicle_id'], ['vehicles.id'],
            name=op.f('fk_gps_positions_vehicle_id_vehicles'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['route_id'], ['routes.id'],
            name=op.f('fk_gps_positions_route_id_routes'),
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_gps_positions')),
    )
    op.create_index(op.f('ix_gps_positions_vehicle_id'),
                    'gps_positions', ['vehicle_id'])
    op.create_index(op.f('ix_gps_positions_route_id'),
                    'gps_positions', ['route_id'])
    op.create_index(op.f('ix_gps_positions_recorded_at'),
                    'gps_positions', ['recorded_at'])
    op.create_index('ix_gps_positions_vehicle_recorded',
                    'gps_positions', ['vehicle_id', 'recorded_at'])
    # Spatial GIST index for PostGIS queries
    op.execute("""
        CREATE INDEX ix_gps_positions_coordinates
        ON gps_positions USING GIST (coordinates)
    """)

    # ── 5. geofences ─────────────────────────────────────────────────
    op.create_table(
        'geofences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Unique identifier for this record'),
        sa.Column('name', sa.String(255), nullable=False,
                  comment='Human-readable geofence name'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('geofence_type',
                  postgresql.ENUM(
                      'CIRCULAR', 'POLYGON',
                      name='geofence_type_enum', create_type=False
                  ),
                  nullable=False),
        sa.Column('center_point',
                  geoalchemy2.types.Geography(
                      geometry_type='POINT', srid=4326, spatial_index=False
                  ),
                  nullable=True,
                  comment='Center of circular geofence'),
        sa.Column('radius_meters', sa.Numeric(8, 2), nullable=True,
                  comment='Radius in metres for CIRCULAR geofences'),
        sa.Column('polygon_area',
                  geoalchemy2.types.Geography(
                      geometry_type='POLYGON', srid=4326, spatial_index=False
                  ),
                  nullable=True,
                  comment='Polygon boundary for POLYGON geofences'),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default='true'),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'],
            name=op.f('fk_geofences_created_by_user_id_users'),
            ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_geofences')),
    )
    op.create_index(op.f('ix_geofences_is_active'), 'geofences', ['is_active'])
    op.execute("""
        CREATE INDEX ix_geofences_center_point
        ON geofences USING GIST (center_point)
    """)
    op.execute("""
        CREATE INDEX ix_geofences_polygon_area
        ON geofences USING GIST (polygon_area)
    """)

    # ── 6. gps_alerts ────────────────────────────────────────────────
    op.create_table(
        'gps_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Unique identifier for this record'),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Vehicle that triggered this alert'),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Active route when alert was generated'),
        sa.Column('geofence_id', postgresql.UUID(as_uuid=True), nullable=True,
                  comment='Geofence that triggered this alert (if applicable)'),
        sa.Column('alert_type',
                  postgresql.ENUM(
                      'GEOFENCE_ENTRY', 'GEOFENCE_EXIT',
                      'ROUTE_DEVIATION', 'SPEEDING', 'LONG_STOP',
                      name='alert_type_enum', create_type=False
                  ),
                  nullable=False),
        sa.Column('message', sa.Text(), nullable=False,
                  comment='Human-readable alert description'),
        sa.Column('position_lat', sa.Numeric(10, 7), nullable=True),
        sa.Column('position_lon', sa.Numeric(10, 7), nullable=True),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=False,
                  server_default='false'),
        sa.Column('acknowledged_by_user_id', postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['vehicle_id'], ['vehicles.id'],
            name=op.f('fk_gps_alerts_vehicle_id_vehicles'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['route_id'], ['routes.id'],
            name=op.f('fk_gps_alerts_route_id_routes'),
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['geofence_id'], ['geofences.id'],
            name=op.f('fk_gps_alerts_geofence_id_geofences'),
            ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['acknowledged_by_user_id'], ['users.id'],
            name=op.f('fk_gps_alerts_acknowledged_by_user_id_users'),
            ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_gps_alerts')),
    )
    op.create_index(op.f('ix_gps_alerts_vehicle_id'),
                    'gps_alerts', ['vehicle_id'])
    op.create_index(op.f('ix_gps_alerts_alert_type'),
                    'gps_alerts', ['alert_type'])
    op.create_index(op.f('ix_gps_alerts_is_acknowledged'),
                    'gps_alerts', ['is_acknowledged'])
    op.create_index(op.f('ix_gps_alerts_created_at'),
                    'gps_alerts', ['created_at'])

    # ── 7. delivery_evidences ────────────────────────────────────────
    op.create_table(
        'delivery_evidences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Unique identifier for this record'),
        sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Route during which this evidence was captured'),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False,
                  comment='Order this evidence belongs to'),
        sa.Column('evidence_type',
                  postgresql.ENUM(
                      'PHOTO', 'SIGNATURE',
                      name='evidence_type_enum', create_type=False
                  ),
                  nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False,
                  comment='Relative filesystem path inside upload volume'),
        sa.Column('file_url', sa.String(500), nullable=True,
                  comment='Public URL via /uploads/'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False,
                  comment='Device timestamp when evidence was captured'),
        sa.Column('gps_lat', sa.Numeric(10, 7), nullable=True),
        sa.Column('gps_lon', sa.Numeric(10, 7), nullable=True),
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True),
                  nullable=False,
                  comment='Driver (user) who uploaded this evidence'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['route_id'], ['routes.id'],
            name=op.f('fk_delivery_evidences_route_id_routes'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['order_id'], ['orders.id'],
            name=op.f('fk_delivery_evidences_order_id_orders'),
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['uploaded_by_user_id'], ['users.id'],
            name=op.f('fk_delivery_evidences_uploaded_by_user_id_users'),
            ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_delivery_evidences')),
    )
    op.create_index(op.f('ix_delivery_evidences_route_id'),
                    'delivery_evidences', ['route_id'])
    op.create_index(op.f('ix_delivery_evidences_order_id'),
                    'delivery_evidences', ['order_id'])
    op.create_index(op.f('ix_delivery_evidences_evidence_type'),
                    'delivery_evidences', ['evidence_type'])


def downgrade() -> None:
    # Reverse order of creation
    op.drop_table('delivery_evidences')

    op.drop_index(op.f('ix_gps_alerts_created_at'), 'gps_alerts')
    op.drop_index(op.f('ix_gps_alerts_is_acknowledged'), 'gps_alerts')
    op.drop_index(op.f('ix_gps_alerts_alert_type'), 'gps_alerts')
    op.drop_index(op.f('ix_gps_alerts_vehicle_id'), 'gps_alerts')
    op.drop_table('gps_alerts')

    op.execute('DROP INDEX IF EXISTS ix_geofences_polygon_area')
    op.execute('DROP INDEX IF EXISTS ix_geofences_center_point')
    op.drop_index(op.f('ix_geofences_is_active'), 'geofences')
    op.drop_table('geofences')

    op.execute('DROP INDEX IF EXISTS ix_gps_positions_coordinates')
    op.drop_index('ix_gps_positions_vehicle_recorded', 'gps_positions')
    op.drop_index(op.f('ix_gps_positions_recorded_at'), 'gps_positions')
    op.drop_index(op.f('ix_gps_positions_route_id'), 'gps_positions')
    op.drop_index(op.f('ix_gps_positions_vehicle_id'), 'gps_positions')
    op.drop_table('gps_positions')

    op.drop_index(op.f('ix_routes_vehicle_id'), 'routes')
    op.drop_constraint(op.f('fk_routes_vehicle_id_vehicles'), 'routes',
                       type_='foreignkey')
    op.drop_column('routes', 'assigned_load_kg')
    op.drop_column('routes', 'vehicle_id')

    op.drop_index(op.f('ix_vehicles_assigned_driver_id'), 'vehicles')
    op.drop_index(op.f('ix_vehicles_status'), 'vehicles')
    op.drop_index(op.f('ix_vehicles_plate_number'), 'vehicles')
    op.drop_table('vehicles')

    op.execute('DROP TYPE IF EXISTS evidence_type_enum')
    op.execute('DROP TYPE IF EXISTS geofence_type_enum')
    op.execute('DROP TYPE IF EXISTS alert_type_enum')
    op.execute('DROP TYPE IF EXISTS vehicle_status_enum')
