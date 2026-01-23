"""
Tests for NotificationService

Tests notification orchestration, retry logic, and logging.
Uses mocked EmailService to avoid actual email delivery.

Test coverage:
- Successful notification sending
- Retry logic with exponential backoff
- All retries failed scenario
- Missing customer email handling
- Order not found handling
- Notification log creation and updates
- Notification history queries
- Failed notification queries
- Statistics generation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.notification_service import (
    NotificationService,
    OrderNotFoundError,
    MissingRecipientError
)
from app.models.models import Order, NotificationLog, User, Role
from app.models.enums import (
    NotificationStatus,
    NotificationChannel,
    OrderStatus,
    SourceChannel
)


class TestNotificationService:
    """Test suite for NotificationService"""

    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return MagicMock()

    @pytest.fixture
    def notification_service(self, db_session):
        """Create NotificationService with mocked dependencies"""
        with patch('app.services.notification_service.EmailService'):
            service = NotificationService(db_session)
            return service

    @pytest.fixture
    def mock_order(self):
        """Create a mock order with all required fields"""
        order = Mock(spec=Order)
        order.id = uuid4()
        order.order_number = "ORD-20260121-0001"
        order.customer_name = "Juan Pérez"
        order.customer_email = "juan.perez@example.com"
        order.customer_phone = "+56912345678"
        order.address_text = "Calle Falsa 123, Rancagua"
        order.delivery_date = datetime(2026, 1, 22).date()
        order.order_status = OrderStatus.EN_RUTA
        order.assigned_route = None
        return order

    @pytest.fixture
    def mock_notification_log(self, mock_order):
        """Create a mock notification log"""
        log = Mock(spec=NotificationLog)
        log.id = uuid4()
        log.order_id = mock_order.id
        log.channel = NotificationChannel.EMAIL
        log.recipient = mock_order.customer_email
        log.status = NotificationStatus.PENDING
        log.retry_count = 0
        log.sent_at = None
        log.error_message = None
        log.created_at = datetime.utcnow()
        return log

    def test_send_notification_success(
        self,
        notification_service,
        db_session,
        mock_order,
        mock_notification_log
    ):
        """Test successful notification sending on first attempt"""
        # Setup database mock
        db_session.query.return_value.filter.return_value.first.return_value = mock_order
        db_session.add.return_value = None
        db_session.commit.return_value = None
        db_session.refresh.return_value = None

        # Mock notification log creation
        notification_service.db.add = Mock(side_effect=lambda obj: setattr(obj, 'id', uuid4()))

        # Mock email service success
        with patch('app.services.notification_service.render_order_in_transit_email') as mock_render:
            mock_render.return_value = ("<html>Test</html>", "Test plain")
            notification_service.email_service.send_email = Mock(return_value=True)

            # Execute
            log = notification_service.send_order_in_transit_notification(mock_order.id)

            # Assertions
            notification_service.email_service.send_email.assert_called_once()
            assert db_session.commit.called

    def test_send_notification_order_not_found(self, notification_service, db_session):
        """Test that OrderNotFoundError is raised when order doesn't exist"""
        db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(OrderNotFoundError) as exc_info:
            notification_service.send_order_in_transit_notification(uuid4())

        assert "not found" in str(exc_info.value).lower()

    def test_send_notification_missing_email(
        self,
        notification_service,
        db_session,
        mock_order
    ):
        """Test that MissingRecipientError is raised when order has no email"""
        mock_order.customer_email = None
        db_session.query.return_value.filter.return_value.first.return_value = mock_order

        with pytest.raises(MissingRecipientError) as exc_info:
            notification_service.send_order_in_transit_notification(mock_order.id)

        assert "no customer email" in str(exc_info.value).lower()

    def test_send_notification_empty_email(
        self,
        notification_service,
        db_session,
        mock_order
    ):
        """Test that MissingRecipientError is raised when email is empty string"""
        mock_order.customer_email = "  "
        db_session.query.return_value.filter.return_value.first.return_value = mock_order

        with pytest.raises(MissingRecipientError) as exc_info:
            notification_service.send_order_in_transit_notification(mock_order.id)

        assert "no customer email" in str(exc_info.value).lower()

    @patch('app.services.notification_service.time.sleep')
    def test_send_notification_retry_success(
        self,
        mock_sleep,
        notification_service,
        db_session,
        mock_order
    ):
        """Test successful notification after retry"""
        db_session.query.return_value.filter.return_value.first.return_value = mock_order

        # Mock email service: fail first, succeed second
        with patch('app.services.notification_service.render_order_in_transit_email') as mock_render:
            mock_render.return_value = ("<html>Test</html>", "Test plain")
            notification_service.email_service.send_email = Mock(
                side_effect=[False, True]  # Fail first, succeed second
            )

            # Create a real NotificationLog for the test
            real_log = NotificationLog(
                order_id=mock_order.id,
                channel=NotificationChannel.EMAIL,
                recipient=mock_order.customer_email,
                status=NotificationStatus.PENDING
            )

            def mock_add(obj):
                if isinstance(obj, NotificationLog):
                    obj.id = uuid4()

            db_session.add = Mock(side_effect=mock_add)
            db_session.refresh = Mock(side_effect=lambda obj: setattr(obj, 'id', uuid4()) if not hasattr(obj, 'id') else None)

            # Execute
            log = notification_service.send_order_in_transit_notification(mock_order.id)

            # Assertions
            assert notification_service.email_service.send_email.call_count == 2
            mock_sleep.assert_called_once_with(2)  # 2^1 = 2 seconds

    @patch('app.services.notification_service.time.sleep')
    def test_send_notification_all_retries_failed(
        self,
        mock_sleep,
        notification_service,
        db_session,
        mock_order
    ):
        """Test notification failure after all retries exhausted"""
        db_session.query.return_value.filter.return_value.first.return_value = mock_order

        # Mock email service: always fail
        with patch('app.services.notification_service.render_order_in_transit_email') as mock_render:
            mock_render.return_value = ("<html>Test</html>", "Test plain")
            notification_service.email_service.send_email = Mock(return_value=False)

            # Create a real NotificationLog
            real_log = NotificationLog(
                order_id=mock_order.id,
                channel=NotificationChannel.EMAIL,
                recipient=mock_order.customer_email,
                status=NotificationStatus.PENDING
            )

            def mock_add(obj):
                if isinstance(obj, NotificationLog):
                    obj.id = uuid4()

            db_session.add = Mock(side_effect=mock_add)
            db_session.refresh = Mock(side_effect=lambda obj: setattr(obj, 'id', uuid4()) if not hasattr(obj, 'id') else None)

            # Execute
            log = notification_service.send_order_in_transit_notification(
                mock_order.id,
                max_retries=3
            )

            # Assertions
            assert notification_service.email_service.send_email.call_count == 3
            # Exponential backoff: 2^1=2s, 2^2=4s (no sleep after last attempt)
            assert mock_sleep.call_count == 2

    @patch('app.services.notification_service.time.sleep')
    def test_send_notification_exponential_backoff(
        self,
        mock_sleep,
        notification_service,
        db_session,
        mock_order
    ):
        """Test exponential backoff timing"""
        db_session.query.return_value.filter.return_value.first.return_value = mock_order

        with patch('app.services.notification_service.render_order_in_transit_email') as mock_render:
            mock_render.return_value = ("<html>Test</html>", "Test plain")
            notification_service.email_service.send_email = Mock(return_value=False)

            def mock_add(obj):
                if isinstance(obj, NotificationLog):
                    obj.id = uuid4()

            db_session.add = Mock(side_effect=mock_add)
            db_session.refresh = Mock(side_effect=lambda obj: setattr(obj, 'id', uuid4()) if not hasattr(obj, 'id') else None)

            # Execute with custom retry settings
            log = notification_service.send_order_in_transit_notification(
                mock_order.id,
                max_retries=3,
                retry_delay_base=2
            )

            # Verify exponential backoff: 2^1=2, 2^2=4
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2)  # First retry
            mock_sleep.assert_any_call(4)  # Second retry

    def test_get_notification_history(self, notification_service, db_session, mock_order):
        """Test retrieving notification history for an order"""
        # Mock query results
        mock_logs = [
            Mock(spec=NotificationLog, created_at=datetime.utcnow()),
            Mock(spec=NotificationLog, created_at=datetime.utcnow() - timedelta(hours=1))
        ]
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_logs

        # Execute
        logs = notification_service.get_notification_history(mock_order.id)

        # Assertions
        assert len(logs) == 2
        db_session.query.assert_called()

    def test_get_failed_notifications(self, notification_service, db_session):
        """Test retrieving failed notifications"""
        mock_logs = [Mock(spec=NotificationLog) for _ in range(3)]
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs

        # Execute
        logs = notification_service.get_failed_notifications(limit=50)

        # Assertions
        assert len(logs) == 3

    def test_get_failed_notifications_with_channel_filter(
        self,
        notification_service,
        db_session
    ):
        """Test retrieving failed notifications filtered by channel"""
        mock_logs = [Mock(spec=NotificationLog)]
        query_mock = db_session.query.return_value
        filter_mock = query_mock.filter.return_value
        filter_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_logs

        # Execute
        logs = notification_service.get_failed_notifications(
            channel=NotificationChannel.EMAIL
        )

        # Assertions
        assert len(logs) == 1

    def test_get_notification_stats(self, notification_service, db_session):
        """Test notification statistics generation"""
        # Mock logs with different statuses
        mock_logs = [
            Mock(status=NotificationStatus.SENT, retry_count=1, created_at=datetime.utcnow()),
            Mock(status=NotificationStatus.SENT, retry_count=0, created_at=datetime.utcnow()),
            Mock(status=NotificationStatus.FAILED, retry_count=3, created_at=datetime.utcnow()),
            Mock(status=NotificationStatus.PENDING, retry_count=0, created_at=datetime.utcnow()),
        ]
        db_session.query.return_value.filter.return_value.all.return_value = mock_logs

        # Execute
        stats = notification_service.get_notification_stats(days=7)

        # Assertions
        assert stats['total_notifications'] == 4
        assert stats['sent'] == 2
        assert stats['failed'] == 1
        assert stats['pending'] == 1
        assert stats['success_rate'] == 50.0
        assert stats['failure_rate'] == 25.0
        assert stats['avg_retry_count'] == 1.0  # (1+0+3+0)/4

    def test_get_notification_stats_empty(self, notification_service, db_session):
        """Test notification statistics with no logs"""
        db_session.query.return_value.filter.return_value.all.return_value = []

        # Execute
        stats = notification_service.get_notification_stats(days=7)

        # Assertions
        assert stats['total_notifications'] == 0
        assert stats['success_rate'] == 0
        assert stats['failure_rate'] == 0
        assert stats['avg_retry_count'] == 0
