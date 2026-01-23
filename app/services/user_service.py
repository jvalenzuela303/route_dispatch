"""
User Service for user management operations

This service handles all user-related CRUD operations including:
- Creating users (admin only)
- Retrieving user information
- Updating user details
- Soft deleting users
- Password management

All operations enforce RBAC rules and log audit trails.
"""

from typing import List, Optional
from uuid import UUID
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError as SQLIntegrityError

from app.models.models import User, Role
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.services.auth_service import AuthService
from app.models.enums import AuditResult
from app.exceptions import (
    NotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    WeakPasswordError,
    InvalidCredentialsError
)


class UserService:
    """
    Service for managing user operations

    This service provides secure user management with:
    - RBAC enforcement
    - Password strength validation
    - Audit logging
    - Soft delete support
    """

    def __init__(self, db: Session):
        """
        Initialize UserService

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.audit_service = AuditService(db)
        self.permission_service = PermissionService(db)

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role_id: UUID,
        created_by: User,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Create a new user

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            role_id: ID of the role to assign
            created_by: User creating this user (must be Admin)
            ip_address: Optional IP address for audit logging

        Returns:
            Created User object

        Raises:
            InsufficientPermissionsError: If created_by is not Admin
            UserAlreadyExistsError: If username or email already exists
            NotFoundError: If role_id doesn't exist
            WeakPasswordError: If password doesn't meet requirements
        """
        # Validate permissions - only Admin can create users
        if not self.permission_service.can_create_user(created_by):
            self.audit_service.log_action(
                user_id=created_by.id,
                action="CREATE_USER_FAILED",
                entity_type="USER",
                entity_id=None,
                details={"reason": "insufficient_permissions", "username": username},
                result=AuditResult.DENIED,
                ip_address=ip_address
            )
            raise InsufficientPermissionsError(
                action="create_user",
                user_role=created_by.role.role_name,
                required_role="Administrador"
            )

        # Validate password strength
        self._validate_password_strength(password)

        # Check if username already exists
        existing_user = self.db.query(User).filter(User.username == username).first()
        if existing_user:
            raise UserAlreadyExistsError(field="username", value=username)

        # Check if email already exists
        existing_email = self.db.query(User).filter(User.email == email).first()
        if existing_email:
            raise UserAlreadyExistsError(field="email", value=email)

        # Validate role exists
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise NotFoundError(
                code="ROLE_NOT_FOUND",
                message=f"Role with ID {role_id} not found"
            )

        # Hash password
        password_hash = AuthService.hash_password(password)

        # Create user
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
            active_status=True
        )

        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
        except SQLIntegrityError as e:
            self.db.rollback()
            raise UserAlreadyExistsError(field="username or email", value=username)

        # Log user creation
        self.audit_service.log_action(
            user_id=created_by.id,
            action="CREATE_USER",
            entity_type="USER",
            entity_id=new_user.id,
            details={
                "username": username,
                "email": email,
                "role": role.role_name,
                "created_by": created_by.username
            },
            result=AuditResult.SUCCESS,
            ip_address=ip_address
        )

        return new_user

    def get_user(self, user_id: UUID, requester: User) -> User:
        """
        Get user by ID

        Args:
            user_id: ID of user to retrieve
            requester: User making the request

        Returns:
            User object

        Raises:
            NotFoundError: If user doesn't exist
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found"
            )

        # Users can view their own profile
        # Admin and Encargado Bodega can view all users
        if user_id != requester.id:
            if requester.role.role_name not in ['Administrador', 'Encargado Bodega']:
                raise InsufficientPermissionsError(
                    action="view_user",
                    user_role=requester.role.role_name
                )

        return user

    def list_users(
        self,
        requester: User,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> List[User]:
        """
        List users with pagination

        Args:
            requester: User making the request
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Whether to return only active users

        Returns:
            List of User objects

        Raises:
            InsufficientPermissionsError: If requester lacks permissions
        """
        # Only Admin and Encargado Bodega can list users
        if requester.role.role_name not in ['Administrador', 'Encargado Bodega']:
            raise InsufficientPermissionsError(
                action="list_users",
                user_role=requester.role.role_name
            )

        query = self.db.query(User)

        if active_only:
            query = query.filter(User.active_status == True)

        users = query.offset(skip).limit(limit).all()
        return users

    def update_user(
        self,
        user_id: UUID,
        updated_by: User,
        username: Optional[str] = None,
        email: Optional[str] = None,
        role_id: Optional[UUID] = None,
        active_status: Optional[bool] = None,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Update user information

        Args:
            user_id: ID of user to update
            updated_by: User performing the update (must be Admin)
            username: New username (optional)
            email: New email (optional)
            role_id: New role ID (optional)
            active_status: New active status (optional)
            ip_address: Optional IP address for audit logging

        Returns:
            Updated User object

        Raises:
            NotFoundError: If user doesn't exist
            InsufficientPermissionsError: If updated_by is not Admin
            UserAlreadyExistsError: If username/email already taken
        """
        # Only Admin can update users
        if not self.permission_service.can_create_user(updated_by):
            raise InsufficientPermissionsError(
                action="update_user",
                user_role=updated_by.role.role_name,
                required_role="Administrador"
            )

        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found"
            )

        update_details = {}

        # Update username if provided
        if username is not None and username != user.username:
            existing = self.db.query(User).filter(User.username == username).first()
            if existing:
                raise UserAlreadyExistsError(field="username", value=username)
            user.username = username
            update_details['username'] = username

        # Update email if provided
        if email is not None and email != user.email:
            existing = self.db.query(User).filter(User.email == email).first()
            if existing:
                raise UserAlreadyExistsError(field="email", value=email)
            user.email = email
            update_details['email'] = email

        # Update role if provided
        if role_id is not None and role_id != user.role_id:
            role = self.db.query(Role).filter(Role.id == role_id).first()
            if not role:
                raise NotFoundError(
                    code="ROLE_NOT_FOUND",
                    message=f"Role with ID {role_id} not found"
                )
            old_role = user.role.role_name
            user.role_id = role_id
            update_details['role'] = {'old': old_role, 'new': role.role_name}

        # Update active status if provided
        if active_status is not None and active_status != user.active_status:
            user.active_status = active_status
            update_details['active_status'] = active_status

        self.db.commit()
        self.db.refresh(user)

        # Log update
        self.audit_service.log_action(
            user_id=updated_by.id,
            action="UPDATE_USER",
            entity_type="USER",
            entity_id=user.id,
            details={
                "updated_user": user.username,
                "updated_by": updated_by.username,
                "changes": update_details
            },
            result=AuditResult.SUCCESS,
            ip_address=ip_address
        )

        return user

    def delete_user(
        self,
        user_id: UUID,
        deleted_by: User,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Soft delete user (set active_status to False)

        Args:
            user_id: ID of user to delete
            deleted_by: User performing the deletion (must be Admin)
            ip_address: Optional IP address for audit logging

        Returns:
            True if deletion successful

        Raises:
            NotFoundError: If user doesn't exist
            InsufficientPermissionsError: If deleted_by is not Admin
        """
        # Only Admin can delete users
        if not self.permission_service.can_create_user(deleted_by):
            raise InsufficientPermissionsError(
                action="delete_user",
                user_role=deleted_by.role.role_name,
                required_role="Administrador"
            )

        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found"
            )

        # Soft delete - set active_status to False
        user.active_status = False
        self.db.commit()

        # Log deletion
        self.audit_service.log_action(
            user_id=deleted_by.id,
            action="DELETE_USER",
            entity_type="USER",
            entity_id=user.id,
            details={
                "deleted_user": user.username,
                "deleted_by": deleted_by.username
            },
            result=AuditResult.SUCCESS,
            ip_address=ip_address
        )

        return True

    def change_password(
        self,
        user_id: UUID,
        requester: User,
        new_password: str,
        old_password: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Change user password

        Args:
            user_id: ID of user whose password to change
            requester: User making the request
            new_password: New plain text password (will be hashed)
            old_password: Current password (required if user changes own password)
            ip_address: Optional IP address for audit logging

        Returns:
            True if password changed successfully

        Raises:
            NotFoundError: If user doesn't exist
            InsufficientPermissionsError: If requester lacks permissions
            InvalidCredentialsError: If old_password is incorrect
            WeakPasswordError: If new password doesn't meet requirements
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found"
            )

        is_own_password = (user_id == requester.id)
        is_admin = self.permission_service.can_create_user(requester)

        # Permission checks
        if not is_own_password and not is_admin:
            raise InsufficientPermissionsError(
                action="change_password",
                user_role=requester.role.role_name
            )

        # If user is changing their own password, verify old password
        if is_own_password and old_password:
            if not AuthService.verify_password(old_password, user.password_hash):
                self.audit_service.log_action(
                    user_id=requester.id,
                    action="CHANGE_PASSWORD_FAILED",
                    entity_type="USER",
                    entity_id=user.id,
                    details={"reason": "invalid_old_password"},
                    result=AuditResult.DENIED,
                    ip_address=ip_address
                )
                raise InvalidCredentialsError("Current password is incorrect")

        # Validate new password strength
        self._validate_password_strength(new_password)

        # Hash and update password
        user.password_hash = AuthService.hash_password(new_password)
        self.db.commit()

        # Log password change
        self.audit_service.log_action(
            user_id=requester.id,
            action="CHANGE_PASSWORD",
            entity_type="USER",
            entity_id=user.id,
            details={
                "target_user": user.username,
                "changed_by": requester.username,
                "is_own_password": is_own_password
            },
            result=AuditResult.SUCCESS,
            ip_address=ip_address
        )

        return True

    def _validate_password_strength(self, password: str) -> None:
        """
        Validate password meets security requirements

        Requirements:
        - At least 8 characters
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit

        Args:
            password: Password to validate

        Raises:
            WeakPasswordError: If password doesn't meet requirements
        """
        if len(password) < 8:
            raise WeakPasswordError(
                "Password must be at least 8 characters long"
            )

        if not re.search(r'[A-Z]', password):
            raise WeakPasswordError(
                "Password must contain at least one uppercase letter"
            )

        if not re.search(r'[a-z]', password):
            raise WeakPasswordError(
                "Password must contain at least one lowercase letter"
            )

        if not re.search(r'\d', password):
            raise WeakPasswordError(
                "Password must contain at least one digit"
            )
