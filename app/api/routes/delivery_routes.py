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

from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.route_optimization_service import RouteOptimizationService
from app.services.workflow_orchestrator import WorkflowOrchestrator
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

    Uses WorkflowOrchestrator for complete workflow execution
    """
    try:
        orchestrator = WorkflowOrchestrator(db)

        # For activation, we need to pass the route's delivery_date
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route {route_id} not found"
            )

        # Execute activation workflow
        result = orchestrator.route_generation_workflow(
            delivery_date=route.route_date,
            driver_id=activation_data.driver_id,
            user=current_user,
            auto_activate=True  # Force activation
        )

        return {
            'route': RouteDetailResponse.from_orm(result['route']),
            'orders_count': result['orders_count'],
            'notifications_sent': result.get('notifications_sent', 0),
            'driver': {
                'id': str(result['driver'].id),
                'username': result['driver'].username,
                'email': result['driver'].email
            },
            'status': result['status'],
            'next_steps': result.get('next_steps', []),
            'workflow_status': result['workflow_status']
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

                stops.append({
                    'id': order.id,
                    'stop_sequence': idx + 1,
                    'order': {
                        'id': order.id,
                        'order_number': order.order_number,
                        'customer_name': order.customer_name,
                        'address_text': order.address_text
                    },
                    'latitude': coords.lat if coords else None,
                    'longitude': coords.lon if coords else None,
                    'estimated_arrival': None,
                    'actual_arrival': None,
                    'delivered': order.order_status == 'ENTREGADO',
                    'delivery_notes': order.notes
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
