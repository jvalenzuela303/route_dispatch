<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoutesStore } from '@/stores/routes'
import { useNotificationsStore } from '@/stores/notifications'
import type { RouteStop } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import Modal from '@/components/common/Modal.vue'
import RouteMap from '@/components/routes/RouteMap.vue'
import {
  TruckIcon,
  MapPinIcon,
  PhoneIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PlayIcon,
  FlagIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const routesStore = useRoutesStore()
const notifications = useNotificationsStore()

const isLoading = ref(true)
const showDeliveryModal = ref(false)
const showIncidentModal = ref(false)
const selectedStop = ref<RouteStop | null>(null)
const deliveryNotes = ref('')
const incidentReason = ref('')
const isSubmitting = ref(false)

const activeRoute = computed(() => routesStore.activeRoute)

const currentStop = computed(() => {
  if (!activeRoute.value) return null
  return activeRoute.value.stops.find(
    (s) => s.status === 'PENDIENTE' || s.status === 'EN_CAMINO' || s.status === 'LLEGADO'
  )
})

const completedStops = computed(() => {
  if (!activeRoute.value) return []
  return activeRoute.value.stops.filter((s) => s.status === 'ENTREGADO')
})

const pendingStops = computed(() => {
  if (!activeRoute.value) return []
  return activeRoute.value.stops.filter(
    (s) => s.status === 'PENDIENTE' && s.id !== currentStop.value?.id
  )
})

const progressPercent = computed(() => {
  if (!activeRoute.value || activeRoute.value.stops_count === 0) return 0
  return Math.round(
    (activeRoute.value.completed_stops / activeRoute.value.stops_count) * 100
  )
})

onMounted(async () => {
  try {
    await routesStore.fetchActiveRoute()
    if (!routesStore.activeRoute) {
      await routesStore.fetchMyRoutes()
    }
  } catch (error) {
    console.error('Error loading route:', error)
  } finally {
    isLoading.value = false
  }
})

const startRoute = async () => {
  if (!activeRoute.value) return

  try {
    await routesStore.startRoute(activeRoute.value.id)
    notifications.success('Ruta iniciada', '¡Buena suerte con las entregas!')
  } catch {
    notifications.error('Error', 'No se pudo iniciar la ruta')
  }
}

const openDeliveryModal = (stop: RouteStop) => {
  selectedStop.value = stop
  deliveryNotes.value = ''
  showDeliveryModal.value = true
}

const openIncidentModal = (stop: RouteStop) => {
  selectedStop.value = stop
  incidentReason.value = ''
  showIncidentModal.value = true
}

const confirmDelivery = async () => {
  if (!activeRoute.value || !selectedStop.value) return

  isSubmitting.value = true
  try {
    await routesStore.markStopDelivered(
      activeRoute.value.id,
      selectedStop.value.id,
      deliveryNotes.value || undefined
    )
    notifications.success('Entrega confirmada', 'Se ha registrado la entrega exitosamente')
    showDeliveryModal.value = false
  } catch {
    notifications.error('Error', 'No se pudo confirmar la entrega')
  } finally {
    isSubmitting.value = false
  }
}

const confirmIncident = async () => {
  if (!activeRoute.value || !selectedStop.value || !incidentReason.value) return

  isSubmitting.value = true
  try {
    await routesStore.reportIncident(
      activeRoute.value.id,
      selectedStop.value.id,
      incidentReason.value
    )
    notifications.warning('Incidencia reportada', 'Se ha registrado la incidencia')
    showIncidentModal.value = false
  } catch {
    notifications.error('Error', 'No se pudo reportar la incidencia')
  } finally {
    isSubmitting.value = false
  }
}

const completeRoute = async () => {
  if (!activeRoute.value) return

  try {
    await routesStore.completeRoute(activeRoute.value.id)
    notifications.success('Ruta completada', '¡Excelente trabajo!')
  } catch {
    notifications.error('Error', 'No se pudo completar la ruta')
  }
}

const formatTime = (date: string | null | undefined) => {
  if (!date) return '--:--'
  try {
    return format(new Date(date), 'HH:mm', { locale: es })
  } catch {
    return '--:--'
  }
}
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando ruta..." />
    </div>

    <!-- No active route -->
    <div v-else-if="!activeRoute" class="text-center py-20">
      <TruckIcon class="w-16 h-16 text-gray-300 mx-auto mb-4" />
      <h2 class="text-xl font-semibold text-gray-900 mb-2">
        No tienes rutas asignadas
      </h2>
      <p class="text-gray-500">
        Espera a que se te asigne una ruta de entrega
      </p>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">
              {{ activeRoute.name }}
            </h1>
            <div class="flex items-center space-x-3 mt-2">
              <StatusBadge :status="activeRoute.status" />
              <span class="text-gray-500">
                {{ activeRoute.stops_count }} paradas
              </span>
            </div>
          </div>

          <!-- Mostrar "Iniciar Ruta" solo si ACTIVA y aún no iniciada -->
          <div v-if="activeRoute.status === 'ACTIVA' && !activeRoute.started_at">
            <button class="btn-success" @click="startRoute">
              <PlayIcon class="w-5 h-5 mr-2" />
              Iniciar Ruta
            </button>
          </div>

          <div v-else-if="progressPercent === 100 && activeRoute.status === 'ACTIVA'">
            <button class="btn-primary" @click="completeRoute">
              <FlagIcon class="w-5 h-5 mr-2" />
              Finalizar Ruta
            </button>
          </div>
        </div>

        <!-- Progress bar -->
        <div class="mt-4">
          <div class="flex justify-between text-sm mb-2">
            <span class="text-gray-600">Progreso</span>
            <span class="font-medium">
              {{ activeRoute.completed_stops }}/{{ activeRoute.stops_count }} entregas
            </span>
          </div>
          <div class="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full bg-success-500 transition-all duration-500"
              :style="{ width: `${progressPercent}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Map -->
        <div class="card p-0 overflow-hidden order-2 lg:order-1">
          <RouteMap
            :stops="activeRoute.stops"
            :route-status="activeRoute.status"
            class="h-80 lg:h-[500px]"
          />
        </div>

        <!-- Stops -->
        <div class="space-y-6 order-1 lg:order-2">
          <!-- Current stop -->
          <div v-if="currentStop" class="card border-2 border-primary-500">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-semibold text-primary-700">
                Próxima Entrega
              </h2>
              <span class="text-2xl font-bold text-primary-600">
                #{{ currentStop.sequence_number }}
              </span>
            </div>

            <div class="space-y-3">
              <p class="text-xl font-semibold text-gray-900">
                {{ currentStop.order?.customer_name }}
              </p>

              <div class="flex items-start text-gray-600">
                <MapPinIcon class="w-5 h-5 mr-2 mt-0.5 flex-shrink-0" />
                <span>{{ currentStop.order?.address_text }}</span>
              </div>

              <div class="flex items-center text-gray-600">
                <PhoneIcon class="w-5 h-5 mr-2" />
                <a
                  :href="`tel:${currentStop.order?.customer_phone}`"
                  class="text-primary-600 hover:underline"
                >
                  {{ currentStop.order?.customer_phone }}
                </a>
              </div>

              <div v-if="currentStop.notes" class="p-3 bg-gray-50 rounded-lg">
                <p class="text-sm text-gray-600">
                  <strong>Notas:</strong> {{ currentStop.notes }}
                </p>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex space-x-3 mt-6">
              <button
                class="btn-success flex-1"
                @click="openDeliveryModal(currentStop)"
              >
                <CheckCircleIcon class="w-5 h-5 mr-2" />
                Entregado
              </button>
              <button
                class="btn-danger flex-1"
                @click="openIncidentModal(currentStop)"
              >
                <ExclamationTriangleIcon class="w-5 h-5 mr-2" />
                Incidencia
              </button>
            </div>
          </div>

          <!-- Pending stops -->
          <div v-if="pendingStops.length > 0" class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">
              Siguientes Paradas ({{ pendingStops.length }})
            </h2>

            <div class="space-y-3">
              <div
                v-for="stop in pendingStops"
                :key="stop.id"
                class="flex items-center p-3 bg-gray-50 rounded-lg"
              >
                <div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-sm font-bold text-white mr-3">
                  {{ stop.sequence_number }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-gray-900 truncate">
                    {{ stop.order?.customer_name }}
                  </p>
                  <p class="text-sm text-gray-500 truncate">
                    {{ stop.order?.address_text }}
                  </p>
                </div>
                <span class="text-xs text-gray-400">
                  {{ formatTime(stop.estimated_arrival) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Completed stops -->
          <div v-if="completedStops.length > 0" class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">
              Completadas ({{ completedStops.length }})
            </h2>

            <div class="space-y-2">
              <div
                v-for="stop in completedStops"
                :key="stop.id"
                class="flex items-center p-2 text-success-700"
              >
                <CheckCircleIcon class="w-5 h-5 mr-2" />
                <span class="text-sm">
                  #{{ stop.sequence_number }} - {{ stop.order?.customer_name }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Delivery confirmation modal -->
    <Modal
      :open="showDeliveryModal"
      title="Confirmar Entrega"
      @close="showDeliveryModal = false"
    >
      <div class="space-y-4">
        <p class="text-gray-600">
          ¿Confirmas la entrega a <strong>{{ selectedStop?.order?.customer_name }}</strong>?
        </p>

        <div>
          <label class="label">Notas (opcional)</label>
          <textarea
            v-model="deliveryNotes"
            rows="3"
            class="input"
            placeholder="Notas adicionales sobre la entrega..."
          ></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3">
          <button class="btn-secondary" @click="showDeliveryModal = false">
            Cancelar
          </button>
          <button
            class="btn-success"
            :disabled="isSubmitting"
            @click="confirmDelivery"
          >
            <span v-if="isSubmitting" class="spinner w-5 h-5 mr-2"></span>
            Confirmar Entrega
          </button>
        </div>
      </template>
    </Modal>

    <!-- Incident report modal -->
    <Modal
      :open="showIncidentModal"
      title="Reportar Incidencia"
      @close="showIncidentModal = false"
    >
      <div class="space-y-4">
        <p class="text-gray-600">
          Reportar incidencia en la entrega a <strong>{{ selectedStop?.order?.customer_name }}</strong>
        </p>

        <div>
          <label class="label">Razón de la incidencia *</label>
          <select v-model="incidentReason" class="input">
            <option value="">Seleccionar motivo</option>
            <option value="Cliente ausente">Cliente ausente</option>
            <option value="Dirección incorrecta">Dirección incorrecta</option>
            <option value="Cliente rechazó entrega">Cliente rechazó entrega</option>
            <option value="Producto dañado">Producto dañado</option>
            <option value="Acceso restringido">Acceso restringido</option>
            <option value="Otro">Otro</option>
          </select>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3">
          <button class="btn-secondary" @click="showIncidentModal = false">
            Cancelar
          </button>
          <button
            class="btn-danger"
            :disabled="!incidentReason || isSubmitting"
            @click="confirmIncident"
          >
            <span v-if="isSubmitting" class="spinner w-5 h-5 mr-2"></span>
            Reportar Incidencia
          </button>
        </div>
      </template>
    </Modal>
  </div>
</template>
