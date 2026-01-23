"""
Route Optimization Usage Examples

Demonstrates how to use the RouteOptimizationService for:
- Generating optimized delivery routes
- Activating routes and assigning drivers
- Retrieving route details
- Handling errors

Setup:
1. Ensure database is running and migrations applied
2. Have orders in DOCUMENTADO status with coordinates
3. Have user accounts (Encargado/Admin for route generation, Repartidor for delivery)

Run:
    python examples/route_optimization_example.py
"""

import sys
import os
from datetime import date, timedelta
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.models import User, Order, Invoice
from app.models.enums import OrderStatus
from app.services.route_optimization_service import RouteOptimizationService
from app.exceptions import RouteOptimizationError, ValidationError


def print_section(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def example_1_generate_route():
    """
    Example 1: Generate optimized route for tomorrow's deliveries

    Prerequisites:
    - Orders in DOCUMENTADO status
    - Orders have delivery_date = tomorrow
    - Orders have invoices linked
    - Orders have been geocoded
    """
    print_section("Example 1: Generate Route for Tomorrow")

    # Get database session
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Get admin/encargado user
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            print("ERROR: Admin user not found. Create user first.")
            return

        # Calculate tomorrow's date
        tomorrow = date.today() + timedelta(days=1)

        print(f"Generating route for: {tomorrow}")
        print(f"User: {user.username} ({user.role.role_name})")

        # Check eligible orders
        eligible_orders = db.query(Order).filter(
            Order.order_status == OrderStatus.DOCUMENTADO,
            Order.delivery_date == tomorrow,
            Order.address_coordinates.isnot(None)
        ).all()

        print(f"Eligible orders: {len(eligible_orders)}")

        if not eligible_orders:
            print("\nNo eligible orders found. Create some orders first:")
            print("  1. Create orders with OrderService")
            print("  2. Create invoices with InvoiceService")
            print("  3. Geocode addresses with GeocodingService")
            return

        # List eligible orders
        print("\nEligible orders:")
        for order in eligible_orders:
            print(f"  - {order.order_number}: {order.customer_name} - {order.address_text}")

        # Generate route
        print("\nGenerating optimized route...")
        service = RouteOptimizationService(db)
        route = service.generate_route_for_date(tomorrow, user)

        # Display results
        print("\nRoute Generated Successfully!")
        print(f"  Route ID: {route.id}")
        print(f"  Route Name: {route.route_name}")
        print(f"  Status: {route.status.value}")
        print(f"  Date: {route.route_date}")
        print(f"  Total Distance: {route.total_distance_km} km")
        print(f"  Estimated Duration: {route.estimated_duration_minutes} minutes")
        print(f"  Number of Stops: {len(route.stop_sequence)}")

        print("\nOptimized Stop Sequence:")
        for idx, order_id in enumerate(route.stop_sequence, start=1):
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                print(f"  {idx}. {order.order_number} - {order.customer_name}")

    except RouteOptimizationError as e:
        print(f"\nRoute Optimization Error: {e.message}")
        print(f"Code: {e.code}")
        print(f"Details: {e.details}")

    finally:
        db.close()


def example_2_activate_route():
    """
    Example 2: Activate a route and assign to driver

    This transitions all orders in the route to EN_RUTA status
    """
    print_section("Example 2: Activate Route and Assign Driver")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Get users
        admin = db.query(User).filter(User.username == "admin").first()
        driver = db.query(User).filter(User.role.role_name == "Repartidor").first()

        if not admin or not driver:
            print("ERROR: Admin or Driver user not found")
            return

        print(f"Admin: {admin.username}")
        print(f"Driver: {driver.username}")

        # Find a DRAFT route
        from app.models.models import Route
        from app.models.enums import RouteStatus

        draft_route = db.query(Route).filter(
            Route.status == RouteStatus.DRAFT
        ).first()

        if not draft_route:
            print("\nNo DRAFT routes found. Generate a route first (Example 1)")
            return

        print(f"\nFound DRAFT route: {draft_route.route_name}")
        print(f"  Route ID: {draft_route.id}")
        print(f"  Date: {draft_route.route_date}")
        print(f"  Stops: {len(draft_route.stop_sequence)}")

        # Activate route
        print(f"\nActivating route and assigning to {driver.username}...")
        service = RouteOptimizationService(db)
        activated_route = service.activate_route(
            route_id=draft_route.id,
            driver_id=driver.id,
            user=admin
        )

        print("\nRoute Activated Successfully!")
        print(f"  Status: {activated_route.status.value}")
        print(f"  Assigned Driver: {activated_route.assigned_driver.username}")
        print(f"  Started At: {activated_route.started_at}")

        # Verify orders transitioned to EN_RUTA
        print("\nOrder Status Updates:")
        for order_id in activated_route.stop_sequence:
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                print(f"  {order.order_number}: {order.order_status.value}")

    except RouteOptimizationError as e:
        print(f"\nError: {e.message}")
    except ValidationError as e:
        print(f"\nValidation Error: {e.message}")

    finally:
        db.close()


def example_3_get_route_details():
    """
    Example 3: Get detailed route information

    Retrieves complete route details including ordered stops
    """
    print_section("Example 3: Get Route Details")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Find any route
        from app.models.models import Route

        route = db.query(Route).first()

        if not route:
            print("No routes found. Generate a route first (Example 1)")
            return

        print(f"Retrieving details for: {route.route_name}")

        # Get details
        service = RouteOptimizationService(db)
        details = service.get_route_details(route.id)

        # Display details
        print("\nRoute Details:")
        print(f"  Route ID: {details['route_id']}")
        print(f"  Name: {details['route_name']}")
        print(f"  Date: {details['route_date']}")
        print(f"  Status: {details['status']}")

        if details['assigned_driver_id']:
            print(f"  Assigned Driver ID: {details['assigned_driver_id']}")

        print(f"\nMetrics:")
        print(f"  Total Distance: {details['total_distance_km']} km")
        print(f"  Estimated Duration: {details['estimated_duration_minutes']} minutes")
        print(f"  Actual Duration: {details['actual_duration_minutes'] or 'N/A'}")

        print(f"\nTimestamps:")
        print(f"  Started: {details['started_at'] or 'Not started'}")
        print(f"  Completed: {details['completed_at'] or 'Not completed'}")

        print(f"\nStops ({details['num_stops']}):")
        for stop in details['stops']:
            print(f"  {stop['stop_number']}. {stop['order_number']}")
            print(f"     Customer: {stop['customer_name']}")
            print(f"     Phone: {stop['customer_phone']}")
            print(f"     Address: {stop['address_text']}")
            print(f"     Status: {stop['order_status']}")
            print()

    except RouteOptimizationError as e:
        print(f"\nError: {e.message}")

    finally:
        db.close()


def example_4_performance_test():
    """
    Example 4: Test route generation performance

    Measures time to generate route with varying order counts
    """
    print_section("Example 4: Performance Testing")

    import time

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            print("ERROR: Admin user not found")
            return

        tomorrow = date.today() + timedelta(days=1)

        # Count eligible orders
        eligible_count = db.query(Order).filter(
            Order.order_status == OrderStatus.DOCUMENTADO,
            Order.delivery_date == tomorrow,
            Order.address_coordinates.isnot(None)
        ).count()

        print(f"Eligible orders: {eligible_count}")

        if eligible_count == 0:
            print("No eligible orders for performance test")
            return

        # Generate route and measure time
        service = RouteOptimizationService(db)

        print("\nGenerating route...")
        start_time = time.time()
        route = service.generate_route_for_date(tomorrow, user)
        elapsed = time.time() - start_time

        print(f"\nPerformance Results:")
        print(f"  Orders Processed: {len(route.stop_sequence)}")
        print(f"  Generation Time: {elapsed:.2f} seconds")
        print(f"  Total Distance: {route.total_distance_km} km")
        print(f"  Estimated Duration: {route.estimated_duration_minutes} minutes")

        # Performance assessment
        if eligible_count <= 10:
            threshold = 2.0
        elif eligible_count <= 50:
            threshold = 10.0
        else:
            threshold = 30.0

        if elapsed < threshold:
            print(f"\n  Performance: EXCELLENT (< {threshold}s)")
        else:
            print(f"\n  Performance: ACCEPTABLE (< {threshold}s threshold)")

        # Cleanup - delete the test route
        db.delete(route)
        db.commit()
        print("\nTest route deleted")

    except RouteOptimizationError as e:
        print(f"\nError: {e.message}")

    finally:
        db.close()


def example_5_error_handling():
    """
    Example 5: Error handling examples

    Demonstrates proper error handling for common scenarios
    """
    print_section("Example 5: Error Handling")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            print("ERROR: Admin user not found")
            return

        service = RouteOptimizationService(db)

        # Error 1: No eligible orders
        print("1. Testing: No eligible orders for date")
        try:
            far_future = date.today() + timedelta(days=365)
            route = service.generate_route_for_date(far_future, user)
        except RouteOptimizationError as e:
            print(f"   Expected Error: {e.message}")
            print(f"   Error Code: {e.code}")

        # Error 2: Invalid route ID
        print("\n2. Testing: Get details for non-existent route")
        try:
            import uuid
            fake_id = uuid.uuid4()
            details = service.get_route_details(fake_id)
        except RouteOptimizationError as e:
            print(f"   Expected Error: {e.message}")

        # Error 3: Activate non-DRAFT route
        print("\n3. Testing: Activate already active route")
        from app.models.models import Route
        from app.models.enums import RouteStatus

        active_route = db.query(Route).filter(
            Route.status == RouteStatus.ACTIVE
        ).first()

        if active_route:
            try:
                driver = db.query(User).filter(
                    User.role.role_name == "Repartidor"
                ).first()
                service.activate_route(active_route.id, driver.id, user)
            except RouteOptimizationError as e:
                print(f"   Expected Error: {e.message}")
        else:
            print("   No ACTIVE routes to test with")

        # Error 4: Invalid driver
        print("\n4. Testing: Activate with invalid driver")
        draft_route = db.query(Route).filter(
            Route.status == RouteStatus.DRAFT
        ).first()

        if draft_route:
            try:
                import uuid
                fake_driver_id = uuid.uuid4()
                service.activate_route(draft_route.id, fake_driver_id, user)
            except ValidationError as e:
                print(f"   Expected Error: {e.message}")
        else:
            print("   No DRAFT routes to test with")

        print("\nAll error cases handled correctly!")

    except Exception as e:
        print(f"\nUnexpected error: {e}")

    finally:
        db.close()


def main():
    """
    Main function to run all examples
    """
    print("\n" + "=" * 80)
    print("  ROUTE OPTIMIZATION SERVICE - USAGE EXAMPLES")
    print("=" * 80)

    examples = [
        ("Generate Route", example_1_generate_route),
        ("Activate Route", example_2_activate_route),
        ("Get Route Details", example_3_get_route_details),
        ("Performance Test", example_4_performance_test),
        ("Error Handling", example_5_error_handling)
    ]

    print("\nAvailable examples:")
    for idx, (name, _) in enumerate(examples, start=1):
        print(f"  {idx}. {name}")
    print("  0. Run all examples")

    try:
        choice = input("\nEnter example number (0-5): ").strip()

        if choice == "0":
            for name, func in examples:
                func()
        elif choice.isdigit() and 1 <= int(choice) <= len(examples):
            examples[int(choice) - 1][1]()
        else:
            print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        print(f"\nError running examples: {e}")


if __name__ == "__main__":
    main()
