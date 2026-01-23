"""
Business Rules testing for Invoice Requirements (BR-004, BR-005)

Critical business rules:
- BR-004: Orders cannot transition to EN_RUTA without invoice
- BR-005: Creating invoice auto-transitions order to DOCUMENTADO

These rules are CRITICAL for the order workflow integrity.
"""

import pytest
import uuid
from decimal import Decimal

from app.models.enums import OrderStatus, InvoiceType
from app.services.invoice_service import InvoiceService
from app.services.order_service import OrderService
from app.exceptions import (
    ValidationError,
    InvoiceRequiredError,
    IntegrityError
)


class TestInvoiceAutoTransition:
    """Test BR-005: Auto-transition to DOCUMENTADO on invoice creation"""

    def test_create_invoice_auto_transitions_to_documentado(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """
        CRITICAL TEST: Creating invoice auto-transitions order to DOCUMENTADO

        Steps:
        1. Order is in EN_PREPARACION
        2. Create invoice
        3. Verify order status changed to DOCUMENTADO
        """
        invoice_service = InvoiceService(db_session)

        # Verify initial state
        assert sample_order_en_preparacion.order_status == OrderStatus.EN_PREPARACION
        assert sample_order_en_preparacion.invoice is None

        # Create invoice
        invoice = invoice_service.create_invoice(
            order_id=sample_order_en_preparacion.id,
            invoice_number="FAC-001-2026",
            invoice_type=InvoiceType.FACTURA,
            total_amount=Decimal("50000.00"),
            user=admin_user
        )

        # Refresh order from DB
        db_session.refresh(sample_order_en_preparacion)

        # Verify auto-transition occurred
        assert sample_order_en_preparacion.order_status == OrderStatus.DOCUMENTADO
        assert sample_order_en_preparacion.invoice_id == invoice.id

    def test_create_invoice_on_wrong_status_fails(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """
        Test invoice creation fails if order not in EN_PREPARACION

        Expected: ValidationError
        """
        invoice_service = InvoiceService(db_session)

        # Order is PENDIENTE, not EN_PREPARACION
        assert sample_order_pendiente.order_status == OrderStatus.PENDIENTE

        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_pendiente.id,
                invoice_number="FAC-002-2026",
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("50000.00"),
                user=admin_user
            )

        assert exc_info.value.code == "INVALID_STATE_FOR_INVOICE"
        assert "EN_PREPARACION" in exc_info.value.message

    def test_create_duplicate_invoice_on_same_order_fails(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice
    ):
        """
        Test cannot create second invoice for same order

        Expected: ValidationError with ORDER_ALREADY_HAS_INVOICE
        """
        invoice_service = InvoiceService(db_session)

        # Order already has invoice
        assert sample_order_with_invoice.invoice is not None

        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_with_invoice.id,
                invoice_number="FAC-DUPLICATE-2026",
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("30000.00"),
                user=admin_user
            )

        assert exc_info.value.code == "ORDER_ALREADY_HAS_INVOICE"

    def test_create_invoice_with_duplicate_number_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion,
        another_order_en_preparacion
    ):
        """
        SECURITY TEST: Invoice number must be unique across all invoices

        Expected: IntegrityError with DUPLICATE_INVOICE_NUMBER
        """
        invoice_service = InvoiceService(db_session)

        # Create first invoice
        invoice_service.create_invoice(
            order_id=sample_order_en_preparacion.id,
            invoice_number="FAC-UNIQUE-001",
            invoice_type=InvoiceType.FACTURA,
            total_amount=Decimal("50000.00"),
            user=admin_user
        )

        # Attempt to create second invoice with same number
        with pytest.raises(IntegrityError) as exc_info:
            invoice_service.create_invoice(
                order_id=another_order_en_preparacion.id,
                invoice_number="FAC-UNIQUE-001",  # Duplicate!
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("60000.00"),
                user=admin_user
            )

        assert exc_info.value.code == "DUPLICATE_INVOICE_NUMBER"

    def test_create_invoice_with_negative_amount_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """
        Test invoice amount must be positive

        Expected: ValidationError
        """
        invoice_service = InvoiceService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number="FAC-NEG-001",
                invoice_type=InvoiceType.FACTURA,
                total_amount=Decimal("-50000.00"),  # Negative!
                user=admin_user
            )

        assert exc_info.value.code == "INVALID_AMOUNT"

    def test_create_invoice_with_zero_amount_fails(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """
        Test invoice amount must be greater than zero

        Expected: ValidationError
        """
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


class TestInvoiceRequiredForRouting:
    """Test BR-004: Invoice required before EN_RUTA transition"""

    def test_transition_to_en_ruta_without_invoice_fails(
        self,
        db_session,
        admin_user,
        sample_order_documentado_no_invoice,
        sample_route_active
    ):
        """
        CRITICAL TEST: Cannot transition to EN_RUTA without invoice

        Expected: InvoiceRequiredError or ValidationError
        """
        order_service = OrderService(db_session)

        # Order is DOCUMENTADO but has NO invoice (edge case)
        assert sample_order_documentado_no_invoice.order_status == OrderStatus.DOCUMENTADO
        assert sample_order_documentado_no_invoice.invoice is None

        with pytest.raises((InvoiceRequiredError, ValidationError)) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_documentado_no_invoice.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user,
                route_id=sample_route_active.id
            )

        # Verify error mentions invoice requirement
        error_message = str(exc_info.value.message).lower()
        assert "invoice" in error_message or "factura" in error_message

    def test_transition_to_en_ruta_with_invoice_succeeds(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice,
        sample_route_active
    ):
        """
        Test EN_RUTA transition succeeds when invoice exists

        Expected: Transition successful
        """
        order_service = OrderService(db_session)

        # Order has invoice
        assert sample_order_with_invoice.invoice is not None
        assert sample_order_with_invoice.order_status == OrderStatus.DOCUMENTADO

        # Transition should succeed
        updated_order = order_service.transition_order_state(
            order_id=sample_order_with_invoice.id,
            new_status=OrderStatus.EN_RUTA,
            user=admin_user,
            route_id=sample_route_active.id
        )

        assert updated_order.order_status == OrderStatus.EN_RUTA
        assert updated_order.assigned_route_id == sample_route_active.id

    def test_orders_without_invoice_excluded_from_routing(
        self,
        db_session,
        admin_user,
        sample_delivery_date
    ):
        """
        Test get_orders_for_delivery_date excludes orders without invoice

        Expected: Only orders with invoices returned
        """
        order_service = OrderService(db_session)

        # Get eligible orders for routing
        eligible_orders = order_service.get_orders_for_delivery_date(
            delivery_date=sample_delivery_date,
            user=admin_user
        )

        # All returned orders must have invoices
        for order in eligible_orders:
            assert order.invoice is not None, \
                f"Order {order.order_number} has no invoice but was returned for routing"


