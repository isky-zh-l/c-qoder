<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  ApiError,
  documentDownloadUrl,
  favoriteDocument,
  getDocument,
  getWorkspace,
  unfavoriteDocument,
} from '../api/client'
import { authState, clearSession } from '../auth/session'
import type { DocumentDetail, Workspace } from '../api/types'
import { siteTitle } from '../site'
import { formatDateTime } from '../utils/format'
import {
  consumeHomeReturn,
  restoreScrollPosition,
} from '../utils/scrollMemory'
import { beginProgress, endProgress } from '../utils/progress'
import { currentPageLoadingToken, endPageLoading } from '../utils/pageLoading'
import DeleteDocumentDialog from '../components/DeleteDocumentDialog.vue'
import DocumentBlocks from '../components/DocumentBlocks.vue'
import EditDocumentDialog from '../components/EditDocumentDialog.vue'
import ShareDialog from '../components/ShareDialog.vue'

const route = useRoute()
const router = useRouter()

const document = ref<DocumentDetail | null>(null)
const workspace = ref<Workspace | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const readingProgress = ref(0)
const favoriteBusy = ref(false)
const editOpen = ref(false)
const deleteOpen = ref(false)
const shareOpen = ref(false)
const toast = ref<{
  id: number
  tone: 'success' | 'error' | 'info'
  message: string
} | null>(null)
let toastTimer: number | null = null
let toastId = 0
let loadToken = 0

const user = computed(() => authState.user)
const chapters = computed(() => workspace.value?.chapters ?? [])
const retentionDays = computed(() => workspace.value?.recycle_retention_days ?? 7)
const kindLabel = computed(() => {
  if (!document.value) {
    return ''
  }
  if (document.value.kind === 'note') {
    return '笔记'
  }
  return document.value.language === 'h' ? 'H 源码' : 'C 源码'
})
const docTitle = computed(() =>
  document.value ? `${document.value.title} · ${siteTitle.value}` : siteTitle.value,
)

function blockHasContent(block: DocumentDetail['blocks'][number]): boolean {
  if (block.block_type === 'image') {
    return block.asset_id !== null
  }
  const content = block.content as Record<string, unknown>
  for (const key of ['markdown', 'text', 'latex']) {
    const value = content[key]
    if (typeof value === 'string' && value.trim()) {
      return true
    }
  }
  for (const key of ['rows', 'headers', 'items']) {
    const value = content[key]
    if (Array.isArray(value) && value.length) {
      return true
    }
  }
  return false
}

const hasContent = computed(() =>
  (document.value?.blocks ?? []).some(blockHasContent),
)

function goEdit() {
  const current = document.value
  if (!current) return
  router.push({
    name: current.kind === 'source' ? 'source-edit' : 'document-edit',
    params: { id: current.id },
  })
}

function updateReadingProgress() {
  const el = window.document.scrollingElement || window.document.documentElement
  const max = el.scrollHeight - el.clientHeight
  readingProgress.value = max > 0 ? Math.min(1, Math.max(0, el.scrollTop / max)) : 0
}

function notify(
  message: string,
  tone: 'success' | 'error' | 'info' = 'success',
) {
  toastId += 1
  toast.value = { id: toastId, tone, message }
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }
  toastTimer = window.setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 3200)
}

async function handleUnauthorized(error: unknown): Promise<boolean> {
  if (error instanceof ApiError && error.status === 401) {
    clearSession()
    await router.replace({
      name: 'login',
      query: { next: route.fullPath },
    })
    return true
  }
  return false
}

async function loadWorkspace() {
  try {
    workspace.value = await getWorkspace()
  } catch {
    // 阅读内容优先，统计失败不阻断正文
  }
}

async function loadDocument(showLoading = true) {
  const token = ++loadToken
  const pageToken = currentPageLoadingToken()
  if (showLoading) {
    loading.value = true
    document.value = null
    beginProgress()
  }
  errorMessage.value = ''
  try {
    const id = Number(route.params.id)
    if (!Number.isInteger(id) || id <= 0) {
      errorMessage.value = '文档地址无效。'
      return
    }
    const data = await getDocument(id)
    if (token === loadToken) {
      document.value = data
      if (showLoading) {
        const restored = restoreScrollPosition(route.fullPath)
        if (!restored) {
          window.scrollTo({ top: 0, behavior: 'smooth' })
        }
      }
    }
  } catch (error) {
    if (token !== loadToken) {
      return
    }
    if (await handleUnauthorized(error)) {
      return
    }
    errorMessage.value =
      error instanceof ApiError
        ? error.status === 404
          ? '文档不存在，可能已移入回收站或不属于当前账号。'
          : error.message
        : '文档读取失败，请稍后重试'
  } finally {
    if (token === loadToken) {
      loading.value = false
    }
    if (showLoading) {
      endProgress()
      endPageLoading(pageToken)
    }
  }
}

