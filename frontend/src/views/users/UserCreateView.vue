<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUsersStore } from '@/stores/users'
import { useNotificationsStore } from '@/stores/notifications'
import type { UserCreate } from '@/services/users.service'
import { ArrowLeftIcon, EyeIcon, EyeSlashIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const usersStore = useUsersStore()
const notifications = useNotificationsStore()

const isSubmitting = ref(false)
const showPassword = ref(false)

const form = ref<UserCreate>({
  email: '',
  password: '',
  full_name: '',
  role_id: '',
})

const errors = ref<Record<string, string>>({})

onMounted(async () => {
  await usersStore.fetchRoles()
})

const isValid = computed(() => {
  return (
    form.value.email.includes('@') &&
    form.value.password.length >= 8 &&
    form.value.full_name.length >= 2 &&
    !!form.value.role_id
  )
})

const validateForm = (): boolean => {
  errors.value = {}

  if (!form.value.email.includes('@')) {
    errors.value.email = 'Ingresa un email válido'
  }

  if (form.value.password.length < 8) {
    errors.value.password = 'La contraseña debe tener al menos 8 caracteres'
  }

  if (form.value.full_name.length < 2) {
    errors.value.full_name = 'El nombre debe tener al menos 2 caracteres'
  }

  if (!form.value.role_id) {
    errors.value.role_id = 'Selecciona un rol'
  }

  return Object.keys(errors.value).length === 0
}

const handleSubmit = async () => {
  if (!validateForm() || isSubmitting.value) return

  isSubmitting.value = true

  try {
    const user = await usersStore.createUser(form.value)
    notifications.success('Usuario creado', `Se ha creado el usuario ${user.full_name}`)
    router.push('/users')
  } catch {
    notifications.error('Error', 'No se pudo crear el usuario. Verifica que el email no esté en uso.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <!-- Header -->
    <div class="flex items-center space-x-4 mb-6">
      <button
        class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        @click="router.back()"
      >
        <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
      </button>
      <div>
        <h1 class="page-title">Nuevo Usuario</h1>
        <p class="page-description">Crear una nueva cuenta de usuario</p>
      </div>
    </div>

    <form @submit.prevent="handleSubmit">
      <div class="card">
        <div class="space-y-6">
          <!-- Full name -->
          <div>
            <label for="full_name" class="label">Nombre completo *</label>
            <input
              id="full_name"
              v-model="form.full_name"
              type="text"
              :class="['input', errors.full_name ? 'input-error' : '']"
              placeholder="Juan Pérez"
            />
            <p v-if="errors.full_name" class="mt-1 text-sm text-danger-600">
              {{ errors.full_name }}
            </p>
          </div>

          <!-- Email -->
          <div>
            <label for="email" class="label">Correo electrónico *</label>
            <input
              id="email"
              v-model="form.email"
              type="email"
              :class="['input', errors.email ? 'input-error' : '']"
              placeholder="usuario@empresa.cl"
            />
            <p v-if="errors.email" class="mt-1 text-sm text-danger-600">
              {{ errors.email }}
            </p>
          </div>

          <!-- Password -->
          <div>
            <label for="password" class="label">Contraseña *</label>
            <div class="relative">
              <input
                id="password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                :class="['input pr-12', errors.password ? 'input-error' : '']"
                placeholder="Mínimo 8 caracteres"
              />
              <button
                type="button"
                class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                @click="showPassword = !showPassword"
              >
                <EyeSlashIcon v-if="showPassword" class="w-5 h-5" />
                <EyeIcon v-else class="w-5 h-5" />
              </button>
            </div>
            <p v-if="errors.password" class="mt-1 text-sm text-danger-600">
              {{ errors.password }}
            </p>
          </div>

          <!-- Role -->
          <div>
            <label for="role_id" class="label">Rol *</label>
            <select
              id="role_id"
              v-model="form.role_id"
              :class="['input', errors.role_id ? 'input-error' : '']"
            >
              <option :value="0">Seleccionar rol</option>
              <option
                v-for="role in usersStore.roles"
                :key="role.id"
                :value="role.id"
              >
                {{ role.name }}
              </option>
            </select>
            <p v-if="errors.role_id" class="mt-1 text-sm text-danger-600">
              {{ errors.role_id }}
            </p>

            <!-- Role descriptions -->
            <div class="mt-4 p-4 bg-gray-50 rounded-lg">
              <p class="text-sm font-medium text-gray-700 mb-2">Permisos por rol:</p>
              <ul class="text-xs text-gray-500 space-y-1">
                <li><strong>Administrador:</strong> Acceso completo, gestión de usuarios</li>
                <li><strong>Encargado de Bodega:</strong> Pedidos, facturas, rutas, reportes</li>
                <li><strong>Vendedor:</strong> Crear y ver sus propios pedidos y facturas</li>
                <li><strong>Repartidor:</strong> Ver y gestionar rutas asignadas</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-end space-x-4 mt-8 pt-6 border-t border-gray-100">
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
            {{ isSubmitting ? 'Creando...' : 'Crear Usuario' }}
          </button>
        </div>
      </div>
    </form>
  </div>
</template>
