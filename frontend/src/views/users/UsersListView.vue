<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUsersStore } from '@/stores/users'
import { useNotificationsStore } from '@/stores/notifications'
import type { User } from '@/types'
import DataTable from '@/components/common/DataTable.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

const router = useRouter()
const usersStore = useUsersStore()
const notifications = useNotificationsStore()

const searchQuery = ref('')
const showDeleteDialog = ref(false)
const selectedUser = ref<User | null>(null)
const isDeleting = ref(false)

const columns = [
  { key: 'full_name', label: 'Nombre' },
  { key: 'email', label: 'Email' },
  { key: 'role.name', label: 'Rol', width: '150px' },
  { key: 'is_active', label: 'Estado', width: '100px' },
  { key: 'created_at', label: 'Creado', width: '130px' },
  { key: 'actions', label: '', width: '120px' },
]

onMounted(() => {
  loadUsers()
})

watch(searchQuery, () => {
  usersStore.setSearch(searchQuery.value)
  loadUsers()
})

const loadUsers = async () => {
  try {
    await usersStore.fetchUsers()
  } catch (error) {
    console.error('Error loading users:', error)
  }
}

const handlePageChange = (page: number) => {
  usersStore.setPage(page)
  loadUsers()
}

const handleRowClick = (user: User) => {
  router.push(`/users/${user.id}/edit`)
}

const openDeleteDialog = (user: User, event: Event) => {
  event.stopPropagation()
  selectedUser.value = user
  showDeleteDialog.value = true
}

const handleDelete = async () => {
  if (!selectedUser.value) return

  isDeleting.value = true
  try {
    await usersStore.deleteUser(selectedUser.value.id)
    notifications.success('Usuario eliminado', 'El usuario ha sido eliminado correctamente')
  } catch {
    notifications.error('Error', 'No se pudo eliminar el usuario')
  } finally {
    isDeleting.value = false
    showDeleteDialog.value = false
  }
}

const toggleUserStatus = async (user: User, event: Event) => {
  event.stopPropagation()
  try {
    await usersStore.toggleUserActive(user.id)
    notifications.success(
      'Estado actualizado',
      `El usuario ha sido ${user.is_active ? 'desactivado' : 'activado'}`
    )
  } catch {
    notifications.error('Error', 'No se pudo actualizar el estado')
  }
}

const formatDate = (date: string | null | undefined) => {
  if (!date) return '-'
  try {
    return format(new Date(date), 'dd MMM yyyy', { locale: es })
  } catch {
    return '-'
  }
}

const getRoleBadgeClass = (roleName: string) => {
  const classes: Record<string, string> = {
    Administrador: 'bg-purple-100 text-purple-700',
    'Encargado de Bodega': 'bg-blue-100 text-blue-700',
    Vendedor: 'bg-green-100 text-green-700',
    Repartidor: 'bg-orange-100 text-orange-700',
  }
  return classes[roleName] || 'bg-gray-100 text-gray-700'
}
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6">
      <div>
        <h1 class="page-title">Usuarios</h1>
        <p class="page-description">Gestión de usuarios del sistema</p>
      </div>

      <RouterLink to="/users/create" class="btn-primary mt-4 sm:mt-0">
        <PlusIcon class="w-5 h-5 mr-2" />
        Nuevo Usuario
      </RouterLink>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      <div class="card">
        <p class="text-sm text-gray-500">Total Usuarios</p>
        <p class="text-2xl font-bold text-gray-900">{{ usersStore.pagination.total }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-500">Activos</p>
        <p class="text-2xl font-bold text-success-600">{{ usersStore.activeUsers.length }}</p>
      </div>
      <div class="card">
        <p class="text-sm text-gray-500">Inactivos</p>
        <p class="text-2xl font-bold text-gray-500">{{ usersStore.inactiveUsers.length }}</p>
      </div>
    </div>

    <!-- Search -->
    <div class="card mb-6">
      <div class="relative">
        <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar por nombre o email..."
          class="input pl-10"
        />
      </div>
    </div>

    <!-- Users table -->
    <DataTable
      :columns="columns"
      :data="usersStore.users"
      :loading="usersStore.isLoading"
      :page="usersStore.pagination.page"
      :total-pages="usersStore.pagination.pages"
      :total-items="usersStore.pagination.total"
      :page-size="usersStore.pagination.size"
      empty-message="No hay usuarios para mostrar"
      @page-change="handlePageChange"
      @row-click="handleRowClick"
    >
      <template #cell-full_name="{ row }">
        <div class="flex items-center">
          <div class="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center mr-3">
            <span class="text-sm font-semibold text-primary-700">
              {{ (row.full_name ?? '?').charAt(0).toUpperCase() }}
            </span>
          </div>
          <div>
            <p class="font-medium text-gray-900">{{ row.full_name }}</p>
          </div>
        </div>
      </template>

      <template #cell-email="{ value }">
        <span class="text-sm text-gray-600">{{ value }}</span>
      </template>

      <template #cell-role.name="{ row }">
        <span
          :class="[
            'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
            getRoleBadgeClass(row.role?.name || ''),
          ]"
        >
          {{ row.role?.name || 'Sin rol' }}
        </span>
      </template>

      <template #cell-is_active="{ row }">
        <button
          :class="[
            'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors',
            row.is_active
              ? 'bg-success-100 text-success-700 hover:bg-success-200'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
          ]"
          @click="toggleUserStatus(row, $event)"
        >
          {{ row.is_active ? 'Activo' : 'Inactivo' }}
        </button>
      </template>

      <template #cell-created_at="{ value }">
        <span class="text-sm text-gray-500">{{ formatDate(value as string) }}</span>
      </template>

      <template #cell-actions="{ row }">
        <div class="flex items-center space-x-2" @click.stop>
          <button
            class="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
            title="Editar"
            @click="router.push(`/users/${row.id}/edit`)"
          >
            <PencilIcon class="w-4 h-4" />
          </button>
          <button
            class="p-2 text-gray-400 hover:text-danger-600 hover:bg-danger-50 rounded-lg transition-colors"
            title="Eliminar"
            @click="openDeleteDialog(row, $event)"
          >
            <TrashIcon class="w-4 h-4" />
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Delete confirmation -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="Eliminar Usuario"
      :message="`¿Estás seguro de eliminar a ${selectedUser?.full_name}? Esta acción no se puede deshacer.`"
      type="danger"
      confirm-text="Eliminar"
      :loading="isDeleting"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
