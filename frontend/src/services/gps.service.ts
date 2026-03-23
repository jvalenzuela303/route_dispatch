import api from './api'

export interface FleetPosition {
  vehicle_id: string
  plate: string
  alias: string | null
  latitude: number
  longitude: number
  speed_kmh: number | null
  route_id: string | null
  last_seen: string
}

export interface GPSAlert {
  id: string
  vehicle_id: string
  route_id: string | null
  geofence_id: string | null
  alert_type: string
  message: string
  position_lat: number | null
  position_lon: number | null
  is_acknowledged: boolean
  acknowledged_by_user_id: string | null
  acknowledged_at: string | null
  created_at: string
}

export interface Geofence {
  id: string
  name: string
  description: string | null
  geofence_type: 'CIRCULAR' | 'POLYGON'
  radius_meters: number | null
  is_active: boolean
  created_at: string
}

export interface GeofenceCreate {
  name: string
  description?: string
  geofence_type: 'CIRCULAR' | 'POLYGON'
  center_lat?: number
  center_lon?: number
  radius_meters?: number
}

export const gpsService = {
  async getFleetPositions(): Promise<FleetPosition[]> {
    const response = await api.get<FleetPosition[]>('/gps/fleet')
    return response.data
  },

  async getVehicleTrack(
    vehicleId: string,
    routeId?: string,
    limit = 500
  ): Promise<{ id: string; latitude: number; longitude: number; recorded_at: string }[]> {
    const response = await api.get(`/gps/vehicles/${vehicleId}/track`, {
      params: { route_id: routeId, limit },
    })
    return response.data
  },

  async getAlerts(unacknowledgedOnly = true): Promise<GPSAlert[]> {
    const response = await api.get<GPSAlert[]>('/gps/alerts', {
      params: { unacknowledged_only: unacknowledgedOnly },
    })
    return response.data
  },

  async acknowledgeAlert(alertId: string): Promise<GPSAlert> {
    const response = await api.post<GPSAlert>(`/gps/alerts/${alertId}/ack`)
    return response.data
  },

  async getGeofences(activeOnly = true): Promise<Geofence[]> {
    const response = await api.get<Geofence[]>('/gps/geofences', {
      params: { active_only: activeOnly },
    })
    return response.data
  },

  async createGeofence(data: GeofenceCreate): Promise<Geofence> {
    const response = await api.post<Geofence>('/gps/geofences', data)
    return response.data
  },

  /** Open a WebSocket to the fleet position feed */
  connectFleetWS(
    onMessage: (data: Record<string, unknown>) => void,
    onClose?: () => void
  ): WebSocket {
    const wsBase = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
    const ws = new WebSocket(`${wsBase}/ws/fleet`)
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data))
      } catch {
        // ignore malformed messages
      }
    }
    ws.onclose = onClose || null
    // Send ping every 30s to keep alive
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30_000)
    ws.addEventListener('close', () => clearInterval(ping))
    return ws
  },

  /** Open a WebSocket for a specific route */
  connectRouteWS(
    routeId: string,
    onMessage: (data: Record<string, unknown>) => void,
    onClose?: () => void
  ): WebSocket {
    const wsBase = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
    const ws = new WebSocket(`${wsBase}/ws/routes/${routeId}`)
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data))
      } catch {
        // ignore
      }
    }
    ws.onclose = onClose || null
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30_000)
    ws.addEventListener('close', () => clearInterval(ping))
    return ws
  },
}

export default gpsService
