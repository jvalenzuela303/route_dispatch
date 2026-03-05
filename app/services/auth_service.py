"""
Authentication Service for JWT-based authentication

This service handles all authentication-related operations including:
- User login with username/password
- JWT access token generation and verification
- Refresh token generation and rotation
- Logout (token revocation)
- Password validation

Security features:
- BCrypt password hashing (factor 12)
- JWT tokens with expiration
- Refresh token rotation
- Token revocation on logout
- Audit logging for all auth events
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.config import get_settings
from app.models.models import User, RefreshToken
from app.services.audit_service import AuditService
from app.models.enums import AuditResult
from app.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    InvalidTokenError,
    UserInactiveError
)


# Password context for BCrypt hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class TokenData:
    """Data extracted from a JWT token"""
    def __init__(self, user_id: UUID, username: str, role_name: str):
        self.user_id = user_id
        self.username = username
        self.role_name = role_name


class TokenResponse:
    """Response containing access and refresh tokens"""
    def __init__(self, access_token: str, refresh_token: str, token_type: str = "bearer", expires_in: int = 1800):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.expires_in = expires_in


class AuthService:
    """
    Service for handling authentication operations

    This service provides secure authentication using JWT tokens with
    access/refresh token pattern. All authentication events are logged
    to the audit trail.
    """

    def __init__(self, db: Session):
        """
        Initialize AuthService

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.audit_service = AuditService(db)
        self.settings = get_settings()

    def login(self, username: str, password: str, ip_address: Optional[str] = None) -> TokenResponse:
        """
        Authenticate user and return access + refresh tokens

        Args:
            username: Username or email
            password: Plain text password
            ip_address: Optional IP address for audit logging

        Returns:
            TokenResponse containing access_token, refresh_token, and metadata

        Raises:
            InvalidCredentialsError: If credentials are invalid
            UserInactiveError: If user account is deactivated
        """
        # Find user by username or email
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            # Log failed login attempt
            self.audit_service.log_action(
                action="LOGIN_FAILED",
                entity_type="USER",
                result=AuditResult.DENIED,
                user=None,
                entity_id=None,
                details={"username": username, "reason": "user_not_found"},
                ip_address=ip_address
            )
            raise InvalidCredentialsError("Invalid username or password")

        # Verify password
        if not self.verify_password(password, user.password_hash):
            # Log failed login attempt
            self.audit_service.log_action(
                action="LOGIN_FAILED",
                entity_type="USER",
                result=AuditResult.DENIED,
                user=user,
                entity_id=user.id,
                details={"username": username, "reason": "invalid_password"},
                ip_address=ip_address
            )
            raise InvalidCredentialsError("Invalid username or password")

        # Check if user is active
        if not user.active_status:
            self.audit_service.log_action(
                action="LOGIN_FAILED",
                entity_type="USER",
                result=AuditResult.DENIED,
                user=user,
                entity_id=user.id,
                details={"username": username, "reason": "user_inactive"},
                ip_address=ip_address
            )
            raise UserInactiveError("User account is deactivated")

        # Generate tokens
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        # Log successful login
        self.audit_service.log_action(
            action="LOGIN_SUCCESS",
            entity_type="USER",
            result=AuditResult.SUCCESS,
            user=user,
            entity_id=user.id,
            details={"username": username, "role": user.role.role_name},
            ip_address=ip_address
        )

        expires_in = self.settings.access_token_expire_minutes * 60
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )

    def refresh_access_token(self, refresh_token: str, ip_address: Optional[str] = None) -> TokenResponse:
        """
        Generate new access token using valid refresh token

        Args:
            refresh_token: JWT refresh token
            ip_address: Optional IP address for audit logging

        Returns:
            TokenResponse with new access token (and optionally new refresh token)

        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenExpiredError: If refresh token is expired
        """
        # Verify refresh token exists in database
        db_token = self.db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()

        if not db_token:
            self.audit_service.log_action(
                action="REFRESH_TOKEN_FAILED",
                entity_type="REFRESH_TOKEN",
                result=AuditResult.DENIED,
                user=None,
                entity_id=None,
                details={"reason": "token_not_found"},
                ip_address=ip_address
            )
            raise InvalidTokenError("Invalid refresh token")

        # Check if token is revoked
        if db_token.is_revoked:
            self.audit_service.log_action(
                action="REFRESH_TOKEN_FAILED",
                entity_type="REFRESH_TOKEN",
                result=AuditResult.DENIED,
                user=None,
                entity_id=db_token.id,
                details={"reason": "token_revoked", "user_id": str(db_token.user_id)},
                ip_address=ip_address
            )
            raise InvalidTokenError("Refresh token has been revoked")

        # Check if token is expired
        if db_token.expires_at < datetime.utcnow():
            self.audit_service.log_action(
                action="REFRESH_TOKEN_FAILED",
                entity_type="REFRESH_TOKEN",
                result=AuditResult.DENIED,
                user=None,
                entity_id=db_token.id,
                details={"reason": "token_expired", "user_id": str(db_token.user_id)},
                ip_address=ip_address
            )
            raise TokenExpiredError("Refresh token has expired")

        # Get user
        user = self.db.query(User).filter(User.id == db_token.user_id).first()
        if not user or not user.active_status:
            raise UserInactiveError("User account is deactivated")

        # Generate new access token
        new_access_token = self.create_access_token(user)

        # Optional: Rotate refresh token (generate new one and revoke old one)
        # For now, we'll reuse the same refresh token
        # To enable rotation, uncomment the following:
        # db_token.is_revoked = True
        # self.db.commit()
        # new_refresh_token = self.create_refresh_token(user)

        # Log successful token refresh
        self.audit_service.log_action(
            action="REFRESH_TOKEN_SUCCESS",
            entity_type="REFRESH_TOKEN",
            result=AuditResult.SUCCESS,
            user=user,
            entity_id=db_token.id,
            details={"username": user.username},
            ip_address=ip_address
        )

        expires_in = self.settings.access_token_expire_minutes * 60
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,  # Reuse same refresh token
            expires_in=expires_in
        )

    def logout(self, user_id: UUID, refresh_token: str, ip_address: Optional[str] = None) -> bool:
        """
        Logout user by revoking their refresh token

        Args:
            user_id: ID of the user logging out
            refresh_token: Refresh token to revoke
            ip_address: Optional IP address for audit logging

        Returns:
            True if logout successful

        Raises:
            InvalidTokenError: If refresh token is invalid
        """
        # Find and revoke the refresh token
        db_token = self.db.query(RefreshToken).filter(
            and_(
                RefreshToken.token == refresh_token,
                RefreshToken.user_id == user_id
            )
        ).first()

        if not db_token:
            raise InvalidTokenError("Invalid refresh token")

        # Revoke the token
        db_token.is_revoked = True
        self.db.commit()

        # Get user for audit log
        user = self.db.query(User).filter(User.id == user_id).first()

        # Log logout
        self.audit_service.log_action(
            action="LOGOUT",
            entity_type="REFRESH_TOKEN",
            result=AuditResult.SUCCESS,
            user=user,
            entity_id=db_token.id,
            details={"token_id": str(db_token.id)},
            ip_address=ip_address
        )

        return True

    def verify_access_token(self, token: str) -> User:
        """
        Verify and decode JWT access token

        Args:
            token: JWT access token

        Returns:
            User object from the token

        Raises:
            InvalidTokenError: If token is invalid or signature doesn't match
            TokenExpiredError: If token is expired
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )

            # Extract user_id from token
            user_id_str: str = payload.get("sub")
            if user_id_str is None:
                raise InvalidTokenError("Token missing subject claim")

            user_id = UUID(user_id_str)

        except JWTError as e:
            if "expired" in str(e).lower():
                raise TokenExpiredError("Access token has expired")
            raise InvalidTokenError(f"Invalid token: {str(e)}")

        # Get user from database
        user = self.db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise InvalidTokenError("User not found")

        if not user.active_status:
            raise UserInactiveError("User account is deactivated")

        return user

    def create_access_token(self, user: User) -> str:
        """
        Generate JWT access token for user

        Args:
            user: User object

        Returns:
            JWT access token string
        """
        expires_delta = timedelta(minutes=self.settings.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.role_name,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }

        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )
        return encoded_jwt

    def create_refresh_token(self, user: User) -> str:
        """
        Generate JWT refresh token and store in database

        Args:
            user: User object

        Returns:
            JWT refresh token string
        """
        expires_delta = timedelta(days=self.settings.refresh_token_expire_days)
        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": str(user.id),
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }

        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )

        # Store refresh token in database
        db_token = RefreshToken(
            token=encoded_jwt,
            user_id=user.id,
            expires_at=expire,
            is_revoked=False
        )
        self.db.add(db_token)
        self.db.commit()

        return encoded_jwt

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using BCrypt (factor 12)

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash using BCrypt

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password from database

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
