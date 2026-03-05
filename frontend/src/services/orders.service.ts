import api from './api'
import type { Order, OrderCreate, OrderUpdate, OrderFilters, PaginatedResponse } from '@/types'

export const ordersService = {
  async getAll(
    page: number = 1,
    size: number = 20,
    filters?: OrderFilters
  ): Promise<PaginatedResponse<Order>> {
    // Backend uses skip/limit instead of page/size
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

    // Backend returns array, we wrap it in paginated format
    const response = await api.get<Order[]>(`/orders?${params}`)
    const items = response.data

    return {
      items,
      total: items.length,
      page,
      pages: 1, // Backend doesn't return total count
      size,
    }
  },

  async getById(id: string): Promise<Order> {
    const response = await api.get<Order>(`/orders/${id}`)
    return response.data
  },

  async create(data: OrderCreate): Promise<Order> {
    // Backend returns { order, warnings, next_steps, ... }
    const response = await api.post<{ order: Order } | Order>('/orders', data)
    const raw = response.data as any
    return raw.order ?? raw
  },

  async update(id: string, data: OrderUpdate): Promise<Order> {
    const response = await api.patch<Order>(`/orders/${id}`, data)
    return response.data
  },

  async updateStatus(id: string, status: string, reason?: string): Promise<Order> {
    const response = await api.put<Order>(`/orders/${id}/status`, {
      new_status: status,
      reason,
    })
    return response.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/orders/${id}`)
  },

  async getMyOrders(
    page: number = 1,
    size: number = 20,
    filters?: OrderFilters
  ): Promise<PaginatedResponse<Order>> {
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

    // Backend returns array, we wrap it in paginated format
    const response = await api.get<Order[]>(`/orders/my-orders?${params}`)
    const items = response.data

    return {
      items,
      total: items.length,
      page,
      pages: 1,
      size,
    }
  },

  async getDocumentedOrders(date?: string): Promise<Order[]> {
    let url: string
    if (date) {
      // Backend endpoint: GET /orders/ready-for-routing/delivery-date/{date}
      url = `/orders/ready-for-routing/delivery-date/${date}`
    } else {
      // Fallback: get all DOCUMENTADO orders
      url = `/orders/status/DOCUMENTADO/list`
    }
    const response = await api.get<Order[]>(url)
    // Map total_amount from nested invoice if not present at root level
    return (response.data ?? []).map((o: any) => ({
      ...o,
      total_amount: o.total_amount ?? o.invoice?.total_amount ?? 0,
    }))
  },

  async checkCutoff(deliveryDate: string): Promise<{ eligible: boolean; message: string }> {
    const response = await api.get<{ eligible: boolean; message: string }>(
      `/orders/check-cutoff?delivery_date=${deliveryDate}`
    )
    return response.data
  },
}

export default ordersService
