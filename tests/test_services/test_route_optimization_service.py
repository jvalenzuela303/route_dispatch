"""
Tests for RouteOptimizationService

Tests:
- Route generation from DOCUMENTADO orders
- Distance matrix calculation with PostGIS
- TSP solver correctness
- Route activation and order transition to EN_RUTA
- Performance requirements (50 orders < 10 seconds)
- Edge cases and error handling
"""

import pytest
import time
import uuid
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from geoalchemy2.elements import WKTElement

from app.models.models import Order, Invoice, Route, User, Role
from app.models.enums import (
    OrderStatus, SourceChannel, InvoiceType,
    RouteStatus, GeocodingConfidence
)
from app.services.route_optimization_service import RouteOptimizationService
from app.exceptions import RouteOptimizationError, ValidationError


# Test Fixtures

@pytest.fixture
def admin_role(db_session):
    """Create admin role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Administrador",
        description="Full system access",
        permissions={
            "override_cutoff": True,
            "generate_routes": True,
            "manage_users": True
        }
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def repartidor_role(db_session):
    """Create repartidor role"""
    role = Role(
        id=uuid.uuid4(),
        role_name="Repartidor",
        description="Delivery driver",
        permissions={
            "view_assigned_routes": True,
            "update_delivery_status": True
        }
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create admin user"""
    user = User(
        id=uuid.uuid4(),
        username="admin_test",
        email="admin@test.com",
        password_hash="hashed_password",
        role_id=admin_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def driver_user(db_session, repartidor_role):
    """Create driver user"""
    user = User(
        id=uuid.uuid4(),
        username="driver_test",
        email="driver@test.com",
        password_hash="hashed_password",
        role_id=repartidor_role.id,
        active_status=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def route_service(db_session):
    """Create RouteOptimizationService instance"""
    return RouteOptimizationService(db_session)


def create_order_with_coordinates(
    db_session,
    user: User,
    delivery_date: date,
    latitude: float,
    longitude: float,
    order_number: str
) -> Order:
    """
    Helper to create order with coordinates and invoice

    Args:
        db_session: Database session
        user: User creating the order
        delivery_date: Delivery date
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        order_number: Order number

    Returns:
        Order: Created order in DOCUMENTADO status with invoice
    """
    # Create order
    order = Order(
        id=uuid.uuid4(),
        order_number=order_number,
        customer_name=f"Customer {order_number}",
        customer_phone="+56912345678",
        customer_email=f"customer{order_number}@test.com",
        address_text=f"Address for {order_number}",
        address_coordinates=WKTElement(f'POINT({longitude} {latitude})', srid=4326),
        geocoding_confidence=GeocodingConfidence.HIGH,
        order_status=OrderStatus.DOCUMENTADO,  # Ready for routing
        source_channel=SourceChannel.WEB,
        delivery_date=delivery_date,
        created_by_user_id=user.id
    )
    db_session.add(order)
    db_session.flush()

    # Create invoice (required for routing)
    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number=f"INV-{order_number}",
        order_id=order.id,
        invoice_type=InvoiceType.BOLETA,
        total_amount=Decimal("50000.00"),
        issued_at=datetime.now(timezone.utc),
        created_by_user_id=user.id
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(order)

    return order


# Tests

class TestRouteGeneration:
    """Test route generation functionality"""

    def test_generate_route_basic(self, db_session, route_service, admin_user):
        """Test basic route generation with 3 orders"""
        tomorrow = date.today() + timedelta(days=1)

        # Create 3 orders with different coordinates in Rancagua
        orders = [
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.170, -70.740, "ORD-001"
            ),
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.172, -70.742, "ORD-002"
            ),
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.168, -70.738, "ORD-003"
            )
        ]

        # Generate route
        route = route_service.generate_route_for_date(tomorrow, admin_user)

        # Assertions
        assert route is not None
        assert route.route_date == tomorrow
        assert route.status == RouteStatus.DRAFT
        assert len(route.stop_sequence) == 3
        assert route.total_distance_km > 0
        assert route.estimated_duration_minutes > 0
        assert "Ruta" in route.route_name

        # Verify all orders are in sequence
        order_ids = [str(o.id) for o in orders]
        for order_id in order_ids:
            assert order_id in route.stop_sequence

    def test_generate_route_no_orders(self, db_session, route_service, admin_user):
        """Test route generation fails when no orders exist"""
        future_date = date.today() + timedelta(days=10)

        with pytest.raises(RouteOptimizationError) as exc_info:
            route_service.generate_route_for_date(future_date, admin_user)

        assert "No hay pedidos documentados" in str(exc_info.value)

    def test_generate_route_only_documentado_orders(
        self, db_session, route_service, admin_user
    ):
        """Test only DOCUMENTADO orders are included in route"""
        tomorrow = date.today() + timedelta(days=1)

        # Create DOCUMENTADO order (should be included)
        order_doc = create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.170, -70.740, "ORD-DOC"
        )

        # Create PENDIENTE order (should be excluded)
        order_pend = Order(
            id=uuid.uuid4(),
            order_number="ORD-PEND",
            customer_name="Pending Customer",
            customer_phone="+56912345678",
            address_text="Pending Address",
            address_coordinates=WKTElement('POINT(-70.740 -34.170)', srid=4326),
            geocoding_confidence=GeocodingConfidence.HIGH,
            order_status=OrderStatus.PENDIENTE,
            source_channel=SourceChannel.WEB,
            delivery_date=tomorrow,
            created_by_user_id=admin_user.id
        )
        db_session.add(order_pend)
        db_session.commit()

        # Generate route
        route = route_service.generate_route_for_date(tomorrow, admin_user)

        # Only DOCUMENTADO order should be included
        assert len(route.stop_sequence) == 1
        assert str(order_doc.id) in route.stop_sequence
        assert str(order_pend.id) not in route.stop_sequence

    def test_generate_route_requires_coordinates(
        self, db_session, route_service, admin_user
    ):
        """Test route generation excludes orders without coordinates"""
        tomorrow = date.today() + timedelta(days=1)

        # Create order without coordinates
        order = Order(
            id=uuid.uuid4(),
            order_number="ORD-NO-COORDS",
            customer_name="No Coords Customer",
            customer_phone="+56912345678",
            address_text="Address without coords",
            address_coordinates=None,  # No coordinates
            order_status=OrderStatus.DOCUMENTADO,
            source_channel=SourceChannel.WEB,
            delivery_date=tomorrow,
            created_by_user_id=admin_user.id
        )
        db_session.add(order)
        db_session.flush()

        # Create invoice
        invoice = Invoice(
            id=uuid.uuid4(),
            invoice_number="INV-NO-COORDS",
            order_id=order.id,
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("50000.00"),
            issued_at=datetime.now(timezone.utc),
            created_by_user_id=admin_user.id
        )
        db_session.add(invoice)
        db_session.commit()

        # Should fail - no orders with coordinates
        with pytest.raises(RouteOptimizationError) as exc_info:
            route_service.generate_route_for_date(tomorrow, admin_user)

        assert "No hay pedidos documentados" in str(exc_info.value)


