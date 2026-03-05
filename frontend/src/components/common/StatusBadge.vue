<script setup lang="ts">
import { computed } from 'vue'
import type { OrderStatus, RouteStatus } from '@/types'

interface Props {
  status?: OrderStatus | RouteStatus | string
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  status: '',
  size: 'md',
})

const statusConfig: Record<string, { label: string; class: string }> = {
  // Order statuses
  PENDIENTE: { label: 'Pendiente', class: 'bg-gray-100 text-gray-700' },
  EN_PREPARACION: { label: 'En Preparación', class: 'bg-blue-100 text-blue-700' },
  DOCUMENTADO: { label: 'Documentado', class: 'bg-purple-100 text-purple-700' },
  EN_RUTA: { label: 'En Ruta', class: 'bg-warning-100 text-warning-700' },
  ENTREGADO: { label: 'Entregado', class: 'bg-success-100 text-success-700' },
  INCIDENCIA: { label: 'Incidencia', class: 'bg-danger-100 text-danger-700' },
  // Route statuses
  ACTIVA: { label: 'Activa', class: 'bg-success-100 text-success-700' },
  EN_PROGRESO: { label: 'En Progreso', class: 'bg-warning-100 text-warning-700' },
  COMPLETADA: { label: 'Completada', class: 'bg-gray-100 text-gray-700' },
  CANCELADA: { label: 'Cancelada', class: 'bg-danger-100 text-danger-700' },
  // Route stop statuses
  EN_CAMINO: { label: 'En Camino', class: 'bg-blue-100 text-blue-700' },
  LLEGADO: { label: 'Llegado', class: 'bg-purple-100 text-purple-700' },
  // Payment statuses
  PAGADO: { label: 'Pagado', class: 'bg-success-100 text-success-700' },
  ANULADO: { label: 'Anulado', class: 'bg-danger-100 text-danger-700' },
  // Priority
  NORMAL: { label: 'Normal', class: 'bg-gray-100 text-gray-700' },
  URGENTE: { label: 'Urgente', class: 'bg-warning-100 text-warning-700' },
  VIP: { label: 'VIP', class: 'bg-purple-100 text-purple-700' },
}

const config = computed(() => {
  return statusConfig[props.status] || { label: props.status, class: 'bg-gray-100 text-gray-700' }
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'px-2 py-0.5 text-xs'
    case 'lg':
      return 'px-4 py-1.5 text-sm'
    default:
      return 'px-2.5 py-1 text-xs'
  }
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center font-medium rounded-full',
      config.class,
      sizeClasses,
    ]"
  >
    {{ config.label }}
  </span>
</template>
