<script setup lang="ts">
import Modal from './Modal.vue'
import { ExclamationTriangleIcon, TrashIcon, CheckCircleIcon } from '@heroicons/vue/24/outline'

interface Props {
  open: boolean
  title?: string
  message: string
  type?: 'danger' | 'warning' | 'success'
  confirmText?: string
  cancelText?: string
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  title: 'Confirmar acción',
  type: 'warning',
  confirmText: 'Confirmar',
  cancelText: 'Cancelar',
  loading: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const icons = {
  danger: TrashIcon,
  warning: ExclamationTriangleIcon,
  success: CheckCircleIcon,
}

const iconColors = {
  danger: 'text-danger-600 bg-danger-100',
  warning: 'text-warning-600 bg-warning-100',
  success: 'text-success-600 bg-success-100',
}

const buttonColors = {
  danger: 'btn-danger',
  warning: 'btn-warning',
  success: 'btn-success',
}
</script>

<template>
  <Modal :open="open" size="sm" @close="emit('cancel')">
    <div class="text-center">
      <div
        :class="[
          'mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4',
          iconColors[type],
        ]"
      >
        <component :is="icons[type]" class="w-6 h-6" />
      </div>

      <h3 class="text-lg font-semibold text-gray-900 mb-2">
        {{ title }}
      </h3>

      <p class="text-sm text-gray-600">
        {{ message }}
      </p>
    </div>

    <template #footer>
      <div class="flex justify-end space-x-3">
        <button
          class="btn-secondary"
          :disabled="loading"
          @click="emit('cancel')"
        >
          {{ cancelText }}
        </button>
        <button
          :class="['btn', buttonColors[type]]"
          :disabled="loading"
          @click="emit('confirm')"
        >
          <span v-if="loading" class="spinner w-4 h-4 mr-2"></span>
          {{ confirmText }}
        </button>
      </div>
    </template>
  </Modal>
</template>
