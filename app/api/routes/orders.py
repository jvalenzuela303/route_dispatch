"""
Orders API endpoints

Implements REST API for order lifecycle management:
- CRUD operations
- State transitions
- Filtering and search
- Permission-based access control
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.order_service import OrderService
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.schemas.order_schemas import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderDetailResponse,
    OrderStateTransition
)
from app.models.models import User, Order
from app.models.enums import OrderStatus
from app.exceptions import (
    NotFoundError,
    ValidationError,
    InsufficientPermissionsError
)


router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create new order",
    description="""
    Create new order with complete workflow:
    - Validates and geocodes address
    - Applies cutoff rules to calculate delivery date
    - Creates order with PENDIENTE status
    - Returns order with warnings and next steps

    **Permissions:** Administrador, Encargado de Bodega, Vendedor

    **Business Rules:**
    - BR-001: Orders before 12:00 PM eligible for same-day delivery
    - BR-002: Orders after 3:00 PM must be next-day delivery
    - BR-003: Admin can override cutoff with reason
    """
)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega', 'Vendedor'])),
    db: Session = Depends(get_db)
):
    """
    Create new order with complete workflow

    Uses WorkflowOrchestrator to handle:
    - Address geocoding and validation
    - Cutoff rule application
    - Delivery date calculation
    - Audit logging
    """
    orchestrator = WorkflowOrchestrator(db)
    result = orchestrator.create_order_workflow(order_data, current_user)

    # Convert order to response schema
    order_response = OrderResponse.from_orm(result['order'])

    return {
        'order': order_response,
        'warnings': result['warnings'],
        'next_steps': result['next_steps'],
        'delivery_date_info': result['delivery_date_info'],
        'workflow_status': result['workflow_status']
    }


@router.get(
    "",
    response_model=List[OrderResponse],
    summary="List orders with filtering",
    description="""
    List orders with filtering and pagination.

    **Filters:**
    - status: Filter by order status
    - delivery_date: Filter by delivery date
    - search: Search in order_number, customer_name, customer_phone

    **Permissions:**
    - Administrador/Encargado: See all orders
    - Vendedor: See only own orders
    - Repartidor: See only orders in assigned routes
    """
)
async def list_orders(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    status: Optional[OrderStatus] = Query(None, description="Filter by order status"),
    delivery_date: Optional[date] = Query(None, description="Filter by delivery date"),
    search: Optional[str] = Query(None, min_length=2, description="Search in order_number, customer_name, customer_phone"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List orders with filtering and RBAC-based access control
    """
    # Start with base query
    query = db.query(Order)

    # Apply RBAC filters
    if current_user.role.role_name == 'Vendedor':
        # Vendedor sees only own orders
        query = query.filter(Order.created_by_user_id == current_user.id)

    elif current_user.role.role_name == 'Repartidor':
        # Repartidor sees only orders in assigned routes
        from app.models.models import Route
        query = query.join(Route, Order.assigned_route_id == Route.id)
        query = query.filter(Route.assigned_driver_id == current_user.id)

    # Admin and Encargado see all orders (no additional filter)

    # Apply status filter
    if status:
        query = query.filter(Order.order_status == status)

    # Apply delivery_date filter
    if delivery_date:
        query = query.filter(Order.delivery_date == delivery_date)

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Order.order_number.ilike(search_pattern),
                Order.customer_name.ilike(search_pattern),
                Order.customer_phone.ilike(search_pattern)
            )
        )

    # Execute query with pagination
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    return orders


