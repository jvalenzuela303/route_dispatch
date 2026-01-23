"""
Shared fixtures for API integration tests
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
from zoneinfo import ZoneInfo
import uuid

from app.main import app
from app.config.database import Base
from app.api.dependencies.database import get_db
from app.models.models import User, Role, Order, Invoice
from app.models.enums import (
    OrderStatus,
    SourceChannel,
    GeocodingConfidence,
    InvoiceType
)
from app.services.auth_service import AuthService


# Test database URL (use in-memory SQLite for tests)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database for each test
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create FastAPI test client with test database
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_role(db_session):
    """Create admin role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Administrador",
        description="Administrator with full access"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture(scope="function")
def vendedor_role(db_session):
    """Create vendedor role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Vendedor",
        description="Sales representative"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture(scope="function")
def encargado_role(db_session):
    """Create encargado role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Encargado de Bodega",
        description="Warehouse manager"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture(scope="function")
def repartidor_role(db_session):
    """Create repartidor role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Repartidor",
        description="Delivery driver"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture(scope="function")
def admin_user(db_session, admin_role):
    """Create admin user"""
    auth_service = AuthService(db_session)
    password_hash = auth_service.hash_password("admin123")

    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@botilleria.cl",
        password_hash=password_hash,
        role_id=admin_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def vendedor_user(db_session, vendedor_role):
    """Create vendedor user"""
    auth_service = AuthService(db_session)
    password_hash = auth_service.hash_password("vendedor123")

    user = User(
        id=uuid.uuid4(),
        username="vendedor1",
        email="vendedor1@botilleria.cl",
        password_hash=password_hash,
        role_id=vendedor_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_token(client, admin_user):
    """Get admin JWT token"""
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "admin123"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def vendedor_token(client, vendedor_user):
    """Get vendedor JWT token"""
    response = client.post(
        "/api/auth/login",
        json={
            "username": "vendedor1",
            "password": "vendedor123"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def sample_order(db_session, admin_user):
    """Create sample order for testing"""
    order = Order(
        id=uuid.uuid4(),
        order_number="ORD-20260122-0001",
        customer_name="Juan Pérez",
        customer_phone="+56912345678",
        customer_email="juan@example.cl",
        address_text="Av. Brasil 1234, Rancagua",
        address_coordinates="POINT(-70.7407 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=date.today(),
        order_status=OrderStatus.PENDIENTE,
        created_by_user_id=admin_user.id,
        created_at=datetime.now(ZoneInfo("America/Santiago")),
        updated_at=datetime.now(ZoneInfo("America/Santiago"))
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture(scope="function")
def sample_invoice(db_session, sample_order, admin_user):
    """Create sample invoice for testing"""
    # First transition order to EN_PREPARACION
    sample_order.order_status = OrderStatus.EN_PREPARACION
    db_session.commit()

    invoice = Invoice(
        id=uuid.uuid4(),
        order_id=sample_order.id,
        invoice_number="FAC-001",
        invoice_type=InvoiceType.FACTURA,
        total_amount=50000,
        issued_at=datetime.now(ZoneInfo("America/Santiago")),
        created_by_user_id=admin_user.id,
        created_at=datetime.now(ZoneInfo("America/Santiago"))
    )
    db_session.add(invoice)

    # Auto-transition to DOCUMENTADO
    sample_order.order_status = OrderStatus.DOCUMENTADO
    db_session.commit()
    db_session.refresh(invoice)
    return invoice
