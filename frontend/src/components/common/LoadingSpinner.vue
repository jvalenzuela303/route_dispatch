<script setup lang="ts">
interface Props {
  size?: 'sm' | 'md' | 'lg'
  text?: string
}

withDefaults(defineProps<Props>(), {
  size: 'md',
  text: '',
})

const sizeClasses = {
  sm: 'w-4 h-4 border',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-2',
}
</script>

<template>
  <div class="flex flex-col items-center justify-center space-y-3">
    <div :class="['spinner', sizeClasses[size]]"></div>
    <span v-if="text" class="text-sm text-gray-500">{{ text }}</span>
  </div>
</template>
