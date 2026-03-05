<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { reportsService } from '@/services'
import type { ComplianceReport } from '@/types'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import {
  DocumentArrowDownIcon,
  CalendarIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
} from '@heroicons/vue/24/outline'
import { format, subDays, startOfMonth } from 'date-fns'
import { es } from 'date-fns/locale'

const isLoading = ref(false)
const report = ref<ComplianceReport | null>(null)
const loadError = ref<string | null>(null)
const dateFrom = ref(format(startOfMonth(new Date()), 'yyyy-MM-dd'))
const dateTo = ref(format(new Date(), 'yyyy-MM-dd'))
const isExporting = ref(false)

onMounted(() => {
  loadReport()
})

const loadReport = async () => {
  isLoading.value = true
  loadError.value = null
  try {
    report.value = await reportsService.getComplianceReport(dateFrom.value, dateTo.value)
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.response?.data?.message || 'No se pudo cargar el reporte'
    loadError.value = msg
    console.error('Error loading report:', error)
  } finally {
    isLoading.value = false
  }
}

const exportOrders = async () => {
  isExporting.value = true
  try {
    const blob = await reportsService.getOrdersReport(dateFrom.value, dateTo.value)
    downloadBlob(blob, `pedidos_${dateFrom.value}_${dateTo.value}.xlsx`)
  } catch (error) {
    console.error('Error exporting:', error)
  } finally {
    isExporting.value = false
  }
}

const exportDeliveries = async () => {
  isExporting.value = true
  try {
    const blob = await reportsService.getDeliveriesReport(dateFrom.value, dateTo.value)
    downloadBlob(blob, `entregas_${dateFrom.value}_${dateTo.value}.xlsx`)
  } catch (error) {
    console.error('Error exporting:', error)
  } finally {
    isExporting.value = false
  }
}

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}

const setQuickRange = (days: number) => {
  dateTo.value = format(new Date(), 'yyyy-MM-dd')
  dateFrom.value = format(subDays(new Date(), days), 'yyyy-MM-dd')
  loadReport()
}

