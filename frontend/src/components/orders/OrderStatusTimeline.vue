<script setup lang="ts">
import { computed } from 'vue'
import type { OrderStatus } from '@/types'
import {
  ClockIcon,
  CubeIcon,
  DocumentCheckIcon,
  TruckIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/vue/24/solid'

interface Props {
  status: OrderStatus
}

const props = defineProps<Props>()

const steps = [
  { key: 'PENDIENTE', label: 'Pendiente', icon: ClockIcon },
  { key: 'EN_PREPARACION', label: 'En Preparación', icon: CubeIcon },
  { key: 'DOCUMENTADO', label: 'Documentado', icon: DocumentCheckIcon },
  { key: 'EN_RUTA', label: 'En Ruta', icon: TruckIcon },
  { key: 'ENTREGADO', label: 'Entregado', icon: CheckCircleIcon },
]

const statusOrder: Record<OrderStatus, number> = {
  PENDIENTE: 0,
  EN_PREPARACION: 1,
  DOCUMENTADO: 2,
  EN_RUTA: 3,
  ENTREGADO: 4,
  INCIDENCIA: -1,
}

const currentIndex = computed(() => statusOrder[props.status])
const isIncident = computed(() => props.status === 'INCIDENCIA')

const getStepStatus = (index: number) => {
  if (isIncident.value) {
    return index === 0 ? 'incident' : 'pending'
  }
  if (index < currentIndex.value) return 'completed'
  if (index === currentIndex.value) return 'current'
  return 'pending'
}

const getStepClasses = (status: string) => {
  switch (status) {
    case 'completed':
      return {
        circle: 'bg-success-500 text-white',
        line: 'bg-success-500',
        label: 'text-success-700 font-medium',
      }
    case 'current':
      return {
        circle: 'bg-primary-500 text-white ring-4 ring-primary-100',
        line: 'bg-gray-200',
        label: 'text-primary-700 font-semibold',
      }
    case 'incident':
      return {
        circle: 'bg-danger-500 text-white ring-4 ring-danger-100',
        line: 'bg-gray-200',
        label: 'text-danger-700 font-semibold',
      }
    default:
      return {
        circle: 'bg-gray-200 text-gray-400',
        line: 'bg-gray-200',
        label: 'text-gray-500',
      }
  }
}
</script>

<template>
  <div>
    <!-- Incident alert -->
    <div
      v-if="isIncident"
      class="mb-6 p-4 bg-danger-50 border border-danger-200 rounded-xl flex items-center"
    >
      <ExclamationTriangleIcon class="w-6 h-6 text-danger-500 mr-3" />
      <div>
        <p class="font-medium text-danger-700">Incidencia Reportada</p>
        <p class="text-sm text-danger-600">Este pedido tiene una incidencia pendiente de resolver</p>
      </div>
    </div>

    <!-- Timeline -->
    <div class="relative">
      <div class="flex items-center justify-between">
        <template v-for="(step, index) in steps" :key="step.key">
          <!-- Step -->
          <div class="flex flex-col items-center relative z-10">
            <div
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300',
                getStepClasses(getStepStatus(index)).circle,
              ]"
            >
              <component :is="step.icon" class="w-5 h-5" />
            </div>
            <span
              :class="[
                'mt-2 text-xs text-center max-w-[80px]',
                getStepClasses(getStepStatus(index)).label,
              ]"
            >
              {{ step.label }}
            </span>
          </div>

          <!-- Connector line -->
          <div
            v-if="index < steps.length - 1"
            class="flex-1 h-1 mx-2 -mt-6"
            :class="getStepClasses(getStepStatus(index)).line"
          ></div>
        </template>
      </div>
    </div>
  </div>
</template>
