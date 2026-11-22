<script setup lang="ts">
import { progressState } from '../utils/progress'
</script>

<template>
  <div
    class="top-progress"
    :class="{ active: progressState.active }"
    aria-hidden="true"
  >
    <span :style="{ transform: `scaleX(${progressState.value / 100})` }"></span>
  </div>
</template>

<style scoped>
.top-progress {
  position: fixed;
  inset: 0 0 auto;
  z-index: 260;
  height: 3px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.top-progress.active {
  opacity: 1;
}

.top-progress span {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: 0 50%;
  background: linear-gradient(90deg, #6f4df0, #ad90ff 70%, #d9c9ff);
  box-shadow: 0 0 10px rgba(111, 77, 240, 0.45);
  transition: transform 0.24s ease;
}

@media (prefers-reduced-motion: reduce) {
  .top-progress span {
    transition: none;
  }
}
</style>