class TestDistanceCalculation:
    """Test distance matrix calculation"""

    def test_distance_matrix_calculation(self, db_session, route_service):
        """Test PostGIS distance calculation"""
        # Define test coordinates in Rancagua
        coordinates = [
            (-34.1706, -70.7406),  # Depot (center of Rancagua)
            (-34.172, -70.742),     # Point 1
            (-34.168, -70.738)      # Point 2
        ]

        # Calculate distance matrix
        matrix = route_service._calculate_distance_matrix(coordinates)

        # Assertions
        assert matrix.shape == (3, 3)
        assert matrix.dtype == int  # OR-Tools requires integers

        # Diagonal should be zero
        assert matrix[0][0] == 0
        assert matrix[1][1] == 0
        assert matrix[2][2] == 0

        # Distances should be symmetric
        assert matrix[0][1] == matrix[1][0]
        assert matrix[0][2] == matrix[2][0]
        assert matrix[1][2] == matrix[2][1]

        # Distances should be positive
        assert matrix[0][1] > 0
        assert matrix[0][2] > 0
        assert matrix[1][2] > 0

        # Distances should be reasonable (a few hundred meters to km)
        # Points are close together in Rancagua
        assert matrix[0][1] < 10000  # Less than 10km
        assert matrix[0][2] < 10000


