import api from './api'
import type { DashboardStats, ComplianceReport, AuditLog, AuditLogFilters, PaginatedResponse } from '@/types'

// Backend response types
interface BackendDailyReport {
  report_date: string
  orders_created_today: number
  orders_by_status: {
    pendiente: number
    en_preparacion: number
    documentado: number
    en_ruta: number
    entregado: number
    incidencia: number
  }
  routes: {
    total_routes: number
    active_routes: number
    completed_routes: number
    draft_routes: number
  }
  deliveries_completed_today: number
  pending_invoices: number
  orders_ready_for_routing: number
  generated_at: string
}

export const reportsService = {
  async getDashboardStats(): Promise<DashboardStats> {
    // Use daily-operations endpoint and transform to DashboardStats format
    const today = new Date().toISOString().split('T')[0]
    const response = await api.get<BackendDailyReport>(`/reports/daily-operations?report_date=${today}`)
    const data = response.data

    // Transform backend response to frontend DashboardStats format
    const totalOrders = Object.values(data.orders_by_status).reduce((a, b) => a + b, 0)

    return {
      orders: {
        total: totalOrders,
        by_status: {
          PENDIENTE: data.orders_by_status.pendiente,
          EN_PREPARACION: data.orders_by_status.en_preparacion,
          DOCUMENTADO: data.orders_by_status.documentado,
          EN_RUTA: data.orders_by_status.en_ruta,
          ENTREGADO: data.orders_by_status.entregado,
          INCIDENCIA: data.orders_by_status.incidencia,
        },
        today: data.orders_created_today,
        pending_delivery: data.orders_by_status.en_ruta + data.orders_by_status.documentado,
      },
      routes: {
        active: data.routes.active_routes,
        completed_today: data.routes.completed_routes,
        on_time_percentage: 85, // Placeholder - backend doesn't provide this
      },
      deliveries: {
        completed_today: data.deliveries_completed_today,
        incidents_today: data.orders_by_status.incidencia,
        average_delivery_time_minutes: 45, // Placeholder - backend doesn't provide this
      },
      revenue: {
        today: 0, // Placeholder - backend doesn't provide this
        this_week: 0,
        this_month: 0,
      },
    }
  },

  async getComplianceReport(dateFrom: string, dateTo: string): Promise<ComplianceReport> {
    // Backend uses start_date / end_date (not date_from / date_to)
    const response = await api.get<any>(
      `/reports/compliance?start_date=${dateFrom}&end_date=${dateTo}`
    )
    const d = response.data

    // Transform backend response → frontend ComplianceReport shape
    const cutoffPct  = Math.round((d.compliance?.cutoff_compliance  ?? 0) * 100)
    const invoicePct = Math.round((d.compliance?.invoice_compliance ?? 0) * 100)
    const delivered  = d.orders?.delivered      ?? 0
    const incidence  = d.orders?.with_incidence ?? 0
    const total      = d.orders?.total          ?? 0

    return {
      period: { from: d.period_start ?? dateFrom, to: d.period_end ?? dateTo },
      cutoff_compliance: {
        total_orders:         total,
        compliant:            Math.round(total * (d.compliance?.cutoff_compliance ?? 0)),
        overridden:           Math.round(total * (1 - (d.compliance?.cutoff_compliance ?? 1))),
        compliance_percentage: cutoffPct,
      },
      invoice_compliance: {
        orders_with_invoice:    Math.round(total * (d.compliance?.invoice_compliance ?? 0)),
        orders_without_invoice: Math.round(total * (1 - (d.compliance?.invoice_compliance ?? 1))),
        compliance_percentage:  invoicePct,
      },
      delivery_compliance: {
        on_time:             delivered,
        late:                0,
        incidents:           incidence,
        on_time_percentage:  total > 0 ? Math.round((delivered / total) * 100) : 0,
      },
      by_user: [],
    }
  },

  async getAuditLogs(
    page: number = 1,
    size: number = 50,
    filters?: AuditLogFilters
  ): Promise<PaginatedResponse<AuditLog>> {
    const params = new URLSearchParams({
      page: page.toString(),
      size: size.toString(),
    })

    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value))
        }
      })
    }

    const response = await api.get<PaginatedResponse<AuditLog>>(`/reports/audit-logs?${params}`)
    return response.data
  },

  async getOrdersReport(dateFrom: string, dateTo: string): Promise<Blob> {
    const response = await api.get(
      `/reports/orders/export?date_from=${dateFrom}&date_to=${dateTo}`,
      { responseType: 'blob' }
    )
    return response.data
  },

  async getDeliveriesReport(dateFrom: string, dateTo: string): Promise<Blob> {
    const response = await api.get(
      `/reports/deliveries/export?date_from=${dateFrom}&date_to=${dateTo}`,
      { responseType: 'blob' }
    )
    return response.data
  },
}

export default reportsService
