"""
Tests for EmailService

Tests SMTP email sending functionality with mocked SMTP connections.
Uses unittest.mock to avoid actual email delivery during tests.

Test coverage:
- Email sending success
- SMTP authentication errors
- SMTP connection errors
- HTML + plain text multipart emails
- Connection testing
- Configuration validation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import smtplib
from app.services.email_service import (
    EmailService,
    SMTPConfigurationError,
    EmailServiceError
)


class TestEmailService:
    """Test suite for EmailService"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with valid SMTP configuration"""
        settings = Mock()
        settings.smtp_host = "smtp.gmail.com"
        settings.smtp_port = 587
        settings.smtp_user = "test@example.com"
        settings.smtp_password = "test_password"
        settings.smtp_from_email = "noreply@botilleria.cl"
        settings.smtp_from_name = "Botillería Test"
        settings.smtp_use_tls = True
        settings.smtp_timeout = 10
        settings.debug = False
        return settings

    @pytest.fixture
    def email_service(self, mock_settings):
        """Create EmailService with mocked settings"""
        with patch('app.services.email_service.get_settings', return_value=mock_settings):
            service = EmailService()
            return service

    def test_init_validates_config(self, mock_settings):
        """Test that __init__ validates SMTP configuration"""
        # Valid config should not raise
        with patch('app.services.email_service.get_settings', return_value=mock_settings):
            service = EmailService()
            assert service.settings == mock_settings

    def test_init_raises_on_missing_host(self, mock_settings):
        """Test that missing SMTP_HOST raises SMTPConfigurationError"""
        mock_settings.smtp_host = ""
        with patch('app.services.email_service.get_settings', return_value=mock_settings):
            with pytest.raises(SMTPConfigurationError) as exc_info:
                EmailService()
            assert "smtp_host" in str(exc_info.value).lower()

    def test_init_raises_on_missing_user(self, mock_settings):
        """Test that missing SMTP_USER raises SMTPConfigurationError"""
        mock_settings.smtp_user = ""
        with patch('app.services.email_service.get_settings', return_value=mock_settings):
            with pytest.raises(SMTPConfigurationError) as exc_info:
                EmailService()
            assert "smtp_user" in str(exc_info.value).lower()

    def test_init_raises_on_missing_password(self, mock_settings):
        """Test that missing SMTP_PASSWORD raises SMTPConfigurationError"""
        mock_settings.smtp_password = ""
        with patch('app.services.email_service.get_settings', return_value=mock_settings):
            with pytest.raises(SMTPConfigurationError) as exc_info:
                EmailService()
            assert "smtp_password" in str(exc_info.value).lower()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp_class, email_service):
        """Test successful email sending"""
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        # Send email
        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test Subject",
            html_body="<h1>Test HTML</h1>",
            plain_text_body="Test Plain Text"
        )

        # Assertions
        assert result is True
        mock_smtp_class.assert_called_once_with(
            email_service.settings.smtp_host,
            email_service.settings.smtp_port,
            timeout=email_service.settings.smtp_timeout
        )
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(
            email_service.settings.smtp_user,
            email_service.settings.smtp_password
        )
        mock_server.send_message.assert_called_once()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_without_plain_text(self, mock_smtp_class, email_service):
        """Test email sending with only HTML body"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test Subject",
            html_body="<h1>Test HTML</h1>"
        )

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_empty_recipient(self, mock_smtp_class, email_service):
        """Test that empty recipient email returns False"""
        result = email_service.send_email(
            to_email="",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False
        mock_smtp_class.assert_not_called()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_smtp_auth_error(self, mock_smtp_class, email_service):
        """Test SMTP authentication error handling"""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_smtp_recipients_refused(self, mock_smtp_class, email_service):
        """Test SMTP recipients refused error handling"""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPRecipientsRefused({})
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="invalid@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_connection_refused(self, mock_smtp_class, email_service):
        """Test connection refused error handling"""
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_timeout_error(self, mock_smtp_class, email_service):
        """Test timeout error handling"""
        mock_smtp_class.side_effect = TimeoutError("Connection timeout")

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_generic_smtp_exception(self, mock_smtp_class, email_service):
        """Test generic SMTP exception handling"""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException("Generic SMTP error")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_unexpected_exception(self, mock_smtp_class, email_service):
        """Test unexpected exception handling"""
        mock_server = MagicMock()
        mock_server.send_message.side_effect = RuntimeError("Unexpected error")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_test_connection_success(self, mock_smtp_class, email_service):
        """Test successful connection test"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.test_connection()

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_test_connection_failure(self, mock_smtp_class, email_service):
        """Test connection test failure"""
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        result = email_service.test_connection()

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_test_connection_auth_failure(self, mock_smtp_class, email_service):
        """Test connection test with auth failure"""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Bad auth")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.test_connection()

        assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_test_email(self, mock_smtp_class, email_service):
        """Test sending a test email"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_test_email("admin@example.com")

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_with_tls_disabled(self, mock_smtp_class, email_service):
        """Test email sending without TLS"""
        email_service.settings.smtp_use_tls = False
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_called_once()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_debug_mode(self, mock_smtp_class, email_service):
        """Test email sending in debug mode"""
        email_service.settings.debug = True
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = email_service.send_email(
            to_email="customer@example.com",
            subject="Test",
            html_body="<h1>Test</h1>"
        )

        assert result is True
        # In debug mode, set_debuglevel should be called
        mock_server.set_debuglevel.assert_called_once_with(1)
