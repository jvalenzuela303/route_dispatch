"""
Fixtures for performance tests
"""

import pytest
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.models import Order, Invoice
from app.models.enums import OrderStatus, InvoiceType, SourceChannel, GeocodingConfidence


TIMEZONE = ZoneInfo("America/Santiago")


@pytest.fixture
def db_session_factory(db_engine):
    """
    Factory for creating new DB sessions (for concurrent tests)

    Returns a function that creates new sessions
    """
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine)

    def _create_session():
        return SessionLocal()

    return _create_session


@pytest.fixture
def create_bulk_orders(db_session, admin_user):
    """
    Factory fixture for creating bulk orders for performance testing

    Usage:
        create_bulk_orders(count=100, delivery_date=some_date)
    """
    def _create_orders(count: int, delivery_date: date = None):
        """Create N orders for performance testing"""
        if delivery_date is None:
            delivery_date = date.today() + timedelta(days=1)

        base_lat = -34.1706
        base_lon = -70.7406

        created_orders = []

        for i in range(count):
            # Vary coordinates
            lat_offset = (i % 20 - 10) * 0.002
            lon_offset = ((i // 20) % 20 - 10) * 0.002

            order = Order(
                id=uuid.uuid4(),
                order_number=f"PERF-{datetime.now().strftime('%Y%m%d')}-{i:05d}",
                customer_name=f"Performance Test Customer {i}",
                customer_phone="+56912345678",
                address_text=f"Calle Test {100 + i}, Rancagua",
                address_coordinates=f'POINT({base_lon + lon_offset} {base_lat + lat_offset})',
                geocoding_confidence=GeocodingConfidence.HIGH,
                source_channel=SourceChannel.WEB,
                delivery_date=delivery_date,
                order_status=OrderStatus.DOCUMENTADO,  # Ready for routing
                created_by_user_id=admin_user.id
            )

            db_session.add(order)
            db_session.flush()

            # Create invoice
            invoice = Invoice(
                id=uuid.uuid4(),
                invoice_number=f"PERF-INV-{i:06d}",
                order_id=order.id,
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("25000.00"),
                issued_at=datetime.now(TIMEZONE),
                created_by_user_id=admin_user.id
            )

            db_session.add(invoice)
            created_orders.append(order)

        db_session.commit()
        return created_orders

    return _create_orders
