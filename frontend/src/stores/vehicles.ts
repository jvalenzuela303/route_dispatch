import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import vehiclesService, { type Vehicle, type VehicleCreate, type VehicleUpdate } from '@/services/vehicles.service'

export const useVehiclesStore = defineStore('vehicles', () => {
  // State
  const vehicles = ref<Vehicle[]>([])
  const availableVehicles = ref<Vehicle[]>([])
  const currentVehicle = ref<Vehicle | null>(null)
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const byStatus = computed(() => ({
    AVAILABLE: vehicles.value.filter((v) => v.status === 'AVAILABLE'),
    IN_ROUTE: vehicles.value.filter((v) => v.status === 'IN_ROUTE'),
    MAINTENANCE: vehicles.value.filter((v) => v.status === 'MAINTENANCE'),
  }))

  // Actions
  async function fetchVehicles(includeInactive = false): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const result = await vehiclesService.getAll({ include_inactive: includeInactive, limit: 200 })
      vehicles.value = result.items
      total.value = result.total
    } catch (e: unknown) {
      error.value = (e as Error).message
    } finally {
      isLoading.value = false
    }
  }

  async function fetchAvailable(): Promise<void> {
    try {
      availableVehicles.value = await vehiclesService.getAvailable()
    } catch {
      availableVehicles.value = []
    }
  }

  async function fetchById(id: string): Promise<Vehicle> {
    isLoading.value = true
    error.value = null
    try {
      const v = await vehiclesService.getById(id)
      currentVehicle.value = v
      return v
    } catch (e: unknown) {
      error.value = (e as Error).message
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function createVehicle(data: VehicleCreate): Promise<Vehicle> {
    const v = await vehiclesService.create(data)
    vehicles.value.unshift(v)
    total.value++
    return v
  }

  async function updateVehicle(id: string, data: VehicleUpdate): Promise<Vehicle> {
    const v = await vehiclesService.update(id, data)
    const idx = vehicles.value.findIndex((x) => x.id === id)
    if (idx !== -1) vehicles.value[idx] = v
    if (currentVehicle.value?.id === id) currentVehicle.value = v
    return v
  }

  async function deleteVehicle(id: string): Promise<void> {
    await vehiclesService.delete(id)
    vehicles.value = vehicles.value.filter((v) => v.id !== id)
    total.value--
  }

  async function assignDriver(vehicleId: string, userId: string): Promise<Vehicle> {
    const v = await vehiclesService.assignDriver(vehicleId, userId)
    _updateInList(v)
    return v
  }

  async function unassignDriver(vehicleId: string): Promise<Vehicle> {
    const v = await vehiclesService.unassignDriver(vehicleId)
    _updateInList(v)
    return v
  }

  async function setMaintenance(vehicleId: string): Promise<Vehicle> {
    const v = await vehiclesService.setMaintenance(vehicleId)
    _updateInList(v)
    return v
  }

  async function release(vehicleId: string): Promise<Vehicle> {
    const v = await vehiclesService.release(vehicleId)
    _updateInList(v)
    return v
  }

  function _updateInList(v: Vehicle): void {
    const idx = vehicles.value.findIndex((x) => x.id === v.id)
    if (idx !== -1) vehicles.value[idx] = v
    if (currentVehicle.value?.id === v.id) currentVehicle.value = v
  }

  return {
    vehicles,
    availableVehicles,
    currentVehicle,
    total,
    isLoading,
    error,
    byStatus,
    fetchVehicles,
    fetchAvailable,
    fetchById,
    createVehicle,
    updateVehicle,
    deleteVehicle,
    assignDriver,
    unassignDriver,
    setMaintenance,
    release,
  }
})
