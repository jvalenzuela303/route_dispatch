<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import L from 'leaflet'
import type { RouteStop, RouteStatus } from '@/types'

interface Props {
  stops: RouteStop[]
  routeStatus?: RouteStatus
  interactive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  routeStatus: 'PENDIENTE',
  interactive: true,
})

const emit = defineEmits<{
  'stop-click': [stop: RouteStop]
}>()

const mapContainer = ref<HTMLElement | null>(null)
let map: L.Map | null = null
let markersLayer: L.LayerGroup | null = null
let routeLine: L.Polyline | null = null

// Depot location (Rancagua)
const DEPOT = {
  lat: -34.1708,
  lng: -70.7444,
}

// Center of Rancagua
const DEFAULT_CENTER: [number, number] = [-34.17, -70.74]
const DEFAULT_ZOOM = 13

const sortedStops = computed(() => {
  return [...props.stops].sort((a, b) => a.sequence_number - b.sequence_number)
})

onMounted(() => {
  initMap()
})

watch(
  () => props.stops,
  () => {
    updateMarkers()
  },
  { deep: true }
)

const initMap = () => {
  if (!mapContainer.value) return

  map = L.map(mapContainer.value, {
    center: DEFAULT_CENTER,
    zoom: DEFAULT_ZOOM,
    zoomControl: props.interactive,
    dragging: props.interactive,
    scrollWheelZoom: props.interactive,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19,
  }).addTo(map)

  markersLayer = L.layerGroup().addTo(map)

  updateMarkers()
}

const updateMarkers = () => {
  if (!map || !markersLayer) return

  markersLayer.clearLayers()
  if (routeLine) {
    map.removeLayer(routeLine)
  }

  // Add depot marker
  const depotIcon = createCustomIcon('depot', '🏠')
  L.marker([DEPOT.lat, DEPOT.lng], { icon: depotIcon })
    .bindPopup('<strong>Bodega</strong><br>Punto de partida')
    .addTo(markersLayer)

  // Collect coordinates for route line
  const coordinates: [number, number][] = [[DEPOT.lat, DEPOT.lng]]

  // Add stop markers
  sortedStops.value.forEach((stop) => {
    // Coordinates come from the stop directly (backend RouteStopResponse)
    // or fall back to the nested order (older data)
    const lat = stop.latitude ?? (stop.order as any)?.latitude
    const lng = stop.longitude ?? (stop.order as any)?.longitude
    if (!lat || !lng) return
    coordinates.push([lat, lng])

    const status = getStopMarkerStatus(stop)
    const icon = createCustomIcon(status, String(stop.sequence_number))

    const marker = L.marker([lat, lng], { icon })
      .bindPopup(createPopupContent(stop))
      .addTo(markersLayer!)

    if (props.interactive) {
      marker.on('click', () => {
        emit('stop-click', stop)
      })
    }
  })

  // Add route line
  if (coordinates.length > 1) {
    routeLine = L.polyline(coordinates, {
      color: '#3b82f6',
      weight: 3,
      opacity: 0.7,
      dashArray: '10, 10',
    }).addTo(map)
  }

  // Fit bounds
  if (coordinates.length > 1) {
    const bounds = L.latLngBounds(coordinates.map((c) => L.latLng(c[0], c[1])))
    map.fitBounds(bounds, { padding: [50, 50] })
  }
}

const getStopMarkerStatus = (stop: RouteStop): string => {
  switch (stop.status) {
    case 'ENTREGADO':
      return 'delivered'
    case 'INCIDENCIA':
      return 'incident'
    case 'EN_CAMINO':
    case 'LLEGADO':
      return 'current'
    default:
      return 'pending'
  }
}

const createCustomIcon = (status: string, label: string) => {
  const colors: Record<string, string> = {
    depot: '#22c55e',
    delivered: '#22c55e',
    incident: '#ef4444',
    current: '#f59e0b',
    pending: '#3b82f6',
  }

  const color = colors[status] || colors.pending

  return L.divIcon({
    className: 'custom-div-icon',
    html: `
      <div style="
        background-color: ${color};
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        font-size: 12px;
        border: 3px solid white;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        ${status === 'current' ? 'animation: pulse 2s infinite;' : ''}
      ">
        ${label}
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })
}

const createPopupContent = (stop: RouteStop): string => {
  const statusLabels: Record<string, string> = {
    PENDIENTE: 'Pendiente',
    EN_CAMINO: 'En Camino',
    LLEGADO: 'Llegado',
    ENTREGADO: 'Entregado',
    INCIDENCIA: 'Incidencia',
  }

  return `
    <div style="min-width: 200px;">
      <strong style="font-size: 14px;">#${stop.sequence_number} - ${stop.order?.customer_name || 'Cliente'}</strong>
      <br>
      <span style="color: #666; font-size: 12px;">${stop.order?.address_text || 'Sin dirección'}</span>
      <br>
      <span style="
        display: inline-block;
        margin-top: 8px;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
        background: ${stop.status === 'ENTREGADO' ? '#dcfce7' : stop.status === 'INCIDENCIA' ? '#fee2e2' : '#e0e7ff'};
        color: ${stop.status === 'ENTREGADO' ? '#166534' : stop.status === 'INCIDENCIA' ? '#991b1b' : '#3730a3'};
      ">
        ${statusLabels[stop.status] || stop.status}
      </span>
      ${
        stop.incident_reason
          ? `<br><span style="color: #dc2626; font-size: 11px; margin-top: 4px; display: block;">
              ⚠️ ${stop.incident_reason}
            </span>`
          : ''
      }
    </div>
  `
}
</script>

<template>
  <div ref="mapContainer" class="w-full h-full min-h-[300px]"></div>
</template>

<style>
@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

.custom-div-icon {
  background: transparent;
  border: none;
}
</style>
