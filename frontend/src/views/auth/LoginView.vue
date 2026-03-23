<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationsStore } from '@/stores/notifications'
import { EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const notifications = useNotificationsStore()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const isSubmitting = ref(false)
const formError = ref('')

const isValid = computed(() => {
  return email.value.length > 0 && password.value.length > 0
})

const togglePassword = () => {
  showPassword.value = !showPassword.value
}

const handleSubmit = async () => {
  if (!isValid.value || isSubmitting.value) return

  isSubmitting.value = true
  formError.value = ''

  try {
    await authStore.login({
      email: email.value,
      password: password.value,
    })

    notifications.success('Bienvenido', `Hola, ${authStore.userName}`)

    const redirect = route.query.redirect as string
    router.push(redirect || '/')
  } catch (error) {
    formError.value = 'Credenciales inválidas. Por favor, verifica tu usuario y contraseña.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex">

    <!-- Panel izquierdo — branding oscuro estilo Socomep -->
    <div class="hidden lg:flex lg:w-1/2 flex-col justify-between p-12"
         style="background-color: #222222;">

      <!-- Logo Socomep -->
      <div>
        <img src="/socomep-logo.png" alt="Socomep" class="h-8 w-auto" style="filter: brightness(0) invert(1);" />
        <span class="text-white/40 text-xs uppercase tracking-widest block mt-2" style="font-size: 0.65rem;">Sistema de Despacho</span>
      </div>

      <!-- Hero text -->
      <div>
        <!-- Línea roja decorativa -->
        <div class="w-12 h-1 mb-6 rounded-full" style="background-color: #F02D00;"></div>
        <h1 class="text-5xl font-black text-white uppercase leading-tight mb-4">
          Gestión de<br />
          <span style="color: #F02D00;">Entregas</span><br />
          Inteligente
        </h1>
        <p class="text-white/60 text-base leading-relaxed max-w-sm">
          Optimiza rutas de despacho. Controla pedidos,
          facturas y repartidores desde un solo lugar.
        </p>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-3 gap-6">
        <div class="border-l-2 pl-4" style="border-color: #F02D00;">
          <p class="text-3xl font-black text-white">24+</p>
          <p class="text-white/50 text-xs uppercase tracking-wider">Endpoints</p>
        </div>
        <div class="border-l-2 pl-4" style="border-color: #00B2BD;">
          <p class="text-3xl font-black text-white">4</p>
          <p class="text-white/50 text-xs uppercase tracking-wider">Roles</p>
        </div>
        <div class="border-l-2 pl-4" style="border-color: #F02D00;">
          <p class="text-3xl font-black text-white">100%</p>
          <p class="text-white/50 text-xs uppercase tracking-wider">Optimizado</p>
        </div>
      </div>
    </div>

    <!-- Panel derecho — formulario -->
    <div class="flex-1 flex items-center justify-center p-8 bg-gray-100">
      <div class="w-full max-w-md">

        <!-- Logo mobile -->
        <div class="lg:hidden flex items-center justify-center mb-8">
          <img src="/socomep-logo.png" alt="Socomep" class="h-8 w-auto" />
        </div>

        <!-- Card formulario -->
        <div class="bg-white rounded-2xl shadow-medium p-8">

          <!-- Encabezado -->
          <div class="mb-8">
            <div class="w-8 h-1 rounded-full mb-4" style="background-color: #F02D00;"></div>
            <h2 class="text-2xl font-black uppercase text-gray-900 tracking-tight">
              Iniciar Sesión
            </h2>
            <p class="text-gray-500 text-sm mt-1">
              Ingresa tus credenciales para continuar
            </p>
          </div>

          <!-- Error -->
          <div
            v-if="formError"
            class="mb-6 p-4 bg-red-50 border-l-4 rounded-lg text-red-700 text-sm"
            style="border-color: #F02D00;"
          >
            {{ formError }}
          </div>

          <form @submit.prevent="handleSubmit">
            <div class="space-y-5">

              <!-- Usuario / Email -->
              <div>
                <label for="email" class="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                  Usuario o Correo
                </label>
                <input
                  id="email"
                  v-model="email"
                  type="email"
                  class="input"
                  placeholder="tu@email.com"
                  autocomplete="email"
                  required
                />
              </div>

              <!-- Contraseña -->
              <div>
                <label for="password" class="block text-xs font-bold uppercase tracking-wider text-gray-600 mb-1.5">
                  Contraseña
                </label>
                <div class="relative">
                  <input
                    id="password"
                    v-model="password"
                    :type="showPassword ? 'text' : 'password'"
                    class="input pr-12"
                    placeholder="••••••••"
                    autocomplete="current-password"
                    required
                  />
                  <button
                    type="button"
                    class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                    @click="togglePassword"
                  >
                    <EyeSlashIcon v-if="showPassword" class="w-5 h-5" />
                    <EyeIcon v-else class="w-5 h-5" />
                  </button>
                </div>
              </div>

              <!-- Recordarme -->
              <div class="flex items-center justify-between">
                <label class="flex items-center">
                  <input
                    type="checkbox"
                    class="rounded border-gray-300 focus:ring-primary-500"
                    style="accent-color: #F02D00;"
                  />
                  <span class="ml-2 text-sm text-gray-600">Recordarme</span>
                </label>
                <a href="#" class="text-sm font-medium hover:underline" style="color: #F02D00;">
                  ¿Olvidaste tu contraseña?
                </a>
              </div>

              <!-- Botón submit -->
              <button
                type="submit"
                class="w-full py-3 px-4 rounded-lg text-white font-bold uppercase tracking-wider text-sm
                       transition-all duration-200 flex items-center justify-center
                       disabled:opacity-50 disabled:cursor-not-allowed"
                style="background-color: #F02D00;"
                :style="{ backgroundColor: isSubmitting ? '#d42400' : '#F02D00' }"
                :disabled="!isValid || isSubmitting"
                @mouseover="(e: MouseEvent) => !isSubmitting && ((e.target as HTMLElement).style.backgroundColor = '#ff5731')"
                @mouseout="(e: MouseEvent) => !isSubmitting && ((e.target as HTMLElement).style.backgroundColor = '#F02D00')"
              >
                <span v-if="isSubmitting" class="spinner w-5 h-5 mr-2"></span>
                {{ isSubmitting ? 'Ingresando...' : 'Ingresar' }}
              </button>
            </div>
          </form>
        </div>

        <p class="text-center mt-6 text-xs text-gray-400 uppercase tracking-wider">
          Logistics © {{ new Date().getFullYear() }}
        </p>
      </div>
    </div>
  </div>
</template>