async function toggleFavorite() {
  if (!document.value || favoriteBusy.value) {
    return
  }
  favoriteBusy.value = true
  const next = !document.value.is_favorite
  document.value = { ...document.value, is_favorite: next }
  if (workspace.value) {
    workspace.value = {
      ...workspace.value,
      favorite_count: Math.max(
        0,
        workspace.value.favorite_count + (next ? 1 : -1),
      ),
    }
  }
  try {
    if (next) {
      await favoriteDocument(document.value.id)
      notify('已加入收藏')
    } else {
      await unfavoriteDocument(document.value.id)
      notify('已移出收藏')
    }
  } catch (error) {
    notificationError(error)
    await Promise.all([loadDocument(false), loadWorkspace()])
  } finally {
    favoriteBusy.value = false
  }
}

function notificationError(error: unknown) {
  if (error instanceof ApiError) {
    notify(error.message, 'error')
  } else {
    notify('操作失败，请稍后重试', 'error')
  }
}

async function handleSaved(saved: DocumentDetail) {
  editOpen.value = false
  document.value = saved
  notify('修改已保存')
  await loadWorkspace()
}

async function handleShareChanged() {
  await loadDocument(false)
  await loadWorkspace()
}

async function handleDeleted() {
  deleteOpen.value = false
  await router.replace({ name: 'workspace' })
}

function exitToHome() {
  const returnPath = consumeHomeReturn()
  if (returnPath) {
    router.push(returnPath)
    return
  }
  router.push({ name: 'workspace' })
}

watch(docTitle, (value) => {
  window.document.title = value
}, { immediate: true })

watch(
  () => route.params.id,
  () => {
    if (route.name === 'document') {
      loadDocument(true)
    }
  },
)

watch(
  () => document.value?.id,
  () => nextTick(updateReadingProgress),
)

onMounted(() => {
  loadDocument(true)
  loadWorkspace()
  window.addEventListener('scroll', updateReadingProgress, { passive: true })
  window.addEventListener('resize', updateReadingProgress)
})

onBeforeUnmount(() => {
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }
  window.removeEventListener('scroll', updateReadingProgress)
  window.removeEventListener('resize', updateReadingProgress)
})
</script>

