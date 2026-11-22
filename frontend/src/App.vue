<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import BackgroundDecor from './components/BackgroundDecor.vue'
import TopProgress from './components/TopProgress.vue'
import { loadSiteTitle } from './site'

onMounted(loadSiteTitle)
</script>

<template>
  <div class="app-root">
    <TopProgress />
    <BackgroundDecor />
    <RouterView />
  </div>
</template>

<style scoped>
.app-root {
  position: relative;
  z-index: 1;
  min-height: 100vh;
}
</style>
