"""
Pydantic schemas for authentication endpoints

These schemas define the request/response structure for authentication
operations including login, token refresh, and logout.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class LoginRequest(BaseModel):
    """Request schema for user login"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Username or email address"
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User password"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "admin",
                "password": "AdminPass123"
            }
        }
    }


class TokenResponse(BaseModel):
    """Response schema containing JWT tokens"""

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication"
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens"
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')"
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    }


class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing access token"""

    refresh_token: str = Field(
        ...,
        description="Valid refresh token"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    }


class LogoutRequest(BaseModel):
    """Request schema for user logout"""

    refresh_token: str = Field(
        ...,
        description="Refresh token to revoke"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    }


class ChangePasswordRequest(BaseModel):
    """Request schema for changing user password"""

    old_password: Optional[str] = Field(
        None,
        description="Current password (required when user changes own password)"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 chars, must contain uppercase, lowercase, and digit)"
    )

    @field_validator('new_password')
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
                "old_password": "OldPass123",
                "new_password": "NewSecurePass456"
            }
        }
    }
