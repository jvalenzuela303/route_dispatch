"""
Invoices API endpoints

Implements REST API for invoice management:
- Create invoice and auto-transition order to DOCUMENTADO
- List and retrieve invoices
- Link invoices to orders
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.invoice_service import InvoiceService
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.schemas.invoice_schemas import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceListResponse
)
from app.models.models import User, Invoice
from app.exceptions import (
    NotFoundError,
    ValidationError,
    IntegrityError
)


router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create invoice and link to order",
    description="""
    Create invoice and automatically transition order to DOCUMENTADO.

    **Workflow:**
    1. Create invoice with fiscal document number
    2. Link invoice to order
    3. Auto-transition order from EN_PREPARACION → DOCUMENTADO (BR-005)
    4. Order becomes ready for routing

    **Permissions:** Administrador, Encargado de Bodega, Vendedor

    **Business Rules:**
    - BR-005: Linking invoice auto-transitions order to DOCUMENTADO
    - Order must be in EN_PREPARACION status
    - Invoice number must be unique
    """
)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega', 'Vendedor'])),
    db: Session = Depends(get_db)
):
    """
    Create invoice and execute linking workflow

    Uses WorkflowOrchestrator to handle:
    - Invoice creation
    - Order state transition
    - Audit logging
    """
    orchestrator = WorkflowOrchestrator(db)

    try:
        result = orchestrator.invoice_linking_workflow(invoice_data, current_user)

        # Convert to response schemas
        invoice_response = InvoiceResponse.from_orm(result['invoice'])

        return {
            'invoice': invoice_response,
            'order_id': str(result['order'].id),
            'order_status': result['order'].order_status.value,
            'transition': result['transition'],
            'next_steps': result['next_steps'],
            'workflow_status': result['workflow_status']
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except (ValidationError, IntegrityError) as e:
        raise HTTPException(
            status_code=e.http_status,
            detail=e.message
        )


@router.get(
    "",
    response_model=List[InvoiceResponse],
    summary="List invoices",
    description="""
    List invoices with filtering and pagination.

    **Filters:**
    - order_id: Filter by associated order
    - search: Search in invoice_number

    **Permissions:**
    - Administrador/Encargado: See all invoices
    - Vendedor: See only invoices for own orders
    """
)
async def list_invoices(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    order_id: Optional[UUID] = Query(None, description="Filter by order ID"),
    search: Optional[str] = Query(None, min_length=2, description="Search in invoice_number"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List invoices with filtering and RBAC
    """
    # Start with base query
    query = db.query(Invoice)

    # Apply RBAC filters
    if current_user.role.role_name == 'Vendedor':
        # Vendedor sees only invoices for own orders
        from app.models.models import Order
        query = query.join(Order, Invoice.order_id == Order.id)
        query = query.filter(Order.created_by_user_id == current_user.id)

    # Admin and Encargado see all invoices (no additional filter)

    # Apply order_id filter
    if order_id:
        query = query.filter(Invoice.order_id == order_id)

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(Invoice.invoice_number.ilike(search_pattern))

    # Execute query with pagination
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

    return invoices


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice by ID",
    description="""
    Get detailed invoice information by ID.

    **Permissions:**
    - Administrador/Encargado: See any invoice
    - Vendedor: See only invoices for own orders
    """
)
async def get_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get invoice by ID with permission checks
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    # Permission checks
    if current_user.role.role_name == 'Vendedor':
        if invoice.order.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access invoices for orders you created"
            )

    return invoice


@router.get(
    "/order/{order_id}/invoice",
    response_model=InvoiceResponse,
    summary="Get invoice for specific order",
    description="""
    Get invoice associated with an order.

    **Permissions:** Same as get_invoice
    """
)
async def get_invoice_by_order(
    order_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get invoice for specific order
    """
    invoice = db.query(Invoice).filter(Invoice.order_id == order_id).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No invoice found for order {order_id}"
        )

    # Permission checks
    if current_user.role.role_name == 'Vendedor':
        if invoice.order.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access invoices for orders you created"
            )

    return invoice


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete invoice",
    description="""
    Delete invoice and revert order status.

    **Warning:** This will transition order back to EN_PREPARACION if it was DOCUMENTADO.

    **Permissions:** Administrador only

    **Note:** Cannot delete invoice if order is already EN_RUTA or beyond
    """
)
async def delete_invoice(
    invoice_id: UUID,
    current_user: User = Depends(require_roles(['Administrador'])),
    db: Session = Depends(get_db)
):
    """
    Delete invoice (with status reversion)
    """
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found"
        )

    # Check if order is already in route
    order = invoice.order
    if order.order_status not in ['PENDIENTE', 'EN_PREPARACION', 'DOCUMENTADO']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete invoice - order is already {order.order_status.value}"
        )

    # Revert order status if it was DOCUMENTADO
    if order.order_status == 'DOCUMENTADO':
        from app.models.enums import OrderStatus
        order.order_status = OrderStatus.EN_PREPARACION

    db.delete(invoice)
    db.commit()

    return None
