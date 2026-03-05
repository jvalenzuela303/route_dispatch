<script setup lang="ts" generic="T extends Record<string, unknown>">
import { computed } from 'vue'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/vue/24/outline'

interface Column {
  key: string
  label: string
  sortable?: boolean
  width?: string
  class?: string
}

interface Props {
  columns: Column[]
  data: T[]
  loading?: boolean
  page?: number
  totalPages?: number
  totalItems?: number
  pageSize?: number
  emptyMessage?: string
  selectable?: boolean
  selectedIds?: (string | number)[]
  idKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  page: 1,
  totalPages: 1,
  totalItems: 0,
  pageSize: 20,
  emptyMessage: 'No hay datos para mostrar',
  selectable: false,
  selectedIds: () => [],
  idKey: 'id',
})

const emit = defineEmits<{
  'page-change': [page: number]
  'row-click': [row: T]
  'selection-change': [ids: (string | number)[]]
}>()

const startItem = computed(() => (props.page - 1) * props.pageSize + 1)
const endItem = computed(() => Math.min(props.page * props.pageSize, props.totalItems))

const pages = computed(() => {
  const total = props.totalPages
  const current = props.page
  const pages: (number | string)[] = []

  if (total <= 7) {
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)

    if (current > 3) {
      pages.push('...')
    }

    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
      if (!pages.includes(i)) {
        pages.push(i)
      }
    }

    if (current < total - 2) {
      pages.push('...')
    }

    pages.push(total)
  }

  return pages
})

const isAllSelected = computed(() => {
  if (props.data.length === 0) return false
  return props.data.every((row) => props.selectedIds.includes(row[props.idKey] as string | number))
})

const toggleAll = () => {
  if (isAllSelected.value) {
    emit('selection-change', [])
  } else {
    emit(
      'selection-change',
      props.data.map((row) => row[props.idKey] as string | number)
    )
  }
}

const toggleRow = (row: T) => {
  const id = row[props.idKey] as string | number
  const newSelection = props.selectedIds.includes(id)
    ? props.selectedIds.filter((i) => i !== id)
    : [...props.selectedIds, id]
  emit('selection-change', newSelection)
}

const getValue = (row: T, key: string): unknown => {
  const keys = key.split('.')
  let value: unknown = row
  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = (value as Record<string, unknown>)[k]
    } else {
      return undefined
    }
  }
  return value
}
</script>

<template>
  <div class="table-container">
    <table class="table">
      <thead>
        <tr>
          <th v-if="selectable" class="w-12">
            <input
              type="checkbox"
              :checked="isAllSelected"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              @change="toggleAll"
            />
          </th>
          <th
            v-for="column in columns"
            :key="column.key"
            :style="column.width ? { width: column.width } : undefined"
            :class="column.class"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <!-- Loading state -->
        <tr v-if="loading">
          <td :colspan="selectable ? columns.length + 1 : columns.length" class="text-center py-12">
            <div class="flex flex-col items-center justify-center space-y-3">
              <div class="spinner w-8 h-8"></div>
              <span class="text-sm text-gray-500">Cargando...</span>
            </div>
          </td>
        </tr>

        <!-- Empty state -->
        <tr v-else-if="data.length === 0">
          <td :colspan="selectable ? columns.length + 1 : columns.length" class="text-center py-12">
            <div class="flex flex-col items-center justify-center space-y-2">
              <svg class="w-12 h-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
              <span class="text-sm text-gray-500">{{ emptyMessage }}</span>
            </div>
          </td>
        </tr>

        <!-- Data rows -->
        <tr
          v-for="(row, index) in data"
          v-else
          :key="index"
          class="cursor-pointer"
          @click="emit('row-click', row)"
        >
          <td v-if="selectable" @click.stop>
            <input
              type="checkbox"
              :checked="selectedIds.includes(row[idKey] as string | number)"
              class="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              @change="toggleRow(row)"
            />
          </td>
          <td v-for="column in columns" :key="column.key" :class="column.class">
            <slot :name="`cell-${column.key}`" :row="row" :value="getValue(row, column.key)">
              {{ getValue(row, column.key) ?? '-' }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1"
      class="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50"
    >
      <p class="text-sm text-gray-600">
        Mostrando <span class="font-medium">{{ startItem }}</span> a
        <span class="font-medium">{{ endItem }}</span> de
        <span class="font-medium">{{ totalItems }}</span> resultados
      </p>

      <nav class="flex items-center space-x-1">
        <button
          :disabled="page <= 1"
          class="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="emit('page-change', page - 1)"
        >
          <ChevronLeftIcon class="w-5 h-5" />
        </button>

        <template v-for="p in pages" :key="p">
          <span v-if="p === '...'" class="px-2 text-gray-400">...</span>
          <button
            v-else
            :class="[
              'px-3 py-1.5 text-sm rounded-lg',
              p === page
                ? 'bg-primary-600 text-white'
                : 'hover:bg-gray-200 text-gray-700',
            ]"
            @click="emit('page-change', p as number)"
          >
            {{ p }}
          </button>
        </template>

        <button
          :disabled="page >= totalPages"
          class="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="emit('page-change', page + 1)"
        >
          <ChevronRightIcon class="w-5 h-5" />
        </button>
      </nav>
    </div>
  </div>
</template>
