"""
Authentication and Authorization dependencies for FastAPI

These dependencies provide:
- JWT token extraction and verification
- User authentication from tokens
- Role-based access control (RBAC)
"""

from typing import List, Callable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.models.models import User
from app.services.auth_service import AuthService
from app.api.dependencies.database import get_db
from app.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    UserInactiveError,
    InsufficientPermissionsError
)


# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to extract and verify JWT access token from Authorization header

    Args:
        credentials: HTTP Bearer credentials from Authorization header
        db: Database session

    Returns:
        Authenticated User object

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found
    """
    token = credentials.credentials

    try:
        auth_service = AuthService(db)
        user = auth_service.verify_access_token(token)
        return user

    except (InvalidTokenError, TokenExpiredError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to verify that the authenticated user is active

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Active User object

    Raises:
        HTTPException 403: If user account is deactivated
    """
    if not current_user.active_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    return current_user


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Dependency factory that creates a role checker for specific roles

    This is a higher-order function that returns a dependency function
    configured to check for specific roles.

    Args:
        allowed_roles: List of role names that are allowed (e.g., ['Administrador', 'Encargado Bodega'])

    Returns:
        Dependency function that verifies user has one of the allowed roles

    Usage:
        @router.post("/users")
        async def create_user(
            user_data: UserCreate,
            current_user: User = Depends(require_roles(['Administrador']))
        ):
            # Only users with 'Administrador' role can access this endpoint
            pass

    Raises:
        HTTPException 403: If user doesn't have any of the required roles
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """
        Inner dependency that checks if user has required role

        Args:
            current_user: Active user from get_current_active_user dependency

        Returns:
            User object if they have required role

        Raises:
            HTTPException 403: If user lacks required role
        """
        user_role = current_user.role.role_name

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorized for this action. Required: {', '.join(allowed_roles)}"
            )

        return current_user

    return role_checker


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check for X-Forwarded-For header (if behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"
