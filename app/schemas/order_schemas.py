"""
Pydantic schemas for Order operations

Request/response models with validation for order-related API endpoints
"""

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr
from datetime import datetime, date
from typing import Optional, Any
import uuid
import re

from app.models.enums import OrderStatus, SourceChannel, GeocodingConfidence


# Base schemas for nested objects

class UserBasic(BaseModel):
    """Basic user information for nested responses"""
    id: uuid.UUID
    username: str
    email: str

    class Config:
        from_attributes = True  # Pydantic v2


class RouteBasic(BaseModel):
    """Basic route information for nested responses"""
    id: uuid.UUID
    route_name: str
    route_date: date

    class Config:
        from_attributes = True


# Request schemas

class OrderCreate(BaseModel):
    """Schema for creating a new order"""
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: str = Field(..., pattern=r'^\+56\d{8,9}$')
    customer_email: Optional[EmailStr] = None
    address_text: str = Field(..., min_length=10)
    document_number: str = Field(..., min_length=1, max_length=100, description="Número de boleta o factura del comprador")
    source_channel: SourceChannel
    notes: Optional[str] = None
    override_delivery_date: Optional[date] = None
    override_reason: Optional[str] = None

    @field_validator('customer_name')
    @classmethod
    def validate_customer_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Customer name cannot be empty')
        return v.strip()

    @field_validator('customer_phone')
    @classmethod
    def validate_chilean_phone(cls, v):
        if not v.startswith('+56'):
            raise ValueError('Phone must be Chilean format (+56XXXXXXXXX)')
        return v

    @field_validator('address_text')
    @classmethod
    def validate_address(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Address must be at least 10 characters')
        return v.strip()

    @model_validator(mode='after')
    def validate_override_reason_if_date(self):
        if self.override_delivery_date and not self.override_reason:
            raise ValueError('override_reason is required when override_delivery_date is provided')
        return self


class OrderUpdate(BaseModel):
    """Schema for updating order details"""
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    customer_phone: Optional[str] = Field(None, pattern=r'^\+56\d{8,9}$')
    customer_email: Optional[EmailStr] = None
    address_text: Optional[str] = Field(None, min_length=10)
    document_number: Optional[str] = Field(None, min_length=1, max_length=100)
    notes: Optional[str] = None


class OrderStateTransition(BaseModel):
    """Schema for transitioning order state"""
    new_status: OrderStatus
    reason: Optional[str] = None
    route_id: Optional[uuid.UUID] = None

    @model_validator(mode='after')
    def validate_transition_requirements(self):
        if self.new_status == OrderStatus.INCIDENCIA and not self.reason:
            raise ValueError('Reason is required when transitioning to INCIDENCIA')
        if self.new_status == OrderStatus.EN_RUTA and not self.route_id:
            raise ValueError('route_id is required when transitioning to EN_RUTA')
        return self


# Response schemas

class OrderResponse(BaseModel):
    """Schema for order response"""
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    address_text: str
    document_number: str
    order_status: OrderStatus
    source_channel: SourceChannel
    delivery_date: Optional[date]
    geocoding_confidence: Optional[GeocodingConfidence]
    created_at: datetime
    updated_at: datetime
    created_by: UserBasic
    assigned_route: Optional[RouteBasic]
    notes: Optional[str]

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    """Schema for paginated order list"""
    orders: list[OrderResponse]
    total: int
    limit: int
    offset: int


class OrderDetailResponse(OrderResponse):
    """Extended order response with additional details"""
    address_coordinates: Optional[Any] = None  # Geography WKBElement → WKT string

    @field_validator('address_coordinates', mode='before')
    @classmethod
    def serialize_coordinates(cls, v: Any) -> Optional[str]:
        """Convert GeoAlchemy2 WKBElement to WKT string"""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        # WKBElement from GeoAlchemy2
        try:
            from geoalchemy2.shape import to_shape
            shape = to_shape(v)
            return shape.wkt
        except Exception:
            return str(v)

    class Config:
        from_attributes = True
