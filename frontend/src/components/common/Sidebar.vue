<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { RoleName } from '@/types'
import {
  HomeIcon,
  ClipboardDocumentListIcon,
  TruckIcon,
  MapIcon,
  UsersIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

interface Props {
  isOpen: boolean
}

interface MenuItem {
  name: string
  path: string
  icon: typeof HomeIcon
  roles: RoleName[]
}

defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const route = useRoute()
const authStore = useAuthStore()

const menuItems: MenuItem[] = [
  {
    name: 'Dashboard',
    path: '/',
    icon: HomeIcon,
    roles: ['Administrador', 'Encargado de Bodega', 'Vendedor', 'Repartidor'],
  },
  {
    name: 'Pedidos',
    path: '/orders',
    icon: ClipboardDocumentListIcon,
    roles: ['Administrador', 'Encargado de Bodega', 'Vendedor'],
  },
  {
    name: 'Rutas',
    path: '/routes',
    icon: TruckIcon,
    roles: ['Administrador', 'Encargado de Bodega'],
  },
  {
    name: 'Mis Entregas',
    path: '/tracking',
    icon: MapIcon,
    roles: ['Repartidor'],
  },
  {
    name: 'Usuarios',
    path: '/users',
    icon: UsersIcon,
    roles: ['Administrador'],
  },
  {
    name: 'Reportes',
    path: '/reports',
    icon: ChartBarIcon,
    roles: ['Administrador', 'Encargado de Bodega'],
  },
  {
    name: 'Auditoría',
    path: '/audit-logs',
    icon: ShieldCheckIcon,
    roles: ['Administrador'],
  },
]

const visibleMenuItems = computed(() => {
  return menuItems.filter((item) => authStore.hasRole(item.roles))
})

const isActive = (path: string) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

const close = () => {
  emit('close')
}
</script>

<template>
  <!-- Mobile backdrop -->
  <div
    v-if="isOpen"
    class="fixed inset-0 z-40 lg:hidden"
    style="background-color: rgba(0,0,0,0.6);"
    @click="close"
  />

  <!-- Sidebar oscuro estilo Socomep -->
  <aside
    :class="[
      'fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 lg:relative lg:translate-x-0 flex flex-col',
      isOpen ? 'translate-x-0' : '-translate-x-full',
    ]"
    style="background-color: #222222;"
  >
    <div class="flex flex-col h-full">

      <!-- Logo -->
      <div class="flex items-center justify-between h-16 px-5"
           style="border-bottom: 1px solid rgba(255,255,255,0.08);">
        <RouterLink to="/" class="flex items-center" @click="close">
          <img src="/socomep-logo.png" alt="Socomep" class="h-7 w-auto" style="filter: brightness(0) invert(1);" />
        </RouterLink>
        <button
          class="lg:hidden p-1.5 rounded-md transition-colors"
          style="color: rgba(255,255,255,0.5);"
          @click="close"
        >
          <XMarkIcon class="w-5 h-5" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-3 py-5 space-y-0.5 overflow-y-auto">
        <RouterLink
          v-for="item in visibleMenuItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'flex items-center px-3 py-2.5 text-sm font-semibold rounded-md transition-all duration-150 uppercase tracking-wide',
          ]"
          :style="isActive(item.path)
            ? 'background-color: #F02D00; color: #ffffff;'
            : 'color: rgba(255,255,255,0.55);'"
          @mouseover="(e: MouseEvent) => !isActive(item.path) && ((e.currentTarget as HTMLElement).style.backgroundColor = 'rgba(255,255,255,0.07)')"
          @mouseout="(e: MouseEvent) => !isActive(item.path) && ((e.currentTarget as HTMLElement).style.backgroundColor = 'transparent')"
          @click="close"
        >
          <component
            :is="item.icon"
            class="w-4 h-4 mr-3 flex-shrink-0"
            :style="isActive(item.path) ? 'color: rgba(255,255,255,0.9)' : 'color: rgba(255,255,255,0.4)'"
          />
          {{ item.name }}
        </RouterLink>
      </nav>

      <!-- User info -->
      <div class="px-3 py-4" style="border-top: 1px solid rgba(255,255,255,0.08);">
        <div class="flex items-center px-3 py-3 rounded-md"
             style="background-color: rgba(255,255,255,0.05);">
          <div class="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0"
               style="background-color: #F02D00;">
            <span class="text-xs font-black text-white">
              {{ authStore.userName.charAt(0).toUpperCase() }}
            </span>
          </div>
          <div class="ml-3 flex-1 min-w-0">
            <p class="text-sm font-semibold text-white truncate">
              {{ authStore.userName }}
            </p>
            <p class="text-xs truncate" style="color: rgba(255,255,255,0.4);">
              {{ authStore.userRole }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
