<script setup lang="ts">
import { computed } from 'vue'
import type { UserProfile } from '../api/types'

const props = defineProps<{
  user: UserProfile | null
  siteTitle: string
}>()

const displayName = computed(
  () => props.user?.display_name?.trim() || '未登录',
)

const bio = computed(() => props.user?.bio?.trim() || '')

const initial = computed(() => {
  const name = props.user?.display_name?.trim()
  return name ? Array.from(name)[0] : 'C'
})
</script>

<template>
  <article class="author-card">
    <div class="avatar" aria-hidden="true">
      <span>{{ initial }}</span>
    </div>

    <div class="author-copy">
      <p class="site-mark">{{ siteTitle }}</p>
      <p class="author-name">{{ displayName }}</p>
      <p class="tagline">QODER PRIVATE WORKSPACE</p>
      <p v-if="bio" class="bio">{{ bio }}</p>
      <p class="verified-badge">
        <span aria-hidden="true"></span>Qoder 身份登录
      </p>
    </div>

    <div class="circuit-line" aria-hidden="true">
      <svg viewBox="0 0 180 24" fill="none">
        <path d="M2 12h48l8-8h32l8 8h80" />
        <circle cx="58" cy="4" r="2.2" />
        <circle cx="138" cy="12" r="2.2" />
      </svg>
    </div>
  </article>
</template>

<style scoped>
.author-card {
  position: relative;
  overflow: hidden;
  padding: 22px 20px 18px;
  border: 1px solid rgba(231, 225, 247, 0.9);
  border-radius: var(--radius-lg);
  background:
    radial-gradient(180px 120px at 100% 0%, rgba(115, 87, 255, 0.1), transparent 70%),
    rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-soft);
  animation: card-in 0.55s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}

.author-card::before {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow:
    0 0 0 5px rgba(115, 87, 255, 0.08),
    0 0 18px rgba(115, 87, 255, 0.4);
  content: "";
}

.avatar {
  display: grid;
  width: 58px;
  height: 58px;
  margin-bottom: 16px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 18px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 600;
  background: linear-gradient(145deg, #a58fff, #5436e8);
  box-shadow:
    0 12px 24px -14px rgba(84, 54, 232, 0.8),
    inset 0 0 0 1px rgba(255, 255, 255, 0.18);
}

.site-mark {
  margin-bottom: 7px;
  overflow: hidden;
  color: var(--accent);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}

.author-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.3;
}

.tagline {
  margin-top: 6px;
  overflow-wrap: anywhere;
  color: var(--muted-strong);
  font-size: 12.5px;
  font-weight: 600;
}

.bio {
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.75;
}

.verified-badge {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  margin-top: 10px;
  color: #3c7a58;
  font-size: 10.5px;
  font-weight: 650;
}

.verified-badge span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6fbf8f;
  box-shadow: 0 0 0 4px rgba(111, 191, 143, 0.12);
}

.circuit-line {
  margin-top: 16px;
  color: var(--border-strong);
  opacity: 0.9;
}

.circuit-line svg {
  width: 100%;
  height: 18px;
}

.circuit-line path {
  stroke: currentColor;
  stroke-width: 1;
  stroke-linecap: round;
}

.circuit-line circle {
  fill: var(--accent);
  opacity: 0.4;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
