<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useVehiclesStore } from '@/stores/vehicles'
import { useUsersStore } from '@/stores/users'
import { useNotificationsStore } from '@/stores/notifications'
import type { VehicleCreate, VehicleUpdate } from '@/services/vehicles.service'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'

const router = useRouter()
const route = useRoute()
const store = useVehiclesStore()
const usersStore = useUsersStore()
const notifications = useNotificationsStore()

const isEdit = computed(() => !!route.params.id)
const vehicleId = computed(() => route.params.id as string)
const isSubmitting = ref(false)
const isLoading = ref(false)

interface FormData {
  plate_number: string
  alias: string
  brand: string
  model_name: string
  year: string
  max_load_kg: string
  max_volume_m3: string
  gps_device_id: string
  assigned_driver_id: string
}

const form = ref<FormData>({
  plate_number: '',
  alias: '',
  brand: '',
  model_name: '',
  year: '',
  max_load_kg: '',
  max_volume_m3: '',
  gps_device_id: '',
  assigned_driver_id: '',
})

const errors = ref<Record<string, string>>({})

onMounted(async () => {
  await usersStore.fetchDrivers()
  if (isEdit.value) {
    isLoading.value = true
    try {
      const v = await store.fetchById(vehicleId.value)
      form.value = {
        plate_number: v.plate_number,
        alias: v.alias || '',
        brand: v.brand || '',
        model_name: v.model_name || '',
        year: v.year?.toString() || '',
        max_load_kg: v.max_load_kg?.toString() || '',
        max_volume_m3: v.max_volume_m3?.toString() || '',
        gps_device_id: v.gps_device_id || '',
        assigned_driver_id: v.assigned_driver_id || '',
      }
    } catch {
      notifications.error('Error', 'No se pudo cargar el vehículo')
      router.push('/vehicles')
    } finally {
      isLoading.value = false
    }
  }
})

const isValid = computed(() => form.value.plate_number.trim().length >= 4)

function validate(): boolean {
  errors.value = {}
  if (!form.value.plate_number.trim()) {
    errors.value.plate_number = 'La placa es obligatoria'
  }
  if (form.value.year && (isNaN(Number(form.value.year)) || Number(form.value.year) < 1990)) {
    errors.value.year = 'Año inválido'
  }
  return Object.keys(errors.value).length === 0
}

async function submit() {
  if (!validate()) return
  isSubmitting.value = true
  try {
    const payload = {
      plate_number: form.value.plate_number.trim().toUpperCase(),
      alias: form.value.alias || undefined,
      brand: form.value.brand || undefined,
      model_name: form.value.model_name || undefined,
      year: form.value.year ? Number(form.value.year) : undefined,
      max_load_kg: form.value.max_load_kg ? Number(form.value.max_load_kg) : undefined,
      max_volume_m3: form.value.max_volume_m3 ? Number(form.value.max_volume_m3) : undefined,
      gps_device_id: form.value.gps_device_id || undefined,
      assigned_driver_id: form.value.assigned_driver_id || undefined,
    }

    if (isEdit.value) {
      await store.updateVehicle(vehicleId.value, payload as VehicleUpdate)
      notifications.success('Vehículos', 'Vehículo actualizado')
    } else {
      await store.createVehicle(payload as VehicleCreate)
      notifications.success('Vehículos', 'Vehículo creado')
    }
    router.push('/vehicles')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string | { message?: string } } } })
      ?.response?.data?.detail
    if (typeof msg === 'object' && msg?.message) {
      notifications.error('Error', msg.message)
    } else if (typeof msg === 'string') {
      notifications.error('Error', msg)
    } else {
      notifications.error('Error', 'Error al guardar el vehículo')
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="p-6 max-w-2xl mx-auto">
    <button @click="router.back()" class="flex items-center gap-2 text-gray-500 hover:text-gray-700 mb-6">
      <ArrowLeftIcon class="h-4 w-4" />
      Volver
    </button>

    <h1 class="text-2xl font-bold text-gray-900 mb-6">
      {{ isEdit ? 'Editar Vehículo' : 'Nuevo Vehículo' }}
    </h1>

    <div v-if="isLoading" class="flex justify-center py-12">
      <div class="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full" />
    </div>

    <form v-else @submit.prevent="submit" class="bg-white rounded-xl border p-6 space-y-5">
      <!-- Plate -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          Placa <span class="text-red-500">*</span>
        </label>
        <input
          v-model="form.plate_number"
          type="text"
          placeholder="BCDF-12"
          :disabled="isEdit"
          class="w-full rounded-lg border px-3 py-2 text-sm uppercase font-mono disabled:bg-gray-100"
          :class="errors.plate_number ? 'border-red-400' : 'border-gray-300'"
        />
        <p v-if="errors.plate_number" class="text-xs text-red-500 mt-1">{{ errors.plate_number }}</p>
      </div>

      <!-- Alias + Brand row -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Alias</label>
          <input v-model="form.alias" type="text" placeholder="Camión 1" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Marca</label>
          <input v-model="form.brand" type="text" placeholder="Mercedes-Benz" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        </div>
      </div>

      <!-- Model + Year row -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Modelo</label>
          <input v-model="form.model_name" type="text" placeholder="Sprinter 311" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Año</label>
          <input
            v-model="form.year"
            type="number"
            placeholder="2022"
            min="1990"
            max="2100"
            class="w-full rounded-lg border px-3 py-2 text-sm"
            :class="errors.year ? 'border-red-400' : 'border-gray-300'"
          />
          <p v-if="errors.year" class="text-xs text-red-500 mt-1">{{ errors.year }}</p>
        </div>
      </div>

      <!-- Capacity row -->
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Carga máx (kg)</label>
          <input v-model="form.max_load_kg" type="number" step="0.01" placeholder="1000" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Volumen máx (m³)</label>
          <input v-model="form.max_volume_m3" type="number" step="0.01" placeholder="4.5" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        </div>
      </div>

      <!-- GPS device -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">ID Dispositivo GPS (Wialon)</label>
        <input
          v-model="form.gps_device_id"
          type="text"
          placeholder="Dejar vacío si no tiene GPS hardware"
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono"
        />
        <p class="text-xs text-gray-400 mt-1">ID de unidad en la plataforma Wialon. Opcional.</p>
      </div>

      <!-- Driver selector -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">Conductor asignado</label>
        <select v-model="form.assigned_driver_id" class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
          <option value="">Sin conductor asignado</option>
          <option
            v-for="driver in usersStore.availableDrivers"
            :key="driver.id"
            :value="driver.id"
          >
            {{ driver.full_name || driver.email }}
          </option>
        </select>
      </div>

      <!-- Actions -->
      <div class="flex gap-3 pt-2">
        <button
          type="button"
          @click="router.back()"
          class="flex-1 px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
        >
          Cancelar
        </button>
        <button
          type="submit"
          :disabled="!isValid || isSubmitting"
          class="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {{ isSubmitting ? 'Guardando...' : (isEdit ? 'Actualizar' : 'Crear Vehículo') }}
        </button>
      </div>
    </form>
  </div>
</template>
