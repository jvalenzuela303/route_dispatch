<script setup lang="ts">
import { InboxIcon } from '@heroicons/vue/24/outline'

interface Props {
  title?: string
  message?: string
  icon?: typeof InboxIcon
  actionLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Sin datos',
  message: 'No hay elementos para mostrar.',
  icon: InboxIcon,
  actionLabel: '',
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-6 text-center">
    <div class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
      <component :is="props.icon" class="w-8 h-8 text-gray-400" />
    </div>

    <h3 class="text-lg font-medium text-gray-900 mb-1">
      {{ title }}
    </h3>

    <p class="text-sm text-gray-500 max-w-sm">
      {{ message }}
    </p>

    <button
      v-if="actionLabel"
      class="btn-primary mt-6"
      @click="emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
