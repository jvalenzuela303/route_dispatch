"""
Integration tests for authentication API endpoints

Tests all auth endpoints including:
- POST /api/auth/login
- POST /api/auth/refresh
- POST /api/auth/logout
- GET /api/auth/me
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.models import User, Role
from app.services.auth_service import AuthService
from app.api.dependencies.database import get_db


@pytest.fixture
def test_client(db_session):
    """Create test client with dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_role(db_session):
    """Create test role"""
    role = Role(
        role_name="Test Role",
        description="Test role",
        permissions={}
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def test_user(db_session, test_role):
    """Create active test user"""
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


class TestLoginEndpoint:
    """Tests for POST /api/auth/login"""

    def test_login_success(self, test_client, test_user):
        """Test successful login"""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "TestPassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_with_email(self, test_client, test_user):
        """Test login using email"""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser@test.com",
                "password": "TestPassword123"
            }
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_invalid_password(self, test_client, test_user):
        """Test login with wrong password"""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "WrongPassword"
            }
        )

        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_user_not_found(self, test_client):
        """Test login with non-existent user"""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "nonexistent",
                "password": "TestPassword123"
            }
        )

        assert response.status_code == 401

    def test_login_inactive_user(self, test_client, inactive_user):
        """Test login with deactivated account"""
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": "inactiveuser",
                "password": "TestPassword123"
            }
        )

        assert response.status_code == 403
        assert "deactivated" in response.json()["detail"].lower()


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh"""

    def test_refresh_success(self, test_client, test_user):
        """Test successful token refresh"""
        # Login first
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "TestPassword123"
            }
        )

        refresh_token = login_response.json()["refresh_token"]

        # Refresh
        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, test_client):
        """Test refresh with invalid token"""
        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token"}
        )

        assert response.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout"""

    def test_logout_success(self, test_client, test_user):
        """Test successful logout"""
        # Login first
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "TestPassword123"
            }
        )

        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # Logout
        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 204

    def test_logout_revokes_token(self, test_client, test_user):
        """Test that logout revokes refresh token"""
        # Login
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "TestPassword123"
            }
        )

        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # Logout
        test_client.post(
            "/api/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"}
        )

        # Try to use revoked refresh token
        refresh_response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert refresh_response.status_code == 401


class TestGetCurrentUserEndpoint:
    """Tests for GET /api/auth/me"""

    def test_get_current_user_success(self, test_client, test_user):
        """Test getting current user info"""
        # Login first
        login_response = test_client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "TestPassword123"
            }
        )

        access_token = login_response.json()["access_token"]

        # Get current user
        response = test_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "testuser@test.com"
        assert "role" in data

    def test_get_current_user_no_token(self, test_client):
        """Test getting current user without authentication"""
        response = test_client.get("/api/auth/me")

        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials

    def test_get_current_user_invalid_token(self, test_client):
        """Test getting current user with invalid token"""
        response = test_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401
