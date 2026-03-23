"""
Pydantic schemas for Vehicle, GPS and Evidence operations

Covers:
- Vehicle CRUD
- GPS position push (driver APK and Wialon webhook)
- Fleet position summary for the logistics dashboard
- Geofence management
- GPS alert management
- Delivery evidence (photos / signatures)
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from uuid import UUID

from app.models.enums import VehicleStatus, AlertType, GeofenceType, EvidenceType


# ─────────────────────────────────────────────────────────────────
# Vehicle schemas
# ─────────────────────────────────────────────────────────────────

class VehicleCreate(BaseModel):
    plate_number: str = Field(..., max_length=20,
                              description="Chilean license plate (e.g. BCDF-12)")
    alias: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    model_name: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1990, le=2100)
    max_load_kg: Optional[Decimal] = Field(None, gt=0)
    max_volume_m3: Optional[Decimal] = Field(None, gt=0)
    gps_device_id: Optional[str] = Field(
        None, max_length=100,
        description="External GPS device / Wialon unit ID"
    )
    assigned_driver_id: Optional[UUID] = None


class VehicleUpdate(BaseModel):
    alias: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    model_name: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1990, le=2100)
    max_load_kg: Optional[Decimal] = Field(None, gt=0)
    max_volume_m3: Optional[Decimal] = Field(None, gt=0)
    status: Optional[VehicleStatus] = None
    gps_device_id: Optional[str] = Field(None, max_length=100)
    assigned_driver_id: Optional[UUID] = None


class DriverAssignment(BaseModel):
    user_id: UUID = Field(..., description="UUID of the Repartidor user to assign")


class VehicleBasic(BaseModel):
    """Minimal vehicle info for nested responses"""
    id: UUID
    plate_number: str
    alias: Optional[str] = None
    status: VehicleStatus

    class Config:
        from_attributes = True


class VehicleResponse(BaseModel):
    id: UUID
    plate_number: str
    alias: Optional[str] = None
    brand: Optional[str] = None
    model_name: Optional[str] = None
    year: Optional[int] = None
    max_load_kg: Optional[Decimal] = None
    max_volume_m3: Optional[Decimal] = None
    status: VehicleStatus
    assigned_driver_id: Optional[UUID] = None
    gps_device_id: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VehicleListResponse(BaseModel):
    items: List[VehicleResponse]
    total: int


# ─────────────────────────────────────────────────────────────────
# GPS Position schemas
# ─────────────────────────────────────────────────────────────────

class GPSPositionCreate(BaseModel):
    """Pushed by the driver APK every N seconds"""
    vehicle_id: UUID
    route_id: Optional[UUID] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: Optional[float] = Field(None, ge=0)
    heading_degrees: Optional[float] = Field(None, ge=0, le=360)
    accuracy_m: Optional[float] = Field(None, ge=0)
    altitude_m: Optional[float] = None
    recorded_at: Optional[datetime] = None  # defaults to now() if not provided


class GPSPositionResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    route_id: Optional[UUID] = None
    latitude: float
    longitude: float
    speed_kmh: Optional[Decimal] = None
    heading_degrees: Optional[Decimal] = None
    accuracy_m: Optional[Decimal] = None
    source: str
    recorded_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class FleetPositionItem(BaseModel):
    """Latest position per vehicle — used by the logistics dashboard"""
    vehicle_id: str
    plate: str
    alias: Optional[str] = None
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = None
    route_id: Optional[str] = None
    last_seen: datetime


# ─────────────────────────────────────────────────────────────────
# Wialon webhook
# ─────────────────────────────────────────────────────────────────

class WialonWebhookPayload(BaseModel):
    """Payload received from Wialon GPS platform webhook"""
    unit_id: str = Field(..., description="Wialon unit ID — maps to vehicles.gps_device_id")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    speed: float = Field(0, ge=0, description="Speed in km/h")
    course: float = Field(0, ge=0, le=360, description="Heading in degrees")
    altitude: float = Field(0, description="Altitude in metres")
    ts: int = Field(..., description="Unix timestamp from device")


# ─────────────────────────────────────────────────────────────────
# Geofence schemas
# ─────────────────────────────────────────────────────────────────

class GeofenceCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    geofence_type: GeofenceType
    # CIRCULAR fields
    center_lat: Optional[float] = Field(None, ge=-90, le=90)
    center_lon: Optional[float] = Field(None, ge=-180, le=180)
    radius_meters: Optional[Decimal] = Field(None, gt=0)
    # POLYGON fields: list of [lon, lat] pairs
    polygon_coords: Optional[List[List[float]]] = None

    @field_validator('radius_meters')
    @classmethod
    def check_circular_fields(cls, v, values):
        if values.data.get('geofence_type') == GeofenceType.CIRCULAR and v is None:
            raise ValueError('radius_meters required for CIRCULAR geofences')
        return v


class GeofenceResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    geofence_type: GeofenceType
    radius_meters: Optional[Decimal] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# GPS Alert schemas
# ─────────────────────────────────────────────────────────────────

class GPSAlertResponse(BaseModel):
    id: UUID
    vehicle_id: UUID
    route_id: Optional[UUID] = None
    geofence_id: Optional[UUID] = None
    alert_type: AlertType
    message: str
    position_lat: Optional[Decimal] = None
    position_lon: Optional[Decimal] = None
    is_acknowledged: bool
    acknowledged_by_user_id: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────
# Delivery Evidence schemas
# ─────────────────────────────────────────────────────────────────

class DeliveryEvidenceResponse(BaseModel):
    id: UUID
    route_id: UUID
    order_id: UUID
    evidence_type: EvidenceType
    file_url: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    captured_at: datetime
    gps_lat: Optional[Decimal] = None
    gps_lon: Optional[Decimal] = None
    uploaded_by_user_id: UUID

    class Config:
        from_attributes = True
