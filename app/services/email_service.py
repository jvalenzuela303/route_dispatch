"""
Email Service for sending customer notifications via SMTP

This service provides email delivery functionality using Python's standard
smtplib library. It supports HTML emails with plain text fallbacks and
includes comprehensive error handling and logging.

Key features:
- SMTP configuration via environment variables
- HTML + plain text multipart emails
- Connection validation for health checks
- Comprehensive error handling
- Production-ready for Gmail, Outlook, and custom SMTP servers

Configuration:
    All SMTP settings are loaded from environment variables via Settings:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port (587 for TLS, 465 for SSL)
    - SMTP_USER: SMTP username (email address)
    - SMTP_PASSWORD: SMTP password or app-specific password
    - SMTP_FROM_EMAIL: From email address
    - SMTP_FROM_NAME: From display name
    - SMTP_USE_TLS: Use TLS encryption (True/False)
    - SMTP_TIMEOUT: Connection timeout in seconds

Usage:
    >>> email_service = EmailService()
    >>> success = email_service.send_email(
    ...     to_email="customer@example.com",
    ...     subject="Your order is on the way",
    ...     html_body="<h1>Order Update</h1>",
    ...     plain_text_body="Order Update"
    ... )
    >>> if success:
    ...     print("Email sent successfully")

Gmail Setup:
    For Gmail accounts with 2FA enabled:
    1. Go to Google Account > Security > 2-Step Verification
    2. Scroll to "App passwords"
    3. Generate new app password for "Mail"
    4. Use app password as SMTP_PASSWORD

Outlook/Microsoft Setup:
    - SMTP_HOST: smtp-mail.outlook.com
    - SMTP_PORT: 587
    - SMTP_USE_TLS: True
    - Use your Microsoft account email and password
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config.settings import get_settings

# Configure logger
logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors"""
    pass


class SMTPConfigurationError(EmailServiceError):
    """Raised when SMTP configuration is invalid or incomplete"""
    pass


class EmailDeliveryError(EmailServiceError):
    """Raised when email delivery fails"""
    pass