const formatDate = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), "d 'de' MMMM, yyyy", { locale: es })
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
        <h1 class="page-title">Reportes</h1>
        <p class="page-description">Análisis de cumplimiento y métricas</p>
      </div>
    </div>

    <!-- Date filters -->
    <div class="card mb-6">
      <div class="flex flex-col sm:flex-row sm:items-end gap-4">
        <div class="flex-1 grid grid-cols-2 gap-4">
          <div>
            <label class="label">Desde</label>
            <input
              v-model="dateFrom"
              type="date"
              class="input"
            />
          </div>
          <div>
            <label class="label">Hasta</label>
            <input
              v-model="dateTo"
              type="date"
              class="input"
            />
          </div>
        </div>

        <div class="flex items-center space-x-2">
          <button class="btn-secondary text-sm" @click="setQuickRange(7)">
            7 días
          </button>
          <button class="btn-secondary text-sm" @click="setQuickRange(30)">
            30 días
          </button>
          <button class="btn-primary" @click="loadReport">
            <CalendarIcon class="w-5 h-5 mr-2" />
            Aplicar
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Generando reporte..." />
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="card bg-red-50 border border-red-200 text-red-700 text-sm">
      <strong>Error al cargar el reporte:</strong> {{ loadError }}
    </div>

    <template v-else-if="report">
      <!-- Period info -->
      <div class="mb-6 p-4 bg-primary-50 border border-primary-200 rounded-xl">
        <p class="text-primary-700">
          Período: <strong>{{ formatDate(report.period.from) }}</strong> al
          <strong>{{ formatDate(report.period.to) }}</strong>
        </p>
      </div>

      <!-- Compliance metrics -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <!-- Cutoff compliance -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-gray-900">Cumplimiento Horario de Corte</h3>
            <ClockIcon class="w-6 h-6 text-primary-500" />
          </div>

          <div class="mb-4">
            <div class="flex items-end space-x-2">
              <span class="text-4xl font-bold text-primary-600">
                {{ report.cutoff_compliance.compliance_percentage }}%
              </span>
            </div>
          </div>

          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">Pedidos en horario</span>
              <span class="font-medium text-success-600">{{ report.cutoff_compliance.compliant }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Overrides usados</span>
              <span class="font-medium text-warning-600">{{ report.cutoff_compliance.overridden }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Total pedidos</span>
              <span class="font-medium">{{ report.cutoff_compliance.total_orders }}</span>
            </div>
          </div>
        </div>

        <!-- Invoice compliance -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-gray-900">Documentación de Pedidos</h3>
            <CheckCircleIcon class="w-6 h-6 text-success-500" />
          </div>

          <div class="mb-4">
            <div class="flex items-end space-x-2">
              <span class="text-4xl font-bold text-success-600">
                {{ report.invoice_compliance.compliance_percentage }}%
              </span>
            </div>
          </div>

          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">Con factura</span>
              <span class="font-medium text-success-600">{{ report.invoice_compliance.orders_with_invoice }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Sin factura</span>
              <span class="font-medium text-danger-600">{{ report.invoice_compliance.orders_without_invoice }}</span>
            </div>
          </div>
        </div>

        <!-- Delivery compliance -->
        <div class="card">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-gray-900">Entregas a Tiempo</h3>
            <ExclamationTriangleIcon class="w-6 h-6 text-warning-500" />
          </div>

          <div class="mb-4">
            <div class="flex items-end space-x-2">
              <span class="text-4xl font-bold text-warning-600">
                {{ report.delivery_compliance.on_time_percentage }}%
              </span>
            </div>
          </div>

          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-600">A tiempo</span>
              <span class="font-medium text-success-600">{{ report.delivery_compliance.on_time }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Con retraso</span>
              <span class="font-medium text-warning-600">{{ report.delivery_compliance.late }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-600">Incidencias</span>
              <span class="font-medium text-danger-600">{{ report.delivery_compliance.incidents }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- User activity (only when data available) -->
      <div v-if="report.by_user && report.by_user.length > 0" class="card mb-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Actividad por Usuario</h3>

        <div class="overflow-x-auto">
          <table class="min-w-full">
            <thead>
              <tr class="border-b border-gray-200">
                <th class="text-left py-3 px-4 text-sm font-semibold text-gray-600">Usuario</th>
                <th class="text-right py-3 px-4 text-sm font-semibold text-gray-600">Pedidos Creados</th>
                <th class="text-right py-3 px-4 text-sm font-semibold text-gray-600">Overrides de Horario</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="user in report.by_user"
                :key="user.user_id"
                class="border-b border-gray-100 hover:bg-gray-50"
              >
                <td class="py-3 px-4">
                  <span class="font-medium text-gray-900">{{ user.user_name }}</span>
                </td>
                <td class="py-3 px-4 text-right">
                  <span class="font-medium">{{ user.orders_created }}</span>
                </td>
                <td class="py-3 px-4 text-right">
                  <span
                    :class="user.cutoff_overrides > 0 ? 'text-warning-600' : 'text-gray-500'"
                  >
                    {{ user.cutoff_overrides }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Orders summary card -->
      <div class="card mb-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Resumen de Pedidos</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div class="p-3 bg-gray-50 rounded-lg">
            <p class="text-2xl font-bold text-gray-900">{{ report.cutoff_compliance.total_orders }}</p>
            <p class="text-xs text-gray-500 mt-1">Total pedidos</p>
          </div>
          <div class="p-3 bg-green-50 rounded-lg">
            <p class="text-2xl font-bold text-green-700">{{ report.delivery_compliance.on_time }}</p>
            <p class="text-xs text-gray-500 mt-1">Entregados</p>
          </div>
          <div class="p-3 bg-red-50 rounded-lg">
            <p class="text-2xl font-bold text-red-700">{{ report.delivery_compliance.incidents }}</p>
            <p class="text-xs text-gray-500 mt-1">Incidencias</p>
          </div>
          <div class="p-3 bg-blue-50 rounded-lg">
            <p class="text-2xl font-bold text-blue-700">{{ report.delivery_compliance.on_time_percentage }}%</p>
            <p class="text-xs text-gray-500 mt-1">Tasa entrega</p>
          </div>
        </div>
      </div>

      <!-- Export buttons -->
      <div class="card">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Exportar Datos</h3>

        <div class="flex flex-wrap gap-4">
          <button
            class="btn-secondary"
            :disabled="isExporting"
            @click="exportOrders"
          >
            <DocumentArrowDownIcon class="w-5 h-5 mr-2" />
            Exportar Pedidos (Excel)
          </button>

          <button
            class="btn-secondary"
            :disabled="isExporting"
            @click="exportDeliveries"
          >
            <DocumentArrowDownIcon class="w-5 h-5 mr-2" />
            Exportar Entregas (Excel)
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
