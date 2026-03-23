<script setup lang="ts">
/**
 * LiveMapView — real-time fleet position dashboard
 *
 * Uses Leaflet.js (already in the project via RouteTrackingView)
 * + WebSocket via gpsStore to update markers as positions arrive.
 */
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useGpsStore } from '@/stores/gps'
import { useNotificationsStore } from '@/stores/notifications'
import type { FleetPosition } from '@/services/gps.service'
import {
  SignalIcon,
  BellAlertIcon,
  ArrowPathIcon,
} from '@heroicons/vue/24/outline'

const gpsStore = useGpsStore()
const notifications = useNotificationsStore()

const mapContainer = ref<HTMLDivElement | null>(null)
let map: unknown = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const markers: Record<string, any> = {}

// ─────────────────────────────────────────────────────────────────
// Lifecycle
// ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await gpsStore.fetchFleetPositions()
  await gpsStore.fetchAlerts()
  gpsStore.connectFleetWS()
  await nextTick()
  await initMap()
})

onUnmounted(() => {
  gpsStore.disconnectFleetWS()
  if (map) (map as { remove(): void }).remove()
})

// ─────────────────────────────────────────────────────────────────
// Map
// ─────────────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LeafletMap = any

async function initMap() {
  if (!mapContainer.value) return
  const L: LeafletMap = (await import('leaflet')).default
  await import('leaflet/dist/leaflet.css')

  map = L.map(mapContainer.value).setView([-34.1706, -70.7407], 13)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(map)

  L.marker([-34.1706, -70.7407], {
    icon: L.divIcon({ html: '<div style="font-size:24px">🏭</div>', className: '', iconSize: [32, 32] }),
  })
    .addTo(map)
    .bindPopup('Bodega Principal')

  gpsStore.fleetPositions.forEach((pos) => addOrUpdateMarker(L, pos))
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function addOrUpdateMarker(L: LeafletMap, pos: FleetPosition) {
  if (!map) return

  const popupText = `<strong>${pos.plate}</strong>${pos.alias ? ` (${pos.alias})` : ''}<br>${pos.speed_kmh !== null ? `${pos.speed_kmh.toFixed(0)} km/h` : 'Sin velocidad'}<br><small>${new Date(pos.last_seen).toLocaleTimeString()}</small>`

  if (markers[pos.vehicle_id]) {
    markers[pos.vehicle_id].setLatLng([pos.latitude, pos.longitude])
    if (markers[pos.vehicle_id].getPopup()) markers[pos.vehicle_id].setPopupContent(popupText)
  } else {
    const icon = L.divIcon({
      html: `<div style="background:#2563eb;color:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,.3)">🚛</div>`,
      className: '',
      iconSize: [32, 32],
    })
    markers[pos.vehicle_id] = L.marker([pos.latitude, pos.longitude], { icon }).addTo(map).bindPopup(popupText)
  }
}

watch(
  () => gpsStore.fleetPositions,
  async (positions) => {
    const L: LeafletMap = (await import('leaflet')).default
    positions.forEach((pos) => addOrUpdateMarker(L, pos))
  },
  { deep: true }
)

async function refresh() {
  await gpsStore.fetchFleetPositions()
  await gpsStore.fetchAlerts()
}

async function ackAlert(alertId: string) {
  try {
    await gpsStore.acknowledgeAlert(alertId)
    notifications.success('GPS', 'Alerta reconocida')
  } catch {
    notifications.error('Error', 'Error al reconocer alerta')
  }
}

const statusBadge = (type: string) => {
  const map: Record<string, string> = {
    SPEEDING: 'bg-red-100 text-red-800',
    GEOFENCE_ENTRY: 'bg-yellow-100 text-yellow-800',
    GEOFENCE_EXIT: 'bg-orange-100 text-orange-800',
    ROUTE_DEVIATION: 'bg-purple-100 text-purple-800',
    LONG_STOP: 'bg-blue-100 text-blue-800',
  }
  return map[type] || 'bg-gray-100 text-gray-800'
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Toolbar -->
    <div class="flex items-center justify-between px-4 py-3 bg-white border-b">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-bold text-gray-900">Mapa en Vivo</h1>
        <span
          class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
          :class="gpsStore.isConnected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
        >
          <SignalIcon class="h-3 w-3" />
          {{ gpsStore.isConnected ? 'En línea' : 'Desconectado' }}
        </span>
        <span v-if="gpsStore.unacknowledgedAlerts.length" class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-red-100 text-red-700">
          <BellAlertIcon class="h-3 w-3" />
          {{ gpsStore.unacknowledgedAlerts.length }} alerta{{ gpsStore.unacknowledgedAlerts.length !== 1 ? 's' : '' }}
        </span>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-gray-500">{{ gpsStore.fleetPositions.length }} vehículo{{ gpsStore.fleetPositions.length !== 1 ? 's' : '' }} activo{{ gpsStore.fleetPositions.length !== 1 ? 's' : '' }}</span>
        <button @click="refresh" class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100">
          <ArrowPathIcon class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- Main area: map + sidebar -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Map -->
      <div ref="mapContainer" class="flex-1" style="min-height: 400px;" />

      <!-- Sidebar: alerts + fleet list -->
      <div class="w-72 bg-white border-l overflow-y-auto">

        <!-- Unacknowledged alerts -->
        <div v-if="gpsStore.unacknowledgedAlerts.length" class="p-3 border-b">
          <h3 class="text-xs font-semibold text-gray-500 uppercase mb-2">Alertas Activas</h3>
          <div
            v-for="alert in gpsStore.unacknowledgedAlerts"
            :key="alert.id"
            class="mb-2 p-2 rounded-lg border text-xs"
          >
            <div class="flex items-start justify-between gap-1">
              <span class="inline-flex px-1.5 py-0.5 rounded text-xs font-medium" :class="statusBadge(alert.alert_type)">
                {{ alert.alert_type.replace('_', ' ') }}
              </span>
              <button @click="ackAlert(alert.id)" class="text-gray-400 hover:text-gray-600 text-xs">✓</button>
            </div>
            <p class="text-gray-700 mt-1">{{ alert.message }}</p>
            <p class="text-gray-400 mt-0.5">{{ new Date(alert.created_at).toLocaleTimeString() }}</p>
          </div>
        </div>

        <!-- Fleet list -->
        <div class="p-3">
          <h3 class="text-xs font-semibold text-gray-500 uppercase mb-2">Flota</h3>
          <div v-if="!gpsStore.fleetPositions.length" class="text-xs text-gray-400 py-4 text-center">
            Sin posiciones GPS activas.
          </div>
          <div
            v-for="pos in gpsStore.fleetPositions"
            :key="pos.vehicle_id"
            class="flex items-center justify-between py-2 border-b last:border-0"
          >
            <div>
              <div class="text-sm font-semibold text-gray-900">{{ pos.plate }}</div>
              <div class="text-xs text-gray-400">{{ pos.alias || '' }}</div>
            </div>
            <div class="text-right">
              <div class="text-sm font-medium" :class="pos.speed_kmh && pos.speed_kmh > 0 ? 'text-blue-600' : 'text-gray-400'">
                {{ pos.speed_kmh !== null ? `${pos.speed_kmh.toFixed(0)} km/h` : '—' }}
              </div>
              <div class="text-xs text-gray-400">{{ new Date(pos.last_seen).toLocaleTimeString() }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
