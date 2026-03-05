<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { useAuthStore } from '@/stores/auth'
import type { Order, OrderStatus } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const router = useRouter()
const ordersStore = useOrdersStore()
const authStore = useAuthStore()

const showFilters = ref(false)
const searchQuery = ref('')
const statusFilter = ref<OrderStatus | ''>('')
const dateFrom = ref('')
const dateTo = ref('')

const columns = [
  { key: 'order_number', label: 'Nº Pedido', width: '140px' },
  { key: 'document_number', label: 'N° Doc.', width: '110px' },
  { key: 'customer_name', label: 'Cliente' },
  { key: 'address_text', label: 'Dirección' },
  { key: 'order_status', label: 'Estado', width: '140px' },
  { key: 'source_channel', label: 'Canal', width: '100px' },
  { key: 'delivery_date', label: 'Fecha Entrega', width: '130px' },
  { key: 'created_at', label: 'Creado', width: '120px' },
]

const statusOptions: { value: OrderStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'PENDIENTE', label: 'Pendiente' },
  { value: 'EN_PREPARACION', label: 'En Preparación' },
  { value: 'DOCUMENTADO', label: 'Documentado' },
  { value: 'EN_RUTA', label: 'En Ruta' },
  { value: 'ENTREGADO', label: 'Entregado' },
  { value: 'INCIDENCIA', label: 'Incidencia' },
]

onMounted(() => {
  loadOrders()
})

watch([statusFilter, dateFrom, dateTo], () => {
  applyFilters()
})

const loadOrders = async () => {
  try {
    if (authStore.isSeller) {
      await ordersStore.fetchMyOrders()
    } else {
      await ordersStore.fetchOrders()
    }
  } catch (error) {
    console.error('Error loading orders:', error)
  }
}

const applyFilters = () => {
  ordersStore.setFilters({
    status: statusFilter.value || undefined,
    date_from: dateFrom.value || undefined,
    date_to: dateTo.value || undefined,
    search: searchQuery.value || undefined,
  })
  loadOrders()
}

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  ordersStore.clearFilters()
  loadOrders()
}

const handleSearch = () => {
  applyFilters()
}

const handlePageChange = (page: number) => {
  ordersStore.setPage(page)
  loadOrders()
}

const handleRowClick = (order: Order) => {
  router.push(`/orders/${order.id}`)
}

const formatDate = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), 'dd MMM yyyy', { locale: es })
  } catch {
    return '-'
  }
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 class="page-title">Pedidos</h1>
        <p class="page-description">
          {{ authStore.isSeller ? 'Mis pedidos creados' : 'Gestión de todos los pedidos' }}
        </p>
      </div>

      <RouterLink
        v-if="authStore.canCreateOrders"
        to="/orders/create"
        class="btn-primary mt-4 sm:mt-0"
      >
        <PlusIcon class="w-5 h-5 mr-2" />
        Nuevo Pedido
      </RouterLink>
    </div>

    <!-- Search and filters -->
    <div class="card mb-6">
      <div class="flex flex-col sm:flex-row gap-4">
        <!-- Search -->
        <div class="flex-1">
          <div class="relative">
            <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Buscar por cliente, dirección o ID..."
              class="input pl-10"
              @keyup.enter="handleSearch"
            />
          </div>
        </div>

        <!-- Filter toggle -->
        <button
          :class="[
            'btn-secondary',
            showFilters ? 'bg-primary-50 border-primary-300' : '',
          ]"
          @click="showFilters = !showFilters"
        >
          <FunnelIcon class="w-5 h-5 mr-2" />
          Filtros
        </button>
      </div>

      <!-- Filter options -->
      <transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="showFilters" class="mt-4 pt-4 border-t border-gray-100">
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <!-- Status filter -->
            <div>
              <label class="label">Estado</label>
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

            <!-- Date from -->
            <div>
              <label class="label">Desde</label>
              <input
                v-model="dateFrom"
                type="date"
                class="input"
              />
            </div>

            <!-- Date to -->
            <div>
              <label class="label">Hasta</label>
              <input
                v-model="dateTo"
                type="date"
                class="input"
              />
            </div>
          </div>

          <!-- Clear filters -->
          <div class="mt-4 flex justify-end">
            <button
              class="btn-secondary text-sm"
              @click="clearFilters"
            >
              <XMarkIcon class="w-4 h-4 mr-1" />
              Limpiar filtros
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- Orders table -->
    <DataTable
      :columns="columns"
      :data="ordersStore.orders"
      :loading="ordersStore.isLoading"
      :page="ordersStore.pagination.page"
      :total-pages="ordersStore.pagination.pages"
      :total-items="ordersStore.pagination.total"
      :page-size="ordersStore.pagination.size"
      empty-message="No hay pedidos para mostrar"
      @page-change="handlePageChange"
      @row-click="handleRowClick"
    >
      <template #cell-order_number="{ value }">
        <span class="font-mono text-sm text-primary-600">{{ value }}</span>
      </template>

      <template #cell-document_number="{ value }">
        <span class="font-mono text-sm text-gray-700">{{ value || '—' }}</span>
      </template>

      <template #cell-customer_name="{ row }">
        <div>
          <p class="font-medium text-gray-900">{{ row.customer_name }}</p>
          <p class="text-sm text-gray-500">{{ row.customer_phone }}</p>
        </div>
      </template>

      <template #cell-address_text="{ value }">
        <p class="text-sm text-gray-600 truncate max-w-xs">{{ value }}</p>
      </template>

      <template #cell-order_status="{ value }">
        <StatusBadge :status="value as OrderStatus" />
      </template>

      <template #cell-source_channel="{ value }">
        <span class="text-xs px-2 py-1 bg-gray-100 rounded">{{ value }}</span>
      </template>

      <template #cell-delivery_date="{ value }">
        <span class="text-sm">{{ formatDate(value as string) }}</span>
      </template>

      <template #cell-created_at="{ value }">
        <span class="text-sm text-gray-500">{{ formatDate(value as string) }}</span>
      </template>
    </DataTable>
  </div>
</template>