@router.get(
    "/{order_id}",
    response_model=OrderDetailResponse,
    summary="Get order by ID",
    description="""
    Get detailed order information by ID.

    **Permissions:**
    - Administrador/Encargado: See any order
    - Vendedor: See only own orders
    - Repartidor: See only orders in assigned routes
    """
)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get order by ID with permission checks
    """
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )

    # Permission checks
    if current_user.role.role_name == 'Vendedor':
        if order.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access orders you created"
            )

    elif current_user.role.role_name == 'Repartidor':
        if not order.assigned_route_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access orders in your assigned routes"
            )

        if order.assigned_route.assigned_driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access orders in your assigned routes"
            )

    return order


@router.put(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Update order details",
    description="""
    Update order details (customer info, address, notes).

    **Note:** Cannot change order status via this endpoint - use PUT /api/orders/{id}/status

    **Permissions:** Administrador, Encargado de Bodega, Vendedor (own orders only)
    """
)
async def update_order(
    order_id: UUID,
    order_update: OrderUpdate,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega', 'Vendedor'])),
    db: Session = Depends(get_db)
):
    """
    Update order details (not status)
    """
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )

    # Vendedor can only update own orders
    if current_user.role.role_name == 'Vendedor':
        if order.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update orders you created"
            )

    # Apply updates
    update_data = order_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)

    return order


@router.put(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Transition order status",
    description="""
    Transition order to new status with validation.

    Validates state machine transitions and business rules:
    - PENDIENTE → EN_PREPARACION
    - EN_PREPARACION → DOCUMENTADO (requires invoice)
    - DOCUMENTADO → EN_RUTA (requires active route)
    - EN_RUTA → ENTREGADO or INCIDENCIA
    - INCIDENCIA → EN_RUTA or DOCUMENTADO

    **Permissions:** Role-based (see state transition matrix in docs)

    **Business Rules:**
    - BR-006 to BR-013: State transition validation
    - BR-008: EN_RUTA requires invoice and active route
    - BR-010: INCIDENCIA requires reason
    """
)
async def transition_order_status(
    order_id: UUID,
    transition_data: OrderStateTransition,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Transition order to new status

    Validates state machine transitions and business rules.
    """
    service = OrderService(db)

    try:
        order = service.transition_order_state(
            order_id=order_id,
            new_status=transition_data.new_status,
            user=current_user,
            reason=transition_data.reason,
            route_id=transition_data.route_id
        )
        return order

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except (ValidationError, InsufficientPermissionsError) as e:
        raise HTTPException(
            status_code=e.http_status,
            detail=e.message
        )


@router.get(
    "/status/{status_value}/list",
    response_model=List[OrderResponse],
    summary="Get orders by status",
    description="""
    Get all orders with specific status.

    Useful for:
    - Getting DOCUMENTADO orders ready for routing
    - Viewing EN_RUTA orders for active deliveries
    - Checking INCIDENCIA orders requiring attention

    **Permissions:** RBAC filters applied (Vendedor sees own, Repartidor sees assigned routes)
    """
)
async def get_orders_by_status(
    status_value: OrderStatus,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List orders by status with permission filters
    """
    service = OrderService(db)
    orders = service.get_orders_by_status(
        status=status_value,
        user=current_user,
        limit=limit,
        offset=skip
    )
    return orders


@router.get(
    "/ready-for-routing/delivery-date/{delivery_date}",
    response_model=List[OrderResponse],
    summary="Get orders ready for routing",
    description="""
    Get orders ready for routing on specific delivery date.

    Filters:
    - status = DOCUMENTADO
    - delivery_date = specified date
    - invoice exists
    - not yet assigned to route

    Used by route generation workflow.

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_orders_ready_for_routing(
    delivery_date: date,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Get orders ready for routing on delivery date
    """
    service = OrderService(db)
    orders = service.get_orders_for_delivery_date(delivery_date, current_user)
    return orders


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete order",
    description="""
    Delete order (soft delete recommended in production).

    **Permissions:** Administrador only

    **Note:** Only orders in PENDIENTE or EN_PREPARACION can be deleted
    """
)
async def delete_order(
    order_id: UUID,
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
):
    """
    Delete order (only PENDIENTE or EN_PREPARACION)
    """
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )

    # Only allow deletion of PENDIENTE or EN_PREPARACION orders
    if order.order_status not in [OrderStatus.PENDIENTE, OrderStatus.EN_PREPARACION]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete order in status {order.order_status.value}"
        )

    db.delete(order)
    db.commit()

    return None
