<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useRoutesStore } from '@/stores/routes'
import type { Route, RouteStatus } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  PlusIcon,
  FunnelIcon,
  XMarkIcon,
  MapIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const router = useRouter()
const routesStore = useRoutesStore()

const showFilters = ref(false)
const statusFilter = ref<RouteStatus | ''>('')
const dateFrom = ref('')
const dateTo = ref('')

const columns = [
  { key: 'name', label: 'Nombre' },
  { key: 'date', label: 'Fecha', width: '120px' },
  { key: 'driver.full_name', label: 'Repartidor' },
  { key: 'status', label: 'Estado', width: '130px' },
  { key: 'stops_count', label: 'Paradas', width: '100px' },
  { key: 'progress', label: 'Progreso', width: '140px' },
  { key: 'total_distance_km', label: 'Distancia', width: '100px' },
]

const statusOptions: { value: RouteStatus | ''; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'PENDIENTE', label: 'Pendiente' },
  { value: 'ACTIVA', label: 'Activa' },
  { value: 'EN_PROGRESO', label: 'En Progreso' },
  { value: 'COMPLETADA', label: 'Completada' },
  { value: 'CANCELADA', label: 'Cancelada' },
]

onMounted(() => {
  loadRoutes()
})

watch([statusFilter, dateFrom, dateTo], () => {
  applyFilters()
})

const loadRoutes = async () => {
  try {
    await routesStore.fetchRoutes()
  } catch (error) {
    console.error('Error loading routes:', error)
  }
}

const applyFilters = () => {
  routesStore.setFilters({
    status: statusFilter.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
  })
  loadRoutes()
}

const clearFilters = () => {
  statusFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  routesStore.clearFilters()
  loadRoutes()
}

const handlePageChange = (page: number) => {
  routesStore.setPage(page)
  loadRoutes()
}

const handleRowClick = (route: Route) => {
  router.push(`/routes/${route.id}`)
}

const formatDate = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), 'dd MMM yyyy', { locale: es })
  } catch {
    return '-'
  }
}

const getProgressPercent = (route: Route) => {
  if (route.stops_count === 0) return 0
  return Math.round((route.completed_stops / route.stops_count) * 100)
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 class="page-title">Rutas de Entrega</h1>
        <p class="page-description">Gestión y optimización de rutas</p>
      </div>

      <RouterLink to="/routes/generate" class="btn-primary mt-4 sm:mt-0">
        <PlusIcon class="w-5 h-5 mr-2" />
        Generar Ruta
      </RouterLink>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
      <div class="card">
        <p class="text-sm text-gray-500">Pendientes</p>
        <p class="text-2xl font-bold text-gray-600">
          {{ routesStore.routesByStatus.PENDIENTE || 0 }}
        </p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-500">Activas</p>
        <p class="text-2xl font-bold text-success-600">
          {{ routesStore.routesByStatus.ACTIVA || 0 }}
        </p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-500">Completadas Hoy</p>
        <p class="text-2xl font-bold text-primary-600">
          {{ routesStore.routesByStatus.COMPLETADA || 0 }}
        </p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-500">Total Rutas</p>
        <p class="text-2xl font-bold text-gray-900">
          {{ routesStore.pagination.total }}
        </p>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-6">
      <div class="flex flex-col sm:flex-row gap-4">
        <div class="flex-1">
          <select v-model="statusFilter" class="input">
            <option
              v-for="option in statusOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </div>

        <button
          :class="[
            'btn-secondary',
            showFilters ? 'bg-primary-50 border-primary-300' : '',
          ]"
          @click="showFilters = !showFilters"
        >
          <FunnelIcon class="w-5 h-5 mr-2" />
          Más Filtros
        </button>
      </div>

      <transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="showFilters" class="mt-4 pt-4 border-t border-gray-100">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="label">Desde</label>
              <input v-model="dateFrom" type="date" class="input" />
            </div>
            <div>
              <label class="label">Hasta</label>
              <input v-model="dateTo" type="date" class="input" />
            </div>
          </div>

          <div class="mt-4 flex justify-end">
            <button class="btn-secondary text-sm" @click="clearFilters">
              <XMarkIcon class="w-4 h-4 mr-1" />
              Limpiar filtros
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- Routes table -->
    <DataTable
      :columns="columns"
      :data="routesStore.routes"
      :loading="routesStore.isLoading"
      :page="routesStore.pagination.page"
      :total-pages="routesStore.pagination.pages"
      :total-items="routesStore.pagination.total"
      :page-size="routesStore.pagination.size"
      empty-message="No hay rutas para mostrar"
      @page-change="handlePageChange"
      @row-click="handleRowClick"
    >
      <template #cell-name="{ row }">
        <div class="flex items-center">
          <div class="w-8 h-8 rounded-lg bg-primary-100 flex items-center justify-center mr-3">
            <MapIcon class="w-4 h-4 text-primary-600" />
          </div>
          <div>
            <p class="font-medium text-gray-900">{{ row.name }}</p>
            <p class="text-xs text-gray-500">ID: {{ row.id }}</p>
          </div>
        </div>
      </template>

      <template #cell-date="{ value }">
        <span class="text-sm">{{ formatDate(value as string) }}</span>
      </template>

      <template #cell-driver.full_name="{ row }">
        <span class="text-sm">{{ row.driver?.full_name || 'Sin asignar' }}</span>
      </template>

      <template #cell-status="{ value }">
        <StatusBadge :status="value as RouteStatus" />
      </template>

      <template #cell-stops_count="{ row }">
        <span class="text-sm">
          {{ row.completed_stops }}/{{ row.stops_count }}
        </span>
      </template>

      <template #cell-progress="{ row }">
        <div class="flex items-center space-x-2">
          <div class="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full bg-success-500 transition-all duration-300"
              :style="{ width: `${getProgressPercent(row)}%` }"
            ></div>
          </div>
          <span class="text-xs text-gray-500 w-10">
            {{ getProgressPercent(row) }}%
          </span>
        </div>
      </template>

      <template #cell-total_distance_km="{ value }">
        <span class="text-sm">{{ value ? Number(value).toFixed(1) : '0.0' }} km</span>
      </template>
    </DataTable>
  </div>
</template>
