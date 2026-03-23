"""
Pydantic schemas for Route operations

Request/response models with validation for route-related API endpoints
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal
import uuid

from app.models.enums import RouteStatus


# Base schemas for nested objects

class UserBasic(BaseModel):
    """Basic user information for nested responses"""
    id: uuid.UUID
    username: str
    email: str

    class Config:
        from_attributes = True


class OrderBasic(BaseModel):
    """Basic order information for nested responses"""
    id: uuid.UUID
    order_number: str
    customer_name: str
    address_text: str
    customer_phone: Optional[str] = None
    document_number: Optional[str] = None

    class Config:
        from_attributes = True


# Request schemas

class RouteGenerateRequest(BaseModel):
    """Schema for requesting route generation"""
    delivery_date: date = Field(..., description="Date for which to generate route")

    @field_validator('delivery_date')
    @classmethod
    def validate_future_or_today(cls, v):
        """Ensure delivery date is not in the past"""
        if v < date.today():
            raise ValueError('Delivery date cannot be in the past')
        return v


class RouteActivation(BaseModel):
    """Schema for activating a route and assigning to driver"""
    driver_id: uuid.UUID = Field(..., description="UUID of driver to assign route to")
    vehicle_id: Optional[uuid.UUID] = Field(
        None, description="UUID of vehicle to assign to this route"
    )


class RouteStopUpdate(BaseModel):
    """Schema for updating route stop status"""
    delivered: bool = Field(..., description="Whether delivery was completed")
    notes: Optional[str] = Field(None, description="Delivery notes or issues")


# Response schemas

class RouteStopResponse(BaseModel):
    """Schema for route stop (order in route sequence)"""
    id: uuid.UUID
    stop_sequence: int
    order: OrderBasic
    latitude: Optional[float]
    longitude: Optional[float]
    estimated_arrival: Optional[datetime]
    actual_arrival: Optional[datetime]
    delivered: bool
    delivery_notes: Optional[str]
    status: Optional[str] = 'PENDIENTE'
    incident_reason: Optional[str] = None

    class Config:
        from_attributes = True


class RouteResponse(BaseModel):
    """Schema for route response with stops"""
    id: uuid.UUID
    route_name: str
    route_date: date
    status: RouteStatus
    total_distance_km: Optional[Decimal]
    estimated_duration_minutes: Optional[int]
    actual_duration_minutes: Optional[int] = None
    assigned_driver: Optional[UserBasic]
    vehicle_id: Optional[uuid.UUID] = None
    assigned_load_kg: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UserBasic] = None
    stops_count: Optional[int] = Field(None, description="Number of stops in route")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator('stops_count', mode='before')
    @classmethod
    def calculate_stops_count(cls, v):
        """Calculate stops count from stops relationship if available"""
        # This will be populated by the API endpoint
        return v


class RouteDetailResponse(RouteResponse):
    """Extended route response with full stop sequence"""
    stops: List[RouteStopResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class RouteListResponse(BaseModel):
    """Schema for paginated route list"""
    routes: List[RouteResponse]
    total: int
    limit: int
    offset: int


class RouteMapData(BaseModel):
    """Schema for route map visualization data"""
    route_id: uuid.UUID
    route_name: str
    route_date: date
    depot_latitude: float = Field(..., description="Warehouse/depot latitude")
    depot_longitude: float = Field(..., description="Warehouse/depot longitude")
    stops: List[dict] = Field(
        ...,
        description="List of stops with coordinates and customer info",
        example=[
            {
                "stop_sequence": 1,
                "latitude": -34.1706,
                "longitude": -70.7407,
                "customer_name": "Juan Pérez",
                "address": "Av. Brasil 1234, Rancagua"
            }
        ]
    )
    total_distance_km: Optional[Decimal]
    estimated_duration_minutes: Optional[int]

    class Config:
        from_attributes = True
