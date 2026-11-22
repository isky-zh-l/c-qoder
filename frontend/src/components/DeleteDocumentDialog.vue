<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, deleteDocument } from '../api/client'
import type { DocumentSummary } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  document: DocumentSummary | null
  retentionDays: number
}>()

const emit = defineEmits<{
  close: []
  deleted: [document: DocumentSummary]
}>()

const deleting = ref(false)
const errorMessage = ref('')

const kindLabel = computed(() =>
  props.document?.kind === 'source' ? '源码' : '笔记',
)

watch(
  () => props.open,
  (open) => {
    if (open) {
      errorMessage.value = ''
      deleting.value = false
    }
  },
)

async function confirmDelete() {
  if (!props.document || deleting.value) {
    return
  }
  deleting.value = true
  errorMessage.value = ''
  try {
    await deleteDocument(props.document.id)
    emit('deleted', props.document)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError
        ? error.message
        : '删除失败，请稍后重试'
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="移入回收站"
    eyebrow="RECYCLE / SAFE DELETE"
    :dismissible="!deleting"
    size="small"
    @close="emit('close')"
  >
    <div class="delete-body">
      <span class="delete-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M5 7h14M9 7V4.8h6V7m-7.6 0 .9 12h7.4l.9-12M10 10v6m4-6v6"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
      </span>
      <div>
        <p class="delete-lead">
          将{{ kindLabel }}「<strong>{{ document?.title }}</strong>」移入回收站？
        </p>
        <p class="delete-copy">
          文档 ID、模块、图片和收藏关系会保留；收藏会暂时移出收藏架。
          回收站保留 {{ retentionDays }} 天，期间可以恢复。
        </p>
      </div>
    </div>

    <p v-if="errorMessage" class="form-error" role="alert">
      {{ errorMessage }}
    </p>

    <template #footer>
      <button
        type="button"
        class="button secondary"
        :disabled="deleting"
        @click="emit('close')"
      >
        取消
      </button>
      <button
        type="button"
        class="button danger"
        :disabled="deleting"
        @click="confirmDelete"
      >
        {{ deleting ? '正在移入…' : '移入回收站' }}
      </button>
    </template>
  </ModalShell>
</template>

<style scoped>
.delete-body {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.delete-icon {
  display: grid;
  flex: none;
  width: 46px;
  height: 46px;
  place-items: center;
  border: 1px solid #f0d2d2;
  border-radius: 13px;
  color: #b44d4d;
  background: #fff5f5;
}

.delete-icon svg {
  width: 22px;
  height: 22px;
}

.delete-lead {
  color: var(--text);
  font-size: 13.5px;
  line-height: 1.65;
}

.delete-lead strong {
  overflow-wrap: anywhere;
}

.delete-copy {
  margin-top: 7px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.75;
}

.form-error {
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid #f0cccc;
  border-radius: 9px;
  color: #a43e3e;
  font-size: 11px;
  line-height: 1.7;
  background: #fff5f5;
}

.button {
  padding: 9px 17px;
  border-radius: 10px;
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.button.secondary {
  border: 1px solid var(--border-strong);
  color: var(--muted-strong);
  background: #fff;
}

.button.danger {
  border: 1px solid #b44d4d;
  color: #fff;
  background: #b44d4d;
}
</style>
