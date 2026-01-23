"""
Seed data script for Route Dispatch System

Populates the database with initial data for development and testing:
- User roles (Administrador, Encargado de Bodega, Vendedor, Repartidor)
- Test users (one per role)
- Sample orders with various states
- Sample invoices
- Sample routes

Usage:
    python -m app.scripts.seed_data

Environment:
    Requires DATABASE_URL to be configured in .env file
"""

import sys
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

import bcrypt
from geoalchemy2 import WKTElement

# Add project root to path for imports
sys.path.insert(0, '/home/juan/Desarrollo/route_dispatch')

from app.config.database import get_db_context
from app.models import (
    Role, User, Order, Invoice, Route,
    OrderStatus, SourceChannel, GeocodingConfidence,
    InvoiceType, RouteStatus
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_roles(db):
    """Create initial user roles"""
    print("Creating roles...")

    roles_data = [
        {
            "role_name": "Administrador",
            "description": "Full system access with override capabilities for business rules",
            "permissions": {
                "can_create_users": True,
                "can_manage_roles": True,
                "can_override_cutoff": True,
                "can_force_delivery_date": True,
                "can_delete_orders": True,
                "can_view_audit_logs": True,
                "can_manage_routes": True,
                "can_create_orders": True,
                "can_create_invoices": True,
            }
        },
        {
            "role_name": "Encargado de Bodega",
            "description": "Warehouse manager - generates routes and approves deliveries",
            "permissions": {
                "can_create_users": False,
                "can_manage_roles": False,
                "can_override_cutoff": False,
                "can_force_delivery_date": False,
                "can_delete_orders": False,
                "can_view_audit_logs": True,
                "can_manage_routes": True,
                "can_create_orders": True,
                "can_create_invoices": True,
                "can_approve_deliveries": True,
            }
        },
        {
            "role_name": "Vendedor",
            "description": "Sales representative - creates orders and invoices",
            "permissions": {
                "can_create_users": False,
                "can_manage_roles": False,
                "can_override_cutoff": False,
                "can_force_delivery_date": False,
                "can_delete_orders": False,
                "can_view_audit_logs": False,
                "can_manage_routes": False,
                "can_create_orders": True,
                "can_create_invoices": True,
            }
        },
        {
            "role_name": "Repartidor",
            "description": "Delivery driver - views routes and updates delivery status",
            "permissions": {
                "can_create_users": False,
                "can_manage_roles": False,
                "can_override_cutoff": False,
                "can_force_delivery_date": False,
                "can_delete_orders": False,
                "can_view_audit_logs": False,
                "can_manage_routes": False,
                "can_create_orders": False,
                "can_create_invoices": False,
                "can_view_assigned_routes": True,
                "can_update_delivery_status": True,
            }
        }
    ]

    roles = {}
    for role_data in roles_data:
        role = Role(**role_data)
        db.add(role)
        roles[role_data["role_name"]] = role
        print(f"  Created role: {role_data['role_name']}")

    db.commit()
    return roles


def create_users(db, roles):
    """Create test users (one per role)"""
    print("\nCreating test users...")

    # Common password for all test users
    test_password = "Test1234!"
    hashed_password = hash_password(test_password)

    users_data = [
        {
            "username": "admin",
            "email": "admin@botilleria.cl",
            "role": roles["Administrador"],
        },
        {
            "username": "bodega",
            "email": "bodega@botilleria.cl",
            "role": roles["Encargado de Bodega"],
        },
        {
            "username": "vendedor",
            "email": "vendedor@botilleria.cl",
            "role": roles["Vendedor"],
        },
        {
            "username": "repartidor",
            "email": "repartidor@botilleria.cl",
            "role": roles["Repartidor"],
        }
    ]

    users = {}
    for user_data in users_data:
        role = user_data.pop("role")
        user = User(
            **user_data,
            password_hash=hashed_password,
            role_id=role.id,
            active_status=True
        )
        db.add(user)
        users[user_data["username"]] = user
        print(f"  Created user: {user_data['username']} ({user_data['email']}) - Password: {test_password}")

    db.commit()
    return users


def create_orders(db, users):
    """Create sample orders with various states"""
    print("\nCreating sample orders...")

    # Rancagua coordinates and surrounding areas
    # Format: (address_text, latitude, longitude, confidence)
    locations = [
        ("Av. Brasil 1234, Rancagua", -34.1704, -70.7407, GeocodingConfidence.HIGH),
        ("Calle Estado 567, Rancagua", -34.1689, -70.7428, GeocodingConfidence.HIGH),
        ("Av. San Martin 890, Rancagua", -34.1678, -70.7456, GeocodingConfidence.HIGH),
        ("Calle Millán 234, Rancagua", -34.1721, -70.7389, GeocodingConfidence.MEDIUM),
        ("Av. Cachapoal 456, Rancagua", -34.1712, -70.7401, GeocodingConfidence.HIGH),
        ("Calle Astorga 789, Rancagua", -34.1695, -70.7415, GeocodingConfidence.HIGH),
        ("Población Los Libertadores, Machalí", -34.1845, -70.6512, GeocodingConfidence.MEDIUM),
        ("Villa San José, Rancagua", -34.1756, -70.7298, GeocodingConfidence.MEDIUM),
        ("Cerca del Estadio El Teniente", -34.1623, -70.7523, GeocodingConfidence.LOW),
        ("Zona Norte, Rancagua", -34.1589, -70.7445, GeocodingConfidence.LOW),
    ]

    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    orders_data = [
        # PENDIENTE - just created
        {
            "customer_name": "Juan Pérez",
            "customer_phone": "+56912345001",
            "customer_email": "juan.perez@example.com",
            "address_index": 0,
            "order_status": OrderStatus.PENDIENTE,
            "source_channel": SourceChannel.WEB,
            "delivery_date": None,
        },
        {
            "customer_name": "María González",
            "customer_phone": "+56912345002",
            "customer_email": "maria.gonzalez@example.com",
            "address_index": 1,
            "order_status": OrderStatus.PENDIENTE,
            "source_channel": SourceChannel.RRSS,
            "delivery_date": None,
        },
        # EN_PREPARACION - being prepared
        {
            "customer_name": "Pedro Silva",
            "customer_phone": "+56912345003",
            "customer_email": "pedro.silva@example.com",
            "address_index": 2,
            "order_status": OrderStatus.EN_PREPARACION,
            "source_channel": SourceChannel.PRESENCIAL,
            "delivery_date": tomorrow,
        },
        {
            "customer_name": "Ana Martínez",
            "customer_phone": "+56912345004",
            "customer_email": None,
            "address_index": 3,
            "order_status": OrderStatus.EN_PREPARACION,
            "source_channel": SourceChannel.WEB,
            "delivery_date": tomorrow,
        },
        # DOCUMENTADO - invoice linked, ready for routing
        {
            "customer_name": "Carlos Rodríguez",
            "customer_phone": "+56912345005",
            "customer_email": "carlos.rodriguez@example.com",
            "address_index": 4,
            "order_status": OrderStatus.DOCUMENTADO,
            "source_channel": SourceChannel.WEB,
            "delivery_date": today,
        },
        {
            "customer_name": "Lucía Fernández",
            "customer_phone": "+56912345006",
            "customer_email": "lucia.fernandez@example.com",
            "address_index": 5,
            "order_status": OrderStatus.DOCUMENTADO,
            "source_channel": SourceChannel.RRSS,
            "delivery_date": today,
        },
        # EN_RUTA - currently being delivered
        {
            "customer_name": "Roberto Díaz",
            "customer_phone": "+56912345007",
            "customer_email": "roberto.diaz@example.com",
            "address_index": 6,
            "order_status": OrderStatus.EN_RUTA,
            "source_channel": SourceChannel.WEB,
            "delivery_date": today,
        },
        {
            "customer_name": "Carmen Vega",
            "customer_phone": "+56912345008",
            "customer_email": None,
            "address_index": 7,
            "order_status": OrderStatus.EN_RUTA,
            "source_channel": SourceChannel.PRESENCIAL,
            "delivery_date": today,
        },
        # ENTREGADO - delivered yesterday
        {
            "customer_name": "José Torres",
            "customer_phone": "+56912345009",
            "customer_email": "jose.torres@example.com",
            "address_index": 8,
            "order_status": OrderStatus.ENTREGADO,
            "source_channel": SourceChannel.WEB,
            "delivery_date": yesterday,
        },
        # INCIDENCIA - delivery failed
        {
            "customer_name": "Patricia Morales",
            "customer_phone": "+56912345010",
            "customer_email": "patricia.morales@example.com",
            "address_index": 9,
            "order_status": OrderStatus.INCIDENCIA,
            "source_channel": SourceChannel.RRSS,
            "delivery_date": yesterday,
        },
    ]

    orders = []
    for i, order_data in enumerate(orders_data):
        address_index = order_data.pop("address_index")
        address_text, lat, lon, confidence = locations[address_index]

        # Generate order number: ORD-YYYYMMDD-NNNN
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{(i+1):04d}"

        # Create PostGIS point from coordinates
        # Format: POINT(longitude latitude) - note the order!
        point_wkt = f"POINT({lon} {lat})"

        order = Order(
            order_number=order_number,
            customer_name=order_data["customer_name"],
            customer_phone=order_data["customer_phone"],
            customer_email=order_data.get("customer_email"),
            address_text=address_text,
            address_coordinates=WKTElement(point_wkt, srid=4326),
            geocoding_confidence=confidence,
            order_status=order_data["order_status"],
            source_channel=order_data["source_channel"],
            delivery_date=order_data.get("delivery_date"),
            created_by_user_id=users["vendedor"].id,
            notes=None
        )
        db.add(order)
        orders.append(order)
        print(f"  Created order: {order_number} - {order_data['customer_name']} ({order_data['order_status'].value})")

    db.commit()
    return orders


def create_invoices(db, orders, users):
    """Create invoices for some orders"""
    print("\nCreating sample invoices...")

    # Create invoices for orders in DOCUMENTADO, EN_RUTA, ENTREGADO states
    invoice_statuses = [OrderStatus.DOCUMENTADO, OrderStatus.EN_RUTA, OrderStatus.ENTREGADO]

    invoices = []
    invoice_counter = 1

    for order in orders:
        if order.order_status in invoice_statuses:
            # Generate invoice number
            invoice_type = InvoiceType.FACTURA if invoice_counter % 2 == 0 else InvoiceType.BOLETA
            invoice_number = f"{invoice_type.value}-{datetime.now().strftime('%Y%m')}-{invoice_counter:05d}"

            invoice = Invoice(
                invoice_number=invoice_number,
                order_id=order.id,
                invoice_type=invoice_type,
                total_amount=Decimal("45000.00") + (Decimal("5000.00") * invoice_counter),
                issued_at=datetime.now(timezone.utc),
                created_by_user_id=users["vendedor"].id
            )
            db.add(invoice)
            invoices.append(invoice)
            invoice_counter += 1

            print(f"  Created invoice: {invoice_number} for order {order.order_number}")

    db.commit()
    return invoices


def create_routes(db, orders, users):
    """Create sample routes"""
    print("\nCreating sample routes...")

    today = date.today()
    yesterday = today - timedelta(days=1)

    # Route 1: Active route for today with EN_RUTA orders
    en_ruta_orders = [o for o in orders if o.order_status == OrderStatus.EN_RUTA]
    if en_ruta_orders:
        route1 = Route(
            route_name=f"Ruta {today.strftime('%Y-%m-%d')} #1",
            route_date=today,
            assigned_driver_id=users["repartidor"].id,
            status=RouteStatus.ACTIVE,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            total_distance_km=Decimal("15.5"),
            estimated_duration_minutes=120,
            stop_sequence=[str(o.id) for o in en_ruta_orders]
        )
        db.add(route1)

        # Assign orders to this route
        for order in en_ruta_orders:
            order.assigned_route_id = route1.id

        print(f"  Created active route: {route1.route_name} with {len(en_ruta_orders)} stops")

    # Route 2: Completed route from yesterday with ENTREGADO orders
    entregado_orders = [o for o in orders if o.order_status == OrderStatus.ENTREGADO]
    if entregado_orders:
        route2 = Route(
            route_name=f"Ruta {yesterday.strftime('%Y-%m-%d')} #1",
            route_date=yesterday,
            assigned_driver_id=users["repartidor"].id,
            status=RouteStatus.COMPLETED,
            started_at=datetime.now(timezone.utc) - timedelta(days=1, hours=8),
            completed_at=datetime.now(timezone.utc) - timedelta(days=1, hours=4),
            total_distance_km=Decimal("12.3"),
            estimated_duration_minutes=90,
            actual_duration_minutes=105,
            stop_sequence=[str(o.id) for o in entregado_orders]
        )
        db.add(route2)

        # Assign orders to this route
        for order in entregado_orders:
            order.assigned_route_id = route2.id

        print(f"  Created completed route: {route2.route_name} with {len(entregado_orders)} stops")

    # Route 3: Draft route with DOCUMENTADO orders (not yet assigned to driver)
    documentado_orders = [o for o in orders if o.order_status == OrderStatus.DOCUMENTADO]
    if documentado_orders:
        route3 = Route(
            route_name=f"Ruta {today.strftime('%Y-%m-%d')} #2 (Draft)",
            route_date=today,
            assigned_driver_id=None,  # Not yet assigned
            status=RouteStatus.DRAFT,
            total_distance_km=Decimal("18.7"),
            estimated_duration_minutes=150,
            stop_sequence=[str(o.id) for o in documentado_orders]
        )
        db.add(route3)
        print(f"  Created draft route: {route3.route_name} with {len(documentado_orders)} stops")

    db.commit()


def main():
    """Main seeding function"""
    print("=" * 70)
    print("Route Dispatch System - Database Seeding")
    print("=" * 70)

    try:
        with get_db_context() as db:
            # Create all seed data
            roles = create_roles(db)
            users = create_users(db, roles)
            orders = create_orders(db, users)
            invoices = create_invoices(db, orders, users)
            create_routes(db, orders, users)

            print("\n" + "=" * 70)
            print("Database seeding completed successfully!")
            print("=" * 70)
            print("\nTest User Credentials:")
            print("-" * 70)
            print("  Username: admin       | Email: admin@botilleria.cl      | Password: Test1234!")
            print("  Username: bodega      | Email: bodega@botilleria.cl     | Password: Test1234!")
            print("  Username: vendedor    | Email: vendedor@botilleria.cl   | Password: Test1234!")
            print("  Username: repartidor  | Email: repartidor@botilleria.cl | Password: Test1234!")
            print("-" * 70)
            print(f"\nSummary:")
            print(f"  Roles:    {len(roles)}")
            print(f"  Users:    {len(users)}")
            print(f"  Orders:   {len(orders)}")
            print(f"  Invoices: {len(invoices)}")
            print(f"  Routes:   3")
            print("=" * 70)

    except Exception as e:
        print(f"\nError seeding database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