<template>
  <div class="document-page">
    <header class="reading-topbar">
      <div class="reading-topbar-inner">
        <button type="button" class="reading-exit" @click="exitToHome">
          <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path
              d="m11 4.5-4.5 4.5 4.5 4.5"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          退出到主页
        </button>
        <span class="reading-topbar-title">
          {{ document?.title || siteTitle }}
        </span>
        <div class="reading-topbar-actions">
          <button
            type="button"
            class="read-action star-action"
            :class="{ active: document?.is_favorite }"
            :disabled="favoriteBusy || !document"
            :aria-pressed="document?.is_favorite"
            @click="toggleFavorite"
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path
                d="m10 2.6 2.1 4.3 4.8.7-3.5 3.4.8 4.7L10 13.5l-4.2 2.2.8-4.7L3.1 7.6l4.8-.7L10 2.6Z"
              />
            </svg>
            {{ document?.is_favorite ? '已收藏' : '收藏' }}
          </button>
          <RouterLink
            v-if="document?.kind === 'note'"
            class="read-action edit-action"
            :to="{ name: 'document-edit', params: { id: document.id } }"
          >
            编辑
          </RouterLink>
          <RouterLink
            v-else-if="document"
            class="read-action edit-action"
            :to="{ name: 'source-edit', params: { id: document.id } }"
          >
            编辑源码
          </RouterLink>
          <details v-if="document" class="read-more">
            <summary>更多</summary>
            <div class="read-more-menu">
              <a
                v-if="document.kind === 'source'"
                :href="documentDownloadUrl(document.id)"
              >
                下载源码
              </a>
              <button type="button" @click="shareOpen = true">
                {{ document.share_token ? '公开设置' : '分享' }}
              </button>
              <button type="button" @click="editOpen = true">管理</button>
              <button type="button" class="danger" @click="deleteOpen = true">
                移到回收站
              </button>
            </div>
          </details>
        </div>
      </div>
      <div
        class="reading-progress"
        :style="{ transform: `scaleX(${readingProgress})` }"
        aria-hidden="true"
      ></div>
    </header>

    <main class="reading-main">
      <div v-if="loading" class="reading-skeleton" aria-busy="true">
        <p class="sr-only" role="status">正在加载文档</p>
        <span class="skeleton-chip"></span>
        <span class="skeleton-title"></span>
        <span class="skeleton-line"></span>
        <span class="skeleton-line short"></span>
        <span class="skeleton-block"></span>
      </div>

      <div v-else-if="errorMessage" class="reading-error" role="alert">
        <span class="error-mark" aria-hidden="true">!</span>
        <p class="reading-eyebrow">READ / FAILED</p>
        <h1>文档暂时打不开</h1>
        <p>{{ errorMessage }}</p>
        <div class="error-actions">
          <button type="button" class="primary-button" @click="loadDocument(true)">
            重新加载
          </button>
          <button type="button" class="secondary-button" @click="exitToHome">
            退出到主页
          </button>
        </div>
      </div>

      <template v-else-if="document">
        <header class="reading-head">
          <div class="head-meta">
            <span class="kind-chip" :class="document.kind">{{ kindLabel }}</span>
            <span class="private-chip">
              {{ document.visibility === 'public' ? '公开' : '私有' }}
            </span>
            <span class="private-chip">只读</span>
            <span v-if="user?.is_demo" class="private-chip demo-chip">示例空间</span>
            <span class="meta-text">
              {{ formatDateTime(document.updated_at) }} 更新
            </span>
          </div>

          <div class="title-row">
            <h1>{{ document.title }}</h1>
          </div>

          <div class="doc-submeta">
            <span>{{ document.chapter_name || '未分类' }}</span>
            <span v-if="document.folder_path" class="meta-dot" aria-hidden="true"></span>
            <span v-if="document.folder_path">{{ document.folder_path }}</span>
            <span class="meta-dot" aria-hidden="true"></span>
            <span>
              {{ document.summary ? document.summary.slice(0, 80) : '空白文档' }}
            </span>
          </div>
        </header>

        <div class="reading-divider" aria-hidden="true">
          <span>C</span>
        </div>

        <DocumentBlocks
          v-if="document.blocks.length && hasContent"
          :blocks="document.blocks"
          :kind="document.kind"
          :language="document.language"
          :document-id="document.id"
        />

        <section v-else class="empty-document">
          <span class="empty-glyph" aria-hidden="true">C</span>
          <h2>这篇{{ document.kind === 'note' ? '笔记' : '源码文档' }}还没有内容</h2>
          <p v-if="document.kind === 'note'">
            点「去编辑」开始写。工具栏支持标题、列表、表格、公式、代码和图片，
            写完在右上角保存即可。
          </p>
          <p v-else>
            点「去编辑」添加代码、备注和运行结果；导入的 C/H 文件可以直接阅读。
          </p>
          <button type="button" class="primary-button" @click="goEdit">
            去编辑
          </button>
        </section>

        <footer class="reading-foot">
          <span>{{ user?.display_name }}</span>
          <span class="foot-dot" aria-hidden="true"></span>
          <span>只读阅读</span>
          <span class="foot-line" aria-hidden="true"></span>
          <span>
            {{ document.blocks.length }} 个模块 · {{ formatDateTime(document.updated_at) }}
          </span>
        </footer>
      </template>
    </main>

    <Transition name="toast">
      <div
        v-if="toast"
        :key="toast.id"
        class="toast"
        :class="toast.tone"
        role="status"
      >
        <span aria-hidden="true">{{
          toast.tone === 'error' ? '!' : toast.tone === 'info' ? 'i' : '✓'
        }}</span>
        {{ toast.message }}
      </div>
    </Transition>

    <EditDocumentDialog
      :open="editOpen"
      :document="document"
      :chapters="chapters"
      @close="editOpen = false"
      @saved="handleSaved"
    />
    <DeleteDocumentDialog
      :open="deleteOpen"
      :document="document"
      :retention-days="retentionDays"
      @close="deleteOpen = false"
      @deleted="handleDeleted"
    />
    <ShareDialog
      :open="shareOpen"
      :document="document"
      @close="shareOpen = false"
      @changed="handleShareChanged"
    />
  </div>
</template>

<style scoped>
.document-page {
  position: relative;
  min-height: 100vh;
  padding-bottom: 60px;
}

.reading-topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: 1px solid var(--border);
  background: #fbfaff;
}

.reading-progress {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), #9b86ff);
  transform-origin: left center;
  transition: transform 0.12s linear;
}

.reading-topbar-inner {
  display: flex;
  gap: 14px;
  align-items: center;
  width: min(964px, 100%);
  min-height: 56px;
  margin: 0 auto;
  padding: 7px 32px;
}

