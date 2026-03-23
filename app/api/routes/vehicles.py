"""
Vehicles API endpoints

Fleet management REST API:
- CRUD for vehicles
- Driver assignment
- Status management (AVAILABLE / IN_ROUTE / MAINTENANCE)
- Available vehicle listing for route activation
"""

from fastapi import APIRouter, Depends, status, Query
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.vehicle_service import VehicleService
from app.schemas.vehicle_schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    VehicleListResponse,
    DriverAssignment,
)
from app.models.models import User
from app.models.enums import VehicleStatus
from app.exceptions import BusinessRuleViolationError
from fastapi import HTTPException


router = APIRouter(prefix="/api/vehicles", tags=["Vehicles"])


def _http(exc: BusinessRuleViolationError) -> HTTPException:
    """Convert domain exception to HTTPException."""
    return HTTPException(status_code=exc.http_status, detail=exc.to_dict())


# ─────────────────────────────────────────────────────────────────
# Vehicle CRUD
# ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create vehicle",
    description="Register a new vehicle in the fleet. Requires Administrador or Encargado de Bodega.",
)
async def create_vehicle(
    data: VehicleCreate,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.create_vehicle(data)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.get(
    "",
    response_model=VehicleListResponse,
    summary="List vehicles",
    description="Return paginated list of fleet vehicles.",
)
async def list_vehicles(
    include_inactive: bool = Query(False, description="Include soft-deleted vehicles"),
    status_filter: Optional[VehicleStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega", "Repartidor"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        items, total = service.get_all_vehicles(
            include_inactive=include_inactive,
            status_filter=status_filter,
            skip=skip,
            limit=limit,
        )
        return VehicleListResponse(
            items=[VehicleResponse.model_validate(v) for v in items],
            total=total,
        )
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.get(
    "/available",
    response_model=list[VehicleResponse],
    summary="List available vehicles",
    description="Return vehicles with AVAILABLE status for route assignment.",
)
async def list_available_vehicles(
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    service = VehicleService(db)
    vehicles = service.get_available_vehicles()
    return [VehicleResponse.model_validate(v) for v in vehicles]


@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Get vehicle",
)
async def get_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega", "Repartidor"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.get_vehicle(vehicle_id)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
    summary="Update vehicle",
    description="Partial update — only provided fields are changed.",
)
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.update_vehicle(vehicle_id, data)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete vehicle",
)
async def delete_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(require_roles(["Administrador"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        service.soft_delete(vehicle_id)
    except BusinessRuleViolationError as e:
        raise _http(e)


# ─────────────────────────────────────────────────────────────────
# Driver assignment
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{vehicle_id}/assign-driver",
    response_model=VehicleResponse,
    summary="Assign driver to vehicle",
    description="Assign a Repartidor user as the vehicle's driver.",
)
async def assign_driver(
    vehicle_id: UUID,
    body: DriverAssignment,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.assign_driver(vehicle_id, body.user_id)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.delete(
    "/{vehicle_id}/assign-driver",
    response_model=VehicleResponse,
    summary="Remove driver from vehicle",
)
async def unassign_driver(
    vehicle_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.unassign_driver(vehicle_id)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


# ─────────────────────────────────────────────────────────────────
# Status management
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{vehicle_id}/maintenance",
    response_model=VehicleResponse,
    summary="Set vehicle to maintenance",
    description="Mark vehicle as MAINTENANCE — removes it from available pool.",
)
async def set_maintenance(
    vehicle_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.set_maintenance(vehicle_id)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.post(
    "/{vehicle_id}/release",
    response_model=VehicleResponse,
    summary="Release vehicle",
    description="Set vehicle status back to AVAILABLE (after route or maintenance).",
)
async def release_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    try:
        service = VehicleService(db)
        vehicle = service.release_from_route(vehicle_id)
        return VehicleResponse.model_validate(vehicle)
    except BusinessRuleViolationError as e:
        raise _http(e)
