"""
Integration tests for Order -> Notification workflow

Tests the complete integration between OrderService and NotificationService
to verify that notifications are triggered correctly when orders transition
to EN_RUTA status.

Test scenarios:
- Order transition to EN_RUTA triggers notification
- Notification failure doesn't block order state transition
- Notification success is logged in audit trail
- Notification failure is logged in audit trail
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime

from app.services.order_service import OrderService
from app.services.notification_service import NotificationService
from app.models.models import Order, User, Role, NotificationLog
from app.models.enums import (
    OrderStatus,
    SourceChannel,
    NotificationStatus,
    NotificationChannel,
    AuditResult
)


class TestOrderNotificationIntegration:
    """Integration tests for order state transitions triggering notifications"""

    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_user(self):
        """Create mock user with proper role"""
        user = Mock(spec=User)
        user.id = uuid4()
        user.username = "test_user"
        user.email = "test@example.com"

        role = Mock(spec=Role)
        role.role_name = "Encargado de Bodega"
        role.permissions = {
            "transition_to_EN_RUTA": True,
            "manage_routes": True
        }

        user.role = role
        return user

    @pytest.fixture
    def mock_order_documentado(self):
        """Create mock order in DOCUMENTADO status ready for EN_RUTA"""
        order = Mock(spec=Order)
        order.id = uuid4()
        order.order_number = "ORD-20260121-0001"
        order.customer_name = "Juan Pérez"
        order.customer_email = "juan.perez@example.com"
        order.customer_phone = "+56912345678"
        order.address_text = "Calle Falsa 123, Rancagua"
        order.delivery_date = datetime(2026, 1, 22).date()
        order.order_status = OrderStatus.DOCUMENTADO
        order.assigned_route_id = None
        order.assigned_route = None
        order.invoice_id = uuid4()  # Has invoice - can transition to EN_RUTA
        return order

    @pytest.fixture
    def order_service(self, db_session):
        """Create OrderService with mocked dependencies"""
        with patch('app.services.order_service.GeocodingService'), \
             patch('app.services.order_service.AuditService'), \
             patch('app.services.order_service.PermissionService'), \
             patch('app.services.order_service.InvoiceService'), \
             patch('app.services.order_service.CutoffService'):

            service = OrderService(db_session)
            return service

    @patch('app.services.order_service.NotificationService')
    def test_order_en_ruta_triggers_notification(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that transitioning order to EN_RUTA triggers notification"""
        # Setup database mock
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        # Mock notification service
        mock_notification_instance = MagicMock()
        mock_log = Mock(spec=NotificationLog)
        mock_log.id = uuid4()
        mock_log.status = NotificationStatus.SENT
        mock_log.channel = NotificationChannel.EMAIL
        mock_log.recipient = mock_order_documentado.customer_email
        mock_notification_instance.send_order_in_transit_notification.return_value = mock_log
        mock_notification_service_class.return_value = mock_notification_instance

        # Mock permission service
        order_service.permission_service.require_permission = Mock()

        # Execute transition
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Assertions
        # 1. Order status was updated
        assert mock_order_documentado.order_status == OrderStatus.EN_RUTA

        # 2. Notification service was called
        mock_notification_instance.send_order_in_transit_notification.assert_called_once_with(
            mock_order_documentado.id
        )

        # 3. Audit service logged notification success
        order_service.audit_service.log_action.assert_called()

    @patch('app.services.order_service.NotificationService')
    def test_notification_failure_doesnt_block_transition(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that notification failure doesn't prevent order state transition"""
        # Setup database mock
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        # Mock notification service to raise exception
        mock_notification_instance = MagicMock()
        mock_notification_instance.send_order_in_transit_notification.side_effect = Exception(
            "SMTP server unavailable"
        )
        mock_notification_service_class.return_value = mock_notification_instance

        # Mock permission service
        order_service.permission_service.require_permission = Mock()

        # Execute transition
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Assertions
        # 1. Order status WAS updated despite notification failure
        assert mock_order_documentado.order_status == OrderStatus.EN_RUTA

        # 2. Notification was attempted
        mock_notification_instance.send_order_in_transit_notification.assert_called_once()

        # 3. Audit service logged the error
        audit_calls = [call for call in order_service.audit_service.log_action.call_args_list]
        error_logged = any(
            call[1].get('action') == 'NOTIFICATION_ERROR'
            for call in audit_calls
        )
        assert error_logged

    @patch('app.services.order_service.NotificationService')
    def test_notification_success_logged_in_audit(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that successful notification is logged in audit trail"""
        # Setup
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        mock_notification_instance = MagicMock()
        mock_log = Mock(spec=NotificationLog)
        mock_log.id = uuid4()
        mock_log.status = NotificationStatus.SENT
        mock_log.channel = NotificationChannel.EMAIL
        mock_log.recipient = mock_order_documentado.customer_email
        mock_notification_instance.send_order_in_transit_notification.return_value = mock_log
        mock_notification_service_class.return_value = mock_notification_instance

        order_service.permission_service.require_permission = Mock()

        # Execute
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Verify audit log was called with correct parameters
        audit_calls = order_service.audit_service.log_action.call_args_list
        notification_success_logged = any(
            call[1].get('action') == 'NOTIFICATION_SENT' and
            call[1].get('result') == AuditResult.SUCCESS
            for call in audit_calls
        )
        assert notification_success_logged

    @patch('app.services.order_service.NotificationService')
    def test_notification_failed_status_logged_in_audit(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that failed notification (after retries) is logged in audit trail"""
        # Setup
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        mock_notification_instance = MagicMock()
        mock_log = Mock(spec=NotificationLog)
        mock_log.id = uuid4()
        mock_log.status = NotificationStatus.FAILED
        mock_log.channel = NotificationChannel.EMAIL
        mock_log.recipient = mock_order_documentado.customer_email
        mock_log.error_message = "Failed after 3 retries: SMTP timeout"
        mock_notification_instance.send_order_in_transit_notification.return_value = mock_log
        mock_notification_service_class.return_value = mock_notification_instance

        order_service.permission_service.require_permission = Mock()

        # Execute
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Verify audit log recorded the failure
        audit_calls = order_service.audit_service.log_action.call_args_list
        notification_failure_logged = any(
            call[1].get('action') == 'NOTIFICATION_FAILED' and
            call[1].get('result') == AuditResult.ERROR
            for call in audit_calls
        )
        assert notification_failure_logged

    @patch('app.services.order_service.NotificationService')
    def test_order_without_email_still_transitions(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that order without email can still transition (notification fails gracefully)"""
        # Setup order without email
        mock_order_documentado.customer_email = None
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        # Mock notification service to raise MissingRecipientError
        from app.services.notification_service import MissingRecipientError
        mock_notification_instance = MagicMock()
        mock_notification_instance.send_order_in_transit_notification.side_effect = MissingRecipientError(
            "Order has no customer email"
        )
        mock_notification_service_class.return_value = mock_notification_instance

        order_service.permission_service.require_permission = Mock()

        # Execute
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Assertions
        # 1. Order status WAS updated despite missing email
        assert mock_order_documentado.order_status == OrderStatus.EN_RUTA

        # 2. Error was logged in audit
        audit_calls = order_service.audit_service.log_action.call_args_list
        error_logged = any(
            call[1].get('action') == 'NOTIFICATION_ERROR'
            for call in audit_calls
        )
        assert error_logged

    @patch('app.services.order_service.NotificationService')
    def test_idempotent_transition_doesnt_retrigger_notification(
        self,
        mock_notification_service_class,
        order_service,
        db_session,
        mock_user,
        mock_order_documentado
    ):
        """Test that idempotent transition (already in target state) doesn't retrigger notification"""
        # Setup order already in EN_RUTA
        mock_order_documentado.order_status = OrderStatus.EN_RUTA
        db_session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = mock_order_documentado

        mock_notification_instance = MagicMock()
        mock_notification_service_class.return_value = mock_notification_instance

        order_service.permission_service.require_permission = Mock()

        # Execute
        route_id = uuid4()
        result = order_service.transition_order_state(
            order_id=mock_order_documentado.id,
            new_status=OrderStatus.EN_RUTA,
            user=mock_user,
            route_id=route_id
        )

        # Assertions
        # Notification service should NOT be called (idempotent no-op)
        mock_notification_instance.send_order_in_transit_notification.assert_not_called()
