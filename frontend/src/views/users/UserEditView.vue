<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUsersStore } from '@/stores/users'
import { useNotificationsStore } from '@/stores/notifications'
import type { UserUpdate } from '@/services/users.service'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import Modal from '@/components/common/Modal.vue'
import {
  ArrowLeftIcon,
  EyeIcon,
  EyeSlashIcon,
  KeyIcon,
} from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const usersStore = useUsersStore()
const notifications = useNotificationsStore()

const userId = computed(() =>
  Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
)
const isLoading = ref(true)
const isSubmitting = ref(false)
const showResetPasswordModal = ref(false)
const newPassword = ref('')
const showNewPassword = ref(false)
const isResettingPassword = ref(false)

const form = ref<UserUpdate>({
  email: '',
  username: '',
  full_name: '',
  role_id: '',
  is_active: true,
})

const errors = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    await usersStore.fetchRoles()
    const user = await usersStore.fetchUser(userId.value)
    form.value = {
      email: user.email,
      username: (user as any).username || user.full_name,
      full_name: user.full_name,
      role_id: user.role_id,
      is_active: user.is_active,
    }
  } catch {
    notifications.error('Error', 'No se pudo cargar el usuario')
    router.push('/users')
  } finally {
    isLoading.value = false
  }
})

const isValid = computed(() => {
  return (
    form.value.email?.includes('@') &&
    form.value.full_name &&
    form.value.full_name.length >= 2 &&
    !!form.value.role_id
  )
})

const validateForm = (): boolean => {
  errors.value = {}

  if (!form.value.email?.includes('@')) {
    errors.value.email = 'Ingresa un email válido'
  }

  if (!form.value.full_name || form.value.full_name.length < 2) {
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
    await usersStore.updateUser(userId.value, form.value)
    notifications.success('Usuario actualizado', 'Los cambios han sido guardados')
    router.push('/users')
  } catch {
    notifications.error('Error', 'No se pudo actualizar el usuario')
  } finally {
    isSubmitting.value = false
  }
}

const handleResetPassword = async () => {
  if (newPassword.value.length < 8) {
    notifications.error('Error', 'La contraseña debe tener al menos 8 caracteres')
    return
  }

  isResettingPassword.value = true

  try {
    await usersStore.resetUserPassword(userId.value, newPassword.value)
    notifications.success('Contraseña actualizada', 'La nueva contraseña ha sido establecida')
    showResetPasswordModal.value = false
    newPassword.value = ''
  } catch {
    notifications.error('Error', 'No se pudo restablecer la contraseña')
  } finally {
    isResettingPassword.value = false
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-20">
      <LoadingSpinner size="lg" text="Cargando usuario..." />
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-center space-x-4 mb-6">
        <button
          class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          @click="router.back()"
        >
          <ArrowLeftIcon class="w-5 h-5 text-gray-600" />
        </button>
        <div>
          <h1 class="page-title">Editar Usuario</h1>
          <p class="page-description">Modificar datos del usuario</p>
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
              />
              <p v-if="errors.email" class="mt-1 text-sm text-danger-600">
                {{ errors.email }}
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
                <option value="">Seleccionar rol</option>
                <option
                  v-for="role in usersStore.roles"
                  :key="role.id"
                  :value="role.id"
                >
                  {{ (role as any).role_name || role.name }}
                </option>
              </select>
              <p v-if="errors.role_id" class="mt-1 text-sm text-danger-600">
                {{ errors.role_id }}
              </p>
            </div>

            <!-- Active status -->
            <div>
              <label class="flex items-center">
                <input
                  v-model="form.is_active"
                  type="checkbox"
                  class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span class="ml-2 text-sm text-gray-700">Usuario activo</span>
              </label>
              <p class="text-xs text-gray-500 mt-1">
                Los usuarios inactivos no pueden iniciar sesión
              </p>
            </div>

            <!-- Reset password button -->
            <div class="pt-4 border-t border-gray-100">
              <button
                type="button"
                class="btn-secondary"
                @click="showResetPasswordModal = true"
              >
                <KeyIcon class="w-5 h-5 mr-2" />
                Restablecer Contraseña
              </button>
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
              {{ isSubmitting ? 'Guardando...' : 'Guardar Cambios' }}
            </button>
          </div>
        </div>
      </form>
    </template>

    <!-- Reset password modal -->
    <Modal
      :open="showResetPasswordModal"
      title="Restablecer Contraseña"
      @close="showResetPasswordModal = false"
    >
      <div class="space-y-4">
        <p class="text-gray-600">
          Ingresa la nueva contraseña para el usuario.
        </p>

        <div>
          <label for="new_password" class="label">Nueva Contraseña *</label>
          <div class="relative">
            <input
              id="new_password"
              v-model="newPassword"
              :type="showNewPassword ? 'text' : 'password'"
              class="input pr-12"
              placeholder="Mínimo 8 caracteres"
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              @click="showNewPassword = !showNewPassword"
            >
              <EyeSlashIcon v-if="showNewPassword" class="w-5 h-5" />
              <EyeIcon v-else class="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3">
          <button
            class="btn-secondary"
            @click="showResetPasswordModal = false"
          >
            Cancelar
          </button>
          <button
            class="btn-primary"
            :disabled="newPassword.length < 8 || isResettingPassword"
            @click="handleResetPassword"
          >
            <span v-if="isResettingPassword" class="spinner w-5 h-5 mr-2"></span>
            Restablecer
          </button>
        </div>
      </template>
    </Modal>
  </div>
</template>
