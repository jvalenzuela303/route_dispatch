import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Route, RouteFilters, RouteGenerateRequest, PaginatedResponse } from '@/types'
import { routesService } from '@/services'

export const useRoutesStore = defineStore('routes', () => {
  // State
  const routes = ref<Route[]>([])
  const currentRoute = ref<Route | null>(null)
  const activeRoute = ref<Route | null>(null)
  const pagination = ref({
    page: 1,
    size: 20,
    total: 0,
    pages: 0,
  })
  const filters = ref<RouteFilters>({})
  const isLoading = ref(false)
  const isGenerating = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const pendingRoutes = computed(() =>
    routes.value.filter((r) => r.status === 'PENDIENTE')
  )

  const activeRoutes = computed(() =>
    routes.value.filter((r) => r.status === 'ACTIVA' || r.status === 'EN_PROGRESO')
  )

  const completedRoutes = computed(() =>
    routes.value.filter((r) => r.status === 'COMPLETADA')
  )

  const routesByStatus = computed(() => ({
    PENDIENTE: pendingRoutes.value.length,
    ACTIVA: activeRoutes.value.length,
    COMPLETADA: completedRoutes.value.length,
  }))

  const currentRouteProgress = computed(() => {
    if (!currentRoute.value) return 0
    const { stops_count, completed_stops } = currentRoute.value
    if (stops_count === 0) return 0
    return Math.round((completed_stops / stops_count) * 100)
  })

  // Actions
  async function fetchRoutes(page?: number): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response: PaginatedResponse<Route> = await routesService.getAll(
        page || pagination.value.page,
        pagination.value.size,
        filters.value
      )

      routes.value = response.items
      pagination.value = {
        page: response.page,
        size: response.size,
        total: response.total,
        pages: response.pages,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar rutas'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchRoute(id: string | number): Promise<Route> {
    isLoading.value = true
    error.value = null

    try {
      currentRoute.value = await routesService.getById(id)
      return currentRoute.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar ruta'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchMyRoutes(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      routes.value = await routesService.getMyRoutes(filters.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar mis rutas'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchActiveRoute(): Promise<Route | null> {
    isLoading.value = true
    error.value = null

    try {
      activeRoute.value = await routesService.getActiveRoute()
      return activeRoute.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar ruta activa'
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function generateRoute(data: RouteGenerateRequest): Promise<Route> {
    isGenerating.value = true
    error.value = null

    try {
      const response = await routesService.generate(data)
      routes.value.unshift(response.route)
      return response.route
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al generar ruta'
      throw err
    } finally {
      isGenerating.value = false
    }
  }

  async function activateRoute(id: string | number, driverId?: string | number): Promise<Route> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await routesService.activate(id, driverId)
      updateRouteInList(updated)
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al activar ruta'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function startRoute(id: string | number): Promise<Route> {
    isLoading.value = true
    error.value = null

    try {
      await routesService.start(id)
      // Fetch full detail with stops so TrackingView keeps its stops
      const updated = await routesService.getById(id)
      updateRouteInList(updated)
      activeRoute.value = updated
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al iniciar ruta'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function completeRoute(id: string | number): Promise<Route> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await routesService.complete(id)
      updateRouteInList(updated)
      if (activeRoute.value?.id === id) {
        activeRoute.value = null
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al completar ruta'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function cancelRoute(id: string | number, reason?: string): Promise<Route> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await routesService.cancel(id, reason)
      updateRouteInList(updated)
      if (activeRoute.value?.id === id) {
        activeRoute.value = null
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cancelar ruta'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function markStopDelivered(
    routeId: string | number,
    stopId: string | number,
    notes?: string
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await routesService.markStopDelivered(routeId, stopId, notes)
      // Refresh the full route (with stops) so the tracking view updates
      const updated = await routesService.getById(routeId)
      if (activeRoute.value?.id === updated.id) {
        activeRoute.value = updated
      }
      if (currentRoute.value?.id === updated.id) {
        currentRoute.value = updated
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al marcar entrega'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function reportIncident(
    routeId: string | number,
    stopId: string | number,
    reason: string
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await routesService.reportIncident(routeId, stopId, reason)
      // Refresh the full route (with stops) so the tracking view updates
      const updated = await routesService.getById(routeId)
      if (activeRoute.value?.id === updated.id) {
        activeRoute.value = updated
      }
      if (currentRoute.value?.id === updated.id) {
        currentRoute.value = updated
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al reportar incidencia'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function updateRouteInList(updated: Route): void {
    const index = routes.value.findIndex((r) => r.id === updated.id)
    if (index !== -1) {
      routes.value[index] = updated
    }
    if (currentRoute.value?.id === updated.id) {
      currentRoute.value = updated
    }
  }

  function setFilters(newFilters: RouteFilters): void {
    filters.value = newFilters
    pagination.value.page = 1
  }

  function clearFilters(): void {
    filters.value = {}
    pagination.value.page = 1
  }

  function setPage(page: number): void {
    pagination.value.page = page
  }

  function clearError(): void {
    error.value = null
  }

  function clearCurrentRoute(): void {
    currentRoute.value = null
  }

  return {
    // State
    routes,
    currentRoute,
    activeRoute,
    pagination,
    filters,
    isLoading,
    isGenerating,
    error,
    // Getters
    pendingRoutes,
    activeRoutes,
    completedRoutes,
    routesByStatus,
    currentRouteProgress,
    // Actions
    fetchRoutes,
    fetchRoute,
    fetchMyRoutes,
    fetchActiveRoute,
    generateRoute,
    activateRoute,
    startRoute,
    completeRoute,
    cancelRoute,
    markStopDelivered,
    reportIncident,
    setFilters,
    clearFilters,
    setPage,
    clearError,
    clearCurrentRoute,
  }
})
