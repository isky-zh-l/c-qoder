<script setup lang="ts">
import { siteTitle } from '../site'

defineProps<{
  title: string
  eyebrow?: string
  subtitle?: string
}>()
</script>

<template>
  <main class="auth-page">
    <div class="auth-frame">
      <div class="auth-brand-row">
        <span class="brand-glyph" aria-hidden="true">C</span>
        <span class="brand-name">{{ siteTitle }}</span>
      </div>

      <section class="auth-card">
        <p class="auth-eyebrow">{{ eyebrow || 'ACCOUNT / C NOTES' }}</p>
        <h1>{{ title }}</h1>
        <p v-if="subtitle" class="auth-subtitle">{{ subtitle }}</p>
        <slot />
      </section>

      <p class="auth-foot">
        <slot name="footer">服务器存储 · 跨设备访问</slot>
      </p>
    </div>
  </main>
</template>
