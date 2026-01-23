"""
Pydantic schemas for Order operations

Request/response models with validation for order-related API endpoints
"""

from pydantic import BaseModel, Field, validator, EmailStr
from datetime import datetime, date
from typing import Optional
from decimal import Decimal
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


class InvoiceBasic(BaseModel):
    """Basic invoice information for nested responses"""
    id: uuid.UUID
    invoice_number: str
    total_amount: Decimal

    class Config:
        from_attributes = True


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
    customer_phone: str = Field(..., regex=r'^\+56\d{8,9}$')
    customer_email: Optional[EmailStr] = None
    address_text: str = Field(..., min_length=10)
    source_channel: SourceChannel
    notes: Optional[str] = None
    override_delivery_date: Optional[date] = None
    override_reason: Optional[str] = None

    @validator('customer_name')
    def validate_customer_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Customer name cannot be empty')
        return v.strip()

    @validator('customer_phone')
    def validate_chilean_phone(cls, v):
        if not v.startswith('+56'):
            raise ValueError('Phone must be Chilean format (+56XXXXXXXXX)')
        return v

    @validator('address_text')
    def validate_address(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Address must be at least 10 characters')
        return v.strip()

    @validator('override_reason')
    def validate_override_reason_if_date(cls, v, values):
        if values.get('override_delivery_date') and not v:
            raise ValueError('override_reason is required when override_delivery_date is provided')
        return v


class OrderUpdate(BaseModel):
    """Schema for updating order details"""
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    customer_phone: Optional[str] = Field(None, regex=r'^\+56\d{8,9}$')
    customer_email: Optional[EmailStr] = None
    address_text: Optional[str] = Field(None, min_length=10)
    notes: Optional[str] = None


class OrderStateTransition(BaseModel):
    """Schema for transitioning order state"""
    new_status: OrderStatus
    reason: Optional[str] = None
    route_id: Optional[uuid.UUID] = None

    @validator('reason')
    def validate_reason_for_incidencia(cls, v, values):
        if values.get('new_status') == OrderStatus.INCIDENCIA and not v:
            raise ValueError('Reason is required when transitioning to INCIDENCIA')
        return v

    @validator('route_id')
    def validate_route_for_en_ruta(cls, v, values):
        if values.get('new_status') == OrderStatus.EN_RUTA and not v:
            raise ValueError('route_id is required when transitioning to EN_RUTA')
        return v


# Response schemas

class OrderResponse(BaseModel):
    """Schema for order response"""
    id: uuid.UUID
    order_number: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    address_text: str
    order_status: OrderStatus
    source_channel: SourceChannel
    delivery_date: Optional[date]
    geocoding_confidence: Optional[GeocodingConfidence]
    created_at: datetime
    updated_at: datetime
    created_by: UserBasic
    invoice: Optional[InvoiceBasic]
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
    address_coordinates: Optional[str]  # Geography as WKT string

    class Config:
        from_attributes = True
