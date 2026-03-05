import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Role, PaginatedResponse } from '@/types'
import { usersService, type UserCreate, type UserUpdate } from '@/services/users.service'

export const useUsersStore = defineStore('users', () => {
  // State
  const users = ref<User[]>([])
  const currentUser = ref<User | null>(null)
  const roles = ref<Role[]>([])
  const drivers = ref<User[]>([])
  const pagination = ref({
    page: 1,
    size: 20,
    total: 0,
    pages: 0,
  })
  const searchQuery = ref('')
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const activeUsers = computed(() => users.value.filter((u) => u.is_active))
  const inactiveUsers = computed(() => users.value.filter((u) => !u.is_active))

  const usersByRole = computed(() => {
    const byRole: Record<string, User[]> = {}
    users.value.forEach((user) => {
      const roleName = user.role?.name || 'Sin rol'
      if (!byRole[roleName]) {
        byRole[roleName] = []
      }
      byRole[roleName].push(user)
    })
    return byRole
  })

  const availableDrivers = computed(() =>
    drivers.value.filter((d) => d.is_active)
  )

  // Actions
  async function fetchUsers(page?: number): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response: PaginatedResponse<User> = await usersService.getAll(
        page || pagination.value.page,
        pagination.value.size,
        searchQuery.value || undefined
      )

      users.value = response.items
      pagination.value = {
        page: response.page,
        size: response.size,
        total: response.total,
        pages: response.pages,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar usuarios'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchUser(id: string): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      currentUser.value = await usersService.getById(id)
      return currentUser.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar usuario'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function createUser(data: UserCreate): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      const user = await usersService.create(data)
      users.value.unshift(user)
      return user
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al crear usuario'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateUser(id: string, data: UserUpdate): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await usersService.update(id, data)
      const index = users.value.findIndex((u) => u.id === id)
      if (index !== -1) {
        users.value[index] = updated
      }
      if (currentUser.value?.id === id) {
        currentUser.value = updated
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al actualizar usuario'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function deleteUser(id: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await usersService.delete(id)
      users.value = users.value.filter((u) => u.id !== id)
      if (currentUser.value?.id === id) {
        currentUser.value = null
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al eliminar usuario'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function toggleUserActive(id: string): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await usersService.toggleActive(id)
      const index = users.value.findIndex((u) => u.id === id)
      if (index !== -1) {
        users.value[index] = updated
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cambiar estado'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function resetUserPassword(id: string, newPassword: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await usersService.resetPassword(id, newPassword)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al resetear contraseña'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchRoles(): Promise<void> {
    try {
      roles.value = await usersService.getRoles()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar roles'
    }
  }

  async function fetchDrivers(): Promise<void> {
    try {
      drivers.value = await usersService.getDrivers()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar repartidores'
      throw err
    }
  }

  function setSearch(query: string): void {
    searchQuery.value = query
    pagination.value.page = 1
  }

  function setPage(page: number): void {
    pagination.value.page = page
  }

  function clearError(): void {
    error.value = null
  }

  function clearCurrentUser(): void {
    currentUser.value = null
  }

  return {
    // State
    users,
    currentUser,
    roles,
    drivers,
    pagination,
    searchQuery,
    isLoading,
    error,
    // Getters
    activeUsers,
    inactiveUsers,
    usersByRole,
    availableDrivers,
    // Actions
    fetchUsers,
    fetchUser,
    createUser,
    updateUser,
    deleteUser,
    toggleUserActive,
    resetUserPassword,
    fetchRoles,
    fetchDrivers,
    setSearch,
    setPage,
    clearError,
    clearCurrentUser,
  }
})
