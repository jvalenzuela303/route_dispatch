"""
User Management API endpoints

This module provides endpoints for:
- Creating users (admin only)
- Listing users (admin and warehouse manager)
- Retrieving user details
- Updating user information (admin only)
- Deleting/deactivating users (admin only)
- Changing passwords

All operations enforce RBAC and log audit trails.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api.dependencies.database import get_db
from app.api.dependencies.auth import (
    get_current_active_user,
    require_roles,
    get_client_ip
)
from app.schemas.user_schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse
)
from app.schemas.auth_schemas import ChangePasswordRequest
from app.models.models import User
from app.services.user_service import UserService
from app.exceptions import (
    NotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    WeakPasswordError,
    InvalidCredentialsError
)


router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user (admin only)"
)
async def create_user(
    user_data: UserCreate,
    request: Request,
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Create a new user

    Only administrators can create users.

    Args:
        user_data: User creation data
        request: FastAPI request object (for IP logging)
        current_user: Currently authenticated admin user
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 409: If username or email already exists
        HTTPException 400: If password is weak
        HTTPException 404: If role_id doesn't exist
    """
    ip_address = get_client_ip(request)

    try:
        user_service = UserService(db)
        new_user = user_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role_id=user_data.role_id,
            created_by=current_user,
            ip_address=ip_address
        )

        return UserResponse.model_validate(new_user)

    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )
    except WeakPasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating user"
        )


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List users",
    description="List all users with pagination (admin and warehouse manager only)"
)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    active_only: bool = Query(True, description="Only return active users"),
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
) -> List[UserResponse]:
    """
    List users with pagination

    Only administrators and warehouse managers can list users.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        active_only: Whether to return only active users
        current_user: Currently authenticated user
        db: Database session

    Returns:
        List of user information

    Raises:
        HTTPException 403: If user lacks permissions
    """
    try:
        user_service = UserService(db)
        users = user_service.list_users(
            requester=current_user,
            skip=skip,
            limit=limit,
            active_only=active_only
        )

        return [UserResponse.model_validate(user) for user in users]

    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing users"
        )


@router.get(
    "/roles",
    response_model=list,
    status_code=status.HTTP_200_OK,
    summary="List roles",
    description="List all available roles for user assignment"
)
async def list_roles(
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
) -> list:
    """Return all roles for use in user create/edit forms."""
    from app.models.models import Role
    roles = db.query(Role).order_by(Role.role_name).all()
    return [
        {"id": str(r.id), "role_name": r.role_name, "description": r.description}
        for r in roles
    ]


@router.get(
    "/drivers",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List drivers",
    description="List all active users with Repartidor role (for route assignment)"
)
async def list_drivers(
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
) -> List[UserResponse]:
    """
    Get all active drivers (Repartidor role) for route assignment

    Returns:
        List of active Repartidor users
    """
    from app.models.models import Role
    drivers = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(
            Role.role_name == 'Repartidor',
            User.active_status == True
        )
        .order_by(User.username)
        .all()
    )
    return [UserResponse.model_validate(u) for u in drivers]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user",
    description="Get user details by ID"
)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Get user by ID

    Users can view their own profile. Admin and warehouse manager can view all users.

    Args:
        user_id: ID of user to retrieve
        current_user: Currently authenticated user
        db: Database session

    Returns:
        User information

    Raises:
        HTTPException 404: If user not found
        HTTPException 403: If user lacks permissions
    """
    try:
        user_service = UserService(db)
        user = user_service.get_user(user_id, current_user)

        return UserResponse.model_validate(user)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving user"
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user",
    description="Update user information (admin only)"
)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Update user information

    Only administrators can update users.

    Args:
        user_id: ID of user to update
        user_data: User update data
        request: FastAPI request object (for IP logging)
        current_user: Currently authenticated admin user
        db: Database session

    Returns:
        Updated user information

    Raises:
        HTTPException 404: If user not found
        HTTPException 403: If user is not admin
        HTTPException 409: If username/email already taken
    """
    ip_address = get_client_ip(request)

    try:
        user_service = UserService(db)
        updated_user = user_service.update_user(
            user_id=user_id,
            updated_by=current_user,
            username=user_data.username,
            email=user_data.email,
            role_id=user_data.role_id,
            active_status=user_data.active_status,
            ip_address=ip_address
        )

        return UserResponse.model_validate(updated_user)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message
        )
    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating user"
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Soft delete user (set active_status=False) - admin only"
)
async def delete_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
) -> None:
    """
    Delete user (soft delete)

    Only administrators can delete users. This sets active_status to False
    rather than actually deleting the record.

    Args:
        user_id: ID of user to delete
        request: FastAPI request object (for IP logging)
        current_user: Currently authenticated admin user
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: If user not found
        HTTPException 403: If user is not admin
    """
    ip_address = get_client_ip(request)

    try:
        user_service = UserService(db)
        user_service.delete_user(
            user_id=user_id,
            deleted_by=current_user,
            ip_address=ip_address
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting user"
        )


@router.put(
    "/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change user password. Users can change their own password. Admins can change any password."
)
async def change_password(
    user_id: UUID,
    password_data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> None:
    """
    Change user password

    Users can change their own password (requires old_password).
    Admins can change any user's password (old_password not required).

    Args:
        user_id: ID of user whose password to change
        password_data: Password change data
        request: FastAPI request object (for IP logging)
        current_user: Currently authenticated user
        db: Database session

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: If user not found
        HTTPException 403: If user lacks permissions
        HTTPException 401: If old_password is incorrect
        HTTPException 400: If new password is weak
    """
    ip_address = get_client_ip(request)

    try:
        user_service = UserService(db)
        user_service.change_password(
            user_id=user_id,
            requester=current_user,
            new_password=password_data.new_password,
            old_password=password_data.old_password,
            ip_address=ip_address
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except InsufficientPermissionsError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message
        )
    except WeakPasswordError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while changing password"
        )
