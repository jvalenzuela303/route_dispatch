<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { reportsService } from '@/services'
import type { DashboardStats } from '@/types'
import {
  ClipboardDocumentListIcon,
  TruckIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  CurrencyDollarIcon,
  ClockIcon,
  ArrowTrendingUpIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const authStore = useAuthStore()

const stats = ref<DashboardStats | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const statusColors: Record<string, string> = {
  PENDIENTE: 'bg-gray-500',
  EN_PREPARACION: 'bg-blue-500',
  DOCUMENTADO: 'bg-purple-500',
  EN_RUTA: 'bg-yellow-500',
  ENTREGADO: 'bg-green-500',
  INCIDENCIA: 'bg-red-500',
}

const statusLabels: Record<string, string> = {
  PENDIENTE: 'Pendientes',
  EN_PREPARACION: 'En Preparación',
  DOCUMENTADO: 'Documentados',
  EN_RUTA: 'En Ruta',
  ENTREGADO: 'Entregados',
  INCIDENCIA: 'Incidencias',
}

const quickActions = computed(() => {
  const actions = []

  if (authStore.canCreateOrders) {
    actions.push({
      label: 'Nuevo Pedido',
      icon: ClipboardDocumentListIcon,
      path: '/orders/create',
      color: 'bg-primary-600 hover:bg-primary-700',
    })
  }

  if (authStore.canManageRoutes) {
    actions.push({
      label: 'Generar Ruta',
      icon: TruckIcon,
      path: '/routes/generate',
      color: 'bg-success-600 hover:bg-success-700',
    })
  }

  return actions
})

onMounted(async () => {
  try {
    stats.value = await reportsService.getDashboardStats()
  } catch (err) {
    error.value = 'Error al cargar las estadísticas'
    console.error(err)
  } finally {
    isLoading.value = false
  }
})

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
  }).format(value)
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          ¡Hola, {{ authStore.userName.split(' ')[0] }}!
        </h1>
        <p class="text-gray-500 mt-1">
          Aquí está el resumen de hoy
        </p>
      </div>

      <!-- Quick actions -->
      <div class="flex items-center space-x-3 mt-4 sm:mt-0">
        <RouterLink
          v-for="action in quickActions"
          :key="action.path"
          :to="action.path"
          :class="[
            'inline-flex items-center px-4 py-2 rounded-xl text-white text-sm font-medium transition-colors',
            action.color,
          ]"
        >
          <PlusIcon class="w-5 h-5 mr-2" />
          {{ action.label }}
        </RouterLink>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando estadísticas..." />
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="bg-danger-50 border border-danger-200 rounded-xl p-6 text-center"
    >
      <ExclamationTriangleIcon class="w-12 h-12 text-danger-500 mx-auto mb-4" />
      <p class="text-danger-700">{{ error }}</p>
      <button class="btn-primary mt-4" @click="$router.go(0)">
        Reintentar
      </button>
    </div>

    <!-- Stats content -->
    <template v-else-if="stats">
      <!-- Main stats cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <!-- Orders today -->
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-500">Pedidos Hoy</p>
              <p class="text-3xl font-bold text-gray-900 mt-1">
                {{ stats.orders.today }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-primary-100 flex items-center justify-center">
              <ClipboardDocumentListIcon class="w-6 h-6 text-primary-600" />
            </div>
          </div>
          <div class="mt-4 flex items-center text-sm">
            <span class="text-gray-500">
              {{ stats.orders.pending_delivery }} pendientes de entrega
            </span>
          </div>
        </div>

        <!-- Active routes -->
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-500">Rutas Activas</p>
              <p class="text-3xl font-bold text-gray-900 mt-1">
                {{ stats.routes.active }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-success-100 flex items-center justify-center">
              <TruckIcon class="w-6 h-6 text-success-600" />
            </div>
          </div>
          <div class="mt-4 flex items-center text-sm">
            <span class="text-success-600 font-medium">
              {{ stats.routes.on_time_percentage }}%
            </span>
            <span class="text-gray-500 ml-1">a tiempo</span>
          </div>
        </div>

        <!-- Deliveries today -->
        <div class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-500">Entregas Hoy</p>
              <p class="text-3xl font-bold text-gray-900 mt-1">
                {{ stats.deliveries.completed_today }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-info-100 flex items-center justify-center">
              <CheckCircleIcon class="w-6 h-6 text-info-600" />
            </div>
          </div>
          <div class="mt-4 flex items-center text-sm">
            <ClockIcon class="w-4 h-4 text-gray-400 mr-1" />
            <span class="text-gray-500">
              {{ stats.deliveries.average_delivery_time_minutes }} min promedio
            </span>
          </div>
        </div>

        <!-- Revenue today -->
        <div v-if="authStore.canViewReports" class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-500">Ventas Hoy</p>
              <p class="text-2xl font-bold text-gray-900 mt-1">
                {{ formatCurrency(stats.revenue.today) }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-warning-100 flex items-center justify-center">
              <CurrencyDollarIcon class="w-6 h-6 text-warning-600" />
            </div>
          </div>
          <div class="mt-4 flex items-center text-sm">
            <ArrowTrendingUpIcon class="w-4 h-4 text-success-500 mr-1" />
            <span class="text-gray-500">
              {{ formatCurrency(stats.revenue.this_week) }} esta semana
            </span>
          </div>
        </div>

        <!-- Incidents for driver -->
        <div v-if="authStore.isDriver" class="card">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-500">Incidencias Hoy</p>
              <p class="text-3xl font-bold text-gray-900 mt-1">
                {{ stats.deliveries.incidents_today }}
              </p>
            </div>
            <div class="w-12 h-12 rounded-xl bg-danger-100 flex items-center justify-center">
              <ExclamationTriangleIcon class="w-6 h-6 text-danger-600" />
            </div>
          </div>
        </div>
      </div>

      <!-- Orders by status -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Status breakdown -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Pedidos por Estado</h3>
          </div>
          <div class="space-y-4">
            <div
              v-for="(count, status) in stats.orders.by_status"
              :key="status"
              class="flex items-center"
            >
              <div :class="['w-3 h-3 rounded-full mr-3', statusColors[status as string]]"></div>
              <span class="text-sm text-gray-600 flex-1">{{ statusLabels[status as string] }}</span>
              <span class="text-sm font-semibold text-gray-900">{{ count }}</span>
            </div>
          </div>

          <!-- Status bar -->
          <div class="mt-6 h-3 rounded-full bg-gray-100 overflow-hidden flex">
            <div
              v-for="(count, status) in stats.orders.by_status"
              :key="status"
              :class="statusColors[status as string]"
              :style="{
                width: `${(count / stats.orders.total) * 100}%`,
              }"
            ></div>
          </div>
          <p class="text-sm text-gray-500 mt-2 text-center">
            {{ stats.orders.total }} pedidos en total
          </p>
        </div>

        <!-- Quick links based on role -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Accesos Rápidos</h3>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <RouterLink
              v-if="authStore.canCreateOrders"
              to="/orders"
              class="p-4 rounded-xl border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors group"
            >
              <ClipboardDocumentListIcon class="w-8 h-8 text-gray-400 group-hover:text-primary-600" />
              <p class="mt-2 font-medium text-gray-900">Ver Pedidos</p>
              <p class="text-sm text-gray-500">{{ stats.orders.total }} total</p>
            </RouterLink>

            <RouterLink
              v-if="authStore.canManageRoutes"
              to="/routes"
              class="p-4 rounded-xl border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors group"
            >
              <TruckIcon class="w-8 h-8 text-gray-400 group-hover:text-primary-600" />
              <p class="mt-2 font-medium text-gray-900">Ver Rutas</p>
              <p class="text-sm text-gray-500">{{ stats.routes.active }} activas</p>
            </RouterLink>

            <RouterLink
              v-if="authStore.isDriver"
              to="/tracking"
              class="p-4 rounded-xl border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors group"
            >
              <TruckIcon class="w-8 h-8 text-gray-400 group-hover:text-primary-600" />
              <p class="mt-2 font-medium text-gray-900">Mis Entregas</p>
              <p class="text-sm text-gray-500">Ruta actual</p>
            </RouterLink>

            <RouterLink
              v-if="authStore.canViewReports"
              to="/reports"
              class="p-4 rounded-xl border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors group"
            >
              <ArrowTrendingUpIcon class="w-8 h-8 text-gray-400 group-hover:text-primary-600" />
              <p class="mt-2 font-medium text-gray-900">Reportes</p>
              <p class="text-sm text-gray-500">Análisis completo</p>
            </RouterLink>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
