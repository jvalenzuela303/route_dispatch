<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useOrdersStore } from '@/stores/orders'
import { useNotificationsStore } from '@/stores/notifications'
import type { OrderCreate } from '@/types'
import {
  ArrowLeftIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const ordersStore = useOrdersStore()
const notifications = useNotificationsStore()

const isSubmitting = ref(false)
const apiError = ref<string | null>(null)

const form = ref<OrderCreate>({
  customer_name: '',
  customer_phone: '+56',
  customer_email: '',
  address_text: '',
  notes: '',
  document_number: '',
  source_channel: 'WEB',
})

const errors = ref<Record<string, string>>({})

const isValid = computed(() => {
  return (
    form.value.customer_name.length >= 2 &&
    form.value.customer_phone.length >= 10 &&
    form.value.address_text.length >= 10 &&
    !!form.value.document_number.trim()
  )
})

const validateForm = (): boolean => {
  errors.value = {}
  apiError.value = null

  if (form.value.customer_name.length < 2) {
    errors.value.customer_name = 'El nombre debe tener al menos 2 caracteres'
  }

  if (!form.value.customer_phone.match(/^\+56\d{8,9}$/)) {
    errors.value.customer_phone = 'Formato requerido: +56912345678'
  }

  if (form.value.address_text.length < 10) {
    errors.value.address_text = 'La dirección debe tener al menos 10 caracteres (incluye número de calle)'
  }

  if (!form.value.document_number.trim()) {
    errors.value.document_number = 'El número de boleta/factura es obligatorio'
  }

  return Object.keys(errors.value).length === 0
}

const handleSubmit = async () => {
  if (!validateForm() || isSubmitting.value) return

  isSubmitting.value = true
  apiError.value = null

  try {
    const order = await ordersStore.createOrder(form.value)
    notifications.success('Pedido creado', `El pedido ${order.order_number} ha sido creado exitosamente`)
    router.push(`/orders/${order.id}`)
  } catch (error: any) {
    const msg =
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      'No se pudo crear el pedido'
    apiError.value = msg
    notifications.error('Error al crear pedido', msg)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="max-w-3xl mx-auto">
    <!-- Header -->
    <div class="flex items-center space-x-4 mb-6">
      <button
        class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        @click="router.back()"
      >
        <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
      </button>
      <div>
        <h1 class="page-title">Nuevo Pedido</h1>
        <p class="page-description">Completa los datos del cliente y la entrega</p>
      </div>
    </div>

    <!-- API error banner -->
    <div
      v-if="apiError"
      class="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700"
    >
      <strong>Error:</strong> {{ apiError }}
    </div>

    <form @submit.prevent="handleSubmit">
      <!-- Customer information -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Información del Cliente</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Customer name -->
          <div>
            <label for="customer_name" class="label">Nombre completo *</label>
            <input
              id="customer_name"
              v-model="form.customer_name"
              type="text"
              :class="['input', errors.customer_name ? 'input-error' : '']"
              placeholder="Juan Pérez"
            />
            <p v-if="errors.customer_name" class="mt-1 text-sm text-danger-600">{{ errors.customer_name }}</p>
          </div>

          <!-- Phone -->
          <div>
            <label for="customer_phone" class="label">Teléfono *</label>
            <input
              id="customer_phone"
              v-model="form.customer_phone"
              type="tel"
              :class="['input', errors.customer_phone ? 'input-error' : '']"
              placeholder="+56912345678"
            />
            <p v-if="errors.customer_phone" class="mt-1 text-sm text-danger-600">{{ errors.customer_phone }}</p>
            <p class="mt-1 text-xs text-gray-400">Formato: +56912345678</p>
          </div>

          <!-- Email -->
          <div>
            <label for="customer_email" class="label">Correo electrónico</label>
            <input
              id="customer_email"
              v-model="form.customer_email"
              type="email"
              class="input"
              placeholder="cliente@email.com"
            />
          </div>

          <!-- Document number -->
          <div>
            <label for="document_number" class="label">N° Boleta / Factura *</label>
            <input
              id="document_number"
              v-model="form.document_number"
              type="text"
              :class="['input', errors.document_number ? 'input-error' : '']"
              placeholder="Ej: 12345"
            />
            <p v-if="errors.document_number" class="mt-1 text-sm text-danger-600">{{ errors.document_number }}</p>
          </div>
        </div>
      </div>

      <!-- Delivery information -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Información de Entrega</h2>

        <div class="space-y-4">
          <!-- Address -->
          <div>
            <label for="address_text" class="label">Dirección de entrega *</label>
            <input
              id="address_text"
              v-model="form.address_text"
              type="text"
              :class="['input', errors.address_text ? 'input-error' : '']"
              placeholder="Calle Los Lirios 742, Rancagua"
            />
            <p v-if="errors.address_text" class="mt-1 text-sm text-danger-600">{{ errors.address_text }}</p>
            <p class="mt-1 text-xs text-gray-400">
              Incluye número de calle para mejor geocodificación (ej: Av. O'Higgins 123, Rancagua)
            </p>
          </div>

          <!-- Source channel -->
          <div>
            <label for="source_channel" class="label">Canal de venta *</label>
            <select id="source_channel" v-model="form.source_channel" class="input">
              <option value="WEB">Web</option>
              <option value="RRSS">Redes Sociales (WhatsApp / Instagram)</option>
              <option value="PRESENCIAL">Presencial</option>
            </select>
          </div>

          <!-- Notes -->
          <div>
            <label for="notes" class="label">Notas de entrega</label>
            <textarea
              id="notes"
              v-model="form.notes"
              rows="2"
              class="input"
              placeholder="Instrucciones especiales para el repartidor..."
            ></textarea>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex items-center justify-end space-x-4">
        <button
          type="button"
          class="btn-secondary"
          @click="router.back()"
        >
          Cancelar
        </button>
        <button
          type="submit"
          class="btn-primary"
          :disabled="!isValid || isSubmitting"
        >
          <span v-if="isSubmitting" class="spinner w-5 h-5 mr-2"></span>
          {{ isSubmitting ? 'Creando...' : 'Crear Pedido' }}
        </button>
      </div>
    </form>
  </div>
</template>
