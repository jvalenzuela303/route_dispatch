"""
Pytest configuration and fixtures for Claude Logistics API tests

Provides common fixtures for all test suites including:
- Mock users with different roles
- Database session fixtures
- Mock services
- FastAPI test client
"""

import pytest
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.models import User, Role
from app.models.enums import OrderStatus


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI application

    Returns:
        TestClient instance for making test requests
    """
    return TestClient(app)


@pytest.fixture
def chile_timezone():
    """Chile timezone"""
    return ZoneInfo("America/Santiago")


# Mock user fixtures

@pytest.fixture
def mock_admin_role():
    """Mock Administrador role"""
    role = Mock(spec=Role)
    role.id = uuid.uuid4()
    role.role_name = 'Administrador'
    role.permissions = {'actions': {'*': {'allowed': True}}}
    return role


@pytest.fixture
def mock_encargado_role():
    """Mock Encargado de Bodega role"""
    role = Mock(spec=Role)
    role.id = uuid.uuid4()
    role.role_name = 'Encargado de Bodega'
    role.permissions = {
        'actions': {
            'create_order': {'allowed': True},
            'generate_route': {'allowed': True}
        }
    }
    return role


@pytest.fixture
def mock_vendedor_role():
    """Mock Vendedor role"""
    role = Mock(spec=Role)
    role.id = uuid.uuid4()
    role.role_name = 'Vendedor'
    role.permissions = {
        'actions': {
            'create_order': {'allowed': True},
            'create_invoice': {'allowed': True}
        }
    }
    return role


@pytest.fixture
def mock_repartidor_role():
    """Mock Repartidor role"""
    role = Mock(spec=Role)
    role.id = uuid.uuid4()
    role.role_name = 'Repartidor'
    role.permissions = {
        'actions': {
            'view_route': {'allowed': True}
        }
    }
    return role


@pytest.fixture
def mock_admin_user(mock_admin_role):
    """Mock Administrador user"""
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.username = 'admin_test'
    user.email = 'admin@test.com'
    user.role = mock_admin_role
    user.role_id = mock_admin_role.id
    user.active_status = True
    return user


@pytest.fixture
def mock_encargado_user(mock_encargado_role):
    """Mock Encargado de Bodega user"""
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.username = 'encargado_test'
    user.email = 'encargado@test.com'
    user.role = mock_encargado_role
    user.role_id = mock_encargado_role.id
    user.active_status = True
    return user


@pytest.fixture
def mock_vendedor_user(mock_vendedor_role):
    """Mock Vendedor user"""
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.username = 'vendedor_test'
    user.email = 'vendedor@test.com'
    user.role = mock_vendedor_role
    user.role_id = mock_vendedor_role.id
    user.active_status = True
    return user


@pytest.fixture
def mock_repartidor_user(mock_repartidor_role):
    """Mock Repartidor user"""
    user = Mock(spec=User)
    user.id = uuid.uuid4()
    user.username = 'repartidor_test'
    user.email = 'repartidor@test.com'
    user.role = mock_repartidor_role
    user.role_id = mock_repartidor_role.id
    user.active_status = True
    return user


# Database fixtures

@pytest.fixture(scope='function')
def db_engine():
    """Create in-memory SQLite engine for testing"""
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine):
    """Create database session for testing"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


# Legacy fixtures (for backward compatibility)

@pytest.fixture
def test_db():
    """
    Setup test database connection
    Use db_session instead for new tests
    """
    pass


@pytest.fixture
def test_redis():
    """
    Setup test Redis connection
    This will be implemented in future phases
    """
    pass


# Mock service fixtures

@pytest.fixture
def mock_audit_service():
    """Mock AuditService"""
    service = MagicMock()
    service.log_action.return_value = Mock(id=uuid.uuid4())
    service.log_state_transition.return_value = Mock(id=uuid.uuid4())
    service.log_override_attempt.return_value = Mock(id=uuid.uuid4())
    return service


@pytest.fixture
def mock_permission_service():
    """Mock PermissionService"""
    service = MagicMock()
    service.can_execute_action.return_value = True
    service.require_permission.return_value = None
    return service


# Datetime fixtures

@pytest.fixture
def business_day_monday(chile_timezone):
    """Create a Monday at 10:00 AM"""
    return datetime(2026, 1, 19, 10, 0, 0, tzinfo=chile_timezone)


@pytest.fixture
def cutoff_am_boundary(chile_timezone):
    """Create datetime at exactly 12:00:00"""
    return datetime(2026, 1, 21, 12, 0, 0, tzinfo=chile_timezone)


@pytest.fixture
def cutoff_pm_exceeded(chile_timezone):
    """Create datetime at 15:00:01 (exceeded PM cutoff)"""
    return datetime(2026, 1, 21, 15, 0, 1, tzinfo=chile_timezone)


@pytest.fixture
def friday_evening(chile_timezone):
    """Create Friday at 16:00"""
    return datetime(2026, 1, 23, 16, 0, 0, tzinfo=chile_timezone)
