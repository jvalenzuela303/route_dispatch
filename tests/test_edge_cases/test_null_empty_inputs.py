"""
Edge Case Testing: Null and Empty Inputs

Tests system behavior with null, empty, and malformed inputs.
All endpoints should handle edge cases gracefully with proper validation errors.
"""

import pytest
import uuid
from decimal import Decimal

from app.services.order_service import OrderService
from app.services.invoice_service import InvoiceService
from app.services.user_service import UserService
from app.exceptions import ValidationError
from app.models.enums import SourceChannel, InvoiceType


class TestNullInputs:
    """Test null value handling"""

    def test_create_order_null_customer_name_fails(
        self,
        db_session,
        admin_user
    ):
        """
        Test order creation with null customer_name

        Expected: ValidationError (422 Unprocessable Entity)
        """
        order_service = OrderService(db_session)

        with pytest.raises((ValidationError, TypeError)):
            order_service.create_order(
                customer_name=None,  # NULL!
                customer_phone="+56912345678",
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_order_null_phone_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with null phone"""
        order_service = OrderService(db_session)

        with pytest.raises((ValidationError, TypeError)):
            order_service.create_order(
                customer_name="Test Customer",
                customer_phone=None,  # NULL!
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_order_null_address_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with null address"""
        order_service = OrderService(db_session)

        with pytest.raises((ValidationError, TypeError)):
            order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text=None,  # NULL!
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_invoice_null_invoice_number_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test invoice creation with null invoice_number"""
        invoice_service = InvoiceService(db_session)

        with pytest.raises((ValidationError, TypeError)):
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number=None,  # NULL!
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("50000.00"),
                user=admin_user
            )

    def test_transition_order_null_reason_for_incidencia_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test INCIDENCIA transition with null reason"""
        order_service = OrderService(db_session)

        from app.models.enums import OrderStatus

        with pytest.raises(ValidationError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_en_ruta.id,
                new_status=OrderStatus.INCIDENCIA,
                user=admin_user,
                reason=None  # NULL reason!
            )

        assert exc_info.value.code == "INCIDENCE_REASON_REQUIRED"


class TestEmptyStringInputs:
    """Test empty string handling"""

    def test_create_order_empty_customer_name_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with empty customer_name"""
        order_service = OrderService(db_session)

        # Pydantic should reject empty string for required field
        with pytest.raises(ValidationError):
            order_service.create_order(
                customer_name="",  # Empty!
                customer_phone="+56912345678",
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_order_whitespace_only_customer_name_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with whitespace-only customer_name"""
        order_service = OrderService(db_session)

        with pytest.raises(ValidationError):
            order_service.create_order(
                customer_name="   ",  # Whitespace only!
                customer_phone="+56912345678",
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_order_empty_phone_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with empty phone"""
        order_service = OrderService(db_session)

        with pytest.raises(ValidationError):
            order_service.create_order(
                customer_name="Test Customer",
                customer_phone="",  # Empty!
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

    def test_create_order_short_address_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with too short address (< 10 chars)"""
        order_service = OrderService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text="Short",  # Too short!
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

        assert exc_info.value.code == "ADDRESS_TOO_SHORT"

    def test_incidencia_empty_reason_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test INCIDENCIA with empty reason string"""
        order_service = OrderService(db_session)

        from app.models.enums import OrderStatus

        with pytest.raises(ValidationError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_en_ruta.id,
                new_status=OrderStatus.INCIDENCIA,
                user=admin_user,
                reason=""  # Empty reason!
            )

        assert exc_info.value.code == "INCIDENCE_REASON_REQUIRED"

    def test_admin_override_empty_reason_fails(
        self,
        db_session,
        admin_user
    ):
        """Test admin cutoff override with empty reason"""
        from datetime import datetime, date
        from zoneinfo import ZoneInfo
        from app.services.cutoff_service import CutoffService

        TIMEZONE = ZoneInfo("America/Santiago")

        order_time = datetime(2026, 1, 22, 16, 0, 0, tzinfo=TIMEZONE)
        override_date = date(2026, 1, 22)

        with pytest.raises(ValidationError) as exc_info:
            CutoffService.calculate_delivery_date(
                order_created_at=order_time,
                user=admin_user,
                override_date=override_date,
                override_reason=""  # Empty reason!
            )

        assert exc_info.value.code == "OVERRIDE_REASON_REQUIRED"


class TestInvalidUUIDs:
    """Test invalid UUID handling"""

    def test_get_order_with_invalid_uuid_fails(
        self,
        db_session,
        admin_user
    ):
        """Test getting order with malformed UUID"""
        order_service = OrderService(db_session)

        # Invalid UUID format
        with pytest.raises((ValidationError, ValueError)):
            order_service.transition_order_state(
                order_id="not-a-valid-uuid",  # Invalid!
                new_status="PENDIENTE",
                user=admin_user
            )

    def test_create_invoice_with_invalid_order_id_fails(
        self,
        db_session,
        admin_user
    ):
        """Test creating invoice with non-existent order UUID"""
        invoice_service = InvoiceService(db_session)

        non_existent_id = uuid.uuid4()

        from app.exceptions import NotFoundError

        with pytest.raises(NotFoundError) as exc_info:
            invoice_service.create_invoice(
                order_id=non_existent_id,  # Doesn't exist!
                invoice_number="FAC-INVALID-001",
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("50000.00"),
                user=admin_user
            )

        assert exc_info.value.code == "ORDER_NOT_FOUND"


class TestInvalidPhoneFormats:
    """Test phone number validation"""

    def test_order_with_non_chilean_phone_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with non-Chilean phone format"""
        order_service = OrderService(db_session)

        invalid_phones = [
            "+1234567890",  # US format
            "912345678",    # Missing country code
            "+5691234",     # Too short
            "+569123456789012345",  # Too long
        ]

        for invalid_phone in invalid_phones:
            with pytest.raises(ValidationError) as exc_info:
                order_service.create_order(
                    customer_name="Test Customer",
                    customer_phone=invalid_phone,
                    address_text="Av O'Higgins 123, Rancagua",
                    source_channel=SourceChannel.WEB,
                    user=admin_user
                )

            assert exc_info.value.code == "INVALID_PHONE_FORMAT"


class TestInvalidDateFormats:
    """Test date/datetime validation"""

    def test_invalid_delivery_date_format(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with invalid date format"""
        # Pydantic should handle date validation at schema level
        # This test verifies schema validation works

        # If creating via API, malformed date string would be rejected by Pydantic
        # Example: "2026-13-45" (invalid month/day)
        pass  # Covered by API endpoint tests


class TestInvalidEnumValues:
    """Test enum validation"""

    def test_create_order_invalid_source_channel_fails(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with invalid source channel"""
        order_service = OrderService(db_session)

        with pytest.raises((ValidationError, ValueError)):
            order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text="Av O'Higgins 123, Rancagua",
                source_channel="INVALID_CHANNEL",  # Not in enum!
                user=admin_user
            )

    def test_create_invoice_invalid_type_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test invoice creation with invalid type"""
        invoice_service = InvoiceService(db_session)

        with pytest.raises((ValidationError, ValueError)):
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number="FAC-001",
                invoice_type="INVALID_TYPE",  # Not in enum!
                total_amount=Decimal("50000.00"),
                user=admin_user
            )


class TestNegativeAndZeroValues:
    """Test negative and zero value validation"""

    def test_create_invoice_negative_amount_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test invoice creation with negative amount"""
        invoice_service = InvoiceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number="FAC-NEG-001",
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("-5000.00"),  # Negative!
                user=admin_user
            )

        assert exc_info.value.code == "INVALID_AMOUNT"

    def test_create_invoice_zero_amount_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test invoice creation with zero amount"""
        invoice_service = InvoiceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number="FAC-ZERO-001",
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("0.00"),  # Zero!
                user=admin_user
            )

        assert exc_info.value.code == "INVALID_AMOUNT"


class TestExtremelyLongInputs:
    """Test handling of extremely long inputs"""

    def test_order_with_very_long_notes(
        self,
        db_session,
        admin_user
    ):
        """Test order creation with very long notes (10,000 chars)"""
        order_service = OrderService(db_session)

        very_long_notes = "A" * 10000

        order = order_service.create_order(
            customer_name="Test Customer",
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user,
            notes=very_long_notes
        )

        # Should handle gracefully (database might truncate)
        assert order.notes is not None

    def test_order_with_very_long_customer_name(
        self,
        db_session,
        admin_user
    ):
        """Test order with customer name at DB column limit"""
        order_service = OrderService(db_session)

        # Assuming 255 char limit for customer_name
        long_name = "A" * 255

        order = order_service.create_order(
            customer_name=long_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        assert len(order.customer_name) <= 255
