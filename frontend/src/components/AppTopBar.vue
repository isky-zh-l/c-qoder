<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { UserProfile } from '../api/types'

const props = withDefaults(
  defineProps<{
    user: UserProfile | null
    siteTitle: string
    favoriteCount?: number
    recycleCount?: number
    active?: 'workspace' | 'favorites' | 'recycle' | 'document'
    showBack?: boolean
  }>(),
  {
    favoriteCount: 0,
    recycleCount: 0,
    active: 'workspace',
    showBack: false,
  },
)

const emit = defineEmits<{
  'open-favorites': []
  'open-recycle': []
  logout: []
}>()

const menuOpen = ref(false)
const menuRoot = ref<HTMLElement | null>(null)

const initial = computed(() => {
  const name = props.user?.display_name?.trim()
  return name ? Array.from(name)[0] : 'C'
})

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!menuOpen.value || !menuRoot.value) {
    return
  }
  if (!menuRoot.value.contains(event.target as Node)) {
    closeMenu()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeMenu()
  }
}

function requestLogout() {
  closeMenu()
  emit('logout')
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <RouterLink class="brand" :to="{ name: 'workspace' }">
        <span class="brand-glyph" aria-hidden="true">C</span>
        <span class="brand-copy">
          <span class="brand-name">{{ siteTitle }}</span>
          <span class="brand-sub">PRIVATE STUDY SPACE</span>
        </span>
      </RouterLink>

      <nav class="topnav" aria-label="工作区导航">
        <RouterLink
          class="topnav-link notes-link"
          :class="{ active: active === 'workspace' }"
          :to="{ name: 'workspace' }"
        >
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M4 5.5h7M4 9h9M4 12.5h6M14.5 5.5v9"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
            />
          </svg>
          <span>笔记</span>
        </RouterLink>
        <button
          type="button"
          class="topnav-link favorite-link"
          :class="{ active: active === 'favorites' }"
          @click="emit('open-favorites')"
        >
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="m10 2.6 2.1 4.3 4.8.7-3.5 3.4.8 4.7L10 13.5l-4.2 2.2.8-4.7L3.1 7.6l4.8-.7L10 2.6Z"
            />
          </svg>
          <span>收藏</span>
          <span class="nav-count">{{ favoriteCount }}</span>
        </button>
        <button
          type="button"
          class="topnav-link"
          :class="{ active: active === 'recycle' }"
          @click="emit('open-recycle')"
        >
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M4.5 6h11M7 6V4.6h6V6m-7.4 0 .8 9.1h7.2l.8-9.1M8.4 8.7v4.2m3.2-4.2v4.2"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
            />
          </svg>
          <span>回收站</span>
          <span v-if="recycleCount" class="nav-count">{{ recycleCount }}</span>
        </button>
        <RouterLink
          v-if="showBack"
          class="topnav-link back-link"
          :to="{ name: 'workspace' }"
        >
          <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="m12.5 5-5 5 5 5"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          工作区
        </RouterLink>
      </nav>

      <div ref="menuRoot" class="account-menu">
        <button
          type="button"
          class="account-trigger"
          :aria-expanded="menuOpen"
          aria-haspopup="menu"
          @click="toggleMenu"
        >
          <span class="account-avatar" aria-hidden="true">{{ initial }}</span>
          <span class="account-name">{{ user?.display_name || '账号' }}</span>
          <svg class="chevron" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="m4.5 6.5 3.5 3 3.5-3"
              stroke="currentColor"
              stroke-width="1.3"
              stroke-linecap="round"
            />
          </svg>
        </button>

        <Transition name="menu">
          <div v-if="menuOpen" class="account-popover" role="menu">
            <div class="account-summary">
              <strong>{{ user?.display_name }}</strong>
              <span>{{ user?.is_demo ? '示例空间 · 可直接体验' : 'Qoder 独立空间' }}</span>
            </div>
            <button
              type="button"
              class="menu-action mobile-only"
              @click="emit('open-favorites'); closeMenu()"
            >
              收藏 · {{ favoriteCount }}
            </button>
            <button
              type="button"
              class="menu-action mobile-only"
              @click="emit('open-recycle'); closeMenu()"
            >
              回收站 · {{ recycleCount }}
            </button>
            <RouterLink
              class="menu-action"
              :to="{ name: 'account' }"
              @click="closeMenu"
            >
              账号设置
            </RouterLink>
            <button type="button" class="menu-action" @click="requestLogout">
              退出登录
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 70;
  border-bottom: 1px solid rgba(231, 225, 247, 0.82);
  background: #fbfaff;
}

