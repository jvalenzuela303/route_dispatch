import api from './api'

export interface Vehicle {
  id: string
  plate_number: string
  alias: string | null
  brand: string | null
  model_name: string | null
  year: number | null
  max_load_kg: number | null
  max_volume_m3: number | null
  status: 'AVAILABLE' | 'IN_ROUTE' | 'MAINTENANCE'
  assigned_driver_id: string | null
  gps_device_id: string | null
  active: boolean
  created_at: string
  updated_at: string
}

export interface VehicleCreate {
  plate_number: string
  alias?: string
  brand?: string
  model_name?: string
  year?: number
  max_load_kg?: number
  max_volume_m3?: number
  gps_device_id?: string
  assigned_driver_id?: string
}

export interface VehicleUpdate {
  alias?: string
  brand?: string
  model_name?: string
  year?: number
  max_load_kg?: number
  max_volume_m3?: number
  status?: 'AVAILABLE' | 'IN_ROUTE' | 'MAINTENANCE'
  gps_device_id?: string
  assigned_driver_id?: string
}

export const vehiclesService = {
  async getAll(params?: {
    include_inactive?: boolean
    status_filter?: string
    skip?: number
    limit?: number
  }): Promise<{ items: Vehicle[]; total: number }> {
    const response = await api.get<{ items: Vehicle[]; total: number }>('/vehicles', { params })
    return response.data
  },

  async getAvailable(): Promise<Vehicle[]> {
    const response = await api.get<Vehicle[]>('/vehicles/available')
    return response.data
  },

  async getById(id: string): Promise<Vehicle> {
    const response = await api.get<Vehicle>(`/vehicles/${id}`)
    return response.data
  },

  async create(data: VehicleCreate): Promise<Vehicle> {
    const response = await api.post<Vehicle>('/vehicles', data)
    return response.data
  },

  async update(id: string, data: VehicleUpdate): Promise<Vehicle> {
    const response = await api.patch<Vehicle>(`/vehicles/${id}`, data)
    return response.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/vehicles/${id}`)
  },

  async assignDriver(vehicleId: string, userId: string): Promise<Vehicle> {
    const response = await api.post<Vehicle>(`/vehicles/${vehicleId}/assign-driver`, {
      user_id: userId,
    })
    return response.data
  },

  async unassignDriver(vehicleId: string): Promise<Vehicle> {
    const response = await api.delete<Vehicle>(`/vehicles/${vehicleId}/assign-driver`)
    return response.data
  },

  async setMaintenance(vehicleId: string): Promise<Vehicle> {
    const response = await api.post<Vehicle>(`/vehicles/${vehicleId}/maintenance`)
    return response.data
  },

  async release(vehicleId: string): Promise<Vehicle> {
    const response = await api.post<Vehicle>(`/vehicles/${vehicleId}/release`)
    return response.data
  },
}

export default vehiclesService
