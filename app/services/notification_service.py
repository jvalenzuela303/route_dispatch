"""
Notification Service for managing customer communications

This service orchestrates customer notifications across multiple channels
(currently Email, with SMS/WhatsApp/Push planned for future).

Key features:
- Multi-channel support (EMAIL, SMS, WhatsApp, Push)
- Retry logic with exponential backoff
- Comprehensive logging in notification_logs table
- Graceful error handling (notifications are "best effort")
- Extensible architecture for future channels

Business value:
- Reduce customer anxiety about order status
- Improve customer satisfaction with timely updates
- Reduce support calls by proactively communicating status
- Build trust through transparent communication

Architecture:
    NotificationService (orchestrator)
    └── EmailService (channel implementation)
    └── SMSService (future)
    └── WhatsAppService (future)
    └── PushService (future)

Usage:
    >>> from app.services.notification_service import NotificationService
    >>> notification_service = NotificationService(db_session)
    >>> log = notification_service.send_order_in_transit_notification(order_id)
    >>> print(f"Notification status: {log.status}")
"""

import time
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.email_service import EmailService, EmailServiceError
from app.models.models import Order, NotificationLog
from app.models.enums import NotificationStatus, NotificationChannel
from app.templates.email_templates import render_order_in_transit_email

# Configure logger
logger = logging.getLogger(__name__)


class NotificationServiceError(Exception):
    """Base exception for notification service errors"""
    pass


class OrderNotFoundError(NotificationServiceError):
    """Raised when order is not found in database"""
    pass


class MissingRecipientError(NotificationServiceError):
    """Raised when order has no customer email/phone"""
    pass


