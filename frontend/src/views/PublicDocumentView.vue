<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ApiError, getPublicDocument } from '../api/client'
import type {
  DocumentBlock,
  PublicBlock,
  PublicDocument,
} from '../api/types'
import { siteTitle } from '../site'
import { formatDateTime } from '../utils/format'
import DocumentBlocks from '../components/DocumentBlocks.vue'

const route = useRoute()
const publication = ref<PublicDocument | null>(null)
const loading = ref(true)
const errorMessage = ref('')
let loadToken = 0

const shareToken = computed(() => String(route.params.shareToken || ''))
const blocks = computed<DocumentBlock[]>(() =>
  (publication.value?.blocks || []).map(
    (block: PublicBlock, index: number) => ({
      id: -(index + 1),
      block_type: block.block_type,
      content: block.content,
      asset_id: block.asset_id,
      sort_order: block.sort_order,
    }),
  ),
)
const pageTitle = computed(() =>
  publication.value
    ? `${publication.value.title} · ${siteTitle.value}`
    : `公开分享 · ${siteTitle.value}`,
)

function ensureNoindex() {
  let meta = window.document.querySelector<HTMLMetaElement>(
    'meta[name="robots"]',
  )
  if (!meta) {
    meta = window.document.createElement('meta')
    meta.name = 'robots'
    window.document.head.appendChild(meta)
  }
  meta.content = 'noindex, nofollow'
}

async function load() {
  const token = ++loadToken
  loading.value = true
  errorMessage.value = ''
  publication.value = null
  if (!shareToken.value) {
    errorMessage.value = '公开链接无效。'
    loading.value = false
    return
  }
  try {
    const data = await getPublicDocument(shareToken.value)
    if (token !== loadToken) {
      return
    }
    publication.value = data
    ensureNoindex()
  } catch (error) {
    if (token !== loadToken) {
      return
    }
    errorMessage.value =
      error instanceof ApiError
        ? '内容不存在或已取消公开。'
        : '公开内容读取失败，请稍后重试。'
  } finally {
    if (token === loadToken) {
      loading.value = false
    }
  }
}

watch(pageTitle, (value) => {
  window.document.title = value
}, { immediate: true })

watch(shareToken, load)

onMounted(load)
onBeforeUnmount(() => {
  const meta = window.document.querySelector('meta[name="robots"]')
  if (meta?.getAttribute('content') === 'noindex, nofollow') {
    meta.remove()
  }
})
</script>

<template>
  <div class="public-page">
    <header class="public-topbar">
      <RouterLink class="public-brand" :to="{ name: 'login' }">
        <span class="brand-glyph" aria-hidden="true">C</span>
        <span>
          <strong>{{ siteTitle }}</strong>
          <small>PUBLIC ARTICLE</small>
        </span>
      </RouterLink>
      <RouterLink class="login-link" :to="{ name: 'login' }">
        登录
      </RouterLink>
    </header>

    <main class="public-main">
      <div v-if="loading" class="public-skeleton" aria-busy="true">
        <p class="sr-only" role="status">正在加载公开内容</p>
        <span class="skeleton-chip"></span>
        <span class="skeleton-title"></span>
        <span class="skeleton-line"></span>
        <span class="skeleton-block"></span>
      </div>

      <div v-else-if="errorMessage" class="public-error" role="alert">
        <span class="error-glyph" aria-hidden="true">!</span>
        <p class="public-eyebrow">PUBLIC / UNAVAILABLE</p>
        <h1>内容暂时无法打开</h1>
        <p>{{ errorMessage }}</p>
        <button type="button" @click="load">重新加载</button>
      </div>

      <article v-else-if="publication" class="public-article">
        <header class="article-head">
          <div class="head-meta">
            <span class="kind-chip" :class="publication.kind">
              {{
                publication.kind === 'note'
                  ? '笔记'
                  : publication.language === 'h'
                    ? 'H 源码'
                    : 'C 源码'
              }}
            </span>
            <span class="public-chip">公开分享</span>
            <time :datetime="publication.published_at">
              {{ formatDateTime(publication.published_at) }} 发布
            </time>
          </div>
          <h1>{{ publication.title }}</h1>
          <p class="author-line">
            作者
            <strong>{{ publication.author.display_name }}</strong>
            · 发布快照
          </p>
        </header>

        <div class="article-divider" aria-hidden="true">
          <span>C</span>
        </div>

        <DocumentBlocks
          :blocks="blocks"
          :kind="publication.kind"
          :language="publication.language"
          :public-share-token="shareToken"
        />

        <footer class="public-foot">
          <span>{{ publication.author.display_name }}</span>
          <span class="foot-line" aria-hidden="true"></span>
          <span>单篇公开分享 · 不提供公开列表</span>
        </footer>
      </article>
    </main>
  </div>
</template>

