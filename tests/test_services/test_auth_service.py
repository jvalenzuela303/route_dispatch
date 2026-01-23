"""
Tests for AuthService

This module tests all authentication operations including:
- User login
- Token generation and verification
- Refresh token operations
- Logout functionality
- Security scenarios (expired tokens, invalid tokens, etc.)
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.services.auth_service import AuthService
from app.models.models import User, Role, RefreshToken
from app.models.enums import AuditResult
from app.exceptions import (
    InvalidCredentialsError,
    UserInactiveError,
    TokenExpiredError,
    InvalidTokenError
)
from app.config import get_settings


@pytest.fixture
def auth_service(db_session):
    """Create AuthService instance for testing"""
    return AuthService(db_session)


@pytest.fixture
def test_role(db_session):
    """Create test role"""
    role = Role(
        role_name="Test Role",
        description="Test role for authentication tests",
        permissions={"test": True}
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def test_user(db_session, test_role):
    """Create test user with hashed password"""
    user = User(
        username="testuser",
        email="testuser@test.com",
        password_hash=AuthService.hash_password("TestPassword123"),
        role_id=test_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session, test_role):
    """Create inactive test user"""
    user = User(
        username="inactiveuser",
        email="inactive@test.com",
        password_hash=AuthService.hash_password("TestPassword123"),
        role_id=test_role.id,
        active_status=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestLogin:
    """Tests for login functionality"""

    def test_login_success(self, auth_service, test_user):
        """Test successful login with valid credentials"""
        token_response = auth_service.login(
            username="testuser",
            password="TestPassword123"
        )

        assert token_response.access_token is not None
        assert token_response.refresh_token is not None
        assert token_response.token_type == "bearer"
        assert token_response.expires_in > 0

    def test_login_with_email(self, auth_service, test_user):
        """Test login using email instead of username"""
        token_response = auth_service.login(
            username="testuser@test.com",
            password="TestPassword123"
        )

        assert token_response.access_token is not None
        assert token_response.refresh_token is not None

    def test_login_invalid_password(self, auth_service, test_user):
        """Test login with incorrect password"""
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(
                username="testuser",
                password="WrongPassword"
            )

        assert "Invalid username or password" in str(exc_info.value)

    def test_login_user_not_found(self, auth_service):
        """Test login with non-existent user"""
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(
                username="nonexistent",
                password="TestPassword123"
            )

        assert "Invalid username or password" in str(exc_info.value)

    def test_login_inactive_user(self, auth_service, inactive_user):
        """Test login with deactivated user account"""
        with pytest.raises(UserInactiveError) as exc_info:
            auth_service.login(
                username="inactiveuser",
                password="TestPassword123"
            )

        assert "deactivated" in str(exc_info.value).lower()

    def test_login_creates_refresh_token_in_db(self, auth_service, test_user, db_session):
        """Test that login creates refresh token in database"""
        initial_count = db_session.query(RefreshToken).count()

        auth_service.login(
            username="testuser",
            password="TestPassword123"
        )

        final_count = db_session.query(RefreshToken).count()
        assert final_count == initial_count + 1


class TestTokenGeneration:
    """Tests for token generation"""

    def test_create_access_token(self, auth_service, test_user):
        """Test access token generation"""
        token = auth_service.create_access_token(test_user)

        assert token is not None
        assert isinstance(token, str)

        # Decode and verify token contents
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        assert payload["sub"] == str(test_user.id)
        assert payload["username"] == test_user.username
        assert payload["email"] == test_user.email
        assert payload["type"] == "access"

    def test_create_refresh_token(self, auth_service, test_user, db_session):
        """Test refresh token generation and storage"""
        initial_count = db_session.query(RefreshToken).count()

        token = auth_service.create_refresh_token(test_user)

        assert token is not None
        assert isinstance(token, str)

        # Verify token stored in database
        final_count = db_session.query(RefreshToken).count()
        assert final_count == initial_count + 1

        db_token = db_session.query(RefreshToken).filter(
            RefreshToken.token == token
        ).first()
        assert db_token is not None
        assert db_token.user_id == test_user.id
        assert db_token.is_revoked is False


class TestTokenVerification:
    """Tests for token verification"""

    def test_verify_access_token_valid(self, auth_service, test_user):
        """Test verification of valid access token"""
        token = auth_service.create_access_token(test_user)
        verified_user = auth_service.verify_access_token(token)

        assert verified_user.id == test_user.id
        assert verified_user.username == test_user.username

    def test_verify_access_token_expired(self, auth_service, test_user):
        """Test verification of expired access token"""
        settings = get_settings()

        # Create token that expired 1 hour ago
        expire = datetime.utcnow() - timedelta(hours=1)
        payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "email": test_user.email,
            "role": test_user.role.role_name,
            "exp": expire,
            "type": "access"
        }

        expired_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        with pytest.raises(TokenExpiredError) as exc_info:
            auth_service.verify_access_token(expired_token)

        assert "expired" in str(exc_info.value).lower()

    def test_verify_access_token_invalid_signature(self, auth_service, test_user):
        """Test verification of token with invalid signature"""
        # Create token with wrong secret
        payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }

        invalid_token = jwt.encode(
            payload,
            "wrong-secret-key",
            algorithm="HS256"
        )

        with pytest.raises(InvalidTokenError):
            auth_service.verify_access_token(invalid_token)

    def test_verify_access_token_missing_subject(self, auth_service):
        """Test verification of token missing subject claim"""
        settings = get_settings()

        payload = {
            "username": "testuser",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }

        invalid_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.verify_access_token(invalid_token)

        assert "subject" in str(exc_info.value).lower()


class TestRefreshToken:
    """Tests for refresh token operations"""

    def test_refresh_access_token_success(self, auth_service, test_user):
        """Test successful refresh of access token"""
        # Login to get initial tokens
        initial_response = auth_service.login(
            username="testuser",
            password="TestPassword123"
        )

        # Use refresh token to get new access token
        new_response = auth_service.refresh_access_token(
            refresh_token=initial_response.refresh_token
        )

        assert new_response.access_token is not None
        assert new_response.access_token != initial_response.access_token
        assert new_response.refresh_token == initial_response.refresh_token

    def test_refresh_access_token_not_found(self, auth_service):
        """Test refresh with non-existent token"""
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.refresh_access_token(
                refresh_token="non-existent-token"
            )

        assert "Invalid refresh token" in str(exc_info.value)

    def test_refresh_access_token_revoked(self, auth_service, test_user, db_session):
        """Test refresh with revoked token"""
        # Create refresh token
        refresh_token = auth_service.create_refresh_token(test_user)

        # Revoke it
        db_token = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        db_token.is_revoked = True
        db_session.commit()

        # Try to use revoked token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.refresh_access_token(refresh_token)

        assert "revoked" in str(exc_info.value).lower()

    def test_refresh_access_token_expired(self, auth_service, test_user, db_session):
        """Test refresh with expired token"""
        # Create refresh token with past expiration
        db_token = RefreshToken(
            token="expired-token",
            user_id=test_user.id,
            expires_at=datetime.utcnow() - timedelta(days=1),
            is_revoked=False
        )
        db_session.add(db_token)
        db_session.commit()

        with pytest.raises(TokenExpiredError) as exc_info:
            auth_service.refresh_access_token("expired-token")

        assert "expired" in str(exc_info.value).lower()


class TestLogout:
    """Tests for logout functionality"""

    def test_logout_success(self, auth_service, test_user, db_session):
        """Test successful logout"""
        # Create refresh token
        refresh_token = auth_service.create_refresh_token(test_user)

        # Logout
        result = auth_service.logout(test_user.id, refresh_token)

        assert result is True

        # Verify token is revoked
        db_token = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        assert db_token.is_revoked is True

    def test_logout_invalid_token(self, auth_service, test_user):
        """Test logout with invalid token"""
        with pytest.raises(InvalidTokenError):
            auth_service.logout(test_user.id, "invalid-token")

    def test_logout_prevents_refresh(self, auth_service, test_user):
        """Test that logged out token cannot be used for refresh"""
        # Create and logout
        refresh_token = auth_service.create_refresh_token(test_user)
        auth_service.logout(test_user.id, refresh_token)

        # Try to use revoked token
        with pytest.raises(InvalidTokenError):
            auth_service.refresh_access_token(refresh_token)


class TestPasswordHashing:
    """Tests for password hashing"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 50  # BCrypt hashes are long

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_hash_password_different_each_time(self):
        """Test that hashing same password produces different hashes (salt)"""
        password = "TestPassword123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert AuthService.verify_password(password, hash1) is True
        assert AuthService.verify_password(password, hash2) is True
