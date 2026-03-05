<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRoutesStore } from '@/stores/routes'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { useUsersStore } from '@/stores/users'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import RouteMap from '@/components/routes/RouteMap.vue'
import {
  ArrowLeftIcon,
  PlayIcon,
  XCircleIcon,
  ClockIcon,
  MapPinIcon,
  TruckIcon,
  UserIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const route = useRoute()
const router = useRouter()
const routesStore = useRoutesStore()
const authStore = useAuthStore()
const notifications = useNotificationsStore()
const usersStore = useUsersStore()

// Route IDs are UUIDs (strings) in the backend – do NOT convert to Number
const routeId = computed(() => route.params.id as string)
const isLoading = ref(true)
const showActivateDialog = ref(false)
const showCancelDialog = ref(false)
const isActioning = ref(false)
const selectedDriverId = ref<string>('')
const driversLoadError = ref(false)

onMounted(async () => {
  try {
    await routesStore.fetchRoute(routeId.value)
  } catch {
    notifications.error('Error', 'No se pudo cargar la ruta')
    router.push('/routes')
    return
  } finally {
    isLoading.value = false
  }

  try {
    await usersStore.fetchDrivers()
  } catch {
    driversLoadError.value = true
    notifications.warning('Advertencia', 'No se pudieron cargar los repartidores. Verifica que existan usuarios con rol Repartidor activos.')
  }
})

const currentRoute = computed(() => routesStore.currentRoute)

const canActivate = computed(() => {
  return currentRoute.value?.status === 'PENDIENTE' && authStore.canManageRoutes
})

const canCancel = computed(() => {
  return (
    currentRoute.value &&
    ['PENDIENTE', 'ACTIVA'].includes(currentRoute.value.status) &&
    authStore.canManageRoutes
  )
})

const progressPercent = computed(() => {
  if (!currentRoute.value || currentRoute.value.stops_count === 0) return 0
  return Math.round(
    (currentRoute.value.completed_stops / currentRoute.value.stops_count) * 100
  )
})

const canConfirmActivate = computed(() => !!selectedDriverId.value)

const handleActivate = async () => {
  if (!selectedDriverId.value) {
    notifications.error('Error', 'Debes seleccionar un repartidor para activar la ruta')
    return
  }
  isActioning.value = true
  try {
    await routesStore.activateRoute(routeId.value, selectedDriverId.value)
    notifications.success(
      'Ruta activada',
      'La ruta ha sido activada y los clientes serán notificados.'
    )
  } catch {
    notifications.error('Error', 'No se pudo activar la ruta')
  } finally {
    isActioning.value = false
    showActivateDialog.value = false
    selectedDriverId.value = ''
  }
}

const handleCancel = async () => {
  isActioning.value = true
  try {
    await routesStore.cancelRoute(routeId.value, 'Cancelada por el usuario')
    notifications.success('Ruta cancelada', 'La ruta ha sido cancelada.')
    router.push('/routes')
  } catch {
    notifications.error('Error', 'No se pudo cancelar la ruta')
  } finally {
    isActioning.value = false
    showCancelDialog.value = false
  }
}

const formatDate = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), "EEEE, dd 'de' MMMM yyyy", { locale: es })
  } catch {
    return '-'
  }
}

