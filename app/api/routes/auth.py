"""
Authentication API endpoints

This module provides endpoints for:
- User login (username/password)
- Token refresh (using refresh token)
- User logout (revoke refresh token)

All authentication operations are logged to the audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_db
from app.api.dependencies.auth import get_current_active_user, get_client_ip
from app.schemas.auth_schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest
)
from app.models.models import User
from app.services.auth_service import AuthService
from app.exceptions import (
    InvalidCredentialsError,
    UserInactiveError,
    InvalidTokenError,
    TokenExpiredError
)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate user with username/email and password. Returns access and refresh tokens."
)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Authenticate user and return JWT tokens

    Args:
        credentials: Login credentials (username/email and password)
        request: FastAPI request object (for IP logging)
        db: Database session

    Returns:
        TokenResponse containing access_token, refresh_token, and metadata

    Raises:
        HTTPException 401: If credentials are invalid
        HTTPException 403: If user account is deactivated
    """
    ip_address = get_client_ip(request)

    try:
        auth_service = AuthService(db)
        token_response = auth_service.login(
            username=credentials.username,
            password=credentials.password,
            ip_address=ip_address
        )

        return TokenResponse(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            token_type=token_response.token_type,
            expires_in=token_response.expires_in
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message
        )
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Use a valid refresh token to obtain a new access token"
)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using valid refresh token

    Args:
        refresh_request: Request containing refresh token
        request: FastAPI request object (for IP logging)
        db: Database session

    Returns:
        TokenResponse with new access token

    Raises:
        HTTPException 401: If refresh token is invalid or expired
        HTTPException 403: If user account is deactivated
    """
    ip_address = get_client_ip(request)

    try:
        auth_service = AuthService(db)
        token_response = auth_service.refresh_access_token(
            refresh_token=refresh_request.refresh_token,
            ip_address=ip_address
        )

        return TokenResponse(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            token_type=token_response.token_type,
            expires_in=token_response.expires_in
        )

    except (InvalidTokenError, TokenExpiredError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message
        )
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during token refresh"
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="User logout",
    description="Revoke refresh token to log out user"
)
async def logout(
    logout_request: LogoutRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> None:
    """
    Logout user by revoking their refresh token

    Args:
        logout_request: Request containing refresh token to revoke
        request: FastAPI request object (for IP logging)
        current_user: Currently authenticated user
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 401: If refresh token is invalid
    """
    ip_address = get_client_ip(request)

    try:
        auth_service = AuthService(db)
        auth_service.logout(
            user_id=current_user.id,
            refresh_token=logout_request.refresh_token,
            ip_address=ip_address
        )

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during logout"
        )


@router.get(
    "/me",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get current user info",
    description="Get information about the currently authenticated user"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Get current user information

    Args:
        current_user: Currently authenticated user

    Returns:
        Dictionary containing user information
    """
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.username,  # Use username as display name
        "is_active": current_user.active_status,
        "role": {
            "id": str(current_user.role.id),
            "name": current_user.role.role_name,
            "permissions": current_user.role.permissions
        },
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat()
    }
