import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Notification } from '@/types'

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref<Notification[]>([])

  function addNotification(notification: Omit<Notification, 'id'>): string {
    const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const newNotification: Notification = {
      ...notification,
      id,
      duration: notification.duration ?? 5000,
    }

    notifications.value.push(newNotification)

    // Auto-remove after duration
    if (newNotification.duration && newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }

    return id
  }

  function removeNotification(id: string): void {
    const index = notifications.value.findIndex((n) => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
    }
  }

  function clearAll(): void {
    notifications.value = []
  }

  // Convenience methods
  function success(title: string, message: string, duration?: number): string {
    return addNotification({ type: 'success', title, message, duration })
  }

  function error(title: string, message: string, duration?: number): string {
    return addNotification({ type: 'error', title, message, duration: duration ?? 8000 })
  }

  function warning(title: string, message: string, duration?: number): string {
    return addNotification({ type: 'warning', title, message, duration })
  }

  function info(title: string, message: string, duration?: number): string {
    return addNotification({ type: 'info', title, message, duration })
  }

  return {
    notifications,
    addNotification,
    removeNotification,
    clearAll,
    success,
    error,
    warning,
    info,
  }
})
