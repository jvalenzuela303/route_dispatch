"""
Delivery Routes API endpoints

Implements REST API for route optimization and management:
- Generate optimized routes using TSP solver
- Activate routes and assign to drivers
- View route details and stop sequences
- Get map visualization data
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel


class IncidentRequest(BaseModel):
    incident_reason: str

from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.route_optimization_service import RouteOptimizationService
from app.schemas.route_schemas import (
    RouteResponse,
    RouteDetailResponse,
    RouteGenerateRequest,
    RouteActivation,
    RouteMapData,
    RouteListResponse
)
from app.models.models import User, Route, Order
from app.models.enums import RouteStatus
from app.exceptions import (
    RouteOptimizationError,
    ValidationError
)
from app.config.settings import get_settings


router = APIRouter(prefix="/api/routes", tags=["Delivery Routes"])


@router.post(
    "/generate",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Generate optimized route",
    description="""
    Generate optimized delivery route for specific date using TSP solver.

    **Workflow:**
    1. Fetch all DOCUMENTADO orders for delivery_date
    2. Validate orders have invoices and coordinates
    3. Calculate distance matrix using PostGIS
    4. Solve TSP using Google OR-Tools
    5. Create route in DRAFT status with optimized stop sequence

    **Permissions:** Administrador, Encargado de Bodega

    **Business Rules:**
    - BR-024: Route optimization for 50 orders must complete in < 10 seconds
    - BR-025: Only DOCUMENTADO orders with invoices and coordinates
    """
)
async def generate_route(
    route_data: RouteGenerateRequest,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Generate optimized route for delivery date
    """
    try:
        service = RouteOptimizationService(db)
        route = service.generate_route_for_date(
            delivery_date=route_data.delivery_date,
            user=current_user
        )

        # Get stop count
        stop_count = len(route.stop_sequence) if route.stop_sequence else 0

        return {
            'route': RouteResponse.from_orm(route),
            'stop_count': stop_count,
            'status': route.status.value,
            'next_steps': [
                f"Revise la ruta generada ({stop_count} paradas, {route.total_distance_km} km)",
                "Active la ruta para asignar al repartidor y notificar clientes",
                f"Use POST /api/routes/{route.id}/activate para activar"
            ]
        }

    except RouteOptimizationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.post(
    "/{route_id}/activate",
    response_model=dict,
    summary="Activate route and assign to driver",
    description="""
    Activate route and execute complete workflow:
    1. Assign route to driver
    2. Transition route DRAFT → ACTIVE
    3. Transition all orders to EN_RUTA
    4. Send notifications to customers
    5. Set started_at timestamp

    **Permissions:** Administrador, Encargado de Bodega

    **Business Rules:**
    - BR-026: Activating route transitions all orders to EN_RUTA
    - Triggers customer notifications (Email/WhatsApp/SMS)
    """
)
async def activate_route(
    route_id: UUID,
    activation_data: RouteActivation,
    auto_activate: bool = Query(True, description="Auto-activate route immediately"),
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Activate route and assign to driver

    Uses RouteOptimizationService to activate the existing route directly
    """
    try:
        # Verify route exists first
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route {route_id} not found"
            )

        # Activate the existing route directly (DRAFT → ACTIVE)
        service = RouteOptimizationService(db)
        activated_route = service.activate_route(
            route_id=route_id,
            driver_id=activation_data.driver_id,
            user=current_user
        )

        db.refresh(activated_route)

        # Count orders in route
        orders_count = len(activated_route.stop_sequence) if activated_route.stop_sequence else 0

        # Count notifications sent for this route's orders
        from app.models.models import NotificationLog
        from app.models.enums import NotificationStatus
        notifications_sent = (
            db.query(NotificationLog)
            .join(Order, NotificationLog.order_id == Order.id)
            .filter(
                Order.assigned_route_id == activated_route.id,
                NotificationLog.status == NotificationStatus.SENT
            )
            .count()
        )

        return {
            'route': RouteDetailResponse.from_orm(activated_route),
            'orders_count': orders_count,
            'notifications_sent': notifications_sent,
            'driver': {
                'id': str(activated_route.assigned_driver.id),
                'username': activated_route.assigned_driver.username,
                'email': activated_route.assigned_driver.email
            },
            'status': activated_route.status.value,
            'next_steps': [
                f"Ruta {activated_route.route_name} ACTIVADA",
                f"{orders_count} pedidos en ruta EN_RUTA",
                f"{notifications_sent} notificaciones enviadas a clientes",
                "Repartidor puede comenzar entregas"
            ],
            'workflow_status': 'ROUTE_ACTIVATED'
        }

    except (RouteOptimizationError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.get(
    "",
    response_model=List[RouteResponse],
    summary="List routes",
    description="""
    List routes with filtering and pagination.

    **Filters:**
    - status: Filter by route status
    - delivery_date: Filter by delivery date
    - assigned_driver_id: Filter by assigned driver

    **Permissions:**
    - Administrador/Encargado: See all routes
    - Repartidor: See only assigned routes
    """
)
async def list_routes(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    status: Optional[RouteStatus] = Query(None, description="Filter by route status"),
    delivery_date: Optional[date] = Query(None, description="Filter by delivery date"),
    assigned_driver_id: Optional[UUID] = Query(None, description="Filter by assigned driver"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List routes with filtering and RBAC
    """
    # Start with base query
    query = db.query(Route)

    # Apply RBAC filters
    if current_user.role.role_name == 'Repartidor':
        # Repartidor sees only assigned routes
        query = query.filter(Route.assigned_driver_id == current_user.id)

    # Admin and Encargado see all routes (no additional filter)

    # Apply status filter
    if status:
        query = query.filter(Route.status == status)

    # Apply delivery_date filter
    if delivery_date:
        query = query.filter(Route.route_date == delivery_date)

    # Apply assigned_driver_id filter
    if assigned_driver_id:
        query = query.filter(Route.assigned_driver_id == assigned_driver_id)

    # Execute query with pagination
    routes = query.order_by(Route.created_at.desc()).offset(skip).limit(limit).all()

    # Add stops_count to each route
    for route in routes:
        route.stops_count = len(route.stop_sequence) if route.stop_sequence else 0

    return routes


@router.get(
    "/{route_id}",
    response_model=RouteDetailResponse,
    summary="Get route by ID with full stop sequence",
    description="""
    Get detailed route information including:
    - Route metadata (distance, duration, status)
    - Complete stop sequence with coordinates
    - Associated orders

    **Permissions:**
    - Administrador/Encargado: See any route
    - Repartidor: See only assigned routes
    """
)
async def get_route(
    route_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get route by ID with full details
    """
    route = db.query(Route).filter(Route.id == route_id).first()

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )

    # Permission check for Repartidor
    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your assigned routes"
            )

    # Add stops_count
    route.stops_count = len(route.stop_sequence) if route.stop_sequence else 0

    # Build stops data — stop_sequence may be list of UUIDs or list of dicts
    stops = []
    if route.stop_sequence:
        from sqlalchemy import text as _text
        for idx, entry in enumerate(route.stop_sequence):
            # Support both plain UUID strings and full stop objects
            if isinstance(entry, dict):
                oid_raw = entry.get('order_id')
                stop_status = entry.get('status', 'PENDING')
                actual_arrival = entry.get('actual_arrival')
                stop_notes = entry.get('notes')
                incident_reason = entry.get('incident_reason')
            else:
                oid_raw = entry
                stop_status = 'PENDING'
                actual_arrival = None
                stop_notes = None
                incident_reason = None

            try:
                oid = UUID(str(oid_raw))
            except Exception:
                continue

            order = db.query(Order).filter(Order.id == oid).first()
            if not order:
                continue

            coords = db.execute(
                _text("SELECT ST_Y(address_coordinates::geometry) as lat, ST_X(address_coordinates::geometry) as lon FROM orders WHERE id = :oid"),
                {"oid": order.id}
            ).first()

            # Derive frontend status from stop_sequence status or order status
            if stop_status in ('DELIVERED',) or order.order_status.value == 'ENTREGADO':
                fe_status = 'ENTREGADO'
            elif stop_status == 'INCIDENT' or order.order_status.value == 'INCIDENCIA':
                fe_status = 'INCIDENCIA'
            else:
                fe_status = 'PENDIENTE'

            stops.append({
                'id': order.id,
                'stop_sequence': idx + 1,
                'order': {
                    'id': order.id,
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'customer_phone': order.customer_phone,
                    'address_text': order.address_text,
                    'document_number': order.document_number,
                },
                'latitude': coords.lat if coords else None,
                'longitude': coords.lon if coords else None,
                'estimated_arrival': None,
                'actual_arrival': actual_arrival,
                'delivered': fe_status == 'ENTREGADO',
                'status': fe_status,
                'delivery_notes': stop_notes or order.notes,
                'incident_reason': incident_reason,
            })

    # Create response with stops
    route_dict = RouteDetailResponse.from_orm(route).dict()
    route_dict['stops'] = stops

    return route_dict


@router.get(
    "/{route_id}/map-data",
    response_model=RouteMapData,
    summary="Get route map visualization data",
    description="""
    Get data for map visualization:
    - Depot coordinates (warehouse)
    - Stop coordinates in optimized sequence
    - Customer info for each stop

    Perfect for rendering routes on Leaflet, Google Maps, etc.

    **Permissions:** Same as get_route
    """
)
async def get_route_map_data(
    route_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get route data formatted for map visualization
    """
    route = db.query(Route).filter(Route.id == route_id).first()

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )

    # Permission check for Repartidor
    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your assigned routes"
            )

    # Get depot coordinates from settings
    settings = get_settings()
    depot_lat = settings.depot_latitude
    depot_lon = settings.depot_longitude

    # Build stops data
    stops = []
    if route.stop_sequence:
        for idx, order_id in enumerate(route.stop_sequence):
            order = db.query(Order).filter(Order.id == UUID(order_id) if isinstance(order_id, str) else order_id).first()
            if order:
                # Extract coordinates from PostGIS POINT
                from sqlalchemy import text
                coords = db.execute(
                    text("SELECT ST_Y(address_coordinates::geometry) as lat, ST_X(address_coordinates::geometry) as lon FROM orders WHERE id = :order_id"),
                    {"order_id": order.id}
                ).first()

                if coords:
                    stops.append({
                        'stop_sequence': idx + 1,
                        'latitude': float(coords.lat),
                        'longitude': float(coords.lon),
                        'customer_name': order.customer_name,
                        'address': order.address_text,
                        'order_number': order.order_number
                    })

    return {
        'route_id': route.id,
        'route_name': route.route_name,
        'route_date': route.route_date,
        'depot_latitude': depot_lat,
        'depot_longitude': depot_lon,
        'stops': stops,
        'total_distance_km': route.total_distance_km,
        'estimated_duration_minutes': route.estimated_duration_minutes
    }


