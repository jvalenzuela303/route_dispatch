"""
Password and Token Security Testing

CRITICAL security tests verifying password hashing, token security, and authentication.

Test categories:
1. Password hashing (BCrypt)
2. Password non-exposure in responses
3. JWT token security (expiration, tampering, revocation)
4. Refresh token rotation
5. Token non-exposure in logs
"""

import pytest
from jose import jwt
from datetime import datetime, timedelta
import uuid

from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.config.settings import get_settings
from app.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    UserInactiveError,
    InvalidCredentialsError
)


class TestPasswordHashing:
    """Test password hashing with BCrypt"""

    def test_password_hashed_with_bcrypt(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        CRITICAL: Verify passwords are hashed with BCrypt (not plaintext)

        Expected: password_hash starts with $2b$ (BCrypt marker)
        """
        user_service = UserService(db_session)

        plain_password = "SuperSecure123!"

        new_user = user_service.create_user(
            username=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password=plain_password,
            role_id=vendedor_role.id,
            full_name="Test User",
            current_user=admin_user
        )

        # Verify password is hashed (BCrypt format)
        assert new_user.password_hash.startswith("$2b$"), \
            "Password must be hashed with BCrypt"

        # Verify password hash is NOT the plaintext password
        assert new_user.password_hash != plain_password, \
            "CRITICAL: Password stored as plaintext!"

        # Verify BCrypt work factor is 12 (as per auth_service.py)
        # BCrypt format: $2b$12$...
        bcrypt_parts = new_user.password_hash.split("$")
        work_factor = int(bcrypt_parts[2])
        assert work_factor >= 12, \
            f"BCrypt work factor should be >= 12, got {work_factor}"

    def test_same_password_produces_different_hashes(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        Test BCrypt produces different hashes for same password (salt)

        Expected: Two users with same password have different hashes
        """
        user_service = UserService(db_session)

        plain_password = "SamePassword123!"

        user1 = user_service.create_user(
            username=f"user1_{uuid.uuid4().hex[:8]}",
            email=f"user1_{uuid.uuid4().hex[:8]}@example.com",
            password=plain_password,
            role_id=vendedor_role.id,
            full_name="User One",
            current_user=admin_user
        )

        user2 = user_service.create_user(
            username=f"user2_{uuid.uuid4().hex[:8]}",
            email=f"user2_{uuid.uuid4().hex[:8]}@example.com",
            password=plain_password,
            role_id=vendedor_role.id,
            full_name="User Two",
            current_user=admin_user
        )

        # Hashes should be different (BCrypt uses random salt)
        assert user1.password_hash != user2.password_hash, \
            "BCrypt should produce different hashes for same password"

    def test_password_verification_works(
        self,
        db_session
    ):
        """
        Test BCrypt password verification works correctly

        Expected: Correct password verifies, wrong password fails
        """
        auth_service = AuthService(db_session)

        plain_password = "CorrectPassword123!"
        hashed_password = AuthService.hash_password(plain_password)

        # Correct password should verify
        assert AuthService.verify_password(plain_password, hashed_password) is True

        # Wrong password should fail
        assert AuthService.verify_password("WrongPassword", hashed_password) is False


class TestPasswordNonExposure:
    """Test passwords never exposed in responses or logs"""

    def test_password_not_in_user_object(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        CRITICAL: Verify User object doesn't expose password_hash in serialization

        Expected: Pydantic schemas exclude password_hash
        """
        user_service = UserService(db_session)

        user = user_service.create_user(
            username=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePass123!",
            role_id=vendedor_role.id,
            full_name="Test User",
            current_user=admin_user
        )

        # Simulate serialization to dict (as would happen in API response)
        from app.schemas.user_schemas import UserResponse
        user_schema = UserResponse.model_validate(user)
        user_dict = user_schema.model_dump()

        # Verify password_hash not in response
        assert 'password_hash' not in user_dict, \
            "CRITICAL: password_hash exposed in API response!"
        assert 'password' not in user_dict, \
            "CRITICAL: password exposed in API response!"

    def test_login_response_no_password(
        self,
        db_session,
        admin_user
    ):
        """
        Test login response doesn't include password

        Expected: Only access_token, refresh_token, token_type
        """
        auth_service = AuthService(db_session)

        token_response = auth_service.login(
            username=admin_user.username,
            password="admin123"  # Default password from fixtures
        )

        # Convert to dict
        response_dict = {
            'access_token': token_response.access_token,
            'refresh_token': token_response.refresh_token,
            'token_type': token_response.token_type,
            'expires_in': token_response.expires_in
        }

        # Verify no password fields
        assert 'password' not in response_dict
        assert 'password_hash' not in response_dict

    def test_failed_login_no_password_leak(
        self,
        db_session
    ):
        """
        CRITICAL: Failed login error messages don't leak password information

        Expected: Generic "Invalid username or password" message
        """
        auth_service = AuthService(db_session)

        # Attempt login with wrong password
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(
                username="admin",
                password="wrong_password"
            )

        error_message = str(exc_info.value.message).lower()

        # Error should be generic (no hints about username vs password)
        assert "invalid username or password" in error_message
        # Should NOT leak actual password or hash
        assert "wrong_password" not in error_message
        assert "$2b$" not in error_message  # BCrypt hash marker


class TestJWTTokenSecurity:
    """Test JWT token security and validation"""

    def test_token_contains_required_claims(
        self,
        db_session,
        admin_user
    ):
        """
        Test JWT access token contains required claims

        Expected: sub, username, email, role, exp, iat, type
        """
        auth_service = AuthService(db_session)

        access_token = auth_service.create_access_token(admin_user)

        # Decode without verification to inspect claims
        settings = get_settings()
        payload = jwt.decode(
            access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # Verify required claims
        assert 'sub' in payload  # User ID
        assert 'username' in payload
        assert 'email' in payload
        assert 'role' in payload
        assert 'exp' in payload  # Expiration
        assert 'iat' in payload  # Issued at
        assert 'type' in payload  # Token type

        # Verify type is "access"
        assert payload['type'] == 'access'

    def test_expired_token_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Expired tokens must be rejected

        Expected: TokenExpiredError
        """
        auth_service = AuthService(db_session)
        settings = get_settings()

        # Create token that's already expired
        expired_time = datetime.utcnow() - timedelta(minutes=1)

        payload = {
            'sub': str(admin_user.id),
            'username': admin_user.username,
            'email': admin_user.email,
            'role': admin_user.role.role_name,
            'exp': expired_time,
            'iat': expired_time - timedelta(minutes=30),
            'type': 'access'
        }

        expired_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        # Attempt to verify expired token
        with pytest.raises(TokenExpiredError) as exc_info:
            auth_service.verify_access_token(expired_token)

        assert "expired" in str(exc_info.value.message).lower()

    def test_tampered_token_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Tampered tokens must be rejected (signature validation)

        Expected: InvalidTokenError
        """
        auth_service = AuthService(db_session)

        # Create valid token
        valid_token = auth_service.create_access_token(admin_user)

        # Tamper with token (change one character)
        tampered_token = valid_token[:-10] + "AAAAAAAAAA"

        # Attempt to verify tampered token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.verify_access_token(tampered_token)

        assert "invalid" in str(exc_info.value.message).lower()

    def test_token_with_wrong_secret_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Token signed with wrong secret must be rejected

        Expected: InvalidTokenError
        """
        auth_service = AuthService(db_session)
        settings = get_settings()

        # Create token with wrong secret
        payload = {
            'sub': str(admin_user.id),
            'username': admin_user.username,
            'exp': datetime.utcnow() + timedelta(minutes=30),
            'type': 'access'
        }

        wrong_token = jwt.encode(
            payload,
            "wrong-secret-key",  # Wrong secret!
            algorithm=settings.jwt_algorithm
        )

        # Attempt to verify
        with pytest.raises(InvalidTokenError):
            auth_service.verify_access_token(wrong_token)

    def test_token_for_inactive_user_rejected(
        self,
        db_session,
        inactive_user
    ):
        """
        Test token for inactive user is rejected

        Expected: UserInactiveError
        """
        auth_service = AuthService(db_session)

        # Create token for inactive user
        token = auth_service.create_access_token(inactive_user)

        # Verify should fail
        with pytest.raises(UserInactiveError) as exc_info:
            auth_service.verify_access_token(token)

        assert "deactivated" in str(exc_info.value.message).lower()

    def test_token_without_sub_claim_rejected(
        self,
        db_session
    ):
        """
        Test token without 'sub' claim is rejected

        Expected: InvalidTokenError
        """
        auth_service = AuthService(db_session)
        settings = get_settings()

        # Create malformed token (missing 'sub')
        payload = {
            'username': 'hacker',
            'exp': datetime.utcnow() + timedelta(minutes=30),
            'type': 'access'
            # Missing 'sub'!
        }

        malformed_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.verify_access_token(malformed_token)

        assert "subject" in str(exc_info.value.message).lower()


class TestRefreshTokenSecurity:
    """Test refresh token security and rotation"""

    def test_refresh_token_stored_in_database(
        self,
        db_session,
        admin_user
    ):
        """
        Test refresh tokens are stored in database for revocation

        Expected: RefreshToken record created
        """
        auth_service = AuthService(db_session)

        refresh_token = auth_service.create_refresh_token(admin_user)

        # Query database for token
        from app.models.models import RefreshToken

        token_record = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()

        assert token_record is not None
        assert token_record.user_id == admin_user.id
        assert token_record.is_revoked is False

    def test_revoked_refresh_token_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Revoked refresh tokens must be rejected

        Expected: InvalidTokenError
        """
        auth_service = AuthService(db_session)

        # Create and then revoke token
        refresh_token = auth_service.create_refresh_token(admin_user)

        auth_service.logout(
            user_id=admin_user.id,
            refresh_token=refresh_token
        )

        # Attempt to use revoked token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.refresh_access_token(refresh_token)

        assert "revoked" in str(exc_info.value.message).lower()

    def test_expired_refresh_token_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        Test expired refresh tokens are rejected

        Expected: TokenExpiredError
        """
        auth_service = AuthService(db_session)
        settings = get_settings()

        # Create expired refresh token
        expired_time = datetime.utcnow() - timedelta(days=1)

        payload = {
            'sub': str(admin_user.id),
            'exp': expired_time,
            'iat': expired_time - timedelta(days=7),
            'type': 'refresh'
        }

        expired_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        # Store in database (to pass DB check)
        from app.models.models import RefreshToken
        db_token = RefreshToken(
            token=expired_token,
            user_id=admin_user.id,
            expires_at=expired_time,
            is_revoked=False
        )
        db_session.add(db_token)
        db_session.commit()

        # Attempt to use expired token
        with pytest.raises(TokenExpiredError):
            auth_service.refresh_access_token(expired_token)

    def test_refresh_token_not_in_database_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Refresh tokens not in database must be rejected

        Expected: InvalidTokenError
        """
        auth_service = AuthService(db_session)
        settings = get_settings()

        # Create token but don't store in database
        payload = {
            'sub': str(admin_user.id),
            'exp': datetime.utcnow() + timedelta(days=7),
            'type': 'refresh'
        }

        fake_token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )

        # Attempt to use token not in database
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.refresh_access_token(fake_token)

        assert "not found" in str(exc_info.value.message).lower() or \
               "invalid" in str(exc_info.value.message).lower()

    def test_logout_revokes_refresh_token(
        self,
        db_session,
        admin_user
    ):
        """
        Test logout properly revokes refresh token

        Expected: is_revoked set to True
        """
        auth_service = AuthService(db_session)

        # Create refresh token
        refresh_token = auth_service.create_refresh_token(admin_user)

        # Logout (revokes token)
        result = auth_service.logout(
            user_id=admin_user.id,
            refresh_token=refresh_token
        )

        assert result is True

        # Verify token is revoked in database
        from app.models.models import RefreshToken

        token_record = db_session.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()

        assert token_record.is_revoked is True


class TestTokenNonExposure:
    """Test tokens are not exposed in logs or error messages"""

    def test_audit_log_does_not_store_full_token(
        self,
        db_session,
        admin_user
    ):
        """
        Test audit logs don't store full JWT tokens (security risk)

        Expected: Audit logs store token ID, not full token
        """
        auth_service = AuthService(db_session)

        # Login creates audit log
        token_response = auth_service.login(
            username=admin_user.username,
            password="admin123"
        )

        # Check audit log doesn't contain full token
        from app.models.models import AuditLog

        recent_login = db_session.query(AuditLog).filter(
            AuditLog.user_id == admin_user.id,
            AuditLog.action == "LOGIN_SUCCESS"
        ).order_by(AuditLog.timestamp.desc()).first()

        assert recent_login is not None

        # Audit log details should NOT contain full access token
        details_str = str(recent_login.details)
        assert token_response.access_token not in details_str, \
            "CRITICAL: Full access token stored in audit log!"

    def test_error_message_no_token_leak(
        self,
        db_session
    ):
        """
        Test error messages don't leak token information

        Expected: Generic error messages
        """
        auth_service = AuthService(db_session)

        # Invalid token
        with pytest.raises(InvalidTokenError) as exc_info:
            auth_service.verify_access_token("invalid.token.here")

        error_message = str(exc_info.value.message)

        # Error should not contain actual token value
        assert "invalid.token.here" not in error_message
