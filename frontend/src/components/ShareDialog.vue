<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ApiError,
  updateVisibility,
} from '../api/client'
import type {
  DocumentDetail,
  PublicationResponse,
  Visibility,
} from '../api/types'
import { formatDateTime } from '../utils/format'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  document: DocumentDetail | null
}>()

const emit = defineEmits<{
  close: []
  changed: []
}>()

const state = ref<PublicationResponse>({
  visibility: 'private',
  share_token: null,
  share_url: null,
  published_at: null,
  published_version: null,
})
const busy = ref(false)
const errorMessage = ref('')
const copied = ref(false)

const isPublic = computed(() => state.value.visibility === 'public')
const isOutdated = computed(
  () =>
    isPublic.value &&
    props.document !== null &&
    state.value.published_version !== null &&
    state.value.published_version !== props.document.version,
)
const absoluteShareUrl = computed(() => {
  if (!state.value.share_url) {
    return ''
  }
  return new URL(state.value.share_url, window.location.origin).href
})

function syncFromDocument() {
  if (!props.document) {
    return
  }
  state.value = {
    visibility: props.document.visibility,
    share_token: props.document.share_token,
    share_url: props.document.share_url,
    published_at: props.document.published_at,
    published_version: props.document.published_version,
  }
  errorMessage.value = ''
  copied.value = false
}

watch(
  () => [props.open, props.document?.id, props.document?.version],
  () => {
    if (props.open) {
      syncFromDocument()
    }
  },
  { immediate: true },
)

async function changeVisibility(visibility: Visibility) {
  if (!props.document || busy.value) {
    return
  }
  busy.value = true
  errorMessage.value = ''
  try {
    state.value = await updateVisibility(props.document.id, visibility)
    copied.value = false
    emit('changed')
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError
        ? error.message
        : '公开状态更新失败，请稍后重试'
  } finally {
    busy.value = false
  }
}

async function copyLink() {
  if (!absoluteShareUrl.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(absoluteShareUrl.value)
  } catch {
    const area = window.document.createElement('textarea')
    area.value = absoluteShareUrl.value
    area.style.position = 'fixed'
    area.style.opacity = '0'
    window.document.body.appendChild(area)
    area.select()
    window.document.execCommand('copy')
    area.remove()
  }
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1800)
}
</script>

<template>
  <ModalShell
    :open="open"
    title="公开分享"
    eyebrow="PUBLIC / SNAPSHOT"
    :dismissible="!busy"
    size="small"
    @close="emit('close')"
  >
    <div class="share-body">
      <div class="state-line">
        <span class="state-dot" :class="{ public: isPublic }"></span>
        <strong>{{ isPublic ? '公开中' : '默认私有' }}</strong>
        <span v-if="state.published_at" class="state-time">
          {{ formatDateTime(state.published_at) }} 发布
        </span>
      </div>

      <p class="share-copy">
        公开页展示<strong>发布时的独立快照</strong>，之后继续编辑不会自动公开。
        取消发布后，旧链接和公开图片地址立即失效。
      </p>

      <template v-if="isPublic">
        <div class="link-line">
          <input
            class="share-input"
            type="text"
            readonly
            :value="absoluteShareUrl"
            aria-label="公开分享链接"
            @focus="($event.target as HTMLInputElement).select()"
          />
          <button type="button" class="button secondary" @click="copyLink">
            {{ copied ? '已复制' : '复制链接' }}
          </button>
        </div>

        <div class="snapshot-line">
          <span>
            公开快照版本 v{{ state.published_version ?? '—' }}
            · 当前文档 v{{ document?.version ?? '—' }}
          </span>
          <a :href="absoluteShareUrl" target="_blank" rel="noopener noreferrer">
            打开公开页
          </a>
        </div>

        <p v-if="isOutdated" class="outdated">
          文档已更新，但公开页仍显示旧快照。
          重新发布会更新公开内容，链接保持不变。
        </p>

        <div class="share-actions">
          <button
            type="button"
            class="button primary"
            :disabled="busy"
            @click="changeVisibility('public')"
          >
            {{ isOutdated ? '重新发布当前版本' : '更新公开版本' }}
          </button>
          <button
            type="button"
            class="button danger"
            :disabled="busy"
            @click="changeVisibility('private')"
          >
            取消发布
          </button>
        </div>
      </template>

      <template v-else>
        <p class="privacy-note">
          读者只会获得这篇文章的正文和其中引用的图片；
          不会看到邮箱、章节树、收藏、回收站或其他文档。
        </p>
        <div class="share-actions">
          <button
            type="button"
            class="button primary"
            :disabled="busy"
            @click="changeVisibility('public')"
          >
            {{ busy ? '正在发布…' : '发布公开链接' }}
          </button>
        </div>
      </template>

      <p v-if="errorMessage" class="form-error" role="alert">
        {{ errorMessage }}
      </p>
    </div>

    <template #footer>
      <button
        type="button"
        class="button secondary"
        :disabled="busy"
        @click="emit('close')"
      >
        关闭
      </button>
    </template>
  </ModalShell>
</template>

<style scoped>
.share-body {
  display: grid;
  gap: 14px;
}

.state-line {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--muted-strong);
  font-size: 11px;
}

.state-line strong {
  font-size: 12px;
}

.state-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a8a0b8;
}

.state-dot.public {
  background: #6fbf8f;
  box-shadow: 0 0 0 4px rgba(111, 191, 143, 0.12);
}

.state-time {
  margin-left: auto;
  color: var(--muted);
  font-size: 9.5px;
}

.share-copy {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.75;
}

.share-copy strong {
  color: var(--text);
}

.link-line {
  display: flex;
  gap: 7px;
}

.share-input {
  flex: 1;
  min-width: 0;
  height: 37px;
  padding: 0 10px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--muted-strong);
  font: inherit;
  font-family: var(--font-mono);
  font-size: 10px;
  background: #fbf9ff;
  outline: none;
}

.snapshot-line {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  color: var(--muted);
  font-size: 9.5px;
}

.snapshot-line a {
  flex: none;
  color: var(--accent-strong);
}

.outdated {
  padding: 9px 11px;
  border: 1px solid #efdfb7;
  border-radius: 8px;
  color: #805a1c;
  font-size: 10.5px;
  line-height: 1.65;
  background: var(--favorite-gold-soft);
}

.privacy-note {
  padding: 10px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.7;
  background: #fbf9ff;
}

.share-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.button {
  padding: 9px 15px;
  border-radius: 9px;
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  cursor: pointer;
}

.button:disabled {
  opacity: 0.5;
  cursor: default;
}

.button.secondary {
  border: 1px solid var(--border-strong);
  color: var(--muted-strong);
  background: #fff;
}

.button.primary {
  border: 1px solid var(--accent-strong);
  color: #fff;
  background: linear-gradient(145deg, #846aff, #5436e8);
}

.button.danger {
  border: 1px solid #eccaca;
  color: #a43e3e;
  background: #fff5f5;
}

.form-error {
  padding: 9px 11px;
  border: 1px solid #f0cccc;
  border-radius: 8px;
  color: #a43e3e;
  font-size: 10.5px;
  line-height: 1.6;
  background: #fff5f5;
}

@media (max-width: 520px) {
  .link-line {
    flex-direction: column;
  }

  .snapshot-line {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