@router.patch(
    "/{route_id}/stops/{order_id}/delivered",
    summary="Mark a stop as delivered",
    description="""
    Driver confirms delivery at a stop.
    Updates stop status in stop_sequence JSONB and transitions order to ENTREGADO.

    **Permissions:** Repartidor (own route), Administrador, Encargado de Bodega
    """
)
async def mark_stop_delivered(
    route_id: UUID,
    order_id: UUID,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timezone
    from sqlalchemy import text as sa_text

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only update stops on your own routes")

    # Update order status to ENTREGADO
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    from app.models.enums import OrderStatus
    order.order_status = OrderStatus.ENTREGADO

    # Update stop_sequence JSONB entry (handles both dict and plain UUID formats)
    import json as _json
    raw_stops = list(route.stop_sequence or [])
    updated_stops = []
    for entry in raw_stops:
        if isinstance(entry, dict):
            if entry.get('order_id') == str(order_id):
                entry = dict(entry)
                entry['status'] = 'DELIVERED'
                entry['actual_arrival'] = datetime.now(timezone.utc).isoformat()
                if notes:
                    entry['notes'] = notes
        else:
            # Convert plain UUID to dict
            entry = {'order_id': str(entry), 'sequence': raw_stops.index(entry) + 1,
                     'status': 'DELIVERED' if str(entry) == str(order_id) else 'PENDING'}
        updated_stops.append(entry)

    db.execute(
        sa_text("UPDATE routes SET stop_sequence = :seq WHERE id = :rid"),
        {"seq": _json.dumps(updated_stops), "rid": str(route_id)}
    )

    db.commit()

    return {"message": "Entrega confirmada", "order_id": str(order_id),
            "order_status": "ENTREGADO", "stop_status": "DELIVERED"}


@router.patch(
    "/{route_id}/stops/{order_id}/incident",
    summary="Report incident at a stop",
    description="""
    Driver reports a delivery incident (absent customer, wrong address, etc.).
    Updates stop status and transitions order to INCIDENCIA.

    **Permissions:** Repartidor (own route), Administrador, Encargado de Bodega
    """
)
async def report_stop_incident(
    route_id: UUID,
    order_id: UUID,
    payload: IncidentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    incident_reason: str = payload.incident_reason
    from datetime import datetime, timezone
    from sqlalchemy import text as sa_text

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only update stops on your own routes")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    from app.models.enums import OrderStatus
    order.order_status = OrderStatus.INCIDENCIA

    import json as _json
    raw_stops = list(route.stop_sequence or [])
    updated_stops = []
    for entry in raw_stops:
        if isinstance(entry, dict):
            if entry.get('order_id') == str(order_id):
                entry = dict(entry)
                entry['status'] = 'INCIDENT'
                entry['incident_reason'] = incident_reason
                entry['actual_arrival'] = datetime.now(timezone.utc).isoformat()
        else:
            is_target = str(entry) == str(order_id)
            entry = {'order_id': str(entry), 'sequence': raw_stops.index(entry) + 1,
                     'status': 'INCIDENT' if is_target else 'PENDING',
                     'incident_reason': incident_reason if is_target else None}
        updated_stops.append(entry)

    db.execute(
        sa_text("UPDATE routes SET stop_sequence = :seq WHERE id = :rid"),
        {"seq": _json.dumps(updated_stops), "rid": str(route_id)}
    )

    db.commit()

    return {"message": "Incidencia registrada", "order_id": str(order_id),
            "order_status": "INCIDENCIA", "stop_status": "INCIDENT",
            "incident_reason": incident_reason}


@router.post(
    "/{route_id}/start",
    response_model=RouteResponse,
    summary="Driver starts their assigned route",
    description="""
    Allows an assigned driver to confirm they have started their route.
    Updates started_at timestamp if not already set.

    **Permissions:** Repartidor (own routes only), Administrador, Encargado de Bodega
    """
)
async def start_route(
    route_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Driver confirms start of their route"""
    from datetime import datetime, timezone

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )

    # Repartidor can only start their own assigned route
    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only start your own assigned routes"
            )

    if route.status != RouteStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route must be ACTIVE to start (currently {route.status.value})"
        )

    if not route.started_at:
        route.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(route)

    return route


@router.put(
    "/{route_id}/complete",
    response_model=RouteResponse,
    summary="Mark route as completed",
    description="""
    Mark route as completed when all deliveries are finished.

    **Permissions:** Administrador, Encargado de Bodega, Repartidor (own routes only)
    """
)
async def complete_route(
    route_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mark route as completed
    """
    route = db.query(Route).filter(Route.id == route_id).first()

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )

    # Permission check
    if current_user.role.role_name == 'Repartidor':
        if not route.assigned_driver_id or route.assigned_driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only complete your assigned routes"
            )

    # Validate route is ACTIVE
    if route.status != RouteStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Route must be ACTIVE to mark as completed (currently {route.status.value})"
        )

    # Update status
    from datetime import datetime, timezone
    route.status = RouteStatus.COMPLETED
    route.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(route)

    return route


@router.delete(
    "/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete route",
    description="""
    Delete route (only DRAFT routes can be deleted).

    **Permissions:** Administrador, Encargado de Bodega

    **Note:** Cannot delete ACTIVE or COMPLETED routes
    """
)
async def delete_route(
    route_id: UUID,
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Delete route (only DRAFT status)
    """
    route = db.query(Route).filter(Route.id == route_id).first()

    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route {route_id} not found"
        )

    # Only allow deletion of DRAFT routes
    if route.status != RouteStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete route in status {route.status.value} (only DRAFT routes can be deleted)"
        )

    # Reset assigned_route_id for all orders in this route
    if route.stop_sequence:
        for order_id in route.stop_sequence:
            order = db.query(Order).filter(Order.id == UUID(order_id) if isinstance(order_id, str) else order_id).first()
            if order:
                order.assigned_route_id = None

    db.delete(route)
    db.commit()

    return None
