import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, RoleName, LoginRequest } from '@/types'
import { authService, getAccessToken, clearTokens } from '@/services'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!user.value && !!getAccessToken())
  const userRole = computed<RoleName | null>(() => user.value?.role?.name || null)
  const userId = computed(() => user.value?.id || null)
  const userName = computed(() => user.value?.full_name || '')

  const isAdmin = computed(() => userRole.value === 'Administrador')
  const isWarehouseManager = computed(() => userRole.value === 'Encargado de Bodega')
  const isSeller = computed(() => userRole.value === 'Vendedor')
  const isDriver = computed(() => userRole.value === 'Repartidor')

  const canManageUsers = computed(() => isAdmin.value)
  const canManageRoutes = computed(() => isAdmin.value || isWarehouseManager.value)
  const canCreateOrders = computed(() => isAdmin.value || isWarehouseManager.value || isSeller.value)
  const canCreateInvoices = computed(() => isAdmin.value || isWarehouseManager.value || isSeller.value)
  const canViewReports = computed(() => isAdmin.value || isWarehouseManager.value)
  const canViewAuditLogs = computed(() => isAdmin.value)

  // Actions
  async function login(credentials: LoginRequest): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // Login returns tokens, then fetch user data
      await authService.login(credentials)
      // Fetch user info after successful login
      await fetchCurrentUser()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al iniciar sesión'
      error.value = message
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await authService.logout()
    } finally {
      user.value = null
      clearTokens()
    }
  }

  async function fetchCurrentUser(): Promise<void> {
    if (!getAccessToken()) {
      user.value = null
      return
    }

    isLoading.value = true
    try {
      user.value = await authService.getCurrentUser()
    } catch {
      user.value = null
      clearTokens()
    } finally {
      isLoading.value = false
    }
  }

  async function checkAuth(): Promise<boolean> {
    if (!getAccessToken()) {
      return false
    }

    if (!user.value) {
      await fetchCurrentUser()
    }

    return isAuthenticated.value
  }

  function hasRole(roles: RoleName[]): boolean {
    if (!userRole.value) return false
    return roles.includes(userRole.value)
  }

  function hasPermission(permission: string): boolean {
    if (!user.value?.role?.permissions) return false
    return !!user.value.role.permissions[permission]
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    user,
    isLoading,
    error,
    // Getters
    isAuthenticated,
    userRole,
    userId,
    userName,
    isAdmin,
    isWarehouseManager,
    isSeller,
    isDriver,
    canManageUsers,
    canManageRoutes,
    canCreateOrders,
    canCreateInvoices,
    canViewReports,
    canViewAuditLogs,
    // Actions
    login,
    logout,
    fetchCurrentUser,
    checkAuth,
    hasRole,
    hasPermission,
    clearError,
  }
})
