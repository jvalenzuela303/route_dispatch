<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useVehiclesStore } from '@/stores/vehicles'
import { useNotificationsStore } from '@/stores/notifications'
import type { Vehicle } from '@/services/vehicles.service'
import {
  PlusIcon,
  TruckIcon,
  WrenchScrewdriverIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const store = useVehiclesStore()
const notifications = useNotificationsStore()

const confirmTarget = ref<Vehicle | null>(null)
const confirmAction = ref<'delete' | 'maintenance' | 'release' | null>(null)
const isActing = ref(false)
const statusFilter = ref<string>('')

onMounted(() => store.fetchVehicles())

const filtered = computed(() => {
  if (!statusFilter.value) return store.vehicles
  return store.vehicles.filter((v) => v.status === statusFilter.value)
})

const statusBadge = (status: string) => {
  const map: Record<string, string> = {
    AVAILABLE: 'bg-green-100 text-green-800',
    IN_ROUTE: 'bg-blue-100 text-blue-800',
    MAINTENANCE: 'bg-yellow-100 text-yellow-800',
  }
  return map[status] || 'bg-gray-100 text-gray-800'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    AVAILABLE: 'Disponible',
    IN_ROUTE: 'En Ruta',
    MAINTENANCE: 'Mantenimiento',
  }
  return map[status] || status
}

function openConfirm(vehicle: Vehicle, action: 'delete' | 'maintenance' | 'release') {
  confirmTarget.value = vehicle
  confirmAction.value = action
}

function closeConfirm() {
  confirmTarget.value = null
  confirmAction.value = null
}

