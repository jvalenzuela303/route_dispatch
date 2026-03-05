<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRoutesStore } from '@/stores/routes'
import { useOrdersStore } from '@/stores/orders'
import { useUsersStore } from '@/stores/users'
import { useNotificationsStore } from '@/stores/notifications'
import type { Order, RouteGenerateRequest } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  ArrowLeftIcon,
  TruckIcon,
  MapPinIcon,
  CheckIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'

const router = useRouter()
const routesStore = useRoutesStore()
const ordersStore = useOrdersStore()
const usersStore = useUsersStore()
const notifications = useNotificationsStore()

const isLoading = ref(true)
const isGenerating = ref(false)
const allDocumentedOrders = ref<Order[]>([])   // todos los DOCUMENTADO, sin filtro
const selectedOrderIds = ref<string[]>([])

const allDrivers = computed(() => usersStore.availableDrivers)

const form = ref<Partial<RouteGenerateRequest>>({
  date: format(new Date(), 'yyyy-MM-dd'),
  driver_id: undefined,
  order_ids: [],
})

const errors = ref<Record<string, string>>({})

// Fechas disponibles entre los pedidos documentados (para mostrar al usuario)
const availableDates = computed(() => {
  const dates = new Set(
    allDocumentedOrders.value
      .filter((o) => o.delivery_date)
      .map((o) => o.delivery_date as string)
  )
  return Array.from(dates).sort()
})

// Pedidos filtrados por la fecha seleccionada en el formulario
const documentedOrders = computed(() =>
  allDocumentedOrders.value.filter((o) => o.delivery_date === form.value.date)
)

onMounted(async () => {
  try {
    await Promise.all([loadAllDocumentedOrders(), usersStore.fetchDrivers()])
  } catch (error) {
    console.error('Error initializing:', error)
  } finally {
    isLoading.value = false
  }
})

const loadAllDocumentedOrders = async () => {
  try {
    // Cargamos SIN filtro de fecha para ver todos los pedidos disponibles
    allDocumentedOrders.value = await ordersStore.fetchDocumentedOrders(undefined)
    // Si hay pedidos disponibles, pre-seleccionamos la primera fecha con pedidos
    if (availableDates.value.length > 0 && !availableDates.value.includes(form.value.date!)) {
      form.value.date = availableDates.value[0]
    }
  } catch (error) {
    console.error('Error loading orders:', error)
  }
}

const isValid = computed(() =>
  !!form.value.driver_id &&
  !!form.value.date &&
  documentedOrders.value.length > 0
)

const toggleOrder = (orderId: string) => {
  const index = selectedOrderIds.value.indexOf(orderId)
  if (index === -1) {
    selectedOrderIds.value.push(orderId)
  } else {
    selectedOrderIds.value.splice(index, 1)
  }
}

const selectAll = () => {
  if (selectedOrderIds.value.length === documentedOrders.value.length) {
    selectedOrderIds.value = []
  } else {
    selectedOrderIds.value = documentedOrders.value.map((o) => o.id)
  }
}

const validateForm = (): boolean => {
  errors.value = {}

  if (documentedOrders.value.length === 0) {
    errors.value.orders = 'No hay pedidos documentados para la fecha seleccionada'
  }

  if (!form.value.driver_id) {
    errors.value.driver_id = 'Selecciona un repartidor'
  }

  if (!form.value.date) {
    errors.value.date = 'Selecciona una fecha de entrega'
  }

  return Object.keys(errors.value).length === 0
}

const handleSubmit = async () => {
  if (!validateForm() || isGenerating.value) return

  isGenerating.value = true

  try {
    // Step 1: Generate route — backend uses delivery_date to auto-include
    // all DOCUMENTADO orders for that date (order_ids/name ignored by backend)
    const routeData: RouteGenerateRequest = {
      date: form.value.date!,
      driver_id: form.value.driver_id!,
      order_ids: selectedOrderIds.value,
    }

    const route = await routesStore.generateRoute(routeData)

    // Step 2: Immediately activate with the selected driver
    // (backend separates generate and activate steps)
    if (form.value.driver_id) {
      await routesStore.activateRoute(route.id, form.value.driver_id)
      notifications.success(
        'Ruta generada y activada',
        `Ruta con ${route.stops_count} paradas asignada al repartidor.`
      )
    } else {
      notifications.success(
        'Ruta generada',
        `Se creó la ruta con ${route.stops_count} paradas optimizadas.`
      )
    }

    router.push(`/routes/${route.id}`)
  } catch (error) {
    notifications.error('Error', 'No se pudo generar la ruta. Verifica que los pedidos tengan coordenadas válidas.')
  } finally {
    isGenerating.value = false
  }
}

</script>