class TestTSPSolver:
    """Test TSP solver functionality"""

    def test_tsp_solver_simple(self, db_session, route_service):
        """Test TSP solver with simple 3-point problem"""
        # Create simple distance matrix
        # Triangle: A-B=100, A-C=100, B-C=50
        # Optimal route: A -> B -> C -> A or A -> C -> B -> A
        # Both have total distance: 100 + 50 + 100 = 250
        import numpy as np
        matrix = np.array([
            [0, 100, 100],
            [100, 0, 50],
            [100, 50, 0]
        ], dtype=int)

        solution = route_service._solve_tsp(matrix)

        assert solution is not None
        assert "route" in solution
        assert "total_distance" in solution
        assert len(solution["route"]) == 4  # 0 -> 1 -> 2 -> 0
        assert solution["route"][0] == 0  # Starts at depot
        assert solution["route"][-1] == 0  # Returns to depot
        assert solution["total_distance"] == 250  # Optimal solution

    def test_tsp_solver_timeout(self, db_session, route_service):
        """Test TSP solver respects timeout parameter"""
        # Solver should complete within timeout even for small problems
        import numpy as np
        matrix = np.random.randint(100, 1000, size=(10, 10))
        np.fill_diagonal(matrix, 0)

        start_time = time.time()
        solution = route_service._solve_tsp(matrix)
        elapsed = time.time() - start_time

        assert solution is not None
        # Should complete well within timeout (30 seconds default)
        assert elapsed < route_service.optimization_timeout


class TestRouteActivation:
    """Test route activation functionality"""

    def test_activate_route_success(
        self, db_session, route_service, admin_user, driver_user
    ):
        """Test successful route activation"""
        tomorrow = date.today() + timedelta(days=1)

        # Create orders and route
        orders = [
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.170, -70.740, "ORD-ACT-1"
            ),
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.172, -70.742, "ORD-ACT-2"
            )
        ]

        route = route_service.generate_route_for_date(tomorrow, admin_user)
        assert route.status == RouteStatus.DRAFT

        # Activate route
        activated_route = route_service.activate_route(
            route.id, driver_user.id, admin_user
        )

        # Assertions
        assert activated_route.status == RouteStatus.ACTIVE
        assert activated_route.assigned_driver_id == driver_user.id
        assert activated_route.started_at is not None

        # Verify orders transitioned to EN_RUTA
        for order in orders:
            db_session.refresh(order)
            assert order.order_status == OrderStatus.EN_RUTA
            assert order.assigned_route_id == route.id

    def test_activate_route_invalid_status(
        self, db_session, route_service, admin_user, driver_user
    ):
        """Test activation fails if route not in DRAFT"""
        tomorrow = date.today() + timedelta(days=1)

        # Create and activate route
        create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.170, -70.740, "ORD-INV"
        )
        route = route_service.generate_route_for_date(tomorrow, admin_user)
        route_service.activate_route(route.id, driver_user.id, admin_user)

        # Try to activate again
        with pytest.raises(RouteOptimizationError) as exc_info:
            route_service.activate_route(route.id, driver_user.id, admin_user)

        assert "debe estar en DRAFT" in str(exc_info.value)

    def test_activate_route_nonexistent_driver(
        self, db_session, route_service, admin_user
    ):
        """Test activation fails with invalid driver ID"""
        tomorrow = date.today() + timedelta(days=1)

        create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.170, -70.740, "ORD-NODRV"
        )
        route = route_service.generate_route_for_date(tomorrow, admin_user)

        fake_driver_id = uuid.uuid4()
        with pytest.raises(ValidationError) as exc_info:
            route_service.activate_route(route.id, fake_driver_id, admin_user)

        assert "no encontrado" in str(exc_info.value)