.topbar-inner {
  display: flex;
  gap: 22px;
  align-items: center;
  width: min(1380px, 100%);
  height: 66px;
  margin: 0 auto;
  padding: 0 28px;
}

.brand {
  display: flex;
  flex: none;
  gap: 11px;
  align-items: center;
  min-width: 0;
  color: var(--text);
}

.brand-glyph {
  display: grid;
  flex: none;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  background: linear-gradient(145deg, #a58fff, #5436e8);
  box-shadow: 0 9px 20px -13px rgba(84, 54, 232, 0.95);
}

.brand-copy {
  display: grid;
  gap: 1px;
  min-width: 0;
}

.brand-name {
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 750;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-sub {
  color: #a29ab5;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.15em;
}

.topnav {
  display: flex;
  gap: 4px;
  align-items: center;
  margin-left: auto;
}

.topnav-link {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  background: transparent;
  cursor: pointer;
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.topnav-link:hover,
.topnav-link.active {
  border-color: #e6defa;
  color: var(--accent-strong);
  background: #fff;
}

.topnav-link svg {
  width: 14px;
  height: 14px;
}

.favorite-link {
  color: var(--favorite-gold);
}

.favorite-link svg {
  fill: currentColor;
}

.favorite-link.active,
.favorite-link:hover {
  border-color: #ecd9ad;
  color: #9a6d1e;
  background: var(--favorite-gold-soft);
}

.nav-count {
  min-width: 18px;
  padding: 1px 5px;
  border-radius: 999px;
  color: inherit;
  font-family: var(--font-mono);
  font-size: 9px;
  text-align: center;
  background: rgba(115, 87, 255, 0.09);
}

.favorite-link .nav-count {
  background: rgba(184, 134, 47, 0.12);
}

.back-link {
  margin-left: 2px;
  border-color: var(--border);
}

.account-menu {
  position: relative;
  flex: none;
  margin-left: 4px;
}

.account-trigger {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 5px 8px 5px 5px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font: inherit;
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.account-trigger:hover {
  border-color: var(--border-strong);
  box-shadow: 0 8px 20px -18px rgba(61, 42, 120, 0.7);
}

.account-avatar {
  display: grid;
  flex: none;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  background: linear-gradient(145deg, #a58fff, #5436e8);
}

.account-name {
  max-width: 110px;
  overflow: hidden;
  font-size: 11.5px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chevron {
  width: 13px;
  height: 13px;
  color: #a49bb8;
}

.account-popover {
  position: absolute;
  top: calc(100% + 9px);
  right: 0;
  z-index: 80;
  width: 224px;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 60px -30px rgba(33, 27, 51, 0.55);
}

.account-summary {
  display: grid;
  gap: 3px;
  padding: 9px 10px 11px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 5px;
}

.account-summary strong {
  font-size: 13px;
}

.account-summary span {
  overflow: hidden;
  color: var(--muted);
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-action {
  display: block;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 9px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.menu-action:hover {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.menu-action.danger {
  color: #b44d4d;
}

.menu-action.danger:hover {
  background: #fff1f1;
}

.mobile-only {
  display: none;
}

.menu-enter-active,
.menu-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}

@media (max-width: 760px) {
  .topbar-inner {
    gap: 8px;
    height: calc(58px + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 12px 0;
  }

  .topnav-link {
    min-width: 36px;
    min-height: 38px;
    justify-content: center;
    padding: 7px;
  }

  .account-trigger {
    min-height: 38px;
    padding: 4px 7px 4px 4px;
  }

  .account-avatar {
    width: 30px;
    height: 30px;
  }

  .brand-sub,
  .account-name,
  .chevron {
    display: none;
  }

  .brand-name {
    max-width: 42vw;
  }

  .topnav-link {
    padding: 8px;
  }

  .topnav-link > span:not(.nav-count) {
    display: none;
  }

  .topnav-link .nav-count {
    display: inline-block;
  }

  .topnav-link.back-link,
  .topnav-link.notes-link {
    display: none;
  }

  .account-trigger {
    padding: 4px;
  }

  .mobile-only {
    display: block;
  }
}
@media (max-width: 960px) {
  .topbar {
    background: #f9f6ff;
    backdrop-filter: none;
  }
}
</style>
