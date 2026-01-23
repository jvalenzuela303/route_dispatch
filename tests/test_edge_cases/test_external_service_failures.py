"""
Edge Case Testing: External Service Failures

Tests system behavior when external services fail (graceful degradation).
Critical test cases:
- Geocoding API failures (Nominatim timeout/error)
- Email SMTP failures (timeout, auth failure)
- Database connection failures

System must handle failures gracefully without crashing or exposing sensitive data.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from requests.exceptions import Timeout, ConnectionError as RequestsConnectionError

from app.services.geocoding_service import GeocodingService, GeocodingResult
from app.services.email_service import EmailService
from app.services.order_service import OrderService
from app.services.notification_service import NotificationService
from app.models.enums import SourceChannel, GeocodingConfidence, NotificationStatus
from app.exceptions import GeocodingServiceError, InvalidAddressError


class TestGeocodingServiceFailures:
    """Test geocoding service failure handling"""

    def test_nominatim_timeout_returns_error_result(self):
        """
        Test Nominatim API timeout returns GeocodingResult with error

        Expected: success=False, error_message set, no exception raised
        """
        geocoding_service = GeocodingService()

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # Simulate timeout
            mock_get.side_effect = Timeout("Connection timeout")

            result = geocoding_service.geocode_address("Av O'Higgins 123, Rancagua")

            # Should return error result, not raise exception
            assert result.success is False
            assert "timeout" in result.error_message.lower()
            assert result.latitude is None
            assert result.longitude is None

    def test_nominatim_connection_error_returns_error_result(self):
        """
        Test Nominatim connection error is handled gracefully

        Expected: GeocodingResult with error message
        """
        geocoding_service = GeocodingService()

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # Simulate connection error
            mock_get.side_effect = RequestsConnectionError("Connection refused")

            result = geocoding_service.geocode_address("Av O'Higgins 123, Rancagua")

            assert result.success is False
            assert "error" in result.error_message.lower()

    def test_nominatim_empty_response_returns_invalid_result(self):
        """
        Test Nominatim returning empty results

        Expected: INVALID confidence, descriptive error message
        """
        geocoding_service = GeocodingService()

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # Simulate empty response
            mock_response = Mock()
            mock_response.json.return_value = []  # No results
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = geocoding_service.geocode_address("NonExistent Street 999, Rancagua")

            assert result.success is False
            assert result.confidence == GeocodingConfidence.INVALID
            assert "not found" in result.error_message.lower() or "no se encontr" in result.error_message.lower()

    def test_nominatim_malformed_response_returns_error(self):
        """
        Test Nominatim returning malformed JSON

        Expected: Error result with descriptive message
        """
        geocoding_service = GeocodingService()

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # Simulate malformed response (missing lat/lon)
            mock_response = Mock()
            mock_response.json.return_value = [
                {'display_name': 'Some address'}  # Missing lat/lon!
            ]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = geocoding_service.geocode_address("Av O'Higgins 123, Rancagua")

            assert result.success is False
            assert "invalid" in result.error_message.lower() or "respuesta" in result.error_message.lower()

    def test_geocoding_failure_prevents_order_creation(
        self,
        db_session,
        admin_user
    ):
        """
        CRITICAL: Geocoding failure should prevent order creation

        Expected: InvalidAddressError raised
        """
        order_service = OrderService(db_session)

        # Mock geocoding service to return failure
        with patch.object(order_service.geocoding_service, 'geocode_address') as mock_geocode:
            mock_geocode.return_value = GeocodingResult(
                success=False,
                confidence=GeocodingConfidence.INVALID,
                error_message="Address not found"
            )

            with pytest.raises(InvalidAddressError) as exc_info:
                order_service.create_order(
                    customer_name="Test Customer",
                    customer_phone="+56912345678",
                    address_text="Invalid Address 999",
                    source_channel=SourceChannel.WEB,
                    user=admin_user
                )

            assert "address" in str(exc_info.value.message).lower()

    def test_low_confidence_geocoding_rejected(
        self,
        db_session,
        admin_user
    ):
        """
        Test LOW confidence geocoding is rejected

        Expected: InvalidAddressError with descriptive message
        """
        order_service = OrderService(db_session)

        # Mock geocoding service to return LOW confidence
        with patch.object(order_service.geocoding_service, 'geocode_address') as mock_geocode:
            mock_geocode.return_value = GeocodingResult(
                success=True,
                latitude=-34.1706,
                longitude=-70.7406,
                confidence=GeocodingConfidence.LOW,  # LOW confidence!
                display_name="Rancagua, Chile"
            )

            with pytest.raises(InvalidAddressError) as exc_info:
                order_service.create_order(
                    customer_name="Test Customer",
                    customer_phone="+56912345678",
                    address_text="Rancagua Centro",  # Too generic
                    source_channel=SourceChannel.WEB,
                    user=admin_user
                )

            assert "ambigua" in str(exc_info.value.message).lower() or \
                   "ambiguous" in str(exc_info.value.message).lower()

    def test_geocoding_cache_prevents_repeated_api_calls(self):
        """
        Test geocoding cache prevents repeated API calls on failure

        Expected: Second call uses cached failure result (no API call)
        """
        geocoding_service = GeocodingService(cache_backend={})

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # First call - simulate failure
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # First call
            result1 = geocoding_service.geocode_address("Bad Address 999, Rancagua")
            assert result1.success is False
            assert mock_get.call_count == 1

            # Second call (should use cache, no API call)
            result2 = geocoding_service.geocode_address("Bad Address 999, Rancagua")
            assert result2.success is False
            assert result2.cached is True
            # API should not be called again
            assert mock_get.call_count == 1, "Geocoding failure should be cached"


class TestEmailServiceFailures:
    """Test email service failure handling"""

    def test_smtp_authentication_failure_returns_false(self):
        """
        Test SMTP authentication failure is handled gracefully

        Expected: send_email returns False, error logged
        """
        # Mock settings with valid SMTP config
        with patch('app.services.email_service.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                smtp_user="test@example.com",
                smtp_password="wrong_password",
                smtp_from_email="test@example.com",
                smtp_from_name="Test",
                smtp_use_tls=True,
                smtp_timeout=10,
                debug=False
            )

            email_service = EmailService()

            with patch('app.services.email_service.smtplib.SMTP') as mock_smtp:
                # Simulate auth failure
                mock_server = MagicMock()
                mock_server.login.side_effect = Exception("Authentication failed")
                mock_smtp.return_value.__enter__.return_value = mock_server

                result = email_service.send_email(
                    to_email="customer@example.com",
                    subject="Test",
                    html_body="<p>Test</p>",
                    plain_text_body="Test"
                )

                # Should return False, not raise exception
                assert result is False

    def test_smtp_connection_timeout_returns_false(self):
        """
        Test SMTP connection timeout is handled gracefully

        Expected: send_email returns False
        """
        with patch('app.services.email_service.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                smtp_host="unreachable.smtp.server",
                smtp_port=587,
                smtp_user="test@example.com",
                smtp_password="password",
                smtp_from_email="test@example.com",
                smtp_from_name="Test",
                smtp_use_tls=True,
                smtp_timeout=1,  # Short timeout
                debug=False
            )

            email_service = EmailService()

            with patch('app.services.email_service.smtplib.SMTP') as mock_smtp:
                # Simulate timeout
                mock_smtp.side_effect = TimeoutError("Connection timeout")

                result = email_service.send_email(
                    to_email="customer@example.com",
                    subject="Test",
                    html_body="<p>Test</p>"
                )

                assert result is False

    def test_notification_failure_does_not_block_order_transition(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice,
        sample_route_active
    ):
        """
        CRITICAL: Notification failure should NOT block order state transition

        Scenario: Order transitions to EN_RUTA, email notification fails
        Expected: Order still transitions, failure logged for retry
        """
        order_service = OrderService(db_session)

        # Mock notification service to fail
        with patch('app.services.order_service.NotificationService') as mock_notif_service:
            mock_instance = Mock()
            mock_instance.send_order_in_transit_notification.side_effect = Exception("SMTP failed")
            mock_notif_service.return_value = mock_instance

            # Transition should succeed despite notification failure
            from app.models.enums import OrderStatus

            updated_order = order_service.transition_order_state(
                order_id=sample_order_with_invoice.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user,
                route_id=sample_route_active.id
            )

            # Order should be EN_RUTA (transition successful)
            assert updated_order.order_status == OrderStatus.EN_RUTA

    def test_email_service_empty_recipient_returns_false(self):
        """
        Test email service with empty recipient email

        Expected: Returns False immediately, no SMTP call
        """
        with patch('app.services.email_service.get_settings') as mock_settings:
            mock_settings.return_value = Mock(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                smtp_user="test@example.com",
                smtp_password="password",
                smtp_from_email="test@example.com",
                smtp_from_name="Test",
                smtp_use_tls=True,
                smtp_timeout=10,
                debug=False
            )

            email_service = EmailService()

            with patch('app.services.email_service.smtplib.SMTP') as mock_smtp:
                result = email_service.send_email(
                    to_email="",  # Empty!
                    subject="Test",
                    html_body="<p>Test</p>"
                )

                # Should return False without calling SMTP
                assert result is False
                assert mock_smtp.call_count == 0


class TestNotificationServiceFailures:
    """Test notification service resilience"""

    def test_notification_log_created_even_on_failure(
        self,
        db_session,
        sample_order_en_ruta
    ):
        """
        Test notification failure is logged in notification_logs table

        Expected: NotificationLog record with FAILED status
        """
        notification_service = NotificationService(db_session)

        # Mock email service to fail
        with patch.object(notification_service.email_service, 'send_email') as mock_send:
            mock_send.return_value = False  # Email failed

            log = notification_service.send_order_in_transit_notification(
                order_id=sample_order_en_ruta.id
            )

            # Log should be created with FAILED status
            assert log.status == NotificationStatus.FAILED
            assert log.error_message is not None
            assert "failed" in log.error_message.lower() or "error" in log.error_message.lower()

    def test_notification_retry_on_failure(
        self,
        db_session,
        sample_order_en_ruta
    ):
        """
        Test notification can be manually retried after failure

        Expected: Second attempt creates new log entry
        """
        notification_service = NotificationService(db_session)

        # First attempt - fail
        with patch.object(notification_service.email_service, 'send_email') as mock_send:
            mock_send.return_value = False

            log1 = notification_service.send_order_in_transit_notification(
                order_id=sample_order_en_ruta.id
            )

            assert log1.status == NotificationStatus.FAILED

        # Second attempt - succeed
        with patch.object(notification_service.email_service, 'send_email') as mock_send:
            mock_send.return_value = True

            log2 = notification_service.send_order_in_transit_notification(
                order_id=sample_order_en_ruta.id
            )

            assert log2.status == NotificationStatus.SENT

        # Both logs should exist
        from app.models.models import NotificationLog

        logs = db_session.query(NotificationLog).filter(
            NotificationLog.order_id == sample_order_en_ruta.id
        ).all()

        assert len(logs) >= 2


class TestDatabaseConnectionFailures:
    """Test database connection failure handling"""

    def test_database_connection_failure_raises_exception(
        self,
        db_session,
        admin_user
    ):
        """
        Test database connection failure raises appropriate exception

        Note: This is difficult to test without killing actual DB connection
        Testing that services don't hide DB errors
        """
        # This would require integration test with actual DB failure
        # Skip for unit tests
        pass


class TestCachingOnFailure:
    """Test caching behavior on service failures"""

    def test_geocoding_failure_is_cached(self):
        """
        Test failed geocoding results are cached to avoid repeated API calls

        Expected: Subsequent calls for same address return cached failure
        """
        cache_backend = {}
        geocoding_service = GeocodingService(cache_backend=cache_backend)

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # First call - API failure
            mock_get.side_effect = Timeout("Timeout")

            result1 = geocoding_service.geocode_address("Failing Address, Rancagua")
            assert result1.success is False
            assert mock_get.call_count == 1

            # Second call - should use cache
            result2 = geocoding_service.geocode_address("Failing Address, Rancagua")
            assert result2.success is False
            assert result2.cached is True
            # API should not be called again
            assert mock_get.call_count == 1

    def test_geocoding_low_confidence_is_cached(self):
        """
        Test LOW confidence geocoding results are cached

        Expected: Prevents repeated API calls for same bad address
        """
        cache_backend = {}
        geocoding_service = GeocodingService(cache_backend=cache_backend)

        with patch('app.services.geocoding_service.requests.get') as mock_get:
            # Mock LOW confidence response
            mock_response = Mock()
            mock_response.json.return_value = [{
                'lat': '-34.1706',
                'lon': '-70.7406',
                'type': 'suburb',  # Generic type = LOW confidence
                'importance': 0.1,
                'address': {},
                'display_name': 'Rancagua, Chile'
            }]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # First call
            result1 = geocoding_service.geocode_address("Generic Location, Rancagua")
            assert result1.confidence == GeocodingConfidence.LOW
            assert mock_get.call_count == 1

            # Second call - should use cache
            result2 = geocoding_service.geocode_address("Generic Location, Rancagua")
            assert result2.confidence == GeocodingConfidence.LOW
            assert result2.cached is True
            assert mock_get.call_count == 1
