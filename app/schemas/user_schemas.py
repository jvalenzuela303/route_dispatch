"""
Pydantic schemas for user management endpoints

These schemas define the request/response structure for user CRUD operations.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


class RoleResponse(BaseModel):
    """Schema for role information in user responses"""

    id: UUID
    role_name: str
    description: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "role_name": "Administrador",
                "description": "Full system access with override capabilities"
            }
        }
    }


class UserBase(BaseModel):
    """Base schema for user data"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique username for login"
    )
    email: EmailStr = Field(
        ...,
        description="User email address"
    )
    role_id: UUID = Field(
        ...,
        description="ID of the role to assign to this user"
    )


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str = Field(
        ...,
        min_length=8,
        description="User password (will be hashed before storage)"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "jperez",
                "email": "jperez@botilleria.cl",
                "password": "SecurePass123",
                "role_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    }


class UserUpdate(BaseModel):
    """Schema for updating user information"""

    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="New username"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="New email address"
    )
    role_id: Optional[UUID] = Field(
        None,
        description="New role ID"
    )
    active_status: Optional[bool] = Field(
        None,
        description="Whether user account is active"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "jperez_updated",
                "email": "jperez.new@botilleria.cl",
                "active_status": True
            }
        }
    }


class UserResponse(UserBase):
    """Schema for user information in responses"""

    id: UUID
    active_status: bool
    created_at: datetime
    updated_at: datetime
    role: RoleResponse

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "username": "jperez",
                "email": "jperez@botilleria.cl",
                "role_id": "123e4567-e89b-12d3-a456-426614174000",
                "active_status": True,
                "created_at": "2026-01-21T10:00:00Z",
                "updated_at": "2026-01-21T10:00:00Z",
                "role": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "role_name": "Vendedor",
                    "description": "Create orders and invoices"
                }
            }
        }
    }


class UserListResponse(BaseModel):
    """Schema for paginated user list response"""

    users: list[UserResponse]
    total: int
    skip: int
    limit: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "users": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174001",
                        "username": "jperez",
                        "email": "jperez@botilleria.cl",
                        "role_id": "123e4567-e89b-12d3-a456-426614174000",
                        "active_status": True,
                        "created_at": "2026-01-21T10:00:00Z",
                        "updated_at": "2026-01-21T10:00:00Z",
                        "role": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "role_name": "Vendedor",
                            "description": "Create orders and invoices"
                        }
                    }
                ],
                "total": 1,
                "skip": 0,
                "limit": 100
            }
        }
    }