class TestPerformance:
    """Test performance requirements"""

    def test_route_generation_performance_50_orders(
        self, db_session, route_service, admin_user
    ):
        """
        Test route generation with 50 orders completes in < 10 seconds

        BR-024: Performance requirement
        """
        tomorrow = date.today() + timedelta(days=1)

        # Create 50 orders with varied coordinates in Rancagua area
        # Spread across realistic delivery area (~5km x 5km)
        import random
        random.seed(42)  # Reproducible results

        for i in range(50):
            # Random coordinates in Rancagua area
            lat = -34.1706 + random.uniform(-0.03, 0.03)  # ~3km variation
            lon = -70.7406 + random.uniform(-0.03, 0.03)

            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                lat, lon, f"ORD-PERF-{i:03d}"
            )

        # Measure route generation time
        start_time = time.time()
        route = route_service.generate_route_for_date(tomorrow, admin_user)
        elapsed = time.time() - start_time

        # Assertions
        assert route is not None
        assert len(route.stop_sequence) == 50
        assert route.total_distance_km > 0
        assert route.estimated_duration_minutes > 0

        # Performance requirement: < 10 seconds
        assert elapsed < 10.0, f"Route generation took {elapsed:.2f}s (should be <10s)"

    def test_route_generation_performance_10_orders(
        self, db_session, route_service, admin_user
    ):
        """Test route generation with 10 orders is fast"""
        tomorrow = date.today() + timedelta(days=1)

        import random
        random.seed(42)

        for i in range(10):
            lat = -34.1706 + random.uniform(-0.02, 0.02)
            lon = -70.7406 + random.uniform(-0.02, 0.02)

            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                lat, lon, f"ORD-FAST-{i:02d}"
            )

        start_time = time.time()
        route = route_service.generate_route_for_date(tomorrow, admin_user)
        elapsed = time.time() - start_time

        assert route is not None
        assert len(route.stop_sequence) == 10
        # Should be very fast for 10 orders
        assert elapsed < 2.0, f"Route generation took {elapsed:.2f}s (should be <2s)"


class TestRouteDetails:
    """Test route details retrieval"""

    def test_get_route_details(self, db_session, route_service, admin_user):
        """Test getting detailed route information"""
        tomorrow = date.today() + timedelta(days=1)

        orders = [
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.170, -70.740, "ORD-DET-1"
            ),
            create_order_with_coordinates(
                db_session, admin_user, tomorrow,
                -34.172, -70.742, "ORD-DET-2"
            )
        ]

        route = route_service.generate_route_for_date(tomorrow, admin_user)

        # Get details
        details = route_service.get_route_details(route.id)

        # Assertions
        assert details["route_id"] == str(route.id)
        assert details["route_name"] == route.route_name
        assert details["status"] == RouteStatus.DRAFT.value
        assert details["num_stops"] == 2
        assert len(details["stops"]) == 2

        # Check stop details
        for stop in details["stops"]:
            assert "stop_number" in stop
            assert "order_number" in stop
            assert "customer_name" in stop
            assert "address_text" in stop

    def test_get_route_details_nonexistent(self, db_session, route_service):
        """Test getting details for nonexistent route"""
        fake_id = uuid.uuid4()

        with pytest.raises(RouteOptimizationError) as exc_info:
            route_service.get_route_details(fake_id)

        assert "no encontrada" in str(exc_info.value)


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_single_order_route(self, db_session, route_service, admin_user):
        """Test route generation with single order"""
        tomorrow = date.today() + timedelta(days=1)

        order = create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.170, -70.740, "ORD-SINGLE"
        )

        route = route_service.generate_route_for_date(tomorrow, admin_user)

        assert route is not None
        assert len(route.stop_sequence) == 1
        assert str(order.id) in route.stop_sequence

    def test_multiple_routes_same_date(self, db_session, route_service, admin_user):
        """Test generating multiple routes for same date"""
        tomorrow = date.today() + timedelta(days=1)

        # Create first route
        create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.170, -70.740, "ORD-MULT-1"
        )
        route1 = route_service.generate_route_for_date(tomorrow, admin_user)

        # Create second batch of orders
        create_order_with_coordinates(
            db_session, admin_user, tomorrow,
            -34.172, -70.742, "ORD-MULT-2"
        )
        route2 = route_service.generate_route_for_date(tomorrow, admin_user)

        # Both routes should exist
        assert route1.id != route2.id
        assert "#1" in route1.route_name
        # route2 will have both orders since we query all DOCUMENTADO orders
        # This is expected behavior - the service includes all eligible orders
