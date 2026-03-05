import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Order, OrderCreate, OrderUpdate, OrderFilters, PaginatedResponse } from '@/types'
import { ordersService } from '@/services'

export const useOrdersStore = defineStore('orders', () => {
  // State
  const orders = ref<Order[]>([])
  const currentOrder = ref<Order | null>(null)
  const pagination = ref({
    page: 1,
    size: 20,
    total: 0,
    pages: 0,
  })
  const filters = ref<OrderFilters>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const pendingOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'PENDIENTE')
  )

  const preparingOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'EN_PREPARACION')
  )

  const documentedOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'DOCUMENTADO')
  )

  const inRouteOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'EN_RUTA')
  )

  const deliveredOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'ENTREGADO')
  )

  const incidentOrders = computed(() =>
    orders.value.filter((o) => o.order_status === 'INCIDENCIA')
  )

  const ordersByStatus = computed(() => ({
    PENDIENTE: pendingOrders.value.length,
    EN_PREPARACION: preparingOrders.value.length,
    DOCUMENTADO: documentedOrders.value.length,
    EN_RUTA: inRouteOrders.value.length,
    ENTREGADO: deliveredOrders.value.length,
    INCIDENCIA: incidentOrders.value.length,
  }))

  // Actions
  async function fetchOrders(page?: number): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response: PaginatedResponse<Order> = await ordersService.getAll(
        page || pagination.value.page,
        pagination.value.size,
        filters.value
      )

      orders.value = response.items
      pagination.value = {
        page: response.page,
        size: response.size,
        total: response.total,
        pages: response.pages,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar pedidos'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchMyOrders(page?: number): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response = await ordersService.getMyOrders(
        page || pagination.value.page,
        pagination.value.size,
        filters.value
      )

      orders.value = response.items
      pagination.value = {
        page: response.page,
        size: response.size,
        total: response.total,
        pages: response.pages,
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar mis pedidos'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchOrder(id: string): Promise<Order> {
    isLoading.value = true
    error.value = null

    try {
      currentOrder.value = await ordersService.getById(id)
      return currentOrder.value
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar pedido'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function createOrder(data: OrderCreate): Promise<Order> {
    isLoading.value = true
    error.value = null

    try {
      const order = await ordersService.create(data)
      orders.value.unshift(order)
      return order
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al crear pedido'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateOrder(id: string, data: OrderUpdate): Promise<Order> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await ordersService.update(id, data)
      const index = orders.value.findIndex((o) => o.id === id)
      if (index !== -1) {
        orders.value[index] = updated
      }
      if (currentOrder.value?.id === id) {
        currentOrder.value = updated
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al actualizar pedido'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateOrderStatus(
    id: string,
    status: string,
    reason?: string
  ): Promise<Order> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await ordersService.updateStatus(id, status, reason)
      const index = orders.value.findIndex((o) => o.id === id)
      if (index !== -1) {
        orders.value[index] = updated
      }
      if (currentOrder.value?.id === id) {
        currentOrder.value = updated
      }
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al actualizar estado'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function deleteOrder(id: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await ordersService.delete(id)
      orders.value = orders.value.filter((o) => o.id !== id)
      if (currentOrder.value?.id === id) {
        currentOrder.value = null
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al eliminar pedido'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDocumentedOrders(date?: string): Promise<Order[]> {
    isLoading.value = true
    error.value = null

    try {
      return await ordersService.getDocumentedOrders(date)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Error al cargar pedidos documentados'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function setFilters(newFilters: OrderFilters): void {
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

  function clearCurrentOrder(): void {
    currentOrder.value = null
  }

  return {
    // State
    orders,
    currentOrder,
    pagination,
    filters,
    isLoading,
    error,
    // Getters
    pendingOrders,
    preparingOrders,
    documentedOrders,
    inRouteOrders,
    deliveredOrders,
    incidentOrders,
    ordersByStatus,
    // Actions
    fetchOrders,
    fetchMyOrders,
    fetchOrder,
    createOrder,
    updateOrder,
    updateOrderStatus,
    deleteOrder,
    fetchDocumentedOrders,
    setFilters,
    clearFilters,
    setPage,
    clearError,
    clearCurrentOrder,
  }
})
