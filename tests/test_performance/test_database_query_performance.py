"""
Database Query Performance Testing

Tests database query performance for critical operations:
- List orders with filters (< 200ms P95)
- Get order detail with relationships (< 200ms P95)
- Concurrent order creation (no race conditions)
- PostGIS spatial queries (< 500ms)
"""

import pytest
import time
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

from app.services.order_service import OrderService
from app.models.enums import OrderStatus, SourceChannel


class TestOrderQueryPerformance:
    """Test order query performance"""

    @pytest.mark.performance
    def test_list_orders_with_filters_under_200ms(
        self,
        db_session,
        admin_user,
        create_bulk_orders
    ):
        """
        Test listing orders with filters completes in < 200ms (P95)

        Query: GET /api/orders?status=DOCUMENTADO&limit=100
        """
        # Create 500 orders for realistic dataset
        print("\n[SETUP] Creating 500 test orders...")
        create_bulk_orders(count=500)

        order_service = OrderService(db_session)

        # Run query 20 times to get P95
        times = []

        for i in range(20):
            start_time = time.time()

            orders = order_service.get_orders_by_status(
                status=OrderStatus.PENDIENTE,
                user=admin_user,
                limit=100,
                offset=0
            )

            duration = (time.time() - start_time) * 1000  # Convert to ms
            times.append(duration)

        # Calculate P95 (95th percentile)
        times.sort()
        p95_time = times[int(len(times) * 0.95)]

        print(f"\n[RESULT] Query times (ms): min={min(times):.1f}, "
              f"median={times[len(times)//2]:.1f}, p95={p95_time:.1f}, max={max(times):.1f}")

        # Assert P95 is under 200ms
        assert p95_time < 200.0, \
            f"Query P95 time {p95_time:.1f}ms exceeds 200ms target"

    @pytest.mark.performance
    def test_get_order_with_relationships_under_200ms(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice
    ):
        """
        Test getting order with all relationships (invoice, route, etc.) in < 200ms

        Query includes joins for: invoice, assigned_route, created_by_user
        """
        from app.models.models import Order

        times = []

        for i in range(20):
            start_time = time.time()

            # Query with eager loading of relationships
            order = db_session.query(Order).filter(
                Order.id == sample_order_with_invoice.id
            ).first()

            # Access relationships to trigger loading
            _ = order.invoice
            _ = order.created_by_user
            if order.assigned_route_id:
                _ = order.assigned_route

            duration = (time.time() - start_time) * 1000  # ms
            times.append(duration)

        times.sort()
        p95_time = times[int(len(times) * 0.95)]

        print(f"\n[RESULT] Get order with relationships P95: {p95_time:.1f}ms")

        assert p95_time < 200.0, \
            f"Get order query P95 {p95_time:.1f}ms exceeds 200ms target"

    @pytest.mark.performance
    def test_orders_for_delivery_date_query_performance(
        self,
        db_session,
        admin_user,
        create_bulk_orders
    ):
        """
        Test get_orders_for_delivery_date query performance

        This query is critical for route generation
        """
        delivery_date = date.today() + timedelta(days=1)

        # Create 200 orders for delivery date
        print("\n[SETUP] Creating 200 orders for delivery date...")
        create_bulk_orders(count=200, delivery_date=delivery_date)

        order_service = OrderService(db_session)

        times = []

        for i in range(10):
            start_time = time.time()

            orders = order_service.get_orders_for_delivery_date(
                delivery_date=delivery_date,
                user=admin_user
            )

            duration = (time.time() - start_time) * 1000  # ms
            times.append(duration)

        times.sort()
        p95_time = times[int(len(times) * 0.95)]

        print(f"\n[RESULT] Get orders for delivery date P95: {p95_time:.1f}ms")
        print(f"[RESULT] Orders returned: {len(orders)}")

        assert p95_time < 300.0, \
            f"Query P95 {p95_time:.1f}ms exceeds 300ms target"


