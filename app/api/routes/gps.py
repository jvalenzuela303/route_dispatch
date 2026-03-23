"""
GPS API endpoints + WebSocket real-time feed

REST endpoints:
  POST /api/gps/positions          — driver APK pushes position
  POST /api/gps/wialon/webhook     — Wialon hardware webhook
  GET  /api/gps/fleet              — latest position per vehicle
  GET  /api/gps/vehicles/{id}/track — position history (breadcrumbs)
  GET  /api/gps/alerts             — list unacknowledged alerts
  POST /api/gps/alerts/{id}/ack    — acknowledge alert
  POST /api/gps/geofences          — create geofence
  GET  /api/gps/geofences          — list geofences

WebSocket:
  WS   /ws/fleet                   — subscribe to all vehicle positions
  WS   /ws/routes/{route_id}       — subscribe to one route's vehicle
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter, Depends, Header, HTTPException, Query, status, WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.gps_service import GPSService
from app.services.websocket_manager import ws_manager
from app.schemas.vehicle_schemas import (
    GPSPositionCreate,
    GPSPositionResponse,
    FleetPositionItem,
    WialonWebhookPayload,
    GeofenceCreate,
    GeofenceResponse,
    GPSAlertResponse,
)
from app.models.models import User, GPSAlert, Geofence
from app.models.enums import AlertType
from app.exceptions import BusinessRuleViolationError, NotFoundError
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["GPS & Fleet"])


def _http(exc: BusinessRuleViolationError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.to_dict())


# ─────────────────────────────────────────────────────────────────
# Position push (driver APK)
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/gps/positions",
    response_model=GPSPositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Push GPS position (driver APK)",
    description="Called by the React Native driver APK every N seconds to record vehicle position.",
)
async def push_position(
    data: GPSPositionCreate,
    current_user: User = Depends(require_roles(["Repartidor", "Administrador"])),
    db: Session = Depends(get_db),
):
    try:
        service = GPSService(db)
        position = await service.record_from_apk(data)
        return GPSPositionResponse.model_validate(position)
    except BusinessRuleViolationError as e:
        raise _http(e)


# ─────────────────────────────────────────────────────────────────
# Wialon hardware webhook
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/gps/wialon/webhook",
    response_model=GPSPositionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Wialon GPS hardware webhook",
    description="""
    Receives position events from the Wialon GPS hardware platform.

    Authentication: `X-Wialon-Token` header must match `WIALON_WEBHOOK_TOKEN` setting.
    """,
)
async def wialon_webhook(
    payload: WialonWebhookPayload,
    x_wialon_token: Optional[str] = Header(None, alias="X-Wialon-Token"),
    db: Session = Depends(get_db),
):
    # Validate pre-shared token
    if x_wialon_token != settings.wialon_webhook_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Wialon webhook token",
        )

    try:
        service = GPSService(db)
        position = await service.record_from_wialon(payload)
        return GPSPositionResponse.model_validate(position)
    except BusinessRuleViolationError as e:
        raise _http(e)


# ─────────────────────────────────────────────────────────────────
# Fleet positions (dashboard)
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/gps/fleet",
    response_model=List[FleetPositionItem],
    summary="Latest fleet positions",
    description="Returns the most recent GPS position for each active vehicle. Used by logistics dashboard.",
)
async def get_fleet_positions(
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    service = GPSService(db)
    return service.get_fleet_positions()


@router.get(
    "/api/gps/vehicles/{vehicle_id}/track",
    response_model=List[GPSPositionResponse],
    summary="Vehicle position history",
    description="Returns the GPS breadcrumb trail for a vehicle (most recent first).",
)
async def get_vehicle_track(
    vehicle_id: UUID,
    route_id: Optional[UUID] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega", "Repartidor"])),
    db: Session = Depends(get_db),
):
    service = GPSService(db)
    positions = service.get_vehicle_track(
        vehicle_id=vehicle_id,
        route_id=route_id,
        limit=limit,
    )
    return [GPSPositionResponse.model_validate(p) for p in positions]


# ─────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/gps/alerts",
    response_model=List[GPSAlertResponse],
    summary="List GPS alerts",
)
async def list_alerts(
    unacknowledged_only: bool = Query(True),
    vehicle_id: Optional[UUID] = Query(None),
    alert_type: Optional[AlertType] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    query = db.query(GPSAlert)
    if unacknowledged_only:
        query = query.filter(GPSAlert.is_acknowledged == False)
    if vehicle_id:
        query = query.filter(GPSAlert.vehicle_id == vehicle_id)
    if alert_type:
        query = query.filter(GPSAlert.alert_type == alert_type)

    alerts = query.order_by(GPSAlert.created_at.desc()).limit(limit).all()
    return [GPSAlertResponse.model_validate(a) for a in alerts]


@router.post(
    "/api/gps/alerts/{alert_id}/ack",
    response_model=GPSAlertResponse,
    summary="Acknowledge GPS alert",
)
async def acknowledge_alert(
    alert_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    alert = db.query(GPSAlert).filter(GPSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_acknowledged = True
    alert.acknowledged_by_user_id = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return GPSAlertResponse.model_validate(alert)


# ─────────────────────────────────────────────────────────────────
# Geofences
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/gps/geofences",
    response_model=GeofenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create geofence",
)
async def create_geofence(
    data: GeofenceCreate,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    from app.models.enums import GeofenceType

    gf = Geofence(
        name=data.name,
        description=data.description,
        geofence_type=data.geofence_type,
        center_lat=data.center_lat,
        center_lon=data.center_lon,
        radius_meters=data.radius_meters,
        is_active=True,
    )
    db.add(gf)
    db.commit()
    db.refresh(gf)
    return GeofenceResponse.model_validate(gf)


@router.get(
    "/api/gps/geofences",
    response_model=List[GeofenceResponse],
    summary="List geofences",
)
async def list_geofences(
    active_only: bool = Query(True),
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    query = db.query(Geofence)
    if active_only:
        query = query.filter(Geofence.is_active == True)
    return [GeofenceResponse.model_validate(g) for g in query.all()]


@router.delete(
    "/api/gps/geofences/{geofence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate geofence",
)
async def deactivate_geofence(
    geofence_id: UUID,
    current_user: User = Depends(require_roles(["Administrador"])),
    db: Session = Depends(get_db),
):
    gf = db.query(Geofence).filter(Geofence.id == geofence_id).first()
    if not gf:
        raise HTTPException(status_code=404, detail="Geofence not found")
    gf.is_active = False
    db.commit()


# ─────────────────────────────────────────────────────────────────
# WebSocket endpoints
# ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/fleet")
async def ws_fleet(websocket: WebSocket):
    """
    WebSocket — subscribe to all vehicle positions.

    Messages received (JSON):
        { "type": "gps_position", "vehicle_id": "...", "latitude": ..., ... }
        { "type": "gps_alert",    "alert_type": "...", "vehicle_id": "...", ... }
    """
    await ws_manager.connect(websocket, room="fleet")
    try:
        while True:
            # Keep connection alive; client can send ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, room="fleet")


@router.websocket("/ws/routes/{route_id}")
async def ws_route(websocket: WebSocket, route_id: str):
    """
    WebSocket — subscribe to position updates for a specific route.

    Useful for the logistics operator watching a single active route.
    """
    await ws_manager.connect(websocket, room=route_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, room=route_id)