class EmailService:
    """
    Service for sending emails via SMTP

    Supports HTML emails with plain text fallback.
    Configured via environment variables for security.

    Attributes:
        settings: Application settings containing SMTP configuration

    Raises:
        SMTPConfigurationError: If SMTP configuration is incomplete
    """

    def __init__(self):
        """
        Initialize email service with SMTP configuration

        Raises:
            SMTPConfigurationError: If required SMTP settings are missing
        """
        self.settings = get_settings()
        self._validate_smtp_config()

    def _validate_smtp_config(self) -> None:
        """
        Validate that all required SMTP settings are configured

        Raises:
            SMTPConfigurationError: If any required setting is missing or empty

        Note:
            In development, you can set dummy values for testing.
            In production, all fields must be properly configured.
        """
        required_fields = {
            'smtp_host': self.settings.smtp_host,
            'smtp_port': self.settings.smtp_port,
            'smtp_user': self.settings.smtp_user,
            'smtp_password': self.settings.smtp_password,
            'smtp_from_email': self.settings.smtp_from_email,
        }

        missing_fields = [
            field for field, value in required_fields.items()
            if not value or (isinstance(value, str) and not value.strip())
        ]

        if missing_fields:
            raise SMTPConfigurationError(
                f"SMTP configuration incomplete. Missing or empty fields: {', '.join(missing_fields)}. "
                f"Please set these environment variables: {', '.join(f.upper() for f in missing_fields)}"
            )

        logger.info(
            f"SMTP configuration validated: {self.settings.smtp_host}:{self.settings.smtp_port} "
            f"(user: {self.settings.smtp_user})"
        )

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_text_body: Optional[str] = None
    ) -> bool:
        """
        Send email via SMTP

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_body: HTML content of the email
            plain_text_body: Plain text fallback (optional but recommended)

        Returns:
            bool: True if sent successfully, False if delivery failed

        Note:
            This method returns False instead of raising exceptions to allow
            the calling code to implement retry logic. Check logs for details.

        Example:
            >>> service = EmailService()
            >>> success = service.send_email(
            ...     to_email="customer@example.com",
            ...     subject="Order Update",
            ...     html_body="<p>Your order is ready</p>",
            ...     plain_text_body="Your order is ready"
            ... )
        """
        if not to_email or not to_email.strip():
            logger.error("Cannot send email: recipient email is empty")
            return False

        try:
            # Create multipart message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            msg['To'] = to_email

            # Attach plain text part (if provided)
            if plain_text_body:
                part_plain = MIMEText(plain_text_body, 'plain', 'utf-8')
                msg.attach(part_plain)

            # Attach HTML part
            part_html = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part_html)

            # Connect to SMTP server and send
            logger.info(f"Connecting to SMTP server {self.settings.smtp_host}:{self.settings.smtp_port}")

            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout
            ) as server:
                # Enable debug output in development
                if self.settings.debug:
                    server.set_debuglevel(1)

                # Upgrade to TLS if configured
                if self.settings.smtp_use_tls:
                    logger.debug("Initiating STARTTLS")
                    server.starttls()

                # Authenticate
                logger.debug(f"Authenticating as {self.settings.smtp_user}")
                server.login(self.settings.smtp_user, self.settings.smtp_password)

                # Send message
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email} (subject: '{subject}')")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                f"SMTP Authentication failed: {e}. "
                f"Check SMTP_USER and SMTP_PASSWORD. "
                f"For Gmail, use an app-specific password."
            )
            return False

        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient refused: {to_email}. Error: {e}")
            return False

        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected unexpectedly: {e}")
            return False

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error while sending email to {to_email}: {e}")
            return False

        except ConnectionRefusedError as e:
            logger.error(
                f"Connection refused by SMTP server {self.settings.smtp_host}:{self.settings.smtp_port}. "
                f"Check SMTP_HOST and SMTP_PORT settings. Error: {e}"
            )
            return False

        except TimeoutError as e:
            logger.error(
                f"SMTP connection timeout ({self.settings.smtp_timeout}s) "
                f"to {self.settings.smtp_host}:{self.settings.smtp_port}. Error: {e}"
            )
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {type(e).__name__}: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test SMTP connection without sending an email

        Useful for:
        - Health checks in production
        - Validating SMTP configuration during setup
        - Debugging connection issues

        Returns:
            bool: True if connection successful, False otherwise

        Example:
            >>> service = EmailService()
            >>> if service.test_connection():
            ...     print("SMTP connection successful")
            ... else:
            ...     print("SMTP connection failed - check logs")
        """
        try:
            logger.info(
                f"Testing SMTP connection to {self.settings.smtp_host}:{self.settings.smtp_port}"
            )

            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout
            ) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()

                server.login(self.settings.smtp_user, self.settings.smtp_password)

            logger.info("SMTP connection test successful")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed during connection test: {e}")
            return False

        except ConnectionRefusedError as e:
            logger.error(f"SMTP connection refused during test: {e}")
            return False

        except TimeoutError as e:
            logger.error(f"SMTP connection timeout during test: {e}")
            return False

        except Exception as e:
            logger.error(f"SMTP connection test failed: {type(e).__name__}: {e}")
            return False

    def send_test_email(self, to_email: str) -> bool:
        """
        Send a test email to verify configuration

        Useful for validating SMTP setup after configuration.

        Args:
            to_email: Email address to send test email to

        Returns:
            bool: True if test email sent successfully

        Example:
            >>> service = EmailService()
            >>> service.send_test_email("admin@example.com")
        """
        html_body = """
        <html>
        <body>
            <h2>SMTP Configuration Test</h2>
            <p>If you're reading this, your SMTP configuration is working correctly!</p>
            <p>Service: Claude Logistics Email Notification System</p>
            <p>Timestamp: <strong>{timestamp}</strong></p>
        </body>
        </html>
        """

        plain_body = """
        SMTP Configuration Test

        If you're reading this, your SMTP configuration is working correctly!

        Service: Claude Logistics Email Notification System
        """

        from datetime import datetime
        timestamp = datetime.utcnow().isoformat()
        html_body = html_body.format(timestamp=timestamp)

        return self.send_email(
            to_email=to_email,
            subject="[Test] SMTP Configuration Verification",
            html_body=html_body,
            plain_text_body=plain_body
        )
