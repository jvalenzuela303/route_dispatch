<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Bars3Icon,
  BellIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline'

const emit = defineEmits<{
  'toggle-sidebar': []
}>()

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const showUserMenu = ref(false)

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const closeUserMenu = () => {
  showUserMenu.value = false
}

const logout = async () => {
  await authStore.logout()
  router.push('/login')
}

const pageTitle = () => {
  return route.meta.title || 'Dashboard'
}
</script>

<template>
  <header class="h-16 bg-white flex items-center justify-between px-6"
          style="border-bottom: 2px solid #F02D00;">

    <!-- Izquierda -->
    <div class="flex items-center space-x-4">
      <button
        class="lg:hidden p-2 rounded-md transition-colors hover:bg-gray-100"
        @click="emit('toggle-sidebar')"
      >
        <Bars3Icon class="w-6 h-6 text-gray-700" />
      </button>
      <h1 class="text-base font-black uppercase tracking-wide text-gray-900">
        {{ pageTitle() }}
      </h1>
    </div>

    <!-- Derecha -->
    <div class="flex items-center space-x-3">

      <!-- Notificaciones -->
      <button class="p-2 rounded-md hover:bg-gray-100 transition-colors relative">
        <BellIcon class="w-5 h-5 text-gray-600" />
        <span class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full"
              style="background-color: #F02D00;"></span>
      </button>

      <!-- Menú usuario -->
      <div class="relative">
        <button
          class="flex items-center space-x-2.5 px-3 py-1.5 rounded-md hover:bg-gray-100 transition-colors"
          @click="toggleUserMenu"
        >
          <div class="w-8 h-8 rounded-md flex items-center justify-center"
               style="background-color: #F02D00;">
            <span class="text-xs font-black text-white">
              {{ authStore.userName.charAt(0).toUpperCase() }}
            </span>
          </div>
          <div class="hidden md:block text-left">
            <p class="text-sm font-semibold text-gray-800 leading-tight">{{ authStore.userName }}</p>
            <p class="text-xs text-gray-400 leading-tight uppercase tracking-wide" style="font-size: 0.65rem;">
              {{ authStore.userRole }}
            </p>
          </div>
        </button>

        <!-- Dropdown -->
        <transition
          enter-active-class="transition ease-out duration-100"
          enter-from-class="transform opacity-0 scale-95"
          enter-to-class="transform opacity-100 scale-100"
          leave-active-class="transition ease-in duration-75"
          leave-from-class="transform opacity-100 scale-100"
          leave-to-class="transform opacity-0 scale-95"
        >
          <div
            v-if="showUserMenu"
            class="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-medium border border-gray-100 py-1 z-50"
            @click="closeUserMenu"
          >
            <div class="px-4 py-3" style="border-bottom: 1px solid #f3f4f6;">
              <p class="text-sm font-bold text-gray-900">{{ authStore.userName }}</p>
              <p class="text-xs text-gray-500">{{ authStore.user?.email }}</p>
            </div>

            <button class="w-full flex items-center px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
              <UserCircleIcon class="w-4 h-4 mr-3 text-gray-400" />
              Mi Perfil
            </button>

            <button class="w-full flex items-center px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
              <Cog6ToothIcon class="w-4 h-4 mr-3 text-gray-400" />
              Configuración
            </button>

            <div style="border-top: 1px solid #f3f4f6;" class="mt-1 pt-1">
              <button
                class="w-full flex items-center px-4 py-2.5 text-sm font-semibold transition-colors"
                style="color: #F02D00;"
                @mouseenter="(e: MouseEvent) => (e.currentTarget as HTMLElement).style.backgroundColor = '#fff1ee'"
                @mouseleave="(e: MouseEvent) => (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'"
                @click="logout"
              >
                <ArrowRightOnRectangleIcon class="w-4 h-4 mr-3" />
                Cerrar Sesión
              </button>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </header>

  <!-- Click outside -->
  <div
    v-if="showUserMenu"
    class="fixed inset-0 z-40"
    @click="closeUserMenu"
  />
</template>
