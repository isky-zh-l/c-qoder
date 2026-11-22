<script setup lang="ts">
import { useRouter } from 'vue-router'
import { clearPageLoading, pageLoadingState } from '../utils/pageLoading'

const router = useRouter()

function cancel() {
  clearPageLoading()
  void router.push({ name: 'workspace' })
}
</script>

<template>
  <Transition name="page-loading">
    <div
      v-if="pageLoadingState.active"
      class="page-loading"
      role="status"
      aria-live="polite"
    >
      <div class="page-loading-card">
        <span class="page-loading-spinner" aria-hidden="true"></span>
        <strong>{{ pageLoadingState.label }}</strong>
        <p>内容读取完成后会自动打开。</p>
        <button type="button" @click="cancel">返回笔记列表</button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.page-loading {
  position: fixed;
  inset: 0;
  z-index: 180;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(ellipse at 50% 0, rgba(236, 228, 255, 0.9), transparent 60%),
    rgba(247, 244, 255, 0.86);
}

.page-loading-card {
  display: grid;
  justify-items: center;
  gap: 10px;
  width: min(330px, calc(100vw - 48px));
  padding: 26px 22px;
  border: 1px dashed #d7cbf0;
  border-radius: 16px;
  background: #fff;
  text-align: center;
  box-shadow: 0 18px 50px rgba(76, 55, 130, 0.12);
}

.page-loading-spinner {
  width: 26px;
  height: 26px;
  border: 2px solid #ece5fb;
  border-top-color: #6f4df0;
  border-radius: 50%;
  animation: page-loading-spin 0.9s linear infinite;
}

.page-loading-card strong {
  color: #332b49;
  font-size: 14.5px;
}

.page-loading-card p {
  margin: 0;
  color: #8a839c;
  font-size: 12px;
}

.page-loading-card button {
  margin-top: 4px;
  padding: 7px 13px;
  border: 1px solid #e0d8f6;
  border-radius: 9px;
  color: #4b435e;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
}

.page-loading-enter-active,
.page-loading-leave-active {
  transition: opacity 0.16s ease;
}

.page-loading-enter-from,
.page-loading-leave-to {
  opacity: 0;
}

@keyframes page-loading-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .page-loading-spinner {
    animation: none;
  }
}
</style>
