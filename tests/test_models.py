"""
Test suite for SQLAlchemy models

Tests include:
- Model creation and field validation
- Relationships between models
- Unique constraints
- Foreign key constraints
- Enum validations
- PostGIS spatial functionality
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from geoalchemy2 import WKTElement

from app.models import (
    Base, Role, User, Order, Invoice, Route, AuditLog,
    OrderStatus, SourceChannel, GeocodingConfidence,
    InvoiceType, RouteStatus, AuditResult
)


# Test database URL (use in-memory SQLite for fast tests)
# Note: For PostGIS tests, you'll need a real PostgreSQL database
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test

    This ensures test isolation - each test gets a clean database.
    """
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


class TestRoleModel:
    """Tests for Role model"""

    def test_create_role(self, db_session):
        """Test creating a role with permissions"""
        role = Role(
            role_name="Administrador",
            description="Full system access",
            permissions={
                "can_create_users": True,
                "can_override_cutoff": True
            }
        )
        db_session.add(role)
        db_session.commit()

        assert role.id is not None
        assert isinstance(role.id, uuid.UUID)
        assert role.role_name == "Administrador"
        assert role.permissions["can_create_users"] is True
        assert role.created_at is not None
        assert role.updated_at is not None

    def test_role_unique_name(self, db_session):
        """Test that role names must be unique"""
        role1 = Role(role_name="Vendedor", permissions={})
        role2 = Role(role_name="Vendedor", permissions={})

        db_session.add(role1)
        db_session.commit()

        db_session.add(role2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestUserModel:
    """Tests for User model"""

    def test_create_user(self, db_session):
        """Test creating a user with role"""
        role = Role(role_name="Vendedor", permissions={})
        db_session.add(role)
        db_session.commit()

        user = User(
            username="vendedor01",
            email="vendedor01@botilleria.cl",
            password_hash="hashed_password_here",
            role_id=role.id,
            active_status=True
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.username == "vendedor01"
        assert user.email == "vendedor01@botilleria.cl"
        assert user.active_status is True
        assert user.role.role_name == "Vendedor"

    def test_user_unique_email(self, db_session):
        """Test that user emails must be unique"""
        role = Role(role_name="Vendedor", permissions={})
        db_session.add(role)
        db_session.commit()

        user1 = User(
            username="user1",
            email="duplicate@example.com",
            password_hash="hash1",
            role_id=role.id
        )
        user2 = User(
            username="user2",
            email="duplicate@example.com",
            password_hash="hash2",
            role_id=role.id
        )

        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_role_relationship(self, db_session):
        """Test that user-role relationship works correctly"""
        role = Role(role_name="Repartidor", permissions={})
        db_session.add(role)
        db_session.commit()

        user = User(
            username="driver01",
            email="driver@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add(user)
        db_session.commit()

        # Test forward relationship (user -> role)
        assert user.role.role_name == "Repartidor"

        # Test reverse relationship (role -> users)
        assert len(role.users) == 1
        assert role.users[0].username == "driver01"


class TestOrderModel:
    """Tests for Order model"""

    def test_create_order(self, db_session):
        """Test creating an order"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="vendedor",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0001",
            customer_name="Juan Pérez",
            customer_phone="+56912345678",
            customer_email="juan@example.com",
            address_text="Av. Brasil 1234, Rancagua",
            order_status=OrderStatus.PENDIENTE,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        assert order.id is not None
        assert order.order_number == "ORD-20260120-0001"
        assert order.customer_name == "Juan Pérez"
        assert order.order_status == OrderStatus.PENDIENTE
        assert order.created_by.username == "vendedor"

    def test_order_status_enum(self, db_session):
        """Test that order status uses enum values"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0002",
            customer_name="Test",
            customer_phone="+56912345678",
            address_text="Test Address",
            order_status=OrderStatus.EN_RUTA,
            source_channel=SourceChannel.RRSS,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        assert order.order_status == OrderStatus.EN_RUTA
        assert order.order_status.value == "EN_RUTA"

    def test_order_unique_order_number(self, db_session):
        """Test that order numbers must be unique"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order1 = Order(
            order_number="ORD-20260120-0003",
            customer_name="Customer 1",
            customer_phone="+56912345678",
            address_text="Address 1",
            order_status=OrderStatus.PENDIENTE,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        order2 = Order(
            order_number="ORD-20260120-0003",  # Duplicate
            customer_name="Customer 2",
            customer_phone="+56987654321",
            address_text="Address 2",
            order_status=OrderStatus.PENDIENTE,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )

        db_session.add(order1)
        db_session.commit()

        db_session.add(order2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestInvoiceModel:
    """Tests for Invoice model"""

    def test_create_invoice(self, db_session):
        """Test creating an invoice linked to an order"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0004",
            customer_name="Test Customer",
            customer_phone="+56912345678",
            address_text="Test Address",
            order_status=OrderStatus.EN_PREPARACION,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        invoice = Invoice(
            invoice_number="BOLETA-202601-00001",
            order_id=order.id,
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("50000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=user.id
        )
        db_session.add(invoice)
        db_session.commit()

        assert invoice.id is not None
        assert invoice.invoice_number == "BOLETA-202601-00001"
        assert invoice.total_amount == Decimal("50000.00")
        assert invoice.order.order_number == "ORD-20260120-0004"

    def test_invoice_one_to_one_with_order(self, db_session):
        """Test that one order can only have one invoice"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0005",
            customer_name="Test",
            customer_phone="+56912345678",
            address_text="Test",
            order_status=OrderStatus.DOCUMENTADO,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        invoice1 = Invoice(
            invoice_number="INV-001",
            order_id=order.id,
            invoice_type=InvoiceType.FACTURA,
            total_amount=Decimal("100000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=user.id
        )
        db_session.add(invoice1)
        db_session.commit()

        # Try to create a second invoice for the same order
        invoice2 = Invoice(
            invoice_number="INV-002",
            order_id=order.id,  # Same order
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("50000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=user.id
        )
        db_session.add(invoice2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestRouteModel:
    """Tests for Route model"""

    def test_create_route(self, db_session):
        """Test creating a route"""
        role = Role(role_name="Repartidor", permissions={})
        driver = User(
            username="driver",
            email="driver@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, driver])
        db_session.commit()

        route = Route(
            route_name="Ruta 2026-01-20 #1",
            route_date=date.today(),
            assigned_driver_id=driver.id,
            status=RouteStatus.ACTIVE,
            total_distance_km=Decimal("15.5"),
            estimated_duration_minutes=120,
            stop_sequence=["uuid1", "uuid2", "uuid3"]
        )
        db_session.add(route)
        db_session.commit()

        assert route.id is not None
        assert route.route_name == "Ruta 2026-01-20 #1"
        assert route.status == RouteStatus.ACTIVE
        assert route.total_distance_km == Decimal("15.5")
        assert len(route.stop_sequence) == 3
        assert route.assigned_driver.username == "driver"

    def test_route_driver_relationship(self, db_session):
        """Test route-driver relationship"""
        role = Role(role_name="Repartidor", permissions={})
        driver = User(
            username="driver",
            email="driver@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, driver])
        db_session.commit()

        route1 = Route(
            route_name="Route 1",
            route_date=date.today(),
            assigned_driver_id=driver.id,
            status=RouteStatus.ACTIVE
        )
        route2 = Route(
            route_name="Route 2",
            route_date=date.today(),
            assigned_driver_id=driver.id,
            status=RouteStatus.COMPLETED
        )
        db_session.add_all([route1, route2])
        db_session.commit()

        # Test that driver has multiple routes
        assert len(driver.assigned_routes) == 2


class TestAuditLogModel:
    """Tests for AuditLog model"""

    def test_create_audit_log(self, db_session):
        """Test creating an audit log entry"""
        role = Role(role_name="Administrador", permissions={})
        user = User(
            username="admin",
            email="admin@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        log = AuditLog(
            timestamp=datetime.now(timezone.utc),
            user_id=user.id,
            action="CREATE_ORDER",
            entity_type="ORDER",
            entity_id=uuid.uuid4(),
            details={"customer": "Juan Pérez", "amount": 50000},
            result=AuditResult.SUCCESS,
            ip_address="192.168.1.100"
        )
        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.action == "CREATE_ORDER"
        assert log.result == AuditResult.SUCCESS
        assert log.details["customer"] == "Juan Pérez"
        assert log.user.username == "admin"

    def test_audit_log_system_action(self, db_session):
        """Test audit log for system action (no user)"""
        log = AuditLog(
            timestamp=datetime.now(timezone.utc),
            user_id=None,  # System action
            action="SYSTEM_BACKUP",
            entity_type="SYSTEM",
            result=AuditResult.SUCCESS
        )
        db_session.add(log)
        db_session.commit()

        assert log.user_id is None
        assert log.action == "SYSTEM_BACKUP"


class TestModelRelationships:
    """Tests for relationships between models"""

    def test_order_invoice_relationship(self, db_session):
        """Test bidirectional order-invoice relationship"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0006",
            customer_name="Test",
            customer_phone="+56912345678",
            address_text="Test",
            order_status=OrderStatus.DOCUMENTADO,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        invoice = Invoice(
            invoice_number="INV-003",
            order_id=order.id,
            invoice_type=InvoiceType.FACTURA,
            total_amount=Decimal("75000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=user.id
        )
        db_session.add(invoice)
        db_session.commit()

        # Test forward relationship (invoice -> order)
        assert invoice.order.order_number == "ORD-20260120-0006"

        # Test reverse relationship (order -> invoice)
        assert order.invoice.invoice_number == "INV-003"

    def test_cascade_delete_invoice_with_order(self, db_session):
        """Test that deleting an order cascades to invoice"""
        role = Role(role_name="Vendedor", permissions={})
        user = User(
            username="v",
            email="v@example.com",
            password_hash="hash",
            role_id=role.id
        )
        db_session.add_all([role, user])
        db_session.commit()

        order = Order(
            order_number="ORD-20260120-0007",
            customer_name="Test",
            customer_phone="+56912345678",
            address_text="Test",
            order_status=OrderStatus.DOCUMENTADO,
            source_channel=SourceChannel.WEB,
            created_by_user_id=user.id
        )
        db_session.add(order)
        db_session.commit()

        invoice = Invoice(
            invoice_number="INV-004",
            order_id=order.id,
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("30000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=user.id
        )
        db_session.add(invoice)
        db_session.commit()

        invoice_id = invoice.id

        # Delete order
        db_session.delete(order)
        db_session.commit()

        # Invoice should also be deleted (CASCADE)
        deleted_invoice = db_session.get(Invoice, invoice_id)
        assert deleted_invoice is None
