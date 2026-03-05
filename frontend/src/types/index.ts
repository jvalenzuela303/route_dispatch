// ============================================
// Auth Types
// ============================================
export interface User {
  id: string // UUID
  email: string
  full_name: string
  role_id: string // UUID
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Role {
  id: string // UUID
  name: RoleName
  description: string
  permissions: Record<string, boolean>
}

export type RoleName = 'Administrador' | 'Encargado de Bodega' | 'Vendedor' | 'Repartidor'

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface RefreshTokenRequest {
  refresh_token: string
}

// ============================================
// Order Types
// ============================================
export type OrderStatus =
  | 'PENDIENTE'
  | 'EN_PREPARACION'
  | 'DOCUMENTADO'
  | 'EN_RUTA'
  | 'ENTREGADO'
  | 'INCIDENCIA'

export interface Order {
  id: string // UUID
  order_number: string
  customer_name: string
  customer_phone: string
  customer_email?: string
  address_text: string
  document_number: string
  notes?: string                              // backend field (not delivery_notes)
  order_status: OrderStatus
  source_channel?: 'WEB' | 'RRSS' | 'PRESENCIAL'
  delivery_date?: string
  geocoding_confidence?: 'HIGH' | 'MEDIUM' | 'LOW' | 'INVALID'
  created_by_id?: string // UUID
  created_by?: { id: string; username: string; email: string } // UserBasic from backend
  assigned_driver_id?: string // UUID
  assigned_driver?: User
  assigned_route?: { id: string; route_name: string; route_date: string } | null
  route_stop?: RouteStop
  created_at: string
  updated_at?: string
}

export interface OrderCreate {
  customer_name: string
  customer_phone: string
  customer_email?: string
  address_text: string                              // backend field name
  notes?: string                                    // backend field name (not delivery_notes)
  document_number: string
  source_channel: 'WEB' | 'RRSS' | 'PRESENCIAL'   // required by backend
  override_delivery_date?: string                   // optional override
  override_reason?: string
}

export interface OrderUpdate {
  customer_name?: string
  customer_phone?: string
  customer_email?: string
  address_text?: string
  notes?: string
  document_number?: string
}

export interface OrderFilters {
  status?: OrderStatus
  priority?: string
  date_from?: string
  date_to?: string
  search?: string
  created_by_id?: string // UUID
  assigned_driver_id?: string // UUID
}

// ============================================
// Route Types
// ============================================
export type RouteStatus = 'PENDIENTE' | 'ACTIVA' | 'EN_PROGRESO' | 'COMPLETADA' | 'CANCELADA'

export interface Route {
  id: string // UUID
  name: string
  date: string
  status: RouteStatus
  driver_id?: string // UUID
  driver?: User
  total_distance_km: number
  estimated_duration_minutes: number
  actual_duration_minutes?: number
  stops_count: number
  completed_stops: number
  stops: RouteStop[]
  started_at?: string
  completed_at?: string
  created_by_id: string // UUID
  created_by?: User
  created_at: string
  updated_at: string
}

export interface RouteStop {
  id: string // UUID
  route_id: string // UUID
  order_id: string // UUID
  order?: Order
  sequence_number: number
  latitude?: number  // coordinates from backend stop
  longitude?: number
  estimated_arrival: string
  actual_arrival?: string
  status: 'PENDIENTE' | 'EN_CAMINO' | 'LLEGADO' | 'ENTREGADO' | 'INCIDENCIA'
  distance_from_previous_km: number
  notes?: string
  signature_url?: string
  photo_url?: string
  incident_reason?: string
}

export interface RouteGenerateRequest {
  date: string
  driver_id: string // UUID
  order_ids: string[] // UUIDs
}

export interface RouteGenerateResponse {
  route: Route
  optimization_details: {
    total_distance_km: number
    estimated_duration_minutes: number
    stops_sequence: number[]
  }
}

export interface RouteFilters {
  status?: RouteStatus
  driver_id?: string // UUID
  date_from?: string
  date_to?: string
}

export interface DeliveryUpdate {
  status: 'ENTREGADO' | 'INCIDENCIA'
  notes?: string
  incident_reason?: string
}

// ============================================
// Report Types
// ============================================
export interface DashboardStats {
  orders: {
    total: number
    by_status: Record<OrderStatus, number>
    today: number
    pending_delivery: number
  }
  routes: {
    active: number
    completed_today: number
    on_time_percentage: number
  }
  deliveries: {
    completed_today: number
    incidents_today: number
    average_delivery_time_minutes: number
  }
  revenue: {
    today: number
    this_week: number
    this_month: number
  }
}

export interface ComplianceReport {
  period: {
    from: string
    to: string
  }
  cutoff_compliance: {
    total_orders: number
    compliant: number
    overridden: number
    compliance_percentage: number
  }
  invoice_compliance: {
    orders_with_invoice: number
    orders_without_invoice: number
    compliance_percentage: number
  }
  delivery_compliance: {
    on_time: number
    late: number
    incidents: number
    on_time_percentage: number
  }
  by_user: Array<{
    user_id: string // UUID
    user_name: string
    orders_created: number
    cutoff_overrides: number
  }>
}

export interface AuditLog {
  id: string // UUID
  user_id: string // UUID
  user?: User
  action: string
  entity_type: string
  entity_id: string // UUID
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface AuditLogFilters {
  user_id?: string // UUID
  action?: string
  entity_type?: string
  date_from?: string
  date_to?: string
}

// ============================================
// API Response Types
// ============================================
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ApiError {
  detail: string
  status_code?: number
  errors?: Record<string, string[]>
}

// ============================================
// UI Types
// ============================================
export interface MenuItem {
  name: string
  path: string
  icon: string
  roles: RoleName[]
  children?: MenuItem[]
}

export interface Notification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  duration?: number
}

export interface TableColumn<T = unknown> {
  key: keyof T | string
  label: string
  sortable?: boolean
  width?: string
  render?: (value: unknown, row: T) => string
}

export interface SelectOption {
  value: string | number
  label: string
  disabled?: boolean
}