.reading-exit {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  min-height: 34px;
  padding: 6px 8px 6px 5px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--muted);
  font: inherit;
  font-size: 11.5px;
  font-weight: 600;
  white-space: nowrap;
  background: transparent;
  cursor: pointer;
}

.reading-exit:hover {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.reading-exit svg {
  width: 14px;
  height: 14px;
}

.reading-topbar-title {
  flex: 1;
  overflow: hidden;
  color: var(--muted-strong);
  font-size: 12.5px;
  font-weight: 600;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-topbar-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.read-more {
  position: relative;
}

.read-more summary {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted-strong);
  font-size: 11px;
  font-weight: 650;
  list-style: none;
  background: #fff;
  cursor: pointer;
}

.read-more summary::-webkit-details-marker {
  display: none;
}

.read-more summary:hover,
.read-more[open] summary {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.read-more-menu {
  position: absolute;
  top: calc(100% + 5px);
  right: 0;
  z-index: 20;
  display: grid;
  min-width: 136px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 16px 34px -22px rgba(33, 27, 51, 0.5);
}

.read-more-menu button,
.read-more-menu a {
  display: block;
  width: 100%;
  padding: 8px 9px;
  border: 0;
  border-radius: 6px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
  background: transparent;
  cursor: pointer;
}

.read-more-menu button:hover,
.read-more-menu a:hover {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.read-more-menu .danger {
  color: #a84949;
}

@media (max-width: 960px) {
  .reading-topbar {
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(12px);
  }
}

@media (max-width: 640px) {
  .reading-topbar-inner {
    gap: 6px;
    padding: 7px 14px;
  }

  .reading-topbar-title {
    display: none;
  }

  .reading-topbar-actions {
    margin-left: auto;
  }

  .read-action {
    padding: 6px 8px;
  }

  .read-action.star-action {
    width: 34px;
    padding: 6px;
    justify-content: center;
    font-size: 0;
  }

  .read-action.star-action svg {
    width: 15px;
    height: 15px;
  }
}

.reading-main {
  width: min(900px, 100%);
  margin: 0 auto;
  padding: 32px 32px 30px;
}

.back-button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 6px 9px 6px 5px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--muted);
  font: inherit;
  font-size: 10.5px;
  font-weight: 600;
  background: transparent;
  cursor: pointer;
  transition:
    color 0.18s ease,
    background 0.18s ease;
}

.back-button:hover {
  color: var(--accent-strong);
  background: rgba(255, 255, 255, 0.65);
}

.back-button svg {
  width: 15px;
  height: 15px;
}

.reading-head {
  padding: 28px 8px 6px;
  animation: reading-in 0.5s ease both;
}

.head-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.kind-chip,
.private-chip {
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
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

.private-chip {
  color: #8e86a1;
  background: #f4f1fa;
}

.private-chip.demo-chip {
  color: #8a6a12;
  background: #fff8e1;
  border: 1px solid #f0e3b8;
}

.meta-text {
  color: #958da7;
  font-family: var(--font-mono);
  font-size: 9.5px;
}

.meta-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.title-row {
  display: flex;
  gap: 22px;
  align-items: flex-start;
  justify-content: space-between;
  margin-top: 18px;
}

.title-row h1 {
  max-width: 650px;
  overflow-wrap: anywhere;
  font-size: clamp(31px, 4.6vw, 50px);
  font-weight: 770;
  letter-spacing: -0.04em;
  line-height: 1.12;
}

.title-actions {
  display: flex;
  flex: none;
  gap: 6px;
  align-items: center;
  padding-top: 9px;
}

.read-action {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  white-space: nowrap;
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  background: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.read-action svg {
  width: 13px;
  height: 13px;
  fill: transparent;
  stroke: currentColor;
  stroke-width: 1.25;
}

.read-action:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
  background: #fff;
}

.read-action.edit-action {
  border-color: var(--accent);
  color: #fff;
  background: var(--accent);
}

.read-action.edit-action:hover {
  border-color: var(--accent-strong);
  color: #fff;
  background: var(--accent-strong);
}

.star-action.active {
  color: #805a1c;
  border-color: #ead7ae;
  background: var(--favorite-gold-soft);
}

.star-action.active svg {
  fill: currentColor;
}

.read-action.danger {
  color: #a84949;
}

.read-action.danger:hover {
  border-color: #ecc7c7;
  background: #fff4f4;
}

.doc-submeta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin-top: 15px;
  color: var(--muted);
  font-size: 10.5px;
}

.reading-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 27px 8px 28px;
  color: #c8bced;
}