class TestInvoicePermissions:
    """Test invoice operation permissions (BR-015)"""

    def test_vendedor_can_create_invoice(
        self,
        db_session,
        vendedor_user,
        sample_order_en_preparacion
    ):
        """
        Test Vendedor can create invoices

        Expected: Success
        """
        invoice_service = InvoiceService(db_session)

        invoice = invoice_service.create_invoice(
            order_id=sample_order_en_preparacion.id,
            invoice_number="VEND-INV-001",
            invoice_type=InvoiceType.BOLETA,
            total_amount=Decimal("25000.00"),
            user=vendedor_user
        )

        assert invoice.created_by_user_id == vendedor_user.id

    def test_repartidor_cannot_create_invoice(
        self,
        db_session,
        repartidor_user,
        sample_order_en_preparacion
    ):
        """
        SECURITY TEST: Repartidor cannot create invoices

        Expected: InsufficientPermissionsError
        """
        invoice_service = InvoiceService(db_session)

        with pytest.raises(Exception) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_en_preparacion.id,
                invoice_number="REP-INV-001",
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("25000.00"),
                user=repartidor_user
            )

        # Should be permission error
        error_message = str(exc_info.value.message).lower()
        assert "permission" in error_message or "autorizado" in error_message

    def test_vendedor_can_only_view_own_invoices(
        self,
        db_session,
        vendedor_user,
        another_vendedor_user,
        invoice_created_by_another_vendedor
    ):
        """
        SECURITY TEST: Vendedor can only view invoices for own orders

        Expected: NotYourOrderError or InsufficientPermissionsError
        """
        invoice_service = InvoiceService(db_session)

        # Invoice was created by another_vendedor_user
        assert invoice_created_by_another_vendedor.order.created_by_user_id == another_vendedor_user.id

        with pytest.raises(Exception) as exc_info:
            invoice_service.get_invoice_by_id(
                invoice_id=invoice_created_by_another_vendedor.id,
                user=vendedor_user  # Different vendedor
            )

        # Should be permission/ownership error
        error_message = str(exc_info.value.message).lower()
        assert any(word in error_message for word in ["permission", "order", "own", "access"])


class TestInvoiceIdempotency:
    """Test idempotent behavior for invoice operations"""

    def test_auto_transition_is_idempotent(
        self,
        db_session,
        admin_user,
        sample_order_documentado_with_invoice
    ):
        """
        Test auto-transition doesn't fail if order already DOCUMENTADO

        Edge case: Order manually transitioned to DOCUMENTADO before invoice creation
        """
        invoice_service = InvoiceService(db_session)

        # Order is already DOCUMENTADO with invoice
        assert sample_order_documentado_with_invoice.order_status == OrderStatus.DOCUMENTADO

        # Attempting to create second invoice should fail (ORDER_ALREADY_HAS_INVOICE)
        with pytest.raises(ValidationError) as exc_info:
            invoice_service.create_invoice(
                order_id=sample_order_documentado_with_invoice.id,
                invoice_number="IDEMPOTENT-001",
                invoice_type=InvoiceType.BOLETA,
                total_amount=Decimal("30000.00"),
                user=admin_user
            )

        assert exc_info.value.code == "ORDER_ALREADY_HAS_INVOICE"