<template>
  <div class="max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center space-x-4 mb-6">
      <button
        class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        @click="router.back()"
      >
        <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
      </button>
      <div>
        <h1 class="page-title">Generar Ruta</h1>
        <p class="page-description">Selecciona pedidos y asigna un repartidor</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando pedidos documentados..." />
    </div>

    <template v-else>
      <form @submit.prevent="handleSubmit">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Left: Orders selection -->
          <div class="lg:col-span-2 space-y-6">
            <div class="card">
              <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-gray-900">
                  Pedidos Documentados
                </h2>
                <button
                  type="button"
                  class="text-sm text-primary-600 hover:text-primary-700"
                  @click="selectAll"
                >
                  {{ selectedOrderIds.length === documentedOrders.length ? 'Deseleccionar todos' : 'Seleccionar todos' }}
                </button>
              </div>

              <p v-if="errors.orders" class="mb-4 text-sm text-danger-600">
                {{ errors.orders }}
              </p>

              <!-- Orders list -->
              <div v-if="documentedOrders.length > 0" class="space-y-3 max-h-96 overflow-y-auto">
                <div
                  v-for="order in documentedOrders"
                  :key="order.id"
                  :class="[
                    'p-4 border rounded-xl cursor-pointer transition-all',
                    selectedOrderIds.includes(order.id)
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300',
                  ]"
                  @click="toggleOrder(order.id)"
                >
                  <div class="flex items-start">
                    <div
                      :class="[
                        'w-5 h-5 rounded border-2 flex items-center justify-center mr-3 mt-0.5 transition-colors',
                        selectedOrderIds.includes(order.id)
                          ? 'bg-primary-500 border-primary-500'
                          : 'border-gray-300',
                      ]"
                    >
                      <CheckIcon
                        v-if="selectedOrderIds.includes(order.id)"
                        class="w-3 h-3 text-white"
                      />
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center justify-between">
                        <p class="font-medium text-gray-900">{{ order.customer_name }}</p>
                        <StatusBadge :status="order.order_status" size="sm" />
                      </div>
                      <p class="text-sm text-gray-500 mt-1 flex items-center">
                        <MapPinIcon class="w-4 h-4 mr-1" />
                        {{ order.address_text }}
                      </p>
                      <div class="mt-2">
                        <span class="text-xs text-gray-400">{{ order.order_number }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else class="text-center py-8 text-gray-500">
                <TruckIcon class="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p class="font-medium">No hay pedidos documentados para {{ form.date }}</p>
                <template v-if="availableDates.length > 0">
                  <p class="text-xs mt-2 text-gray-400">Pedidos disponibles en otras fechas:</p>
                  <div class="flex flex-wrap justify-center gap-2 mt-2">
                    <button
                      v-for="d in availableDates"
                      :key="d"
                      type="button"
                      class="text-sm px-3 py-1 rounded-full bg-primary-100 text-primary-700 hover:bg-primary-200 transition-colors"
                      @click="form.date = d"
                    >
                      {{ d }}
                    </button>
                  </div>
                </template>
                <template v-else>
                  <p class="text-xs mt-2 text-gray-400">
                    No hay pedidos DOCUMENTADO. Registra una boleta/factura en el detalle del pedido para documentarlo.
                  </p>
                </template>
              </div>
            </div>
          </div>

          <!-- Right: Configuration -->
          <div class="space-y-6">
            <!-- Route config -->
            <div class="card">
              <h2 class="text-lg font-semibold text-gray-900 mb-4">Configuración</h2>

              <div class="space-y-4">
                <!-- Date -->
                <div>
                  <label for="date" class="label">Fecha de Entrega</label>
                  <input
                    id="date"
                    v-model="form.date"
                    type="date"
                    class="input"
                  />
                  <!-- Fechas con pedidos disponibles -->
                  <div v-if="availableDates.length > 0" class="mt-2 flex flex-wrap gap-1">
                    <span class="text-xs text-gray-500">Con pedidos:</span>
                    <button
                      v-for="d in availableDates"
                      :key="d"
                      type="button"
                      :class="[
                        'text-xs px-2 py-0.5 rounded-full border transition-colors',
                        form.date === d
                          ? 'bg-primary-500 text-white border-primary-500'
                          : 'text-primary-600 border-primary-300 hover:bg-primary-50',
                      ]"
                      @click="form.date = d"
                    >
                      {{ d }}
                    </button>
                  </div>
                </div>

                <!-- Driver -->
                <div>
                  <label for="driver_id" class="label">Repartidor *</label>
                  <select
                    id="driver_id"
                    v-model="form.driver_id"
                    :class="['input', errors.driver_id ? 'input-error' : '']"
                  >
                    <option :value="undefined">Seleccionar repartidor</option>
                    <option
                      v-for="driver in allDrivers"
                      :key="driver.id"
                      :value="driver.id"
                    >
                      {{ driver.full_name }}
                    </option>
                  </select>
                  <p v-if="errors.driver_id" class="mt-1 text-sm text-danger-600">
                    {{ errors.driver_id }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Info box -->
            <div class="p-4 bg-info-50 border border-info-200 rounded-xl">
              <p class="text-sm text-info-700">
                <strong>Optimización:</strong> La ruta será optimizada usando el algoritmo TSP
                para minimizar la distancia total de recorrido.
              </p>
            </div>

            <!-- Actions -->
            <div class="space-y-3">
              <button
                type="submit"
                class="btn-primary w-full py-3"
                :disabled="!isValid || isGenerating"
              >
                <span v-if="isGenerating" class="spinner w-5 h-5 mr-2"></span>
                <TruckIcon v-else class="w-5 h-5 mr-2" />
                {{ isGenerating ? 'Generando ruta...' : 'Generar Ruta Optimizada' }}
              </button>

              <button
                type="button"
                class="btn-secondary w-full"
                @click="router.back()"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      </form>
    </template>
  </div>
</template>