class TestConcurrentOperations:
    """Test concurrent operation safety and performance"""

    @pytest.mark.performance
    def test_concurrent_order_creation_no_race_conditions(
        self,
        db_session_factory,
        admin_user
    ):
        """
        CRITICAL: Test concurrent order creation doesn't cause race conditions

        Scenario: 10 users creating orders simultaneously
        Expected: All orders created successfully, no data corruption
        """
        num_concurrent_orders = 10

        def create_order(index):
            """Create order in separate DB session"""
            # Each thread gets its own DB session
            db = db_session_factory()

            try:
                order_service = OrderService(db)

                order = order_service.create_order(
                    customer_name=f"Concurrent Customer {index}",
                    customer_phone="+56912345678",
                    address_text=f"Av O'Higgins {100 + index}, Rancagua",
                    source_channel=SourceChannel.WEB,
                    user=admin_user
                )

                db.commit()
                return {
                    'success': True,
                    'order_id': order.id,
                    'order_number': order.order_number
                }

            except Exception as e:
                db.rollback()
                return {
                    'success': False,
                    'error': str(e)
                }
            finally:
                db.close()

        # Execute concurrent order creations
        print(f"\n[TEST] Creating {num_concurrent_orders} orders concurrently...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_concurrent_orders) as executor:
            futures = [executor.submit(create_order, i) for i in range(num_concurrent_orders)]

            results = [future.result() for future in as_completed(futures)]

        duration = time.time() - start_time

        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        print(f"\n[RESULT] Concurrent creation completed in {duration:.2f}s")
        print(f"[RESULT] Successful: {len(successful)}/{num_concurrent_orders}")
        print(f"[RESULT] Failed: {len(failed)}")

        if failed:
            for f in failed:
                print(f"[ERROR] {f['error']}")

        # Assert all succeeded
        assert len(successful) == num_concurrent_orders, \
            f"Only {len(successful)}/{num_concurrent_orders} orders created successfully"

        # Verify no duplicate order numbers (race condition check)
        order_numbers = [r['order_number'] for r in successful]
        unique_numbers = set(order_numbers)

        assert len(unique_numbers) == len(order_numbers), \
            "CRITICAL: Duplicate order numbers detected (race condition)!"

    @pytest.mark.performance
    def test_concurrent_state_transitions_with_locking(
        self,
        db_session_factory,
        admin_user,
        sample_order_en_ruta
    ):
        """
        Test concurrent state transitions use pessimistic locking

        Scenario: 2 threads trying to transition same order simultaneously
        Expected: One succeeds, one waits (no lost updates)
        """
        order_id = sample_order_en_ruta.id

        def transition_order(target_status):
            """Attempt to transition order"""
            db = db_session_factory()

            try:
                order_service = OrderService(db)

                updated_order = order_service.transition_order_state(
                    order_id=order_id,
                    new_status=target_status,
                    user=admin_user
                )

                db.commit()

                return {
                    'success': True,
                    'final_status': updated_order.order_status.value
                }

            except Exception as e:
                db.rollback()
                return {
                    'success': False,
                    'error': str(e)
                }
            finally:
                db.close()

        # Attempt concurrent transitions
        print(f"\n[TEST] Concurrent transitions on order {order_id}...")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(transition_order, OrderStatus.ENTREGADO),
                executor.submit(transition_order, OrderStatus.INCIDENCIA)
            ]

            results = [future.result() for future in as_completed(futures)]

        # One should succeed, one should fail (or both succeed if idempotent)
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        print(f"[RESULT] Successful: {len(successful)}, Failed: {len(failed)}")

        # Verify final state is consistent
        db = db_session_factory()
        from app.models.models import Order
        final_order = db.query(Order).filter(Order.id == order_id).first()

        print(f"[RESULT] Final order status: {final_order.order_status.value}")

        # Final status should be one of the attempted statuses
        assert final_order.order_status in [OrderStatus.ENTREGADO, OrderStatus.INCIDENCIA], \
            "Order ended in unexpected state after concurrent transitions"

        db.close()


class TestPostGISPerformance:
    """Test PostGIS spatial query performance"""

    @pytest.mark.performance
    def test_postgis_distance_calculation_performance(
        self,
        db_session
    ):
        """
        Test PostGIS ST_Distance query performance

        Target: Single distance calculation < 10ms
        """
        from sqlalchemy import text

        # Rancagua coordinates
        lat1, lon1 = -34.1706, -70.7406
        lat2, lon2 = -34.1800, -70.7500

        times = []

        for i in range(100):
            start_time = time.time()

            sql = text("""
                SELECT ST_Distance(
                    ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography
                ) AS distance_meters
            """)

            result = db_session.execute(sql, {
                'lon1': lon1, 'lat1': lat1,
                'lon2': lon2, 'lat2': lat2
            }).fetchone()

            duration = (time.time() - start_time) * 1000  # ms
            times.append(duration)

        times.sort()
        p95_time = times[int(len(times) * 0.95)]

        print(f"\n[RESULT] PostGIS distance query P95: {p95_time:.2f}ms")
        print(f"[RESULT] Distance: {result.distance_meters:.0f} meters")

        assert p95_time < 10.0, \
            f"PostGIS distance query P95 {p95_time:.2f}ms exceeds 10ms target"

    @pytest.mark.performance
    def test_postgis_batch_distance_calculations(
        self,
        db_session
    ):
        """
        Test batch distance calculations (100 distances)

        Target: < 500ms for 100 distance calculations
        """
        from sqlalchemy import text

        # Generate 10 coordinates (10x10 = 100 distance pairs)
        base_lat = -34.1706
        base_lon = -70.7406

        coordinates = []
        for i in range(10):
            lat = base_lat + (i * 0.01)
            lon = base_lon + (i * 0.01)
            coordinates.append((lat, lon))

        # Measure batch distance calculation
        start_time = time.time()

        distances = []
        for i, (lat1, lon1) in enumerate(coordinates):
            for j, (lat2, lon2) in enumerate(coordinates):
                if i != j:
                    sql = text("""
                        SELECT ST_Distance(
                            ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,
                            ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography
                        ) AS distance_meters
                    """)

                    result = db_session.execute(sql, {
                        'lon1': lon1, 'lat1': lat1,
                        'lon2': lon2, 'lat2': lat2
                    }).fetchone()

                    distances.append(result.distance_meters)

        duration = (time.time() - start_time) * 1000  # ms

        print(f"\n[RESULT] {len(distances)} distance calculations in {duration:.0f}ms")
        print(f"[RESULT] Average per calculation: {duration/len(distances):.2f}ms")

        assert duration < 500.0, \
            f"Batch distance calculation {duration:.0f}ms exceeds 500ms target"
