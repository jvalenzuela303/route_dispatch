import api from './api'
import type { User, Role, PaginatedResponse } from '@/types'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function transformUser(u: any): User {
  return {
    ...u,
    full_name: u.full_name ?? u.username ?? '',
    is_active: u.is_active ?? u.active_status ?? false,
    role: u.role
      ? { ...u.role, name: u.role.name ?? u.role.role_name ?? '' }
      : u.role,
  }
}

export interface UserCreate {
  email: string
  password: string
  full_name: string
  role_id: string // UUID
}

export interface UserUpdate {
  email?: string
  username?: string    // backend field name
  full_name?: string   // alias mapped to username on submit
  role_id?: string     // UUID
  is_active?: boolean  // mapped to active_status on submit
}

export const usersService = {
  async getAll(
    page: number = 1,
    size: number = 20,
    search?: string
  ): Promise<PaginatedResponse<User>> {
    // Backend uses skip/limit instead of page/size
    const skip = (page - 1) * size
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: size.toString(),
    })

    if (search) {
      params.append('search', search)
    }

    // Backend returns array, we wrap it in paginated format
    const response = await api.get<unknown[]>(`/users?${params}`)
    const items = (response.data ?? []).map(transformUser)

    return {
      items,
      total: items.length,
      page,
      pages: 1,
      size,
    }
  },

  async getById(id: string): Promise<User> {
    const response = await api.get<unknown>(`/users/${id}`)
    return transformUser(response.data)
  },

  async create(data: UserCreate): Promise<User> {
    const response = await api.post<unknown>('/users', data)
    return transformUser(response.data)
  },

  async update(id: string, data: UserUpdate): Promise<User> {
    // Map frontend field names to backend field names
    const payload: Record<string, unknown> = {
      ...(data.email !== undefined && { email: data.email }),
      ...(data.role_id !== undefined && { role_id: data.role_id }),
      ...((data.username || data.full_name) !== undefined && {
        username: data.username || data.full_name,
      }),
      ...(data.is_active !== undefined && { active_status: data.is_active }),
    }
    const response = await api.put<unknown>(`/users/${id}`, payload)
    return transformUser(response.data)
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/users/${id}`)
  },

  async toggleActive(id: string): Promise<User> {
    const response = await api.patch<unknown>(`/users/${id}/toggle-active`)
    return transformUser(response.data)
  },

  async resetPassword(id: string, newPassword: string): Promise<void> {
    // Backend: PUT /users/{id}/password with { new_password }
    await api.put(`/users/${id}/password`, {
      new_password: newPassword,
    })
  },

  async getRoles(): Promise<Role[]> {
    const response = await api.get<Role[]>('/users/roles')
    return response.data
  },

  async getDrivers(): Promise<User[]> {
    const response = await api.get<unknown[]>('/users/drivers')
    return (response.data ?? []).map(transformUser)
  },
}

export default usersService
