"""
Invoice service for managing fiscal documents

Implements business rules:
- BR-004: Invoice required for route assignment
- BR-005: Auto-transition to DOCUMENTADO on invoice creation
- BR-015: Invoice operations permissions

CRITICAL: Creating an invoice triggers automatic state transition to DOCUMENTADO
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError

from app.models.models import User, Order, Invoice
from app.models.enums import OrderStatus, InvoiceType, AuditResult
from app.exceptions import ValidationError, IntegrityError, NotFoundError
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService


class InvoiceService:
    """
    Service for managing invoices and auto-transition logic

    All invoice operations must go through this service to ensure
    business rules are properly enforced.
    """

    TIMEZONE = ZoneInfo("America/Santiago")

    def __init__(self, db: Session):
        """
        Initialize invoice service

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.audit_service = AuditService(db)
        self.permission_service = PermissionService(db)

    def create_invoice(
        self,
        order_id: uuid.UUID,
        invoice_number: str,
        invoice_type: InvoiceType,
        total_amount: Decimal,
        user: User,
        issued_at: Optional[datetime] = None
    ) -> Invoice:
        """
        Create invoice and auto-transition order to DOCUMENTADO (BR-005)

        Steps:
        1. Validate permissions
        2. Validate order exists and is in EN_PREPARACION
        3. Validate order doesn't already have invoice
        4. Create invoice
        5. Auto-transition order to DOCUMENTADO
        6. Audit log

        Args:
            order_id: UUID of order
            invoice_number: Unique invoice number
            invoice_type: FACTURA or BOLETA
            total_amount: Total amount in CLP
            user: User creating invoice
            issued_at: Invoice issue timestamp (default: now)

        Returns:
            Invoice: Created invoice

        Raises:
            ValidationError: If order not found, wrong state, or already has invoice
            IntegrityError: If invoice_number duplicated
            InsufficientPermissionsError: If user lacks permission
        """
        # Permission check (BR-015)
        self.permission_service.require_permission(user, 'create_invoice')

        # Validate order exists
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise NotFoundError(
                code='ORDER_NOT_FOUND',
                message=f'Order {order_id} not found'
            )

        # Validate order is in EN_PREPARACION (BR-005 prerequisite)
        if order.order_status != OrderStatus.EN_PREPARACION:
            raise ValidationError(
                code='INVALID_STATE_FOR_INVOICE',
                message=f'Order must be in EN_PREPARACION state to create invoice (currently {order.order_status.value})',
                details={
                    'order_id': str(order_id),
                    'current_status': order.order_status.value,
                    'required_status': 'EN_PREPARACION'
                }
            )

        # Validate order doesn't already have invoice
        if order.invoice:
            raise ValidationError(
                code='ORDER_ALREADY_HAS_INVOICE',
                message=f'Order {order.order_number} already has invoice {order.invoice.invoice_number}',
                details={
                    'order_id': str(order_id),
                    'existing_invoice_id': str(order.invoice.id),
                    'existing_invoice_number': order.invoice.invoice_number
                }
            )

        # Validate amount is positive
        if total_amount <= 0:
            raise ValidationError(
                code='INVALID_AMOUNT',
                message='Invoice amount must be positive',
                details={'total_amount': str(total_amount)}
            )

        # Create invoice
        invoice = Invoice(
            id=uuid.uuid4(),
            invoice_number=invoice_number,
            order_id=order_id,
            invoice_type=invoice_type,
            total_amount=total_amount,
            issued_at=issued_at or datetime.now(self.TIMEZONE),
            created_by_user_id=user.id
        )

        try:
            self.db.add(invoice)
            self.db.flush()  # Flush to catch unique constraint violations

        except SQLAlchemyIntegrityError as e:
            self.db.rollback()
            if 'invoice_number' in str(e.orig):
                raise IntegrityError(
                    code='DUPLICATE_INVOICE_NUMBER',
                    message=f'Invoice number {invoice_number} already exists',
                    details={'invoice_number': invoice_number}
                )
            raise IntegrityError(
                code='DATABASE_INTEGRITY_ERROR',
                message=str(e.orig)
            )

        # BR-005: Auto-transition order to DOCUMENTADO
        auto_transitioned = self._auto_transition_to_documentado(order, invoice, user)

        # Commit transaction
        self.db.commit()
        self.db.refresh(invoice)

        # Audit log
        self.audit_service.log_invoice_creation(
            invoice_id=invoice.id,
            invoice_number=invoice_number,
            order_id=order_id,
            user=user,
            auto_transitioned=auto_transitioned
        )

        return invoice

    def validate_invoice_before_routing(
        self,
        order: Order
    ) -> None:
        """
        Validate that order has invoice before allowing EN_RUTA (BR-004)

        Args:
            order: Order to validate

        Raises:
            ValidationError: If order has no invoice
        """
        if not order.invoice:
            raise ValidationError(
                code='INVOICE_REQUIRED_FOR_ROUTING',
                message=f'Order {order.order_number} must have an invoice before routing',
                details={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'order_status': order.order_status.value
                }
            )

    def get_invoice_by_id(
        self,
        invoice_id: uuid.UUID,
        user: User
    ) -> Invoice:
        """
        Get invoice by ID with permission check

        Args:
            invoice_id: Invoice UUID
            user: User requesting invoice

        Returns:
            Invoice: Invoice instance

        Raises:
            NotFoundError: If invoice not found
            InsufficientPermissionsError: If user lacks permission
        """
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

        if not invoice:
            raise NotFoundError(
                code='INVOICE_NOT_FOUND',
                message=f'Invoice {invoice_id} not found'
            )

        # Permission check
        self.permission_service.require_permission(
            user,
            'view_invoice',
            invoice.order  # Check against order for scope validation
        )

        return invoice

    def get_invoice_by_number(
        self,
        invoice_number: str,
        user: User
    ) -> Invoice:
        """
        Get invoice by invoice number with permission check

        Args:
            invoice_number: Invoice number
            user: User requesting invoice

        Returns:
            Invoice: Invoice instance

        Raises:
            NotFoundError: If invoice not found
            InsufficientPermissionsError: If user lacks permission
        """
        invoice = self.db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number
        ).first()

        if not invoice:
            raise NotFoundError(
                code='INVOICE_NOT_FOUND',
                message=f'Invoice {invoice_number} not found'
            )

        # Permission check
        self.permission_service.require_permission(
            user,
            'view_invoice',
            invoice.order
        )

        return invoice

    def _auto_transition_to_documentado(
        self,
        order: Order,
        invoice: Invoice,
        user: User
    ) -> bool:
        """
        Auto-transition order to DOCUMENTADO when invoice is created (BR-005)

        Args:
            order: Order instance
            invoice: Invoice instance
            user: User creating invoice

        Returns:
            bool: True if transition occurred, False if already DOCUMENTADO
        """
        # Idempotency check
        if order.order_status == OrderStatus.DOCUMENTADO:
            return False

        # Only transition if currently EN_PREPARACION
        if order.order_status != OrderStatus.EN_PREPARACION:
            # Log warning but don't fail
            self.audit_service.log_action(
                action='AUTO_TRANSITION_DOCUMENTADO',
                entity_type='ORDER',
                entity_id=order.id,
                user=user,
                result=AuditResult.ERROR,
                details={
                    'trigger': 'invoice_created',
                    'invoice_id': str(invoice.id),
                    'invoice_number': invoice.invoice_number,
                    'current_status': order.order_status.value,
                    'error': 'Order not in EN_PREPARACION state'
                }
            )
            return False

        # Perform transition
        previous_status = order.order_status
        order.order_status = OrderStatus.DOCUMENTADO

        # Audit log for transition
        self.audit_service.log_action(
            action='AUTO_TRANSITION_DOCUMENTADO',
            entity_type='ORDER',
            entity_id=order.id,
            user=user,  # Credit to user who created invoice
            result=AuditResult.SUCCESS,
            details={
                'previous_status': previous_status.value,
                'new_status': OrderStatus.DOCUMENTADO.value,
                'trigger': 'invoice_created',
                'invoice_id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'business_rule': 'BR-005'
            }
        )

        return True
