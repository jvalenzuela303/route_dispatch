"""
Fixtures específicas para tests de reglas de negocio
"""

import pytest
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal

from app.models.models import User, Role, Order, Invoice, Route
from app.models.enums import (
    OrderStatus,
    InvoiceType,
    SourceChannel,
    GeocodingConfidence,
    RouteStatus
)
from app.services.auth_service import AuthService


TIMEZONE = ZoneInfo("America/Santiago")


@pytest.fixture
def admin_role(db_session):
    """Create Administrador role in DB"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Administrador"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def vendedor_role(db_session):
    """Create Vendedor role in DB"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Vendedor"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def encargado_role(db_session):
    """Create Encargado de Bodega role in DB"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Encargado de Bodega"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def repartidor_role(db_session):
    """Create Repartidor role in DB"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Repartidor"
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create admin user in DB"""
    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@example.com",
        password_hash=AuthService.hash_password("admin123"),
        role_id=admin_role.id,
        full_name="Admin User",
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def vendedor_user(db_session, vendedor_role):
    """Create vendedor user in DB"""
    user = User(
        id=uuid.uuid4(),
        username="vendedor",
        email="vendedor@example.com",
        password_hash=AuthService.hash_password("vendedor123"),
        role_id=vendedor_role.id,
        full_name="Vendedor User",
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def another_vendedor_user(db_session, vendedor_role):
    """Create another vendedor user (for testing ownership)"""
    user = User(
        id=uuid.uuid4(),
        username="vendedor2",
        email="vendedor2@example.com",
        password_hash=AuthService.hash_password("vendedor123"),
        role_id=vendedor_role.id,
        full_name="Vendedor User 2",
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def encargado_user(db_session, encargado_role):
    """Create encargado user in DB"""
    user = User(
        id=uuid.uuid4(),
        username="encargado",
        email="encargado@example.com",
        password_hash=AuthService.hash_password("encargado123"),
        role_id=encargado_role.id,
        full_name="Encargado User",
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def repartidor_user(db_session, repartidor_role):
    """Create repartidor user in DB"""
    user = User(
        id=uuid.uuid4(),
        username="repartidor",
        email="repartidor@example.com",
        password_hash=AuthService.hash_password("repartidor123"),
        role_id=repartidor_role.id,
        full_name="Repartidor User",
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session, vendedor_role):
    """Create inactive user in DB"""
    user = User(
        id=uuid.uuid4(),
        username="inactive",
        email="inactive@example.com",
        password_hash=AuthService.hash_password("password123"),
        role_id=vendedor_role.id,
        full_name="Inactive User",
        active_status=False  # Inactive!
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Order fixtures

@pytest.fixture
def sample_delivery_date():
    """Sample future delivery date"""
    return date.today() + timedelta(days=1)


@pytest.fixture
def sample_order_pendiente(db_session, admin_user, sample_delivery_date):
    """Create order in PENDIENTE status"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.PENDIENTE,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_en_preparacion(db_session, admin_user, sample_delivery_date):
    """Create order in EN_PREPARACION status"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.EN_PREPARACION,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def another_order_en_preparacion(db_session, admin_user, sample_delivery_date):
    """Create another order in EN_PREPARACION"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer 2",
        customer_phone="+56912345679",
        address_text="Calle Astorga 456, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.EN_PREPARACION,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_documentado(db_session, admin_user, sample_delivery_date):
    """Create order in DOCUMENTADO status (with invoice)"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.DOCUMENTADO,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_with_invoice(sample_order_documentado):
    """Alias for clarity"""
    return sample_order_documentado


@pytest.fixture
def sample_order_documentado_no_invoice(db_session, admin_user, sample_delivery_date):
    """Create order in DOCUMENTADO status WITHOUT invoice (edge case)"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.DOCUMENTADO,  # DOCUMENTADO but no invoice!
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_route_draft(db_session, sample_delivery_date):
    """Create route in DRAFT status"""
    route = Route(
        id=uuid.uuid4(),
        route_name=f"Test Route DRAFT",
        route_date=sample_delivery_date,
        status=RouteStatus.DRAFT,
        stop_sequence=[],
        total_distance_km=Decimal("0.0"),
        estimated_duration_minutes=0
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


@pytest.fixture
def sample_route_active(db_session, repartidor_user, sample_delivery_date):
    """Create route in ACTIVE status"""
    route = Route(
        id=uuid.uuid4(),
        route_name=f"Test Route ACTIVE",
        route_date=sample_delivery_date,
        status=RouteStatus.ACTIVE,
        assigned_driver_id=repartidor_user.id,
        stop_sequence=[],
        total_distance_km=Decimal("10.5"),
        estimated_duration_minutes=60,
        started_at=datetime.now(TIMEZONE)
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


@pytest.fixture
def sample_order_en_ruta(db_session, admin_user, sample_route_active, sample_delivery_date):
    """Create order in EN_RUTA status"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.EN_RUTA,
        assigned_route_id=sample_route_active.id,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_incidencia(db_session, admin_user, sample_route_active, sample_delivery_date):
    """Create order in INCIDENCIA status"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.INCIDENCIA,
        assigned_route_id=sample_route_active.id,
        created_by_user_id=admin_user.id,
        notes="[INCIDENCIA] Cliente ausente"
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_entregado(db_session, admin_user, sample_route_active, sample_delivery_date):
    """Create order in ENTREGADO status (final state)"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-TEST-{uuid.uuid4().hex[:8]}",
        customer_name="Test Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.ENTREGADO,
        assigned_route_id=sample_route_active.id,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


# Ownership fixtures

@pytest.fixture
def order_created_by_vendedor(db_session, vendedor_user, sample_delivery_date):
    """Create order owned by vendedor"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-VEND-{uuid.uuid4().hex[:8]}",
        customer_name="Vendedor Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.PENDIENTE,
        created_by_user_id=vendedor_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def order_created_by_other_vendedor(db_session, another_vendedor_user, sample_delivery_date):
    """Create order owned by another vendedor"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-OTHER-{uuid.uuid4().hex[:8]}",
        customer_name="Other Vendedor Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.PENDIENTE,
        created_by_user_id=another_vendedor_user.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def invoice_created_by_another_vendedor(db_session, another_vendedor_user, order_created_by_other_vendedor):
    """Create invoice for order by another vendedor"""
    # Transition order to EN_PREPARACION first
    order_created_by_other_vendedor.order_status = OrderStatus.EN_PREPARACION
    db_session.commit()

    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-OTHER-{uuid.uuid4().hex[:8]}",
        order_id=order_created_by_other_vendedor.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("25000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=another_vendedor_user.id
    )
    db_session.add(invoice)

    # Auto-transition to DOCUMENTADO
    order_created_by_other_vendedor.order_status = OrderStatus.DOCUMENTADO
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


@pytest.fixture
def sample_order_documentado_with_invoice(db_session, admin_user, sample_delivery_date):
    """Create order already DOCUMENTADO with invoice"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-DOC-{uuid.uuid4().hex[:8]}",
        customer_name="Documented Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.DOCUMENTADO,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-DOC-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.FACTURA,
        total_amount=Decimal("50000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


# Route assignment fixtures

@pytest.fixture
def route_assigned_to_repartidor(db_session, repartidor_user, sample_delivery_date):
    """Create route assigned to repartidor"""
    route = Route(
        id=uuid.uuid4(),
        route_name="Repartidor Route",
        route_date=sample_delivery_date,
        status=RouteStatus.ACTIVE,
        assigned_driver_id=repartidor_user.id,
        stop_sequence=[],
        total_distance_km=Decimal("15.0"),
        estimated_duration_minutes=90,
        started_at=datetime.now(TIMEZONE)
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


@pytest.fixture
def route_assigned_to_other_driver(db_session, sample_delivery_date):
    """Create route assigned to another driver"""
    other_driver_id = uuid.uuid4()

    route = Route(
        id=uuid.uuid4(),
        route_name="Other Driver Route",
        route_date=sample_delivery_date,
        status=RouteStatus.ACTIVE,
        assigned_driver_id=other_driver_id,
        stop_sequence=[],
        total_distance_km=Decimal("12.0"),
        estimated_duration_minutes=75,
        started_at=datetime.now(TIMEZONE)
    )
    db_session.add(route)
    db_session.commit()
    db_session.refresh(route)
    return route


@pytest.fixture
def order_in_repartidor_route(db_session, admin_user, route_assigned_to_repartidor, sample_delivery_date):
    """Create order in repartidor's assigned route"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-REP-{uuid.uuid4().hex[:8]}",
        customer_name="Repartidor Route Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.EN_RUTA,
        assigned_route_id=route_assigned_to_repartidor.id,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-REP-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def order_in_other_driver_route(db_session, admin_user, route_assigned_to_other_driver, sample_delivery_date):
    """Create order in another driver's route"""
    order = Order(
        id=uuid.uuid4(),
        order_number=f"ORD-OTHER-{uuid.uuid4().hex[:8]}",
        customer_name="Other Driver Route Customer",
        customer_phone="+56912345678",
        address_text="Av O'Higgins 123, Rancagua",
        address_coordinates="POINT(-70.7406 -34.1706)",
        geocoding_confidence=GeocodingConfidence.HIGH,
        source_channel=SourceChannel.WEB,
        delivery_date=sample_delivery_date,
        order_status=OrderStatus.EN_RUTA,
        assigned_route_id=route_assigned_to_other_driver.id,
        created_by_user_id=admin_user.id
    )
    db_session.add(order)
    db_session.commit()

    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-OTHER-ROUTE-{uuid.uuid4().hex[:8]}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("30000.00"),
        issued_at=datetime.now(TIMEZONE),
        created_by_user_id=admin_user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_en_ruta_assigned_to_repartidor(order_in_repartidor_route):
    """Alias for clarity"""
    return order_in_repartidor_route


@pytest.fixture
def sample_order_en_ruta_assigned_to_other_driver(order_in_other_driver_route):
    """Alias for clarity"""
    return order_in_other_driver_route