.reading-divider::before,
.reading-divider::after {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-strong));
  content: "";
}

.reading-divider::after {
  background: linear-gradient(90deg, var(--border-strong), transparent);
}

.reading-divider span {
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

.empty-document {
  display: grid;
  gap: 8px;
  justify-items: center;
  padding: 70px 24px;
  border: 1px dashed var(--border-strong);
  border-radius: 20px;
  text-align: center;
  background:
    radial-gradient(240px 150px at 50% 0%, rgba(115, 87, 255, 0.08), transparent 74%),
    rgba(255, 255, 255, 0.55);
}

.empty-glyph {
  display: grid;
  width: 52px;
  height: 52px;
  margin-bottom: 5px;
  place-items: center;
  border-radius: 16px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 19px;
  background: var(--accent-soft);
}

.empty-document h2 {
  font-size: 21px;
  letter-spacing: -0.02em;
}

.empty-document p {
  max-width: 480px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}

.empty-document .primary-button {
  margin-top: 8px;
}

.reading-foot {
  display: flex;
  gap: 9px;
  align-items: center;
  margin-top: 50px;
  padding-top: 17px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 10px;
}

.foot-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.foot-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

.reading-foot button {
  border: 0;
  color: var(--accent-strong);
  font: inherit;
  font-size: 10px;
  font-weight: 650;
  background: transparent;
  cursor: pointer;
}

.reading-skeleton {
  display: grid;
  gap: 13px;
  max-width: 720px;
  padding: 50px 8px;
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
  width: 70px;
  height: 20px;
}

.skeleton-title {
  width: 72%;
  height: 42px;
  margin-top: 12px;
}

.skeleton-line {
  width: 88%;
  height: 13px;
}

.skeleton-line.short {
  width: 56%;
}

.skeleton-block {
  width: 100%;
  height: 210px;
  margin-top: 18px;
  border-radius: 17px;
}

.reading-error {
  display: grid;
  gap: 10px;
  justify-items: start;
  padding: 70px 10px;
}

.error-mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid #f0cccc;
  border-radius: 14px;
  color: #b44d4d;
  font-family: var(--font-mono);
  font-size: 20px;
  background: #fff5f5;
}

.reading-eyebrow {
  margin-top: 7px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.17em;
}

.reading-error h1 {
  font-size: 29px;
  letter-spacing: -0.03em;
}

.reading-error > p:not(.reading-eyebrow) {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}

.error-actions {
  display: flex;
  gap: 8px;
  margin-top: 7px;
}

.primary-button,
.secondary-button {
  padding: 9px 15px;
  border-radius: 9px;
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  cursor: pointer;
}

.primary-button {
  border: 1px solid var(--accent-strong);
  color: #fff;
  background: var(--accent-strong);
}

.secondary-button {
  border: 1px solid var(--border-strong);
  color: var(--muted-strong);
  background: #fff;
}

.toast {
  position: fixed;
  top: 78px;
  left: 50%;
  z-index: 220;
  display: flex;
  gap: 8px;
  align-items: center;
  max-width: min(90vw, 460px);
  padding: 9px 13px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 16px 40px -20px rgba(33, 27, 51, 0.5);
  transform: translateX(-50%);
}

.toast > span {
  display: grid;
  flex: none;
  width: 17px;
  height: 17px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 9px;
  background: #6fbf8f;
}

.toast.error > span {
  background: #c96363;
}

.toast.info > span {
  background: var(--accent);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

@keyframes reading-in {
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

@media (max-width: 760px) {
  .reading-main {
    padding: 22px 14px calc(38px + env(safe-area-inset-bottom));
  }

  .reading-head {
    padding: 20px 3px 2px;
  }

  .title-row {
    flex-direction: column;
    gap: 14px;
    margin-top: 15px;
  }

  .title-row h1 {
    font-size: clamp(28px, 9vw, 38px);
  }

  .title-actions {
    width: 100%;
    padding-top: 0;
    flex-wrap: wrap;
  }

  .title-actions {
    gap: 4px;
  }

  .read-action {
    flex: 1 1 auto;
    min-height: 38px;
    justify-content: center;
    padding: 7px;
    font-size: 9.5px;
  }

  .read-action svg {
    width: 12px;
    height: 12px;
  }

  .read-action.danger {
    flex-basis: auto;
  }

  .doc-submeta {
    margin-top: 12px;
  }

  .reading-divider {
    margin: 22px 3px 23px;
  }

  .reading-foot {
    flex-wrap: wrap;
    margin-top: 38px;
  }

  .foot-line {
    display: none;
  }

  .toast {
    top: 70px;
  }
}
</style>