class NotificationService:
    """
    Service for managing customer notifications

    Handles sending notifications via multiple channels (currently Email only)
    with retry logic and comprehensive logging in notification_logs table.

    Attributes:
        db: SQLAlchemy database session
        email_service: Email delivery service

    Example:
        >>> notification_service = NotificationService(db_session)
        >>> log = notification_service.send_order_in_transit_notification(order.id)
        >>> if log.status == NotificationStatus.SENT:
        ...     print("Notification sent successfully")
    """

    def __init__(self, db: Session):
        """
        Initialize notification service

        Args:
            db: SQLAlchemy database session for logging and order queries
        """
        self.db = db
        self.email_service = EmailService()

    def send_order_in_transit_notification(
        self,
        order_id: UUID,
        max_retries: int = 3,
        retry_delay_base: int = 2
    ) -> NotificationLog:
        """
        Send notification when order transitions to EN_RUTA status

        This is the primary notification method triggered when an order
        starts its delivery journey. It:
        1. Fetches order details from database
        2. Validates customer has email address
        3. Creates notification log entry
        4. Attempts to send email with retry logic
        5. Updates log with final status

        Args:
            order_id: UUID of the order
            max_retries: Maximum retry attempts (default 3)
            retry_delay_base: Base delay for exponential backoff in seconds (default 2)

        Returns:
            NotificationLog: Log record of notification attempt with final status

        Raises:
            OrderNotFoundError: If order doesn't exist in database
            MissingRecipientError: If order has no customer_email

        Example:
            >>> log = service.send_order_in_transit_notification(order_id)
            >>> if log.status == NotificationStatus.SENT:
            ...     print(f"Email sent at {log.sent_at}")
            >>> elif log.status == NotificationStatus.FAILED:
            ...     print(f"Failed: {log.error_message}")

        Retry Logic:
            - Retry 1: Wait 2^1 = 2 seconds
            - Retry 2: Wait 2^2 = 4 seconds
            - Retry 3: Wait 2^3 = 8 seconds
            Total time: ~14 seconds before final failure
        """
        logger.info(f"Initiating in-transit notification for order {order_id}")

        # Fetch order with relationships (for driver name in template)
        order = self.db.query(Order).filter(Order.id == order_id).first()

        if not order:
            error_msg = f"Order {order_id} not found"
            logger.error(error_msg)
            raise OrderNotFoundError(error_msg)

        # Validate order has customer email
        if not order.customer_email or not order.customer_email.strip():
            error_msg = f"Order {order_id} has no customer email"
            logger.error(error_msg)
            raise MissingRecipientError(error_msg)

        logger.info(
            f"Order {order.order_number}: Sending notification to {order.customer_email} "
            f"via {NotificationChannel.EMAIL.value}"
        )

        # Create notification log (initial status: PENDING)
        log = NotificationLog(
            order_id=order_id,
            channel=NotificationChannel.EMAIL,
            recipient=order.customer_email,
            status=NotificationStatus.PENDING,
            retry_count=0
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        logger.debug(f"Created notification log {log.id} for order {order.order_number}")

        # Attempt to send with retry logic
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                # Increment retry counter
                log.retry_count = attempt + 1
                self.db.commit()

                logger.info(
                    f"Notification {log.id}: Attempt {attempt + 1}/{max_retries} "
                    f"for order {order.order_number}"
                )

                # Render email template
                html_body, plain_body = render_order_in_transit_email(order)

                # Send email
                success = self.email_service.send_email(
                    to_email=order.customer_email,
                    subject=f"Tu pedido #{order.order_number} está en camino 🚚",
                    html_body=html_body,
                    plain_text_body=plain_body
                )

                if success:
                    # Update log to SENT
                    log.status = NotificationStatus.SENT
                    log.sent_at = datetime.utcnow()
                    self.db.commit()

                    logger.info(
                        f"Notification {log.id} sent successfully to {order.customer_email} "
                        f"(order {order.order_number})"
                    )
                    return log
                else:
                    last_error = "Email service returned False - check email service logs"
                    logger.warning(
                        f"Notification {log.id}: Send attempt {attempt + 1} failed - {last_error}"
                    )

            except EmailServiceError as e:
                last_error = f"EmailServiceError: {str(e)}"
                logger.warning(
                    f"Notification {log.id}: Send attempt {attempt + 1} failed - {last_error}"
                )

            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                logger.error(
                    f"Notification {log.id}: Unexpected error on attempt {attempt + 1} - {last_error}",
                    exc_info=True
                )

            # Increment attempt counter
            attempt += 1

            # Retry with exponential backoff (if not last attempt)
            if attempt < max_retries:
                wait_time = retry_delay_base ** attempt  # 2s, 4s, 8s
                logger.info(
                    f"Notification {log.id}: Waiting {wait_time}s before retry "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)

        # All retries failed
        error_message = (
            f"Failed to send notification after {max_retries} attempts. "
            f"Last error: {last_error}"
        )

        log.status = NotificationStatus.FAILED
        log.error_message = error_message
        self.db.commit()

        logger.error(
            f"Notification {log.id} failed permanently for order {order.order_number}: "
            f"{error_message}"
        )

        return log

    def resend_failed_notification(self, notification_log_id: UUID) -> NotificationLog:
        """
        Retry sending a previously failed notification

        Useful for manual intervention when notifications fail due to
        temporary issues (e.g., SMTP server down, network issues).

        Args:
            notification_log_id: UUID of the notification log to retry

        Returns:
            NotificationLog: Updated log with new status

        Raises:
            NotificationServiceError: If log not found or not in FAILED status

        Example:
            >>> # Find failed notifications
            >>> failed_logs = db.query(NotificationLog).filter(
            ...     NotificationLog.status == NotificationStatus.FAILED
            ... ).all()
            >>> # Retry specific notification
            >>> log = service.resend_failed_notification(failed_logs[0].id)
        """
        log = self.db.query(NotificationLog).filter(
            NotificationLog.id == notification_log_id
        ).first()

        if not log:
            raise NotificationServiceError(f"Notification log {notification_log_id} not found")

        if log.status != NotificationStatus.FAILED:
            raise NotificationServiceError(
                f"Cannot resend notification {notification_log_id}: status is {log.status.value}, "
                f"expected FAILED"
            )

        logger.info(f"Manually retrying failed notification {log.id} for order {log.order_id}")

        # Reset status and retry
        return self.send_order_in_transit_notification(log.order_id)

    def get_notification_history(self, order_id: UUID) -> list[NotificationLog]:
        """
        Get all notification logs for an order

        Useful for customer service to verify what communications
        were sent to a customer and when.

        Args:
            order_id: UUID of the order

        Returns:
            List[NotificationLog]: All notification logs for the order,
                                   ordered by creation time (newest first)

        Example:
            >>> logs = service.get_notification_history(order.id)
            >>> for log in logs:
            ...     print(f"{log.created_at}: {log.channel} - {log.status}")
        """
        logs = self.db.query(NotificationLog).filter(
            NotificationLog.order_id == order_id
        ).order_by(NotificationLog.created_at.desc()).all()

        logger.debug(f"Retrieved {len(logs)} notification logs for order {order_id}")

        return logs

    def get_failed_notifications(
        self,
        limit: int = 100,
        channel: Optional[NotificationChannel] = None
    ) -> list[NotificationLog]:
        """
        Get recently failed notifications for monitoring/alerting

        Useful for:
        - Operations dashboard showing notification failures
        - Automated alerts when failure rate exceeds threshold
        - Manual retry workflows

        Args:
            limit: Maximum number of records to return (default 100)
            channel: Filter by channel (optional)

        Returns:
            List[NotificationLog]: Failed notifications ordered by creation time

        Example:
            >>> # Get all recent failures
            >>> failures = service.get_failed_notifications(limit=50)
            >>> # Get email failures only
            >>> email_failures = service.get_failed_notifications(
            ...     channel=NotificationChannel.EMAIL
            ... )
        """
        query = self.db.query(NotificationLog).filter(
            NotificationLog.status == NotificationStatus.FAILED
        )

        if channel:
            query = query.filter(NotificationLog.channel == channel)

        logs = query.order_by(
            NotificationLog.created_at.desc()
        ).limit(limit).all()

        logger.info(
            f"Retrieved {len(logs)} failed notifications "
            f"(channel: {channel.value if channel else 'all'})"
        )

        return logs

    def get_notification_stats(self, days: int = 7) -> dict:
        """
        Get notification statistics for monitoring

        Provides metrics for:
        - Total notifications sent
        - Success rate by channel
        - Failure analysis
        - Average retry count

        Args:
            days: Number of days to analyze (default 7)

        Returns:
            dict: Statistics summary

        Example:
            >>> stats = service.get_notification_stats(days=30)
            >>> print(f"Success rate: {stats['success_rate']}%")
            >>> print(f"Total sent: {stats['total_sent']}")
        """
        from datetime import timedelta
        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(NotificationLog).filter(
            NotificationLog.created_at >= cutoff_date
        ).all()

        total = len(logs)
        sent = sum(1 for log in logs if log.status == NotificationStatus.SENT)
        failed = sum(1 for log in logs if log.status == NotificationStatus.FAILED)
        pending = sum(1 for log in logs if log.status == NotificationStatus.PENDING)

        stats = {
            'period_days': days,
            'total_notifications': total,
            'sent': sent,
            'failed': failed,
            'pending': pending,
            'success_rate': round((sent / total * 100) if total > 0 else 0, 2),
            'failure_rate': round((failed / total * 100) if total > 0 else 0, 2),
            'avg_retry_count': round(
                sum(log.retry_count for log in logs) / total if total > 0 else 0,
                2
            )
        }

        logger.info(f"Notification stats (last {days} days): {stats}")

        return stats
