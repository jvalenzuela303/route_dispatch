"""
Pydantic schemas for Invoice operations

Request/response models with validation for invoice-related API endpoints
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from decimal import Decimal, ROUND_HALF_UP
import uuid

from app.models.enums import InvoiceType


# Request schemas

class InvoiceCreate(BaseModel):
    """Schema for creating a new invoice"""
    order_id: uuid.UUID
    invoice_number: str = Field(..., min_length=1, max_length=100)
    invoice_type: InvoiceType
    total_amount: Decimal = Field(..., gt=0)
    issued_at: Optional[datetime] = None

    @field_validator('invoice_number')
    @classmethod
    def validate_invoice_number(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Invoice number cannot be empty')
        return v.strip()

    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v):
        if v <= 0:
            raise ValueError('Total amount must be positive')
        # Round to 2 decimal places
        return v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class InvoiceUpdate(BaseModel):
    """Schema for updating invoice (limited fields)"""
    invoice_number: Optional[str] = Field(None, min_length=1, max_length=100)
    total_amount: Optional[Decimal] = Field(None, gt=0)

    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v):
        if v is not None:
            if v <= 0:
                raise ValueError('Total amount must be positive')
            # Round to 2 decimal places
            return v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return v


# Response schemas

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

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Schema for invoice response"""
    id: uuid.UUID
    invoice_number: str
    invoice_type: InvoiceType
    total_amount: Decimal
    issued_at: datetime
    created_at: datetime
    order: OrderBasic
    created_by: UserBasic

    class Config:
        from_attributes = True


class InvoiceListResponse(BaseModel):
    """Schema for paginated invoice list"""
    invoices: list[InvoiceResponse]
    total: int
    limit: int
    offset: int