<style scoped>
.public-page {
  min-height: 100vh;
  padding-bottom: 60px;
}

.public-topbar {
  position: sticky;
  top: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 28px;
  border-bottom: 1px solid rgba(231, 225, 247, 0.82);
  background: rgba(250, 247, 255, 0.82);
}

.public-brand {
  display: flex;
  gap: 10px;
  align-items: center;
  color: var(--text);
}

.brand-glyph {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: 9px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  background: linear-gradient(145deg, #a58fff, #5436e8);
}

.public-brand > span:last-child {
  display: grid;
  gap: 1px;
}

.public-brand strong {
  font-size: 12.5px;
  font-weight: 750;
}

.public-brand small {
  color: #a29ab5;
  font-family: var(--font-mono);
  font-size: 8px;
  letter-spacing: 0.14em;
}

.login-link {
  padding: 7px 13px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font-size: 10.5px;
  font-weight: 650;
  background: #fff;
}

.login-link:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.public-main {
  width: min(900px, 100%);
  margin: 0 auto;
  padding: 46px 32px 30px;
}

.article-head {
  padding: 5px 8px 0;
  animation: article-in 0.5s ease both;
}

.head-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.kind-chip,
.public-chip {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 9.5px;
  font-weight: 700;
}

.kind-chip.note {
  border: 1px solid #e4dcff;
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.kind-chip.source {
  border: 1px solid #dbe9fb;
  color: var(--source-text);
  background: var(--source-badge);
}

.public-chip {
  border: 1px solid #efdfb7;
  color: #805a1c;
  background: var(--favorite-gold-soft);
}

.head-meta time {
  color: #958da7;
  font-family: var(--font-mono);
  font-size: 9.5px;
}

.article-head h1 {
  margin-top: 17px;
  overflow-wrap: anywhere;
  font-size: clamp(32px, 5vw, 52px);
  font-weight: 770;
  letter-spacing: -0.045em;
  line-height: 1.1;
}

.author-line {
  margin-top: 14px;
  color: var(--muted);
  font-size: 11px;
}

.author-line strong {
  color: var(--muted-strong);
  font-weight: 700;
}

.article-divider {
  display: flex;
  gap: 14px;
  align-items: center;
  margin: 27px 8px 28px;
  color: #c8bced;
}

.article-divider::before,
.article-divider::after {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-strong));
  content: "";
}

.article-divider::after {
  background: linear-gradient(90deg, var(--border-strong), transparent);
}

.article-divider span {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10px;
  background: #fff;
}

.public-foot {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 50px;
  padding-top: 17px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 10px;
}

.foot-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

.public-error {
  display: grid;
  gap: 10px;
  justify-items: start;
  padding: 78px 10px;
}

.error-glyph {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border: 1px solid #efdfb7;
  border-radius: 14px;
  color: #805a1c;
  font-family: var(--font-mono);
  font-size: 19px;
  background: var(--favorite-gold-soft);
}

.public-eyebrow {
  margin-top: 6px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.17em;
}

.public-error h1 {
  font-size: 29px;
  letter-spacing: -0.03em;
}

.public-error > p:not(.public-eyebrow) {
  color: var(--muted);
  font-size: 12px;
}

.public-error button {
  margin-top: 8px;
  padding: 8px 14px;
  border: 1px solid var(--accent-strong);
  border-radius: 9px;
  color: #fff;
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  background: var(--accent-strong);
  cursor: pointer;
}

.public-skeleton {
  display: grid;
  gap: 12px;
  padding: 28px 8px;
}

.skeleton-chip,
.skeleton-title,
.skeleton-line,
.skeleton-block {
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #f0ebfb 20%,
    #f9f6ff 42%,
    #f0ebfb 64%
  );
  background-size: 220% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

.skeleton-chip {
  width: 72px;
  height: 19px;
}

.skeleton-title {
  width: 70%;
  height: 42px;
  margin-top: 8px;
}

.skeleton-line {
  width: 32%;
  height: 11px;
}

.skeleton-block {
  width: 100%;
  height: 190px;
  margin-top: 14px;
  border-radius: 16px;
}

@keyframes article-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@media (max-width: 960px) {
  .public-topbar {
    background: rgba(250, 247, 255, 0.82);
    backdrop-filter: blur(18px);
  }
}

@media (max-width: 700px) {
  .public-topbar {
    height: 56px;
    padding: 0 14px;
  }

  .public-main {
    padding: 30px 14px 24px;
  }

  .article-head {
    padding: 2px 3px 0;
  }

  .article-head h1 {
    font-size: clamp(28px, 9vw, 38px);
  }

  .article-divider {
    margin: 22px 3px 23px;
  }

  .public-foot {
    flex-wrap: wrap;
    margin-top: 38px;
  }

  .foot-line {
    display: none;
  }
}
</style>
