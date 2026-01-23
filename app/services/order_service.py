"""
Order service for complete order lifecycle management

Implements business rules:
- BR-001, BR-002, BR-003: Cut-off time and delivery date calculation
- BR-006 to BR-013: State transition validation
- BR-014: Order operation permissions
- BR-022: Optimistic locking for concurrency
- BR-023: Idempotent state transitions

State transition matrix is strictly enforced.
"""

import uuid
from datetime import datetime, date
from typing import List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError

from app.models.models import User, Order, Route
from app.models.enums import OrderStatus, SourceChannel, RouteStatus, AuditResult
from app.exceptions import (
    ValidationError,
    InvalidStateTransitionError,
    InvoiceRequiredError,
    NotFoundError,
    ConcurrencyError,
    IntegrityError,
    InvalidAddressError
)
from app.services.cutoff_service import CutoffService
from app.services.audit_service import AuditService
from app.services.permission_service import PermissionService
from app.services.invoice_service import InvoiceService
from app.services.geocoding_service import GeocodingService, GeocodingResult


class OrderService:
    """
    Service for managing order lifecycle

    Enforces state machine transitions and business rules
    """

    TIMEZONE = ZoneInfo("America/Santiago")

    # Valid state transitions (BR-006 to BR-013)
    VALID_TRANSITIONS = {
        OrderStatus.PENDIENTE: [OrderStatus.EN_PREPARACION],
        OrderStatus.EN_PREPARACION: [OrderStatus.DOCUMENTADO],
        OrderStatus.DOCUMENTADO: [OrderStatus.EN_RUTA],
        OrderStatus.EN_RUTA: [OrderStatus.ENTREGADO, OrderStatus.INCIDENCIA],
        OrderStatus.INCIDENCIA: [OrderStatus.EN_RUTA, OrderStatus.DOCUMENTADO],
        OrderStatus.ENTREGADO: [],  # Final state
    }

    def __init__(
        self,
        db: Session,
        geocoding_service: Optional[GeocodingService] = None
    ):
        """
        Initialize order service

        Args:
            db: SQLAlchemy database session
            geocoding_service: Optional geocoding service (defaults to new instance)
        """
        self.db = db
        self.cutoff_service = CutoffService()
        self.audit_service = AuditService(db)
        self.permission_service = PermissionService(db)
        self.invoice_service = InvoiceService(db)
        self.geocoding_service = geocoding_service or GeocodingService()

    def create_order(
        self,
        customer_name: str,
        customer_phone: str,
        address_text: str,
        source_channel: SourceChannel,
        user: User,
        customer_email: Optional[str] = None,
        notes: Optional[str] = None,
        override_delivery_date: Optional[date] = None,
        override_reason: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> Order:
        """
        Create new order with automatic delivery date calculation

        Args:
            customer_name: Customer full name
            customer_phone: Customer phone (Chilean format +569XXXXXXXX)
            address_text: Delivery address
            source_channel: Order source (WEB, RRSS, PRESENCIAL)
            user: User creating order
            customer_email: Optional customer email
            notes: Optional notes
            override_delivery_date: Admin override of delivery date
            override_reason: Required if override_delivery_date provided
            created_at: Optional timestamp (default: now)

        Returns:
            Order: Created order

        Raises:
            ValidationError: If data validation fails
            InsufficientPermissionsError: If user lacks permission
        """
        # Permission check (BR-014)
        self.permission_service.require_permission(user, 'create_order')

        # Validate customer phone format (Chilean)
        if not customer_phone.startswith('+56'):
            raise ValidationError(
                code='INVALID_PHONE_FORMAT',
                message='Phone must be Chilean format (+56XXXXXXXXX)',
                details={'customer_phone': customer_phone}
            )

        # Validate address length
        if len(address_text.strip()) < 10:
            raise ValidationError(
                code='ADDRESS_TOO_SHORT',
                message='Address must be at least 10 characters',
                details={'address_text': address_text}
            )

        # FASE 3: Geocode and validate address
        geocoding_result = self.geocoding_service.geocode_address(address_text)

        # Validate address quality (HIGH or MEDIUM confidence required)
        is_valid, error_message = self.geocoding_service.validate_address_quality(geocoding_result)
        if not is_valid:
            raise InvalidAddressError(
                message=error_message,
                details={
                    'address_text': address_text,
                    'confidence': geocoding_result.confidence.value if geocoding_result.confidence else None,
                    'display_name': geocoding_result.display_name
                }
            )

        # Generate order number
        order_created_at = created_at or datetime.now(self.TIMEZONE)
        order_number = self._generate_order_number(order_created_at)

        # Calculate delivery date using CutoffService (BR-001, BR-002, BR-003)
        delivery_date = self.cutoff_service.calculate_delivery_date(
            order_created_at=order_created_at,
            user=user,
            override_date=override_delivery_date,
            override_reason=override_reason
        )

        # Create order with geocoded coordinates
        order = Order(
            id=uuid.uuid4(),
            order_number=order_number,
            customer_name=customer_name.strip(),
            customer_phone=customer_phone,
            customer_email=customer_email,
            address_text=address_text.strip(),
            address_coordinates=f'POINT({geocoding_result.longitude} {geocoding_result.latitude})',
            geocoding_confidence=geocoding_result.confidence,
            source_channel=source_channel,
            delivery_date=delivery_date,
            order_status=OrderStatus.PENDIENTE,
            created_by_user_id=user.id,
            notes=notes
        )

        try:
            self.db.add(order)
            self.db.commit()
            self.db.refresh(order)

        except SQLAlchemyIntegrityError as e:
            self.db.rollback()
            if 'order_number' in str(e.orig):
                raise IntegrityError(
                    code='DUPLICATE_ORDER_NUMBER',
                    message=f'Order number {order_number} already exists'
                )
            raise IntegrityError(
                code='DATABASE_INTEGRITY_ERROR',
                message=str(e.orig)
            )

        # Audit log cutoff application
        business_rule = self.cutoff_service._get_business_rule(order_created_at.time())
        self.audit_service.log_cutoff_application(
            order_id=order.id,
            user=user,
            created_at_time=str(order_created_at.time()),
            delivery_date=str(delivery_date),
            business_rule=business_rule
        )

        # If override was used, log it
        if override_delivery_date:
            self.audit_service.log_override_attempt(
                action='OVERRIDE_CUTOFF_TIME',
                user=user,
                reason=override_reason or '',
                result=AuditResult.SUCCESS,
                entity_type='ORDER',
                entity_id=order.id,
                additional_details={
                    'calculated_delivery_date': str(delivery_date),
                    'override_delivery_date': str(override_delivery_date)
                }
            )

        # Log geocoding result for audit trail
        self.audit_service.log_action(
            action='GEOCODE_ADDRESS',
            entity_type='ORDER',
            entity_id=order.id,
            user=user,
            result=AuditResult.SUCCESS,
            details={
                'address_text': address_text,
                'latitude': geocoding_result.latitude,
                'longitude': geocoding_result.longitude,
                'confidence': geocoding_result.confidence.value,
                'display_name': geocoding_result.display_name,
                'cached': geocoding_result.cached
            }
        )

        return order

    def transition_order_state(
        self,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        user: User,
        reason: Optional[str] = None,
        route_id: Optional[uuid.UUID] = None
    ) -> Order:
        """
        Transition order to new state with validations (BR-006 to BR-013)

        Steps:
        1. Fetch order with optimistic lock
        2. Validate transition is valid
        3. Validate permissions
        4. Validate prerequisites (e.g., invoice for EN_RUTA)
        5. Update order status
        6. Audit log
        7. Trigger side effects (e.g., notifications)

        Args:
            order_id: Order UUID
            new_status: Target status
            user: User executing transition
            reason: Required for INCIDENCIA transition
            route_id: Required for EN_RUTA transition

        Returns:
            Order: Updated order

        Raises:
            NotFoundError: If order not found
            InvalidStateTransitionError: If transition invalid
            ValidationError: If prerequisites not met
            InsufficientPermissionsError: If user lacks permission
            ConcurrencyError: If concurrent modification detected
        """
        # Fetch order with pessimistic lock for concurrency safety (BR-022)
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .first()
        )

        if not order:
            raise NotFoundError(
                code='ORDER_NOT_FOUND',
                message=f'Order {order_id} not found'
            )

        # Idempotency check (BR-023)
        if order.order_status == new_status:
            return order  # Already in target state - no-op

        # Validate transition is allowed
        self._validate_state_transition(order.order_status, new_status)

        # Permission check
        action = f'transition_to_{new_status.value}'
        self.permission_service.require_permission(user, action, order)

        # Validate prerequisites based on target status
        self._validate_transition_prerequisites(order, new_status, reason, route_id, user)

        # Store previous status for audit
        previous_status = order.order_status

        # Perform transition
        order.order_status = new_status

        # Handle transition-specific logic
        if new_status == OrderStatus.INCIDENCIA:
            # Append reason to notes
            incidence_note = f"\n[INCIDENCIA - {datetime.now(self.TIMEZONE).isoformat()}] {reason}"
            order.notes = (order.notes or '') + incidence_note

        elif new_status == OrderStatus.EN_RUTA:
            # Assign route
            if route_id:
                order.assigned_route_id = route_id

        elif new_status == OrderStatus.DOCUMENTADO and previous_status == OrderStatus.INCIDENCIA:
            # Reset route assignment when resetting to DOCUMENTADO from INCIDENCIA (BR-012)
            order.assigned_route_id = None

        # Commit transaction
        self.db.commit()
        self.db.refresh(order)

        # Audit log
        additional_details = {}
        if reason:
            additional_details['reason'] = reason
        if route_id:
            additional_details['route_id'] = str(route_id)

        self.audit_service.log_state_transition(
            order_id=order.id,
            order_number=order.order_number,
            from_status=previous_status,
            to_status=new_status,
            user=user,
            result=AuditResult.SUCCESS,
            additional_details=additional_details if additional_details else None
        )

        # Side effects
        if new_status == OrderStatus.EN_RUTA:
            # Trigger customer notification (BR-026) - FASE 6 Implementation
            self._trigger_in_transit_notification(order, user)

        return order

    def _trigger_in_transit_notification(self, order: Order, user: User) -> None:
        """
        Trigger customer notification when order transitions to EN_RUTA

        This is a "best effort" operation - notification failures should not
        block the order state transition. Errors are logged for later retry.

        Args:
            order: Order that transitioned to EN_RUTA
            user: User who triggered the transition

        Note:
            If notification fails, the error is logged in audit_logs but
            the order remains in EN_RUTA status. Customer service can
            manually retry notifications via NotificationService.
        """
        try:
            from app.services.notification_service import NotificationService

            notification_service = NotificationService(self.db)
            log = notification_service.send_order_in_transit_notification(order.id)

            # Log notification result in audit
            if log.status.value == 'SENT':
                self.audit_service.log_action(
                    user=user,
                    action='NOTIFICATION_SENT',
                    entity_type='Order',
                    entity_id=order.id,
                    details={
                        'notification_id': str(log.id),
                        'channel': log.channel.value,
                        'recipient': log.recipient
                    },
                    result=AuditResult.SUCCESS
                )
            else:
                self.audit_service.log_action(
                    user=user,
                    action='NOTIFICATION_FAILED',
                    entity_type='Order',
                    entity_id=order.id,
                    details={
                        'notification_id': str(log.id),
                        'channel': log.channel.value,
                        'recipient': log.recipient,
                        'error': log.error_message
                    },
                    result=AuditResult.ERROR
                )

        except Exception as e:
            # Log error but don't fail the transition
            # Notification is "best effort" - order state change is more critical
            self.audit_service.log_action(
                user=user,
                action='NOTIFICATION_ERROR',
                entity_type='Order',
                entity_id=order.id,
                details={
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                result=AuditResult.ERROR
            )

    def get_orders_by_status(
        self,
        status: OrderStatus,
        user: User,
        limit: int = 100,
        offset: int = 0
    ) -> List[Order]:
        """
        List orders by status with permission filters

        Args:
            status: Filter by status
            user: Current user
            limit: Max results
            offset: Pagination offset

        Returns:
            List[Order]: Filtered orders
        """
        query = self.db.query(Order).filter(Order.order_status == status)

        # Apply permission filters
        if user.role.role_name == 'Vendedor':
            # Vendedor sees only own orders
            query = query.filter(Order.created_by_user_id == user.id)

        elif user.role.role_name == 'Repartidor':
            # Repartidor sees only orders in assigned routes
            query = query.join(Route).filter(Route.assigned_driver_id == user.id)

        # Admin and Encargado see all orders (no filter)

        return query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()

    def get_orders_for_delivery_date(
        self,
        delivery_date: date,
        user: User
    ) -> List[Order]:
        """
        Get orders DOCUMENTADO for specific delivery date (for routing)

        Filters:
        - status = DOCUMENTADO
        - delivery_date = fecha
        - invoice_id IS NOT NULL
        - assigned_route_id IS NULL (not yet routed)

        Args:
            delivery_date: Target delivery date
            user: Current user

        Returns:
            List[Order]: Eligible orders for routing
        """
        # Permission check
        self.permission_service.require_permission(user, 'generate_route')

        return (
            self.db.query(Order)
            .filter(
                Order.order_status == OrderStatus.DOCUMENTADO,
                Order.delivery_date == delivery_date,
                Order.invoice != None,
                Order.assigned_route_id == None
            )
            .order_by(Order.created_at.asc())
            .all()
        )

    def _generate_order_number(self, created_at: datetime) -> str:
        """
        Generate unique order number: ORD-YYYYMMDD-NNNN

        Args:
            created_at: Order creation timestamp

        Returns:
            str: Order number
        """
        date_str = created_at.strftime('%Y%m%d')

        # Get count of orders created today
        today_start = created_at.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = created_at.replace(hour=23, minute=59, second=59, microsecond=999999)

        count = (
            self.db.query(Order)
            .filter(
                Order.created_at >= today_start,
                Order.created_at <= today_end
            )
            .count()
        )

        sequence = str(count + 1).zfill(4)

        return f'ORD-{date_str}-{sequence}'

    def _validate_state_transition(
        self,
        from_status: OrderStatus,
        to_status: OrderStatus
    ) -> None:
        """
        Validate if state transition is allowed

        Args:
            from_status: Current status
            to_status: Target status

        Raises:
            InvalidStateTransitionError: If transition not allowed
        """
        valid_targets = self.VALID_TRANSITIONS.get(from_status, [])

        if to_status not in valid_targets:
            raise InvalidStateTransitionError(
                from_status=from_status.value,
                to_status=to_status.value
            )

    def _validate_transition_prerequisites(
        self,
        order: Order,
        new_status: OrderStatus,
        reason: Optional[str],
        route_id: Optional[uuid.UUID],
        user: User
    ) -> None:
        """
        Validate prerequisites for specific transitions

        Args:
            order: Order instance
            new_status: Target status
            reason: Transition reason (required for INCIDENCIA)
            route_id: Route ID (required for EN_RUTA)
            user: User executing transition

        Raises:
            ValidationError: If prerequisites not met
        """
        # BR-010: INCIDENCIA requires reason
        if new_status == OrderStatus.INCIDENCIA:
            if not reason or reason.strip() == '':
                raise ValidationError(
                    code='INCIDENCE_REASON_REQUIRED',
                    message='Must provide reason for marking order as INCIDENCIA',
                    details={'order_id': str(order.id)}
                )

        # BR-008: EN_RUTA requires invoice and route
        elif new_status == OrderStatus.EN_RUTA:
            # Validate invoice exists (BR-004)
            if not order.invoice:
                raise InvoiceRequiredError(order_id=str(order.id))

            # Validate route assigned and active
            if not route_id:
                raise ValidationError(
                    code='ROUTE_NOT_ASSIGNED',
                    message='Must assign route before transitioning to EN_RUTA',
                    details={'order_id': str(order.id)}
                )

            route = self.db.query(Route).filter(Route.id == route_id).first()
            if not route:
                raise NotFoundError(
                    code='ROUTE_NOT_FOUND',
                    message=f'Route {route_id} not found'
                )

            if route.status != RouteStatus.ACTIVE:
                raise ValidationError(
                    code='ROUTE_NOT_ACTIVE',
                    message=f'Route must be ACTIVE to assign orders (currently {route.status.value})',
                    details={
                        'route_id': str(route_id),
                        'route_status': route.status.value
                    }
                )

        # BR-009: ENTREGADO from EN_RUTA (Repartidor must be assigned to route)
        elif new_status == OrderStatus.ENTREGADO:
            if user.role.role_name == 'Repartidor':
                if not order.assigned_route_id:
                    raise ValidationError(
                        code='ORDER_NOT_IN_ROUTE',
                        message='Order must be in a route to mark as delivered'
                    )

                route = order.assigned_route
                if route.assigned_driver_id != user.id:
                    # This should be caught by permission check, but double-check
                    raise ValidationError(
                        code='NOT_YOUR_ROUTE',
                        message='You can only deliver orders in your assigned route'
                    )
