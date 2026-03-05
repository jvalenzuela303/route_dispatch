<script setup lang="ts">
import { ref } from 'vue'
import { RouterView } from 'vue-router'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'

const sidebarOpen = ref(false)

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}
</script>

<template>
  <div class="flex h-screen bg-gray-50">
    <!-- Sidebar -->
    <Sidebar :is-open="sidebarOpen" @close="closeSidebar" />

    <!-- Main content area -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Header -->
      <Header @toggle-sidebar="toggleSidebar" />

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-6">
        <RouterView v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>
