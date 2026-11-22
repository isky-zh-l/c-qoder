<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ApiError,
  getRecycle,
  restoreRecycle,
} from '../api/client'
import type { DocumentDetail, RecycleItem } from '../api/types'
import { formatDateTime } from '../utils/format'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  retentionDays: number
}>()

const emit = defineEmits<{
  close: []
  restored: [document: DocumentDetail]
}>()

const loading = ref(false)
const loadError = ref('')
const items = ref<RecycleItem[]>([])
const restoringId = ref<number | null>(null)
const conflictId = ref<number | null>(null)
const titleDraft = ref('')
const itemError = ref('')

const hasItems = computed(() => items.value.length > 0)

async function load() {
  loading.value = true
  loadError.value = ''
  itemError.value = ''
  try {
    items.value = await getRecycle()
  } catch (error) {
    loadError.value =
      error instanceof ApiError ? error.message : '回收站读取失败，请重试'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      conflictId.value = null
      titleDraft.value = ''
      load()
    }
  },
  { immediate: true },
)

function startConflict(item: RecycleItem) {
  conflictId.value = item.id
  titleDraft.value = item.title
  itemError.value = '当前空间已有同名文档，请输入新名称后恢复。'
}

async function restore(item: RecycleItem) {
  if (restoringId.value !== null) {
    return
  }
  const useDraft = conflictId.value === item.id
  if (useDraft && !titleDraft.value.trim()) {
    itemError.value = '新名称不能为空。'
    return
  }
  restoringId.value = item.id
  itemError.value = ''
  try {
    const document = await restoreRecycle(
      item.id,
      useDraft ? titleDraft.value : undefined,
    )
    items.value = items.value.filter((entry) => entry.id !== item.id)
    conflictId.value = null
    titleDraft.value = ''
    emit('restored', document)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'document_name_conflict') {
      startConflict(item)
    } else {
      itemError.value =
        error instanceof ApiError ? error.message : '恢复失败，请稍后重试'
    }
  } finally {
    restoringId.value = null
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="回收站"
    eyebrow="RECYCLE / 7 DAYS"
    size="large"
    @close="emit('close')"
  >
    <div class="recycle-head">
      <p>
        删除的文档在这里保留 {{ retentionDays }} 天。期间可恢复原文档 ID、
        模块和图片；附件只要仍被引用就不会被清理。
      </p>
      <button type="button" class="refresh" :disabled="loading" @click="load">
        刷新
      </button>
    </div>

    <div v-if="loading" class="loading-list" role="status">
      <span v-for="index in 3" :key="index" class="loading-row"></span>
      正在读取回收站…
    </div>

    <div v-else-if="loadError" class="load-error" role="alert">
      <p>{{ loadError }}</p>
      <button type="button" class="refresh" @click="load">重试</button>
    </div>

    <div v-else-if="!hasItems" class="recycle-empty">
      <span aria-hidden="true">∅</span>
      <strong>回收站是空的</strong>
      <p>删除的笔记和源码会在这里保留 {{ retentionDays }} 天。</p>
    </div>

    <ul v-else class="recycle-list">
      <li v-for="item in items" :key="item.id" class="recycle-item">
        <div class="item-main">
          <div class="item-line">
            <span class="kind" :class="item.kind">
              {{ item.kind === 'source' ? '源码' : '笔记' }}
            </span>
            <strong>{{ item.title }}</strong>
          </div>
          <div class="item-meta">
            <span>
              {{ formatDateTime(item.deleted_at) }} 删除
            </span>
            <span class="meta-dot" aria-hidden="true"></span>
            <span>{{ item.original_chapter_name || '未分类' }}</span>
            <template v-if="item.original_folder_path">
              <span class="meta-dot" aria-hidden="true"></span>
              <span>{{ item.original_folder_path }}</span>
            </template>
            <span class="meta-dot" aria-hidden="true"></span>
            <span class="days">剩余 {{ item.days_remaining }} 天</span>
          </div>

          <div v-if="conflictId === item.id" class="conflict-row">
            <input
              v-model="titleDraft"
              type="text"
              maxlength="200"
              aria-label="恢复时使用的新名称"
              @keydown.enter.prevent="restore(item)"
            />
            <button
              type="button"
              class="restore-button"
              :disabled="restoringId !== null"
              @click="restore(item)"
            >
              {{ restoringId === item.id ? '恢复中…' : '用新名称恢复' }}
            </button>
          </div>
        </div>

        <button
          v-if="conflictId !== item.id"
          type="button"
          class="restore-button"
          :disabled="restoringId !== null"
          @click="restore(item)"
        >
          {{ restoringId === item.id ? '恢复中…' : '恢复' }}
        </button>
      </li>
    </ul>

    <p v-if="itemError" class="item-error" role="alert">{{ itemError }}</p>

    <template #footer>
      <button type="button" class="button close-button" @click="emit('close')">
        关闭
      </button>
    </template>
  </ModalShell>
</template>

<style scoped>
.recycle-head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.recycle-head p {
  max-width: 560px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.75;
}

.refresh {
  flex: none;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 10px;
  background: #fff;
  cursor: pointer;
}

.refresh:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.loading-list {
  display: grid;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
}

.loading-row {
  height: 66px;
  border-radius: 12px;
  background: linear-gradient(
    90deg,
    #f4efff 20%,
    #fbf9ff 42%,
    #f4efff 64%
  );
  background-size: 220% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

.load-error,
.recycle-empty {
  display: grid;
  gap: 6px;
  justify-items: center;
  padding: 40px 18px;
  border: 1px dashed var(--border-strong);
  border-radius: 14px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  background: rgba(255, 255, 255, 0.55);
}

.recycle-empty span {
  color: #c5b9e8;
  font-family: var(--font-mono);
  font-size: 30px;
}

.recycle-empty strong {
  color: var(--text);
  font-size: 14px;
}

.recycle-empty p {
  font-size: 11px;
}

.recycle-list {
  display: grid;
  gap: 8px;
}

.recycle-item {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
}

.item-main {
  min-width: 0;
}

.item-line {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.item-line strong {
  overflow: hidden;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kind {
  flex: none;
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--accent-strong);
  font-size: 9px;
  font-weight: 700;
  background: var(--accent-soft);
}

.kind.source {
  color: var(--source-text);
  background: var(--source-badge);
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 5px;
  color: #978fa9;
  font-size: 9.5px;
}

.meta-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.days {
  color: #a77a2c;
  font-weight: 650;
}

.conflict-row {
  display: flex;
  gap: 7px;
  margin-top: 9px;
}

.conflict-row input {
  width: min(260px, 48vw);
  height: 32px;
  padding: 0 9px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text);
  font: inherit;
  font-size: 11px;
  background: #fff;
  outline: none;
}

.conflict-row input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(115, 87, 255, 0.08);
}

.restore-button {
  flex: none;
  padding: 7px 12px;
  border: 1px solid #d9cef8;
  border-radius: 9px;
  color: var(--accent-strong);
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.restore-button:hover:not(:disabled) {
  background: var(--accent-faint);
}

.restore-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.item-error {
  margin-top: 12px;
  padding: 9px 11px;
  border: 1px solid #f0cccc;
  border-radius: 9px;
  color: #a43e3e;
  font-size: 10.5px;
  line-height: 1.7;
  background: #fff5f5;
}

.close-button {
  padding: 8px 16px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

@keyframes shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@media (max-width: 560px) {
  .recycle-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .restore-button {
    align-self: flex-end;
  }
}
</style>
