"""
Route Generation Performance Testing

Tests performance of route optimization against business requirements:
- BR-024: Route generation for 50 orders must complete in < 15 seconds
- Target: 100 orders in < 30 seconds

These tests measure actual execution time and identify bottlenecks.
"""

import pytest
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.route_optimization_service import RouteOptimizationService
from app.services.order_service import OrderService
from app.services.invoice_service import InvoiceService
from app.models.enums import OrderStatus, InvoiceType, SourceChannel


TIMEZONE = ZoneInfo("America/Santiago")


class TestRouteGenerationPerformance:
    """Test route generation performance benchmarks"""

    def _create_orders_for_routing(
        self,
        db_session,
        admin_user,
        count: int,
        delivery_date: date
    ):
        """
        Helper: Create N orders ready for routing (DOCUMENTADO with invoices)

        Returns list of created order IDs
        """
        order_service = OrderService(db_session)
        invoice_service = InvoiceService(db_session)

        order_ids = []

        # Rancagua coordinates (vary slightly for realistic routing)
        base_lat = -34.1706
        base_lon = -70.7406

        for i in range(count):
            # Create order
            order = order_service.create_order(
                customer_name=f"Performance Test Customer {i}",
                customer_phone="+56912345678",
                address_text=f"Calle Test {100 + i}, Rancagua",  # Sequential addresses
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

            # Manually set coordinates (skip geocoding for performance test)
            # Vary coordinates slightly to simulate real addresses
            lat_offset = (i % 20 - 10) * 0.002  # ±0.02 degrees
            lon_offset = ((i // 20) % 20 - 10) * 0.002
            order.address_coordinates = f'POINT({base_lon + lon_offset} {base_lat + lat_offset})'

            # Force state to EN_PREPARACION
            order.order_status = OrderStatus.EN_PREPARACION
            order.delivery_date = delivery_date
            db_session.commit()

            # Create invoice (auto-transitions to DOCUMENTADO)
            invoice = invoice_service.create_invoice(
                order_id=order.id,
                invoice_number=f"PERF-{i:05d}",
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("25000.00"),
                user=admin_user
            )

            order_ids.append(order.id)

        db_session.commit()
        return order_ids

    @pytest.mark.performance
    def test_generate_route_50_orders_under_15_seconds(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL PERFORMANCE TEST: Generate route for 50 orders in < 15 seconds

        Business requirement BR-024: Must complete in reasonable time
        Target: < 15 seconds for 50 orders
        """
        delivery_date = date.today() + timedelta(days=1)

        # Create 50 orders ready for routing
        print("\n[SETUP] Creating 50 test orders...")
        setup_start = time.time()
        order_ids = self._create_orders_for_routing(
            db_session, admin_user, count=50, delivery_date=delivery_date
        )
        setup_duration = time.time() - setup_start
        print(f"[SETUP] Created {len(order_ids)} orders in {setup_duration:.2f}s")

        # Measure route generation time
        route_service = RouteOptimizationService(db_session)

        print("[TEST] Starting route generation...")
        start_time = time.time()

        route = route_service.generate_route_for_date(
            delivery_date=delivery_date,
            user=admin_user
        )

        end_time = time.time()
        duration = end_time - start_time

        # Log results
        print(f"\n[RESULT] Route generation completed in {duration:.2f} seconds")
        print(f"[RESULT] Orders in route: {len(route.stop_sequence)}")
        print(f"[RESULT] Total distance: {route.total_distance_km} km")
        print(f"[RESULT] Estimated duration: {route.estimated_duration_minutes} minutes")

        # Assert performance requirement
        assert duration < 15.0, \
            f"Route generation took {duration:.2f}s, exceeds 15s limit (BR-024)"

        # Verify route was created correctly
        assert route.stop_sequence is not None
        assert len(route.stop_sequence) == 50

    @pytest.mark.performance
    @pytest.mark.slow
    def test_generate_route_100_orders_under_30_seconds(
        self,
        db_session,
        admin_user
    ):
        """
        Performance test: Generate route for 100 orders in < 30 seconds

        Stretch target for scalability testing
        """
        delivery_date = date.today() + timedelta(days=2)

        # Create 100 orders
        print("\n[SETUP] Creating 100 test orders...")
        setup_start = time.time()
        order_ids = self._create_orders_for_routing(
            db_session, admin_user, count=100, delivery_date=delivery_date
        )
        setup_duration = time.time() - setup_start
        print(f"[SETUP] Created {len(order_ids)} orders in {setup_duration:.2f}s")

        # Measure route generation time
        route_service = RouteOptimizationService(db_session)

        print("[TEST] Starting route generation...")
        start_time = time.time()

        route = route_service.generate_route_for_date(
            delivery_date=delivery_date,
            user=admin_user
        )

        end_time = time.time()
        duration = end_time - start_time

        # Log results
        print(f"\n[RESULT] Route generation completed in {duration:.2f} seconds")
        print(f"[RESULT] Orders in route: {len(route.stop_sequence)}")
        print(f"[RESULT] Total distance: {route.total_distance_km} km")

        # Assert performance requirement (30s for 100 orders)
        assert duration < 30.0, \
            f"Route generation took {duration:.2f}s, exceeds 30s target for 100 orders"

        assert len(route.stop_sequence) == 100

    @pytest.mark.performance
    def test_route_generation_scales_linearly(
        self,
        db_session,
        admin_user
    ):
        """
        Test route generation time scales reasonably with order count

        Expected: O(n^2) or better (TSP is NP-hard but solver should be efficient)
        """
        order_counts = [10, 20, 30]
        times = []

        for count in order_counts:
            delivery_date = date.today() + timedelta(days=count)

            # Create orders
            self._create_orders_for_routing(
                db_session, admin_user, count=count, delivery_date=delivery_date
            )

            # Measure route generation
            route_service = RouteOptimizationService(db_session)

            start_time = time.time()
            route = route_service.generate_route_for_date(
                delivery_date=delivery_date,
                user=admin_user
            )
            duration = time.time() - start_time

            times.append(duration)
            print(f"\n{count} orders: {duration:.2f}s")

        # Verify scaling is reasonable (not exponential)
        # 30 orders should not take 9x time of 10 orders (would be O(n^3))
        if times[0] > 0.1:  # Only check if base time is measurable
            ratio_30_to_10 = times[2] / times[0]
            assert ratio_30_to_10 < 9.0, \
                f"Scaling appears exponential: 30 orders took {ratio_30_to_10:.1f}x time of 10 orders"


class TestDistanceMatrixPerformance:
    """Test PostGIS distance calculation performance"""

    @pytest.mark.performance
    def test_distance_matrix_calculation_performance(
        self,
        db_session
    ):
        """
        Test distance matrix calculation for 50 locations

        Target: < 5 seconds for 50x50 matrix (2,500 distance calculations)
        """
        route_service = RouteOptimizationService(db_session)

        # Generate 50 random coordinates in Rancagua
        base_lat = -34.1706
        base_lon = -70.7406

        coordinates = [(base_lat, base_lon)]  # Depot

        for i in range(49):
            lat_offset = (i % 7 - 3) * 0.003
            lon_offset = ((i // 7) % 7 - 3) * 0.003
            coordinates.append((base_lat + lat_offset, base_lon + lon_offset))

        # Measure distance matrix calculation
        print(f"\n[TEST] Calculating {len(coordinates)}x{len(coordinates)} distance matrix...")
        start_time = time.time()

        distance_matrix = route_service._calculate_distance_matrix(coordinates)

        duration = time.time() - start_time

        print(f"[RESULT] Distance matrix calculated in {duration:.2f} seconds")
        print(f"[RESULT] Matrix size: {distance_matrix.shape}")

        # Assert performance (should be fast with PostGIS)
        assert duration < 5.0, \
            f"Distance matrix calculation took {duration:.2f}s, exceeds 5s target"

        # Verify matrix correctness
        assert distance_matrix.shape == (50, 50)
        assert distance_matrix[0][0] == 0  # Distance to self is 0


class TestTSPSolverPerformance:
    """Test OR-Tools TSP solver performance"""

    @pytest.mark.performance
    def test_tsp_solver_performance_50_nodes(
        self,
        db_session
    ):
        """
        Test TSP solver for 50 nodes

        Target: < 10 seconds to find good solution
        """
        import numpy as np

        route_service = RouteOptimizationService(db_session)

        # Create synthetic distance matrix (50x50)
        # Use random but symmetric distances
        np.random.seed(42)
        size = 50
        distance_matrix = np.random.randint(1000, 50000, size=(size, size))
        distance_matrix = (distance_matrix + distance_matrix.T) // 2  # Make symmetric
        np.fill_diagonal(distance_matrix, 0)  # Diagonal is 0

        # Measure TSP solver time
        print(f"\n[TEST] Solving TSP for {size} nodes...")
        start_time = time.time()

        solution = route_service._solve_tsp(distance_matrix)

        duration = time.time() - start_time

        print(f"[RESULT] TSP solved in {duration:.2f} seconds")
        print(f"[RESULT] Total distance: {solution['total_distance']} meters")
        print(f"[RESULT] Route length: {len(solution['route'])} nodes")

        # Assert performance
        assert duration < 10.0, \
            f"TSP solver took {duration:.2f}s, exceeds 10s target"

        # Verify solution
        assert solution is not None
        assert 'route' in solution
        assert 'total_distance' in solution
        assert len(solution['route']) == size + 1  # All nodes + return to depot
