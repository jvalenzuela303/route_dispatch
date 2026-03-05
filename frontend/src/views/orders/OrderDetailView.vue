<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import StatusBadge from '@/components/common/StatusBadge.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import OrderStatusTimeline from '@/components/orders/OrderStatusTimeline.vue'
import api from '@/services/api'
import {
  ArrowLeftIcon,
  PhoneIcon,
  EnvelopeIcon,
  MapPinIcon,
  CalendarIcon,
  TruckIcon,
  TrashIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  InformationCircleIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const route = useRoute()
const router = useRouter()
const ordersStore = useOrdersStore()
const authStore = useAuthStore()
const notifications = useNotificationsStore()

const orderId = computed(() =>
  Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
)
const isLoading = ref(true)
const showDeleteDialog = ref(false)
const isDeleting = ref(false)
const isTransitioning = ref(false)
const showIncidentDialog = ref(false)
const incidentReason = ref('')

// ── Invoice creation form (for EN_PREPARACION → DOCUMENTADO) ───
const showInvoiceForm = ref(false)
const isCreatingInvoice = ref(false)
const invoiceForm = ref({
  invoice_number: '',
  invoice_type: 'BOLETA' as 'BOLETA' | 'FACTURA',
  total_amount: '',
})
const invoiceErrors = ref<Record<string, string>>({})

onMounted(async () => {
  if (!orderId.value) {
    notifications.error('Error', 'ID de pedido inválido')
    router.push('/orders')
    return
  }
  try {
    await ordersStore.fetchOrder(orderId.value)
  } catch {
    notifications.error('Error', 'No se pudo cargar el pedido')
    router.push('/orders')
  } finally {
    isLoading.value = false
  }
})

const order = computed(() => ordersStore.currentOrder)

// ── State machine ──────────────────────────────────────────────
// PENDIENTE → EN_PREPARACION (manual)
// EN_PREPARACION → DOCUMENTADO (via invoice creation)
// DOCUMENTADO → EN_RUTA (automatic on route activation)
// EN_RUTA → ENTREGADO (manual) or INCIDENCIA (manual + reason)

const canStartPreparation = computed(() =>
  order.value?.order_status === 'PENDIENTE' &&
  (authStore.isAdmin || authStore.hasRole(['Encargado de Bodega']) || authStore.canCreateOrders)
)

const canCreateInvoice = computed(() =>
  order.value?.order_status === 'EN_PREPARACION' &&
  (authStore.isAdmin || authStore.hasRole(['Encargado de Bodega']) || authStore.canCreateOrders)
)

const canMarkDelivered = computed(() =>
  order.value?.order_status === 'EN_RUTA' &&
  (authStore.isAdmin || authStore.hasRole(['Encargado de Bodega']))
)

const canReportIncident = computed(() =>
  order.value?.order_status === 'EN_RUTA' &&
  (authStore.isAdmin || authStore.hasRole(['Repartidor']))
)

const canDelete = computed(() =>
  authStore.isAdmin && order.value?.order_status === 'PENDIENTE'
)

// ── Actions ────────────────────────────────────────────────────
const handleStartPreparation = async () => {
  if (isTransitioning.value) return
  isTransitioning.value = true
  try {
    await ordersStore.updateOrderStatus(orderId.value, 'EN_PREPARACION')
    notifications.success('Estado actualizado', 'Pedido en preparación')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || 'No se pudo cambiar el estado'
    notifications.error('Error', msg)
  } finally {
    isTransitioning.value = false
  }
}

const handleMarkDelivered = async () => {
  if (isTransitioning.value) return
  isTransitioning.value = true
  try {
    await ordersStore.updateOrderStatus(orderId.value, 'ENTREGADO')
    notifications.success('¡Entregado!', 'El pedido fue marcado como entregado')
  } catch (e: any) {
    const msg = e?.response?.data?.detail || 'No se pudo cambiar el estado'
    notifications.error('Error', msg)
  } finally {
    isTransitioning.value = false
  }
}

const handleReportIncident = async () => {
  if (!incidentReason.value.trim()) {
    notifications.error('Error', 'Debes ingresar el motivo de la incidencia')
    return
  }
  isTransitioning.value = true
  try {
    await ordersStore.updateOrderStatus(orderId.value, 'INCIDENCIA', incidentReason.value)
    notifications.success('Incidencia registrada', incidentReason.value)
    showIncidentDialog.value = false
    incidentReason.value = ''
  } catch (e: any) {
    const msg = e?.response?.data?.detail || 'No se pudo registrar la incidencia'
    notifications.error('Error', msg)
  } finally {
    isTransitioning.value = false
  }
}

const validateInvoice = (): boolean => {
  invoiceErrors.value = {}
  if (!invoiceForm.value.invoice_number.trim()) {
    invoiceErrors.value.invoice_number = 'El número de documento es obligatorio'
  }
  const amount = parseFloat(invoiceForm.value.total_amount)
  if (!invoiceForm.value.total_amount || isNaN(amount) || amount <= 0) {
    invoiceErrors.value.total_amount = 'El monto debe ser mayor a 0'
  }
  return Object.keys(invoiceErrors.value).length === 0
}

const handleCreateInvoice = async () => {
  if (!validateInvoice() || isCreatingInvoice.value) return
  isCreatingInvoice.value = true
  try {
    await api.post('/invoices', {
      order_id: orderId.value,
      invoice_number: invoiceForm.value.invoice_number.trim(),
      invoice_type: invoiceForm.value.invoice_type,
      total_amount: parseFloat(invoiceForm.value.total_amount),
    })
    notifications.success(
      'Documento creado',
      `${invoiceForm.value.invoice_type === 'BOLETA' ? 'Boleta' : 'Factura'} N° ${invoiceForm.value.invoice_number} registrada. Pedido documentado.`
    )
    showInvoiceForm.value = false
    invoiceForm.value = { invoice_number: '', invoice_type: 'BOLETA', total_amount: '' }
    // Reload order to get updated status
    await ordersStore.fetchOrder(orderId.value)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || 'No se pudo crear el documento'
    notifications.error('Error', msg)
  } finally {
    isCreatingInvoice.value = false
  }
}

const handleDelete = async () => {
  isDeleting.value = true
  try {
    await ordersStore.deleteOrder(orderId.value)
    notifications.success('Eliminado', 'El pedido ha sido eliminado')
    router.push('/orders')
  } catch {
    notifications.error('Error', 'No se pudo eliminar el pedido')
  } finally {
    isDeleting.value = false
    showDeleteDialog.value = false
  }
}

// ── Formatters ─────────────────────────────────────────────────
const formatDate = (d: string | null | undefined) => {
  if (!d) return '-'
  try { return format(new Date(d), "dd 'de' MMMM, yyyy", { locale: es }) } catch { return '-' }
}

const formatDateTime = (d: string | null | undefined) => {
  if (!d) return '-'
  try { return format(new Date(d), "dd MMM yyyy 'a las' HH:mm", { locale: es }) } catch { return '-' }
}

const sourceChannelLabel = (ch?: string) => {
  const labels: Record<string, string> = { WEB: 'Web', RRSS: 'Redes Sociales', PRESENCIAL: 'Presencial' }
  return labels[ch ?? ''] ?? ch ?? '-'
}

const confidenceLabel = (c?: string) => {
  const labels: Record<string, string> = { HIGH: 'Alta', MEDIUM: 'Media', LOW: 'Baja', INVALID: 'Inválida' }
  return labels[c ?? ''] ?? '-'
}

const confidenceClass = (c?: string) => {
  if (c === 'HIGH') return 'text-green-600'
  if (c === 'MEDIUM') return 'text-yellow-600'
  return 'text-red-500'
}
</script>

<template>
  <div>
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando pedido..." />
    </div>

    <template v-else-if="order">
      <!-- Header -->
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
        <div class="flex items-center space-x-4">
          <button class="p-2 rounded-lg hover:bg-gray-100 transition-colors" @click="router.back()">
            <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <div class="flex items-center space-x-3">
              <h1 class="text-2xl font-bold text-gray-900">Pedido {{ order.order_number }}</h1>
              <StatusBadge :status="order.order_status" size="lg" />
            </div>
            <p class="text-gray-500 mt-1">Creado {{ formatDateTime(order.created_at) }}</p>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center space-x-3 mt-4 sm:mt-0">
          <!-- PENDIENTE → EN_PREPARACION -->
          <button
            v-if="canStartPreparation"
            :disabled="isTransitioning"
            class="btn-primary"
            @click="handleStartPreparation"
          >
            <span v-if="isTransitioning" class="spinner w-4 h-4 mr-2"></span>
            <ArrowRightIcon v-else class="w-4 h-4 mr-2" />
            Iniciar Preparación
          </button>

          <!-- EN_PREPARACION → DOCUMENTADO (via invoice) -->
          <button
            v-if="canCreateInvoice"
            class="btn-primary"
            @click="showInvoiceForm = !showInvoiceForm"
          >
            <DocumentTextIcon class="w-4 h-4 mr-2" />
            {{ showInvoiceForm ? 'Cancelar' : 'Registrar Boleta / Factura' }}
          </button>

          <!-- EN_RUTA → ENTREGADO -->
          <button
            v-if="canMarkDelivered"
            :disabled="isTransitioning"
            class="btn-primary"
            @click="handleMarkDelivered"
          >
            <span v-if="isTransitioning" class="spinner w-4 h-4 mr-2"></span>
            <ArrowRightIcon v-else class="w-4 h-4 mr-2" />
            Marcar Entregado
          </button>

          <!-- EN_RUTA → INCIDENCIA -->
          <button
            v-if="canReportIncident"
            class="btn-danger"
            @click="showIncidentDialog = true"
          >
            Reportar Incidencia
          </button>

          <!-- Delete -->
          <button
            v-if="canDelete"
            class="btn-danger"
            @click="showDeleteDialog = true"
          >
            <TrashIcon class="w-5 h-5 mr-2" />
            Eliminar
          </button>
        </div>
      </div>

      <!-- Inline invoice form (EN_PREPARACION only) -->
      <div v-if="showInvoiceForm && canCreateInvoice" class="card mb-6 border-2 border-primary-200">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Registrar Documento Tributario</h2>
        <p class="text-sm text-gray-500 mb-4">
          Al registrar la boleta o factura, el pedido avanzará automáticamente a <strong>DOCUMENTADO</strong>
          y podrá ser incluido en una ruta de reparto.
        </p>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Type -->
          <div>
            <label class="label">Tipo de documento *</label>
            <select v-model="invoiceForm.invoice_type" class="input">
              <option value="BOLETA">Boleta</option>
              <option value="FACTURA">Factura</option>
            </select>
          </div>

          <!-- Number -->
          <div>
            <label class="label">N° documento *</label>
            <input
              v-model="invoiceForm.invoice_number"
              type="text"
              :class="['input', invoiceErrors.invoice_number ? 'input-error' : '']"
              placeholder="Ej: 12345"
            />
            <p v-if="invoiceErrors.invoice_number" class="mt-1 text-xs text-danger-600">
              {{ invoiceErrors.invoice_number }}
            </p>
          </div>

          <!-- Amount -->
          <div>
            <label class="label">Monto total ($) *</label>
            <input
              v-model="invoiceForm.total_amount"
              type="number"
              min="1"
              step="1"
              :class="['input', invoiceErrors.total_amount ? 'input-error' : '']"
              placeholder="Ej: 15000"
            />
            <p v-if="invoiceErrors.total_amount" class="mt-1 text-xs text-danger-600">
              {{ invoiceErrors.total_amount }}
            </p>
          </div>
        </div>

        <div class="flex justify-end mt-4">
          <button
            :disabled="isCreatingInvoice"
            class="btn-primary"
            @click="handleCreateInvoice"
          >
            <span v-if="isCreatingInvoice" class="spinner w-4 h-4 mr-2"></span>
            {{ isCreatingInvoice ? 'Guardando...' : 'Registrar y Documentar Pedido' }}
          </button>
        </div>
      </div>

      <!-- DOCUMENTADO info banner -->
      <div
        v-if="order.order_status === 'DOCUMENTADO'"
        class="card mb-6 bg-blue-50 border border-blue-200 flex items-start space-x-3"
      >
        <InformationCircleIcon class="w-6 h-6 text-blue-500 mt-0.5 flex-shrink-0" />
        <div>
          <p class="font-semibold text-blue-800">Pedido listo para despacho</p>
          <p class="text-sm text-blue-600 mt-1">
            Este pedido está documentado. Para avanzar a <strong>EN RUTA</strong>, debe ser incluido en
            una ruta de reparto desde el módulo <strong>Rutas → Generar Ruta</strong> y luego activar la ruta.
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Timeline -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Estado del Pedido</h2>
            <OrderStatusTimeline :status="order.order_status" />
          </div>

          <!-- Customer -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Información del Cliente</h2>
            <div class="space-y-4">
              <div class="flex items-center">
                <div class="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center mr-4">
                  <span class="text-lg font-semibold text-primary-700">
                    {{ order.customer_name.charAt(0).toUpperCase() }}
                  </span>
                </div>
                <p class="font-medium text-gray-900">{{ order.customer_name }}</p>
              </div>

              <div class="flex items-center text-gray-600">
                <PhoneIcon class="w-5 h-5 mr-3 text-gray-400" />
                <a :href="`tel:${order.customer_phone}`" class="hover:text-primary-600">
                  {{ order.customer_phone }}
                </a>
              </div>

              <div v-if="order.customer_email" class="flex items-center text-gray-600">
                <EnvelopeIcon class="w-5 h-5 mr-3 text-gray-400" />
                <a :href="`mailto:${order.customer_email}`" class="hover:text-primary-600">
                  {{ order.customer_email }}
                </a>
              </div>
            </div>
          </div>

          <!-- Delivery -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Información de Entrega</h2>
            <div class="space-y-4">
              <div class="flex items-start">
                <MapPinIcon class="w-5 h-5 mr-3 text-gray-400 mt-0.5" />
                <div>
                  <p class="text-gray-900">{{ order.address_text }}</p>
                  <p :class="['text-xs mt-1', confidenceClass(order.geocoding_confidence)]">
                    Confianza geocodificación: {{ confidenceLabel(order.geocoding_confidence) }}
                  </p>
                </div>
              </div>

              <div class="flex items-center">
                <CalendarIcon class="w-5 h-5 mr-3 text-gray-400" />
                <div>
                  <p class="text-gray-900">{{ formatDate(order.delivery_date) }}</p>
                  <p class="text-sm text-gray-500">Fecha de entrega</p>
                </div>
              </div>

              <div v-if="order.notes" class="p-3 bg-gray-50 rounded-lg">
                <p class="text-sm font-medium text-gray-700 mb-1">Notas:</p>
                <p class="text-sm text-gray-600">{{ order.notes }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Sidebar -->
        <div class="space-y-6">
          <!-- Summary -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Resumen</h2>
            <div class="space-y-3 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-500">N° Documento</span>
                <span class="font-mono font-semibold text-gray-800">
                  {{ order.document_number || '—' }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Canal de venta</span>
                <span class="font-medium">{{ sourceChannelLabel(order.source_channel) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Estado</span>
                <StatusBadge :status="order.order_status" size="sm" />
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Fecha creación</span>
                <span>{{ formatDate(order.created_at) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">Fecha entrega</span>
                <span>{{ formatDate(order.delivery_date) }}</span>
              </div>
            </div>
          </div>

          <!-- Route info -->
          <div v-if="order.assigned_route" class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">Ruta Asignada</h2>
            <div class="flex items-center p-3 bg-gray-50 rounded-lg">
              <TruckIcon class="w-8 h-8 text-primary-600 mr-3" />
              <div>
                <p class="font-medium text-gray-900">{{ order.assigned_route.route_name }}</p>
                <p class="text-sm text-gray-500">{{ formatDate(order.assigned_route.route_date) }}</p>
              </div>
            </div>
          </div>

          <!-- Status guide -->
          <div class="card bg-gray-50">
            <h2 class="text-sm font-semibold text-gray-700 mb-3">Flujo de estados</h2>
            <ol class="space-y-2 text-xs">
              <li class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-yellow-100 text-yellow-700 flex items-center justify-center font-bold text-xs">1</span>
                <span :class="order.order_status === 'PENDIENTE' ? 'font-semibold text-gray-900' : 'text-gray-400'">PENDIENTE — botón "Iniciar Preparación"</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">2</span>
                <span :class="order.order_status === 'EN_PREPARACION' ? 'font-semibold text-gray-900' : 'text-gray-400'">EN_PREPARACION — registrar boleta/factura</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs">3</span>
                <span :class="order.order_status === 'DOCUMENTADO' ? 'font-semibold text-gray-900' : 'text-gray-400'">DOCUMENTADO — incluir en ruta y activarla</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-green-100 text-green-700 flex items-center justify-center font-bold text-xs">4</span>
                <span :class="order.order_status === 'EN_RUTA' ? 'font-semibold text-gray-900' : 'text-gray-400'">EN_RUTA — botón "Marcar Entregado"</span>
              </li>
              <li class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">5</span>
                <span :class="order.order_status === 'ENTREGADO' ? 'font-semibold text-gray-900' : 'text-gray-400'">ENTREGADO ✓</span>
              </li>
            </ol>
          </div>

          <!-- Created by -->
          <div class="card">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Creado por</h2>
            <div class="flex items-center">
              <div class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center mr-3">
                <span class="text-sm font-semibold text-gray-600">
                  {{ order.created_by?.username?.charAt(0)?.toUpperCase() || '?' }}
                </span>
              </div>
              <div>
                <p class="font-medium text-gray-900">{{ order.created_by?.username || 'Desconocido' }}</p>
                <p class="text-sm text-gray-500">{{ order.created_by?.email }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Incident dialog -->
    <div
      v-if="showIncidentDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">Reportar Incidencia</h3>
        <p class="text-sm text-gray-500 mb-4">Describe el problema ocurrido en la entrega.</p>
        <textarea
          v-model="incidentReason"
          rows="3"
          class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          placeholder="Ej: Cliente no estaba en el domicilio..."
        ></textarea>
        <div class="flex justify-end space-x-3 mt-4">
          <button
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            @click="showIncidentDialog = false; incidentReason = ''"
          >
            Cancelar
          </button>
          <button
            :disabled="isTransitioning"
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
            @click="handleReportIncident"
          >
            {{ isTransitioning ? 'Guardando...' : 'Confirmar Incidencia' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="Eliminar Pedido"
      :message="`¿Estás seguro de eliminar el pedido ${order?.order_number}? Esta acción no se puede deshacer.`"
      type="danger"
      confirm-text="Eliminar"
      :loading="isDeleting"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
