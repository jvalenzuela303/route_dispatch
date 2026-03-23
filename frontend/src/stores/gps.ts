import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import gpsService, { type FleetPosition, type GPSAlert, type Geofence } from '@/services/gps.service'

export const useGpsStore = defineStore('gps', () => {
  // State
  const fleetPositions = ref<FleetPosition[]>([])
  const alerts = ref<GPSAlert[]>([])
  const geofences = ref<Geofence[]>([])
  const isConnected = ref(false)
  const isLoading = ref(false)

  let _ws: WebSocket | null = null

  // Getters
  const unacknowledgedAlerts = computed(() =>
    alerts.value.filter((a) => !a.is_acknowledged)
  )

  const vehiclesOnRoute = computed(() =>
    fleetPositions.value.filter((p) => p.route_id !== null)
  )

  // Actions
  async function fetchFleetPositions(): Promise<void> {
    isLoading.value = true
    try {
      fleetPositions.value = await gpsService.getFleetPositions()
    } catch {
      // silently fail — WebSocket keeps it updated
    } finally {
      isLoading.value = false
    }
  }

  async function fetchAlerts(): Promise<void> {
    try {
      alerts.value = await gpsService.getAlerts(true)
    } catch {
      // ignore
    }
  }

  async function fetchGeofences(): Promise<void> {
    try {
      geofences.value = await gpsService.getGeofences()
    } catch {
      // ignore
    }
  }

  async function acknowledgeAlert(alertId: string): Promise<void> {
    const updated = await gpsService.acknowledgeAlert(alertId)
    const idx = alerts.value.findIndex((a) => a.id === alertId)
    if (idx !== -1) alerts.value[idx] = updated
  }

  /** Connect WebSocket and keep fleet positions live */
  function connectFleetWS(): void {
    if (_ws && _ws.readyState === WebSocket.OPEN) return

    _ws = gpsService.connectFleetWS(
      (data) => {
        if (data.type === 'gps_position') {
          _upsertPosition(data as unknown as FleetPosition)
        } else if (data.type === 'gps_alert') {
          fetchAlerts() // refresh alert list on new alert
        }
      },
      () => {
        isConnected.value = false
        // Attempt reconnect after 5s
        setTimeout(() => connectFleetWS(), 5_000)
      }
    )
    _ws.onopen = () => { isConnected.value = true }
  }

  function disconnectFleetWS(): void {
    _ws?.close()
    _ws = null
    isConnected.value = false
  }

  function _upsertPosition(pos: FleetPosition): void {
    const idx = fleetPositions.value.findIndex((p) => p.vehicle_id === pos.vehicle_id)
    if (idx !== -1) {
      fleetPositions.value[idx] = pos
    } else {
      fleetPositions.value.push(pos)
    }
  }

  return {
    fleetPositions,
    alerts,
    geofences,
    isConnected,
    isLoading,
    unacknowledgedAlerts,
    vehiclesOnRoute,
    fetchFleetPositions,
    fetchAlerts,
    fetchGeofences,
    acknowledgeAlert,
    connectFleetWS,
    disconnectFleetWS,
  }
})
