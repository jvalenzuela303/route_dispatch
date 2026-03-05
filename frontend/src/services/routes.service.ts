import api from './api'
import type {
  Route,
  RouteFilters,
  RouteGenerateRequest,
  RouteGenerateResponse,
  RouteStop,
  RouteStatus,
  DeliveryUpdate,
  PaginatedResponse,
} from '@/types'

// ─────────────────────────────────────────────
// Response transformation helpers
// Backend field names differ from frontend types
// ─────────────────────────────────────────────

function mapStatus(backendStatus: string): RouteStatus {
  const map: Record<string, RouteStatus> = {
    DRAFT: 'PENDIENTE',
    ACTIVE: 'ACTIVA',
    COMPLETED: 'COMPLETADA',
    // Pass-through if frontend status already sent
    PENDIENTE: 'PENDIENTE',
    ACTIVA: 'ACTIVA',
    EN_PROGRESO: 'EN_PROGRESO',
    COMPLETADA: 'COMPLETADA',
    CANCELADA: 'CANCELADA',
  }
  return map[backendStatus] ?? 'PENDIENTE'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformStop(s: any): RouteStop {
  return {
    id: s.id,
    route_id: s.route_id ?? '',
    order_id: s.order?.id ?? s.order_id ?? '',
    order: s.order,
    sequence_number: s.stop_sequence ?? s.sequence_number ?? 0,
    latitude: s.latitude ?? undefined,
    longitude: s.longitude ?? undefined,
    estimated_arrival: s.estimated_arrival ?? '',
    actual_arrival: s.actual_arrival,
    status: s.delivered
      ? 'ENTREGADO'
      : s.status ?? 'PENDIENTE',
    distance_from_previous_km: s.distance_from_previous_km ?? 0,
    notes: s.notes ?? s.delivery_notes,
    incident_reason: s.incident_reason,
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformRoute(r: any): Route {
  return {
    // IDs come as UUIDs from backend – keep as-is (string)
    id: r.id,
    name: r.route_name ?? r.name ?? '',
    date: r.route_date ?? r.date ?? '',
    status: mapStatus(r.status),
    driver_id: r.assigned_driver?.id ?? r.driver_id,
    driver: r.assigned_driver
      ? {
          ...r.assigned_driver,
          full_name:
            r.assigned_driver.full_name ??
            r.assigned_driver.username ??
            '',
        }
      : r.driver,
    total_distance_km: r.total_distance_km ?? 0,
    estimated_duration_minutes: r.estimated_duration_minutes ?? 0,
    actual_duration_minutes: r.actual_duration_minutes,
    stops_count: r.stops_count ?? (Array.isArray(r.stops) ? r.stops.length : 0),
    stops: Array.isArray(r.stops) ? r.stops.map(transformStop) : [],
    completed_stops: Array.isArray(r.stops)
      ? r.stops.filter((s: any) => (s.delivered || s.status === 'ENTREGADO')).length
      : (r.completed_stops ?? 0),
    started_at: r.started_at,
    completed_at: r.completed_at,
    created_by_id: r.created_by?.id ?? r.created_by_id,
    created_by: r.created_by,
    created_at: r.created_at,
    updated_at: r.updated_at,
  }
}

// ─────────────────────────────────────────────
// Service
// ─────────────────────────────────────────────

export const routesService = {
  async getAll(
    page: number = 1,
    size: number = 20,
    filters?: RouteFilters
  ): Promise<PaginatedResponse<Route>> {
    const skip = (page - 1) * size
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: size.toString(),
    })

    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value))
        }
      })
    }

    const response = await api.get<unknown[]>(`/routes?${params}`)
    const items = (response.data ?? []).map(transformRoute)

    return {
      items,
      total: items.length,
      page,
      pages: 1,
      size,
    }
  },

  async getById(id: string | number): Promise<Route> {
    const response = await api.get<unknown>(`/routes/${id}`)
    return transformRoute(response.data)
  },

  async generate(data: RouteGenerateRequest): Promise<RouteGenerateResponse> {
    // Backend expects delivery_date (not date), and no driver_id/order_ids/name at generation time
    const payload = {
      delivery_date: data.date,
    }
    const response = await api.post<{ route: unknown }>('/routes/generate', payload)
    const raw = response.data
    return {
      route: transformRoute(raw.route ?? raw),
      optimization_details: {
        total_distance_km: 0,
        estimated_duration_minutes: 0,
        stops_sequence: [],
      },
    }
  },

  async activate(id: string | number, driverId?: string | number): Promise<Route> {
    // Backend uses POST, not PATCH; driver_id required in payload
    const payload = driverId ? { driver_id: driverId } : {}
    const response = await api.post<{ route: unknown }>(`/routes/${id}/activate`, payload)
    const raw = response.data
    return transformRoute(raw.route ?? raw)
  },

  async start(id: string | number): Promise<Route> {
    const response = await api.post<unknown>(`/routes/${id}/start`, {})
    return transformRoute(response.data)
  },

  async complete(id: string | number): Promise<Route> {
    // Backend uses PUT, not PATCH
    const response = await api.put<unknown>(`/routes/${id}/complete`)
    return transformRoute(response.data)
  },

  async cancel(id: string | number, _reason?: string): Promise<Route> {
    // No /cancel endpoint – mark as completed as best-effort
    const response = await api.put<unknown>(`/routes/${id}/complete`)
    return transformRoute(response.data)
  },

  async getMyRoutes(filters?: RouteFilters): Promise<Route[]> {
    const params = new URLSearchParams()
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value))
        }
      })
    }
    // Backend /routes already filters by assigned driver for Repartidor role
    const response = await api.get<unknown>(`/routes?${params}`)
    const data = Array.isArray(response.data) ? response.data : ((response.data as any)?.routes ?? [])
    return data.map(transformRoute)
  },

  async getActiveRoute(): Promise<Route | null> {
    try {
      // Get the first ACTIVE route assigned to current user
      const response = await api.get<unknown>('/routes?status=ACTIVE')
      const data = Array.isArray(response.data) ? response.data : ((response.data as any)?.routes ?? [])
      if (!data.length) return null
      // Fetch full detail with stops so TrackingView can render them
      const first = transformRoute(data[0])
      return await this.getById(first.id)
    } catch {
      return null
    }
  },

  async updateStopStatus(
    routeId: string | number,
    stopId: string | number,
    data: DeliveryUpdate
  ): Promise<RouteStop> {
    const response = await api.patch<RouteStop>(
      `/routes/${routeId}/stops/${stopId}`,
      data
    )
    return transformStop(response.data)
  },

  async markStopArrived(
    routeId: string | number,
    stopId: string | number
  ): Promise<RouteStop> {
    const response = await api.patch<RouteStop>(
      `/routes/${routeId}/stops/${stopId}/arrived`
    )
    return transformStop(response.data)
  },

  async markStopDelivered(
    routeId: string | number,
    stopId: string | number,
    notes?: string
  ): Promise<RouteStop> {
    const response = await api.patch<RouteStop>(
      `/routes/${routeId}/stops/${stopId}/delivered`,
      { notes }
    )
    return transformStop(response.data)
  },

  async reportIncident(
    routeId: string | number,
    stopId: string | number,
    reason: string
  ): Promise<RouteStop> {
    const response = await api.patch<RouteStop>(
      `/routes/${routeId}/stops/${stopId}/incident`,
      { incident_reason: reason }
    )
    return transformStop(response.data)
  },
}

export default routesService
