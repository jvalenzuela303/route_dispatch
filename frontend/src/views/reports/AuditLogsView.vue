<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { reportsService, usersService } from '@/services'
import type { AuditLog, User } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import {
  FunnelIcon,
  XMarkIcon,
  ShieldCheckIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const isLoading = ref(true)
const auditLogs = ref<AuditLog[]>([])
const users = ref<User[]>([])
const pagination = ref({
  page: 1,
  size: 50,
  total: 0,
  pages: 0,
})

const showFilters = ref(false)
const userFilter = ref<string>('')
const actionFilter = ref('')
const entityFilter = ref('')
const dateFrom = ref('')
const dateTo = ref('')

const columns = [
  { key: 'created_at', label: 'Fecha', width: '160px' },
  { key: 'user.full_name', label: 'Usuario', width: '150px' },
  { key: 'action', label: 'Acción', width: '140px' },
  { key: 'entity_type', label: 'Entidad', width: '120px' },
  { key: 'entity_id', label: 'ID', width: '80px' },
  { key: 'details', label: 'Detalles' },
]

const actionOptions = [
  { value: '', label: 'Todas las acciones' },
  { value: 'CREATE', label: 'Crear' },
  { value: 'UPDATE', label: 'Actualizar' },
  { value: 'DELETE', label: 'Eliminar' },
  { value: 'LOGIN', label: 'Iniciar sesión' },
  { value: 'LOGOUT', label: 'Cerrar sesión' },
  { value: 'STATUS_CHANGE', label: 'Cambio de estado' },
  { value: 'CUTOFF_OVERRIDE', label: 'Override horario' },
]

const entityOptions = [
  { value: '', label: 'Todas las entidades' },
  { value: 'ORDER', label: 'Pedido' },
  { value: 'INVOICE', label: 'Factura' },
  { value: 'ROUTE', label: 'Ruta' },
  { value: 'USER', label: 'Usuario' },
]

onMounted(async () => {
  try {
    const usersResponse = await usersService.getAll(1, 100)
    users.value = usersResponse.items
    await loadLogs()
  } catch (error) {
    console.error('Error loading:', error)
  } finally {
    isLoading.value = false
  }
})

watch([userFilter, actionFilter, entityFilter, dateFrom, dateTo], () => {
  pagination.value.page = 1
  loadLogs()
})

const loadLogs = async () => {
  isLoading.value = true
  try {
    const response = await reportsService.getAuditLogs(
      pagination.value.page,
      pagination.value.size,
      {
        user_id: userFilter.value || undefined,
        action: actionFilter.value || undefined,
        entity_type: entityFilter.value || undefined,
        date_from: dateFrom.value || undefined,
        date_to: dateTo.value || undefined,
      }
    )

    auditLogs.value = response.items
    pagination.value = {
      page: response.page,
      size: response.size,
      total: response.total,
      pages: response.pages,
    }
  } catch (error) {
    console.error('Error loading logs:', error)
  } finally {
    isLoading.value = false
  }
}

const clearFilters = () => {
  userFilter.value = ''
  actionFilter.value = ''
  entityFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  loadLogs()
}

const formatDateTime = (date: string) => {
  return format(new Date(date), "dd MMM yyyy HH:mm:ss", { locale: es })
}

const getActionBadgeClass = (action: string) => {
  const classes: Record<string, string> = {
    CREATE: 'bg-success-100 text-success-700',
    UPDATE: 'bg-info-100 text-info-700',
    DELETE: 'bg-danger-100 text-danger-700',
    LOGIN: 'bg-primary-100 text-primary-700',
    LOGOUT: 'bg-gray-100 text-gray-700',
    STATUS_CHANGE: 'bg-warning-100 text-warning-700',
    CUTOFF_OVERRIDE: 'bg-purple-100 text-purple-700',
  }
  return classes[action] || 'bg-gray-100 text-gray-700'
}

const getActionLabel = (action: string) => {
  const labels: Record<string, string> = {
    CREATE: 'Crear',
    UPDATE: 'Actualizar',
    DELETE: 'Eliminar',
    LOGIN: 'Login',
    LOGOUT: 'Logout',
    STATUS_CHANGE: 'Cambio Estado',
    CUTOFF_OVERRIDE: 'Override',
  }
  return labels[action] || action
}

const getEntityLabel = (entity: string) => {
  const labels: Record<string, string> = {
    ORDER: 'Pedido',
    INVOICE: 'Factura',
    ROUTE: 'Ruta',
    USER: 'Usuario',
  }
  return labels[entity] || entity
}

const formatChanges = (log: AuditLog) => {
  if (!log.new_values && !log.old_values) return '-'

  const changes: string[] = []

  if (log.new_values) {
    Object.keys(log.new_values).forEach((key) => {
      const oldVal = log.old_values?.[key]
      const newVal = log.new_values?.[key]
      if (oldVal !== newVal) {
        changes.push(`${key}: ${oldVal || '(vacío)'} → ${newVal}`)
      }
    })
  }

  return changes.length > 0 ? changes.join(', ') : '-'
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 class="page-title">Registro de Auditoría</h1>
        <p class="page-description">Historial de acciones en el sistema</p>
      </div>

      <div class="flex items-center mt-4 sm:mt-0">
        <ShieldCheckIcon class="w-6 h-6 text-primary-500 mr-2" />
        <span class="text-sm text-gray-500">
          {{ pagination.total }} registros
        </span>
      </div>
    </div>

    <!-- Filters -->
    <div class="card mb-6">
      <div class="flex flex-col sm:flex-row gap-4">
        <div class="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <select v-model="userFilter" class="input">
            <option value="">Todos los usuarios</option>
            <option v-for="user in users" :key="user.id" :value="user.id">
              {{ user.full_name }}
            </option>
          </select>

          <select v-model="actionFilter" class="input">
            <option v-for="opt in actionOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>

          <select v-model="entityFilter" class="input">
            <option v-for="opt in entityOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>

          <button
            :class="[
              'btn-secondary',
              showFilters ? 'bg-primary-50 border-primary-300' : '',
            ]"
            @click="showFilters = !showFilters"
          >
            <FunnelIcon class="w-5 h-5 mr-2" />
            Fechas
          </button>
        </div>
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

    <!-- Audit logs table -->
    <DataTable
      :columns="columns"
      :data="auditLogs"
      :loading="isLoading"
      :page="pagination.page"
      :total-pages="pagination.pages"
      :total-items="pagination.total"
      :page-size="pagination.size"
      empty-message="No hay registros de auditoría"
      @page-change="handlePageChange"
    >
      <template #cell-created_at="{ value }">
        <span class="text-sm font-mono">{{ formatDateTime(value as string) }}</span>
      </template>

      <template #cell-user.full_name="{ row }">
        <div class="flex items-center">
          <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center mr-2">
            <span class="text-xs font-medium text-gray-600">
              {{ row.user?.full_name?.charAt(0)?.toUpperCase() || '?' }}
            </span>
          </div>
          <span class="text-sm">{{ row.user?.full_name || 'Sistema' }}</span>
        </div>
      </template>

      <template #cell-action="{ value }">
        <span
          :class="[
            'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
            getActionBadgeClass(value as string),
          ]"
        >
          {{ getActionLabel(value as string) }}
        </span>
      </template>

      <template #cell-entity_type="{ value }">
        <span class="text-sm text-gray-600">{{ getEntityLabel(value as string) }}</span>
      </template>

      <template #cell-entity_id="{ value }">
        <span class="text-sm font-mono text-gray-500">#{{ value }}</span>
      </template>

      <template #cell-details="{ row }">
        <span class="text-sm text-gray-500 truncate block max-w-xs">
          {{ formatChanges(row) }}
        </span>
      </template>
    </DataTable>
  </div>
</template>
