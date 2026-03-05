<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'

interface Props {
  open: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  closeable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  size: 'md',
  closeable: true,
})

const emit = defineEmits<{
  close: []
}>()

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-full mx-4',
}

// Separate render state from visibility to avoid Teleport+Transition unmount race condition
// shouldRender controls Teleport (removed only after leave transition ends)
// isVisible controls the inner v-if (triggers the CSS transition)
const shouldRender = ref(props.open)
const isVisible = ref(props.open)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      shouldRender.value = true
      isVisible.value = true
      document.body.style.overflow = 'hidden'
    } else {
      isVisible.value = false
      document.body.style.overflow = ''
      // shouldRender will be set false in onAfterLeave once animation completes
    }
  }
)

// Called when leave transition finishes — safe to unmount the Teleport now
const onAfterLeave = () => {
  shouldRender.value = false
}

// Cleanup on parent unmount to prevent parentNode null error
onBeforeUnmount(() => {
  shouldRender.value = false
  isVisible.value = false
  document.body.style.overflow = ''
})

const close = () => {
  if (props.closeable) {
    emit('close')
  }
}

const handleBackdropClick = (event: MouseEvent) => {
  if (event.target === event.currentTarget) {
    close()
  }
}
</script>

<template>
  <Teleport v-if="shouldRender" to="body">
    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
      @after-leave="onAfterLeave"
    >
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 overflow-y-auto"
      >
        <!-- Backdrop -->
        <div
          class="fixed inset-0 bg-black/50 backdrop-blur-sm"
          @click="handleBackdropClick"
        />

        <!-- Modal container -->
        <div class="flex min-h-full items-center justify-center p-4">
            <div
              :class="[
                'relative w-full bg-white rounded-2xl shadow-xl',
                sizeClasses[size],
              ]"
              @click.stop
            >
              <!-- Header -->
              <div
                v-if="title || closeable"
                class="flex items-center justify-between px-6 py-4 border-b border-gray-100"
              >
                <h3 v-if="title" class="text-lg font-semibold text-gray-900">
                  {{ title }}
                </h3>
                <button
                  v-if="closeable"
                  class="p-2 rounded-lg hover:bg-gray-100 transition-colors ml-auto"
                  @click="close"
                >
                  <XMarkIcon class="w-5 h-5 text-gray-500" />
                </button>
              </div>

              <!-- Body -->
              <div class="px-6 py-4">
                <slot />
              </div>

              <!-- Footer -->
              <div
                v-if="$slots.footer"
                class="px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl"
              >
                <slot name="footer" />
              </div>
            </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
