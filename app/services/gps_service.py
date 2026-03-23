"""
GPS Service — position recording, geofence checks, alert generation

Handles:
- Recording GPS positions from driver APK or Wialon hardware webhook
- Broadcasting positions via WebSocket
- Basic geofence entry/exit detection (circular only for Phase 2)
- Speed alert detection
"""

import asyncio
import math
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Vehicle, GPSPosition, Geofence, GPSAlert
from app.models.enums import VehicleStatus, AlertType, GeofenceType
from app.schemas.vehicle_schemas import GPSPositionCreate, WialonWebhookPayload
from app.exceptions import NotFoundError, ValidationError
from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Speed threshold for SPEEDING alert (km/h)
SPEED_ALERT_KMH = 80.0


class GPSService:
    """
    Record GPS positions and run real-time checks.

    Source field values:
        "apk"      → position pushed by driver React Native app
        "wialon"   → position received from Wialon hardware webhook
        "browser"  → position from browser Geolocation API (Phase 1 fallback)
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────
    # Public: record position
    # ─────────────────────────────────────────────────────────────────

    async def record_position(
        self,
        vehicle_id: UUID,
        latitude: float,
        longitude: float,
        speed_kmh: Optional[float],
        heading_degrees: Optional[float],
        accuracy_m: Optional[float],
        altitude_m: Optional[float],
        route_id: Optional[UUID],
        source: str,
        recorded_at: Optional[datetime] = None,
    ) -> GPSPosition:
        """
        Persist GPS position and trigger real-time broadcast + checks.

        Raises:
            NotFoundError: Vehicle not found or inactive
        """
        vehicle = (
            self.db.query(Vehicle)
            .filter(Vehicle.id == vehicle_id, Vehicle.active == True)
            .first()
        )
        if not vehicle:
            raise NotFoundError(
                code="VEHICLE_NOT_FOUND",
                message=f"Vehicle {vehicle_id} not found",
            )

        ts = recorded_at or datetime.now(timezone.utc)

        position = GPSPosition(
            vehicle_id=vehicle_id,
            route_id=route_id,
            latitude=Decimal(str(latitude)),
            longitude=Decimal(str(longitude)),
            speed_kmh=Decimal(str(speed_kmh)) if speed_kmh is not None else None,
            heading_degrees=Decimal(str(heading_degrees)) if heading_degrees is not None else None,
            accuracy_m=Decimal(str(accuracy_m)) if accuracy_m is not None else None,
            altitude_m=Decimal(str(altitude_m)) if altitude_m is not None else None,
            source=source,
            recorded_at=ts,
        )

        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)

        # Run checks and broadcast asynchronously (non-blocking)
        try:
            await self._post_position_hooks(vehicle, position)
        except Exception as e:
            logger.warning("post_position_hooks error: %s", e)

        return position

    async def record_from_apk(self, data: GPSPositionCreate) -> GPSPosition:
        """Wrapper for positions pushed by the driver APK."""
        return await self.record_position(
            vehicle_id=data.vehicle_id,
            latitude=data.latitude,
            longitude=data.longitude,
            speed_kmh=data.speed_kmh,
            heading_degrees=data.heading_degrees,
            accuracy_m=data.accuracy_m,
            altitude_m=data.altitude_m,
            route_id=data.route_id,
            source="apk",
            recorded_at=data.recorded_at,
        )

    async def record_from_wialon(self, payload: WialonWebhookPayload) -> GPSPosition:
        """
        Map a Wialon hardware webhook payload to a position record.

        Looks up vehicle by gps_device_id == payload.unit_id.
        """
        vehicle = (
            self.db.query(Vehicle)
            .filter(
                Vehicle.gps_device_id == payload.unit_id,
                Vehicle.active == True,
            )
            .first()
        )
        if not vehicle:
            raise NotFoundError(
                code="VEHICLE_NOT_FOUND",
                message=f"No active vehicle with gps_device_id='{payload.unit_id}'",
            )

        recorded_at = datetime.fromtimestamp(payload.ts, tz=timezone.utc)

        return await self.record_position(
            vehicle_id=vehicle.id,
            latitude=payload.lat,
            longitude=payload.lon,
            speed_kmh=payload.speed,
            heading_degrees=payload.course,
            accuracy_m=None,
            altitude_m=payload.altitude,
            route_id=vehicle.routes[-1].id if vehicle.routes else None,
            source="wialon",
            recorded_at=recorded_at,
        )

    # ─────────────────────────────────────────────────────────────────
    # Public: queries
    # ─────────────────────────────────────────────────────────────────

    def get_fleet_positions(self) -> List[dict]:
        """
        Return latest GPS position per active vehicle.
        Used by the logistics dashboard fleet view.
        """
        from sqlalchemy import func, text

        # Subquery: latest position id per vehicle
        subq = (
            self.db.query(
                GPSPosition.vehicle_id,
                func.max(GPSPosition.recorded_at).label("last_seen"),
            )
            .group_by(GPSPosition.vehicle_id)
            .subquery()
        )

        rows = (
            self.db.query(GPSPosition, Vehicle)
            .join(subq, (GPSPosition.vehicle_id == subq.c.vehicle_id) &
                         (GPSPosition.recorded_at == subq.c.last_seen))
            .join(Vehicle, Vehicle.id == GPSPosition.vehicle_id)
            .filter(Vehicle.active == True)
            .all()
        )

        result = []
        for pos, veh in rows:
            result.append({
                "vehicle_id": str(veh.id),
                "plate": veh.plate_number,
                "alias": veh.alias,
                "latitude": float(pos.latitude),
                "longitude": float(pos.longitude),
                "speed_kmh": float(pos.speed_kmh) if pos.speed_kmh else None,
                "route_id": str(pos.route_id) if pos.route_id else None,
                "last_seen": pos.recorded_at.isoformat(),
            })
        return result

    def get_vehicle_track(
        self,
        vehicle_id: UUID,
        route_id: Optional[UUID] = None,
        limit: int = 500,
    ) -> List[GPSPosition]:
        """Return recent positions for a vehicle (GPS breadcrumb trail)."""
        query = (
            self.db.query(GPSPosition)
            .filter(GPSPosition.vehicle_id == vehicle_id)
        )
        if route_id:
            query = query.filter(GPSPosition.route_id == route_id)

        return (
            query.order_by(GPSPosition.recorded_at.desc())
            .limit(limit)
            .all()
        )

    # ─────────────────────────────────────────────────────────────────
    # Internal: post-position hooks
    # ─────────────────────────────────────────────────────────────────

    async def _post_position_hooks(self, vehicle: Vehicle, position: GPSPosition) -> None:
        """Run after every new position: broadcast + speed check + geofence check."""
        from app.services.websocket_manager import ws_manager

        # 1. Broadcast to WebSocket subscribers
        await ws_manager.broadcast_position(
            vehicle_id=str(vehicle.id),
            plate=vehicle.plate_number,
            alias=vehicle.alias,
            latitude=float(position.latitude),
            longitude=float(position.longitude),
            speed_kmh=float(position.speed_kmh) if position.speed_kmh else None,
            route_id=str(position.route_id) if position.route_id else None,
            recorded_at=position.recorded_at,
        )

        # 2. Speed alert
        if position.speed_kmh and float(position.speed_kmh) > SPEED_ALERT_KMH:
            await self._create_alert(
                vehicle=vehicle,
                position=position,
                alert_type=AlertType.SPEEDING,
                message=(
                    f"Velocidad excesiva: {float(position.speed_kmh):.0f} km/h "
                    f"(límite {SPEED_ALERT_KMH:.0f} km/h)"
                ),
            )

        # 3. Circular geofence checks
        await self._check_geofences(vehicle, position)

    async def _check_geofences(self, vehicle: Vehicle, position: GPSPosition) -> None:
        """Check circular geofences — create ENTRY/EXIT alerts as needed."""
        geofences = (
            self.db.query(Geofence)
            .filter(
                Geofence.is_active == True,
                Geofence.geofence_type == GeofenceType.CIRCULAR,
            )
            .all()
        )

        lat = float(position.latitude)
        lon = float(position.longitude)

        for gf in geofences:
            if gf.center_lat is None or gf.center_lon is None or gf.radius_meters is None:
                continue

            dist = _haversine_m(lat, lon, float(gf.center_lat), float(gf.center_lon))
            inside = dist <= float(gf.radius_meters)

            if inside:
                # Emit entry alert (simple: always emit; production would track state)
                await self._create_alert(
                    vehicle=vehicle,
                    position=position,
                    alert_type=AlertType.GEOFENCE_ENTRY,
                    message=f"Vehículo entró a zona '{gf.name}'",
                    geofence_id=gf.id,
                )

    async def _create_alert(
        self,
        vehicle: Vehicle,
        position: GPSPosition,
        alert_type: AlertType,
        message: str,
        geofence_id=None,
    ) -> None:
        """Persist a GPS alert and broadcast to WebSocket."""
        from app.services.websocket_manager import ws_manager

        alert = GPSAlert(
            vehicle_id=vehicle.id,
            route_id=position.route_id,
            geofence_id=geofence_id,
            alert_type=alert_type,
            message=message,
            position_lat=position.latitude,
            position_lon=position.longitude,
            is_acknowledged=False,
        )
        self.db.add(alert)
        self.db.commit()

        # Broadcast alert to dashboard
        await ws_manager.broadcast_alert(
            alert_type=alert_type.value,
            vehicle_id=str(vehicle.id),
            plate=vehicle.plate_number,
            message=message,
            route_id=str(position.route_id) if position.route_id else None,
        )


# ─────────────────────────────────────────────────────────────────
# Geometry helper
# ─────────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two WGS-84 points."""
    R = 6_371_000  # Earth radius in metres
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
