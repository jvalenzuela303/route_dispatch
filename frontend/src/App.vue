<script setup lang="ts">
import { RouterView } from 'vue-router'
import NotificationContainer from '@/components/common/NotificationContainer.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <RouterView />
    <NotificationContainer />
  </div>
</template>
