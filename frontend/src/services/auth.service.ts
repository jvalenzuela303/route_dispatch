import api, { setTokens, clearTokens } from './api'
import type { LoginRequest, LoginResponse, User } from '@/types'

export const authService = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    // Backend expects JSON with username field (accepts email or username)
    const response = await api.post<LoginResponse>('/auth/login', {
      username: credentials.email,
      password: credentials.password,
    })

    const { access_token, refresh_token } = response.data
    setTokens(access_token, refresh_token)

    return response.data
  },

  async logout(): Promise<void> {
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        await api.post('/auth/logout', { refresh_token: refreshToken })
      }
    } catch {
      // Ignore logout errors
    } finally {
      clearTokens()
    }
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me')
    return response.data
  },

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })

    const { access_token, refresh_token: newRefreshToken } = response.data
    setTokens(access_token, newRefreshToken)

    return response.data
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
}

export default authService
