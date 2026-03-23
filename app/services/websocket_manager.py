"""
WebSocket Manager — real-time GPS position broadcast

Maintains active WebSocket connections and broadcasts fleet position
updates to the logistics dashboard in real time.

Architecture:
  - Each client subscribes to a "room": either "fleet" (all vehicles)
    or a specific route_id (single route tracking)
  - GPS service calls broadcast_position() every time a new position
    is recorded — all subscribers receive the update immediately
  - Connections are cleaned up automatically on disconnect

Thread safety: FastAPI/Starlette runs async, so a plain dict is safe
for managing connections within the single async event loop.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Singleton-style manager for active WebSocket connections.

    Rooms:
        "fleet"          → logistics dashboard watching all vehicles
        "<route_id>"     → subscriber watching one specific route
    """

    def __init__(self):
        # room_id → set of active WebSocket connections
        self._rooms: Dict[str, Set[WebSocket]] = {}

    # ─────────────────────────────────────────────────────────────────
    # Connection lifecycle
    # ─────────────────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, room: str) -> None:
        """Accept connection and add to room."""
        await websocket.accept()
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(websocket)
        logger.info("WS connected: room=%s total=%d", room, len(self._rooms[room]))

    def disconnect(self, websocket: WebSocket, room: str) -> None:
        """Remove connection from room."""
        if room in self._rooms:
            self._rooms[room].discard(websocket)
            if not self._rooms[room]:
                del self._rooms[room]
        logger.info("WS disconnected: room=%s", room)

    # ─────────────────────────────────────────────────────────────────
    # Broadcasting
    # ─────────────────────────────────────────────────────────────────

    async def broadcast_position(
        self,
        vehicle_id: str,
        plate: str,
        alias: str | None,
        latitude: float,
        longitude: float,
        speed_kmh: float | None,
        route_id: str | None,
        recorded_at: datetime,
    ) -> None:
        """
        Broadcast a GPS position update to all relevant rooms.

        Sends to:
        - "fleet" room (always)
        - "<route_id>" room (when the vehicle is on a route)
        """
        payload = {
            "type": "gps_position",
            "vehicle_id": vehicle_id,
            "plate": plate,
            "alias": alias,
            "latitude": latitude,
            "longitude": longitude,
            "speed_kmh": speed_kmh,
            "route_id": route_id,
            "recorded_at": recorded_at.isoformat(),
        }
        message = json.dumps(payload)

        rooms_to_notify = {"fleet"}
        if route_id:
            rooms_to_notify.add(route_id)

        for room in rooms_to_notify:
            await self._broadcast_to_room(room, message)

    async def broadcast_alert(
        self,
        alert_type: str,
        vehicle_id: str,
        plate: str,
        message: str,
        route_id: str | None = None,
    ) -> None:
        """Broadcast a GPS alert to fleet room and optional route room."""
        payload = {
            "type": "gps_alert",
            "alert_type": alert_type,
            "vehicle_id": vehicle_id,
            "plate": plate,
            "message": message,
            "route_id": route_id,
        }
        raw = json.dumps(payload)

        rooms_to_notify = {"fleet"}
        if route_id:
            rooms_to_notify.add(route_id)

        for room in rooms_to_notify:
            await self._broadcast_to_room(room, raw)

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    async def _broadcast_to_room(self, room: str, message: str) -> None:
        """Send message to all connections in a room, removing dead ones."""
        if room not in self._rooms:
            return

        dead: Set[WebSocket] = set()
        for ws in list(self._rooms[room]):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._rooms[room].discard(ws)
        if room in self._rooms and not self._rooms[room]:
            del self._rooms[room]

    def active_connections(self) -> Dict[str, int]:
        """Return dict of room → connection count for monitoring."""
        return {room: len(conns) for room, conns in self._rooms.items()}


# Singleton instance — imported by main.py and gps routes
ws_manager = WebSocketManager()