async function executeAction() {
  if (!confirmTarget.value || !confirmAction.value) return
  isActing.value = true
  try {
    const id = confirmTarget.value.id
    if (confirmAction.value === 'delete') {
      await store.deleteVehicle(id)
      notifications.success('Flota', 'Vehículo eliminado')
    } else if (confirmAction.value === 'maintenance') {
      await store.setMaintenance(id)
      notifications.success('Flota', 'Vehículo en mantenimiento')
    } else if (confirmAction.value === 'release') {
      await store.release(id)
      notifications.success('Flota', 'Vehículo liberado')
    }
    closeConfirm()
  } catch (e: unknown) {
    notifications.error('Error', (e as Error).message || 'Error')
  } finally {
    isActing.value = false
  }
}
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Flota de Vehículos</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ store.total }} vehículo{{ store.total !== 1 ? 's' : '' }} registrado{{ store.total !== 1 ? 's' : '' }}
        </p>
      </div>
      <button
        @click="router.push('/vehicles/create')"
        class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
      >
        <PlusIcon class="h-5 w-5" />
        Nuevo Vehículo
      </button>
    </div>

    <!-- Status summary cards -->
    <div class="grid grid-cols-3 gap-4 mb-6">
      <div
        v-for="(label, key) in { AVAILABLE: 'Disponibles', IN_ROUTE: 'En Ruta', MAINTENANCE: 'Mantenimiento' }"
        :key="key"
        class="bg-white rounded-lg border p-4 cursor-pointer hover:shadow-md transition"
        :class="statusFilter === key ? 'ring-2 ring-blue-500' : ''"
        @click="statusFilter = statusFilter === key ? '' : key"
      >
        <div class="flex items-center gap-3">
          <TruckIcon v-if="key === 'AVAILABLE'" class="h-8 w-8 text-green-500" />
          <TruckIcon v-else-if="key === 'IN_ROUTE'" class="h-8 w-8 text-blue-500" />
          <WrenchScrewdriverIcon v-else class="h-8 w-8 text-yellow-500" />
          <div>
            <div class="text-2xl font-bold text-gray-900">{{ (store.byStatus as Record<string, Vehicle[]>)[key].length }}</div>
            <div class="text-sm text-gray-500">{{ label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="store.isLoading" class="flex justify-center py-12">
      <div class="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full" />
    </div>

    <!-- Table -->
    <div v-else class="bg-white rounded-lg border overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Placa</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Alias / Marca</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Año</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Estado</th>
            <th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">GPS</th>
            <th class="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Acciones</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr
            v-for="v in filtered"
            :key="v.id"
            class="hover:bg-gray-50 cursor-pointer"
            @click="router.push(`/vehicles/${v.id}`)"
          >
            <td class="px-4 py-3 font-mono font-semibold text-gray-900">{{ v.plate_number }}</td>
            <td class="px-4 py-3">
              <div class="font-medium text-gray-900">{{ v.alias || '—' }}</div>
              <div class="text-xs text-gray-400">{{ [v.brand, v.model_name].filter(Boolean).join(' ') || '—' }}</div>
            </td>
            <td class="px-4 py-3 text-gray-600">{{ v.year || '—' }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                :class="statusBadge(v.status)"
              >
                {{ statusLabel(v.status) }}
              </span>
            </td>
            <td class="px-4 py-3">
              <CheckCircleIcon v-if="v.gps_device_id" class="h-5 w-5 text-green-500" title="GPS configurado" />
              <ExclamationTriangleIcon v-else class="h-5 w-5 text-gray-300" title="Sin GPS" />
            </td>
            <td class="px-4 py-3 text-right" @click.stop>
              <div class="flex items-center justify-end gap-2">
                <button
                  v-if="v.status === 'AVAILABLE'"
                  @click="openConfirm(v, 'maintenance')"
                  class="text-xs text-yellow-600 hover:text-yellow-800"
                  title="Poner en mantenimiento"
                >
                  <WrenchScrewdriverIcon class="h-4 w-4" />
                </button>
                <button
                  v-if="v.status === 'MAINTENANCE'"
                  @click="openConfirm(v, 'release')"
                  class="text-xs text-green-600 hover:text-green-800"
                  title="Liberar"
                >
                  <CheckCircleIcon class="h-4 w-4" />
                </button>
                <button
                  @click="router.push(`/vehicles/${v.id}/edit`)"
                  class="text-xs text-blue-600 hover:text-blue-800 px-2 py-1 rounded"
                >
                  Editar
                </button>
                <button
                  @click="openConfirm(v, 'delete')"
                  class="text-xs text-red-500 hover:text-red-700 px-2 py-1 rounded"
                >
                  Eliminar
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="!filtered.length">
            <td colspan="6" class="px-4 py-10 text-center text-gray-400">
              No hay vehículos{{ statusFilter ? ' con ese estado' : '' }}.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Confirm dialog -->
    <Teleport to="body">
      <div
        v-if="confirmTarget"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      >
        <div class="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">
            {{ confirmAction === 'delete' ? 'Eliminar vehículo' :
               confirmAction === 'maintenance' ? 'Mantenimiento' : 'Liberar vehículo' }}
          </h3>
          <p class="text-sm text-gray-600 mb-6">
            <template v-if="confirmAction === 'delete'">
              ¿Eliminar <strong>{{ confirmTarget?.plate_number }}</strong>? Esta acción no se puede deshacer.
            </template>
            <template v-else-if="confirmAction === 'maintenance'">
              ¿Pasar <strong>{{ confirmTarget?.plate_number }}</strong> a mantenimiento?
              No estará disponible para nuevas rutas.
            </template>
            <template v-else>
              ¿Liberar <strong>{{ confirmTarget?.plate_number }}</strong>?
              Quedará disponible para nuevas rutas.
            </template>
          </p>
          <div class="flex gap-3 justify-end">
            <button @click="closeConfirm" class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
              Cancelar
            </button>
            <button
              @click="executeAction"
              :disabled="isActing"
              class="px-4 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50"
              :class="confirmAction === 'delete' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'"
            >
              {{ isActing ? 'Procesando...' : 'Confirmar' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
