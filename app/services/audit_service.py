"""
Audit logging service for compliance and security tracking

Implements business rule BR-018 for mandatory audit logging of all critical actions.
All state transitions, permission denials, and business rule overrides must be logged.

Audit logs are immutable and retained for 5+ years per Chilean tax requirements.
"""

import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.models import User, AuditLog
from app.models.enums import AuditResult, OrderStatus


class AuditService:
    """
    Centralized audit logging service

    All critical system actions must be logged through this service.
    Logs are written synchronously to ensure data integrity.
    """

    TIMEZONE = ZoneInfo("America/Santiago")

    def __init__(self, db: Session):
        """
        Initialize audit service

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def log_action(
        self,
        action: str,
        entity_type: str,
        result: AuditResult,
        user: Optional[User] = None,
        entity_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Create audit log entry

        Args:
            action: Action name (e.g., 'CREATE_ORDER', 'TRANSITION_STATE')
            entity_type: Type of entity (ORDER, INVOICE, ROUTE, USER)
            result: Action result (SUCCESS, DENIED, ERROR)
            user: User performing action (None for system actions)
            entity_id: UUID of affected entity
            details: JSONB with action-specific context
            ip_address: IP address of client request

        Returns:
            AuditLog: Created audit log entry
        """
        audit_log = AuditLog(
            id=uuid.uuid4(),
            timestamp=datetime.now(self.TIMEZONE),
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            result=result,
            ip_address=ip_address
        )

        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)

        return audit_log

    def log_state_transition(
        self,
        order_id: uuid.UUID,
        order_number: str,
        from_status: OrderStatus,
        to_status: OrderStatus,
        user: User,
        result: AuditResult,
        additional_details: Optional[dict] = None
    ) -> AuditLog:
        """
        Log order state transition

        Args:
            order_id: Order UUID
            order_number: Order number for reference
            from_status: Previous status
            to_status: New status
            user: User executing transition
            result: Transition result
            additional_details: Extra context (e.g., incidence_reason)

        Returns:
            AuditLog: Created audit log entry
        """
        details = {
            'order_number': order_number,
            'previous_status': from_status.value,
            'new_status': to_status.value
        }

        if additional_details:
            details.update(additional_details)

        action_name = f'TRANSITION_{to_status.value}'

        return self.log_action(
            action=action_name,
            entity_type='ORDER',
            entity_id=order_id,
            user=user,
            result=result,
            details=details
        )

    def log_override_attempt(
        self,
        action: str,
        user: User,
        reason: str,
        result: AuditResult,
        entity_type: str = 'ORDER',
        entity_id: Optional[uuid.UUID] = None,
        additional_details: Optional[dict] = None
    ) -> AuditLog:
        """
        Log admin override attempt

        Args:
            action: Override action (e.g., 'OVERRIDE_CUTOFF_TIME')
            user: User attempting override
            reason: Justification for override
            result: Override result (SUCCESS or DENIED)
            entity_type: Type of entity
            entity_id: Entity UUID
            additional_details: Extra context

        Returns:
            AuditLog: Created audit log entry
        """
        details = {
            'override_reason': reason,
            'user_role': user.role.role_name
        }

        if additional_details:
            details.update(additional_details)

        return self.log_action(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user=user,
            result=result,
            details=details
        )

    def log_permission_denial(
        self,
        action: str,
        user: User,
        entity_type: str,
        entity_id: Optional[uuid.UUID],
        denial_reason: str,
        required_role: Optional[str] = None
    ) -> AuditLog:
        """
        Log permission denial

        Args:
            action: Action that was denied
            user: User who was denied
            entity_type: Type of entity
            entity_id: Entity UUID
            denial_reason: Why permission was denied
            required_role: Role required for action

        Returns:
            AuditLog: Created audit log entry
        """
        details = {
            'attempted_action': action,
            'user_role': user.role.role_name,
            'denial_reason': denial_reason
        }

        if required_role:
            details['required_role'] = required_role

        return self.log_action(
            action=f'PERMISSION_DENIED_{action}',
            entity_type=entity_type,
            entity_id=entity_id,
            user=user,
            result=AuditResult.DENIED,
            details=details
        )

    def log_cutoff_application(
        self,
        order_id: uuid.UUID,
        user: User,
        created_at_time: str,
        delivery_date: str,
        business_rule: str
    ) -> AuditLog:
        """
        Log cut-off rule application

        Args:
            order_id: Order UUID
            user: User creating order
            created_at_time: Time when order was created
            delivery_date: Calculated delivery date
            business_rule: BR code (BR-001, BR-002, BR-003)

        Returns:
            AuditLog: Created audit log entry
        """
        action_map = {
            'BR-001': 'APPLY_CUTOFF_AM',
            'BR-002': 'APPLY_CUTOFF_PM',
            'BR-003': 'APPLY_CUTOFF_INTERMEDIATE'
        }

        action = action_map.get(business_rule, 'APPLY_CUTOFF')

        return self.log_action(
            action=action,
            entity_type='ORDER',
            entity_id=order_id,
            user=user,
            result=AuditResult.SUCCESS,
            details={
                'created_at_time': created_at_time,
                'delivery_date': delivery_date,
                'rule': business_rule
            }
        )

    def log_invoice_creation(
        self,
        invoice_id: uuid.UUID,
        invoice_number: str,
        order_id: uuid.UUID,
        user: User,
        auto_transitioned: bool = False
    ) -> AuditLog:
        """
        Log invoice creation

        Args:
            invoice_id: Invoice UUID
            invoice_number: Invoice number
            order_id: Associated order UUID
            user: User creating invoice
            auto_transitioned: Whether order auto-transitioned to DOCUMENTADO

        Returns:
            AuditLog: Created audit log entry
        """
        return self.log_action(
            action='CREATE_INVOICE',
            entity_type='INVOICE',
            entity_id=invoice_id,
            user=user,
            result=AuditResult.SUCCESS,
            details={
                'invoice_number': invoice_number,
                'order_id': str(order_id),
                'auto_transitioned': auto_transitioned
            }
        )

    def get_audit_trail(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        limit: int = 50
    ) -> list[AuditLog]:
        """
        Get audit trail for specific entity

        Args:
            entity_type: Type of entity (ORDER, INVOICE, ROUTE, USER)
            entity_id: Entity UUID
            limit: Maximum number of entries to return

        Returns:
            list[AuditLog]: Audit log entries ordered by timestamp DESC
        """
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_user_audit_trail(
        self,
        user_id: uuid.UUID,
        limit: int = 50
    ) -> list[AuditLog]:
        """
        Get audit trail for specific user

        Args:
            user_id: User UUID
            limit: Maximum number of entries

        Returns:
            list[AuditLog]: Audit log entries for user
        """
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_failed_actions(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> list[AuditLog]:
        """
        Get failed/denied actions in last N hours

        Args:
            hours: Number of hours to look back
            limit: Maximum number of entries

        Returns:
            list[AuditLog]: Failed/denied audit log entries
        """
        cutoff_time = datetime.now(self.TIMEZONE) - timedelta(hours=hours)

        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.result.in_([AuditResult.DENIED, AuditResult.ERROR]),
                AuditLog.timestamp >= cutoff_time
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )


# Standalone function for contexts where Session is not available
def create_audit_log_standalone(
    db: Session,
    action: str,
    entity_type: str,
    result: AuditResult,
    user_id: Optional[uuid.UUID] = None,
    entity_id: Optional[uuid.UUID] = None,
    details: Optional[dict] = None
) -> AuditLog:
    """
    Create audit log without AuditService instance

    Useful for database triggers or contexts where service instantiation is not practical.

    Args:
        db: Database session
        action: Action name
        entity_type: Entity type
        result: Action result
        user_id: User UUID (optional)
        entity_id: Entity UUID (optional)
        details: Additional details (optional)

    Returns:
        AuditLog: Created audit log entry
    """
    service = AuditService(db)

    # Create mock user if user_id provided
    user = None
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()

    return service.log_action(
        action=action,
        entity_type=entity_type,
        result=result,
        user=user,
        entity_id=entity_id,
        details=details
    )


# Import for timedelta
from datetime import timedelta