const formatTime = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), 'HH:mm', { locale: es })
  } catch {
    return '-'
  }
}
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando ruta..." />
    </div>

    <template v-else-if="currentRoute">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
        <div class="flex items-center space-x-4">
          <button
            class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            @click="router.back()"
          >
            <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <div class="flex items-center space-x-3">
              <h1 class="text-2xl font-bold text-gray-900">
                {{ currentRoute.name }}
              </h1>
              <StatusBadge :status="currentRoute.status" size="lg" />
            </div>
            <p class="text-gray-500 mt-1">
              {{ formatDate(currentRoute.date) }}
            </p>
          </div>
        </div>

        <div class="flex items-center space-x-3 mt-4 sm:mt-0">
          <button
            v-if="canActivate"
            class="btn-success"
            @click="showActivateDialog = true"
          >
            <PlayIcon class="w-5 h-5 mr-2" />
            Activar Ruta
          </button>

          <button
            v-if="canCancel"
            class="btn-danger"
            @click="showCancelDialog = true"
          >
            <XCircleIcon class="w-5 h-5 mr-2" />
            Cancelar
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left: Map and stops -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Map -->
          <div class="card p-0 overflow-hidden">
            <RouteMap
              :stops="currentRoute.stops"
              :route-status="currentRoute.status"
              class="h-96"
            />
          </div>

          <!-- Stops list -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">
              Paradas ({{ currentRoute.stops_count }})
            </h2>

            <div class="space-y-4">
              <div
                v-for="stop in currentRoute.stops"
                :key="stop.id"
                :class="[
                  'p-4 border rounded-xl transition-colors',
                  stop.status === 'ENTREGADO'
                    ? 'bg-success-50 border-success-200'
                    : stop.status === 'INCIDENCIA'
                    ? 'bg-danger-50 border-danger-200'
                    : 'border-gray-200',
                ]"
              >
                <div class="flex items-start">
                  <!-- Sequence number -->
                  <div
                    :class="[
                      'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold mr-4',
                      stop.status === 'ENTREGADO'
                        ? 'bg-success-500 text-white'
                        : stop.status === 'INCIDENCIA'
                        ? 'bg-danger-500 text-white'
                        : 'bg-primary-500 text-white',
                    ]"
                  >
                    {{ stop.sequence_number }}
                  </div>

                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                      <p class="font-medium text-gray-900">
                        {{ stop.order?.customer_name }}
                      </p>
                      <StatusBadge :status="stop.status" size="sm" />
                    </div>

                    <p class="text-sm text-gray-500 mt-1 flex items-center">
                      <MapPinIcon class="w-4 h-4 mr-1" />
                      {{ stop.order?.address_text }}
                    </p>

                    <div class="flex items-center space-x-4 mt-2 text-xs text-gray-400">
                      <span class="flex items-center">
                        <ClockIcon class="w-3 h-3 mr-1" />
                        Est: {{ formatTime(stop.estimated_arrival) }}
                      </span>
                      <span v-if="stop.actual_arrival">
                        Real: {{ formatTime(stop.actual_arrival) }}
                      </span>
                      <span>
                        {{ stop.distance_from_previous_km ? Number(stop.distance_from_previous_km).toFixed(1) : '0.0' }} km
                      </span>
                    </div>

                    <p v-if="stop.incident_reason" class="mt-2 text-sm text-danger-600">
                      Incidencia: {{ stop.incident_reason }}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: Route info -->
        <div class="space-y-6">
          <!-- Progress -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Progreso</h2>

            <div class="mb-4">
              <div class="flex justify-between text-sm mb-2">
                <span class="text-gray-600">Completado</span>
                <span class="font-medium">{{ progressPercent }}%</span>
              </div>
              <div class="h-3 bg-gray-200 rounded-full overflow-hidden">
                <div
                  class="h-full bg-success-500 transition-all duration-500"
                  :style="{ width: `${progressPercent}%` }"
                ></div>
              </div>
            </div>

            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-600">Entregas realizadas</span>
                <span class="font-medium text-success-600">
                  {{ currentRoute.completed_stops }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-600">Pendientes</span>
                <span class="font-medium">
                  {{ currentRoute.stops_count - currentRoute.completed_stops }}
                </span>
              </div>
            </div>
          </div>

          <!-- Route details -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Detalles</h2>

            <div class="space-y-4">
              <div class="flex items-center">
                <UserIcon class="w-5 h-5 text-gray-400 mr-3" />
                <div>
                  <p class="text-sm text-gray-500">Repartidor</p>
                  <p class="font-medium">
                    {{ currentRoute.driver?.full_name || 'Sin asignar' }}
                  </p>
                </div>
              </div>

              <div class="flex items-center">
                <TruckIcon class="w-5 h-5 text-gray-400 mr-3" />
                <div>
                  <p class="text-sm text-gray-500">Distancia total</p>
                  <p class="font-medium">
                    {{ currentRoute.total_distance_km ? Number(currentRoute.total_distance_km).toFixed(1) : '0.0' }} km
                  </p>
                </div>
              </div>

              <div class="flex items-center">
                <ClockIcon class="w-5 h-5 text-gray-400 mr-3" />
                <div>
                  <p class="text-sm text-gray-500">Duración estimada</p>
                  <p class="font-medium">
                    {{ currentRoute.estimated_duration_minutes }} min
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Timestamps -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Tiempos</h2>

            <div class="space-y-3 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-600">Creada</span>
                <span>{{ formatTime(currentRoute.created_at) }}</span>
              </div>
              <div v-if="currentRoute.started_at" class="flex justify-between">
                <span class="text-gray-600">Iniciada</span>
                <span>{{ formatTime(currentRoute.started_at) }}</span>
              </div>
              <div v-if="currentRoute.completed_at" class="flex justify-between">
                <span class="text-gray-600">Completada</span>
                <span>{{ formatTime(currentRoute.completed_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Activate Dialog (with driver selector) -->
    <div
      v-if="showActivateDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Activar Ruta</h3>
        <p class="text-sm text-gray-500 mb-5">
          Selecciona el repartidor asignado. Los clientes serán notificados de que su pedido está en camino.
        </p>

        <div class="mb-5">
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Repartidor <span class="text-red-500">*</span>
          </label>
          <select
            v-model="selectedDriverId"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            :disabled="usersStore.availableDrivers.length === 0"
          >
            <option value="">
              {{ usersStore.availableDrivers.length === 0 ? 'No hay repartidores disponibles' : 'Selecciona un repartidor...' }}
            </option>
            <option
              v-for="driver in usersStore.availableDrivers"
              :key="driver.id"
              :value="driver.id"
            >
              {{ driver.full_name }}
            </option>
          </select>
          <p v-if="usersStore.availableDrivers.length === 0" class="mt-2 text-sm text-amber-600">
            No hay repartidores activos en el sistema. Crea al menos un usuario con rol
            <strong>Repartidor</strong> en la sección Usuarios.
          </p>
        </div>

        <div class="flex justify-end space-x-3">
          <button
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            @click="showActivateDialog = false; selectedDriverId = ''"
          >
            Cancelar
          </button>
          <button
            :disabled="!canConfirmActivate || isActioning"
            :class="[
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors',
              canConfirmActivate && !isActioning
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-300 cursor-not-allowed',
            ]"
            @click="handleActivate"
          >
            <span v-if="isActioning">Activando...</span>
            <span v-else>Activar Ruta</span>
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="showCancelDialog"
      title="Cancelar Ruta"
      message="¿Estás seguro de cancelar esta ruta? Los pedidos volverán a estado DOCUMENTADO."
      type="danger"
      confirm-text="Cancelar Ruta"
      :loading="isActioning"
      @confirm="handleCancel"
      @cancel="showCancelDialog = false"
    />
  </div>
</template>
