<script setup lang="ts">
import { useNotificationsStore } from '@/stores/notifications'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

const notificationsStore = useNotificationsStore()

const getIcon = (type: string) => {
  switch (type) {
    case 'success':
      return CheckCircleIcon
    case 'error':
      return XCircleIcon
    case 'warning':
      return ExclamationTriangleIcon
    default:
      return InformationCircleIcon
  }
}

const getStyles = (type: string) => {
  switch (type) {
    case 'success':
      return 'bg-success-50 border-success-200 text-success-800'
    case 'error':
      return 'bg-danger-50 border-danger-200 text-danger-800'
    case 'warning':
      return 'bg-warning-50 border-warning-200 text-warning-800'
    default:
      return 'bg-info-50 border-info-200 text-info-800'
  }
}

const getIconStyles = (type: string) => {
  switch (type) {
    case 'success':
      return 'text-success-500'
    case 'error':
      return 'text-danger-500'
    case 'warning':
      return 'text-warning-500'
    default:
      return 'text-info-500'
  }
}
</script>

<template>
  <div class="fixed top-4 right-4 z-50 space-y-3 max-w-sm w-full">
    <TransitionGroup
      enter-active-class="transition ease-out duration-300"
      enter-from-class="transform translate-x-full opacity-0"
      enter-to-class="transform translate-x-0 opacity-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="transform translate-x-0 opacity-100"
      leave-to-class="transform translate-x-full opacity-0"
    >
      <div
        v-for="notification in notificationsStore.notifications"
        :key="notification.id"
        :class="[
          'flex items-start p-4 rounded-xl border shadow-lg',
          getStyles(notification.type),
        ]"
      >
        <component
          :is="getIcon(notification.type)"
          :class="['w-5 h-5 flex-shrink-0', getIconStyles(notification.type)]"
        />
        <div class="ml-3 flex-1">
          <p class="text-sm font-semibold">{{ notification.title }}</p>
          <p class="text-sm mt-0.5 opacity-90">{{ notification.message }}</p>
        </div>
        <button
          class="ml-3 flex-shrink-0 p-1 rounded-lg hover:bg-black/5 transition-colors"
          @click="notificationsStore.removeNotification(notification.id)"
        >
          <XMarkIcon class="w-4 h-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
