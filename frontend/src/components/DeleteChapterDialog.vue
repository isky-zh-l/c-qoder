<script setup lang="ts">
import { ref, watch } from 'vue'
import { ApiError, deleteChapter } from '../api/client'
import type { Chapter } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  chapter: Chapter | null
}>()

const emit = defineEmits<{
  close: []
  deleted: [chapter: Chapter]
}>()

const deleting = ref(false)
const errorMessage = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      deleting.value = false
      errorMessage.value = ''
    }
  },
)

async function confirmDelete() {
  if (!props.chapter || deleting.value) {
    return
  }
  deleting.value = true
  errorMessage.value = ''
  try {
    await deleteChapter(props.chapter.id)
    emit('deleted', props.chapter)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? error.message : '删除失败，请稍后重试'
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="删除章节"
    eyebrow="CHAPTER / DELETE"
    :dismissible="!deleting"
    size="small"
    @close="emit('close')"
  >
    <p class="lead">
      删除章节「<strong>{{ chapter?.name }}</strong>」？
    </p>
    <p class="copy">
      章节里的 {{ chapter?.document_count || 0 }} 篇文档不会删除，会转为“未分类”。
      全部列表和收藏顺序保持不变。
    </p>
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
        {{ deleting ? '正在删除…' : '删除章节' }}
      </button>
    </template>
  </ModalShell>
</template>

<style scoped>
.lead {
  font-size: 14px;
  line-height: 1.6;
}

.lead strong {
  overflow-wrap: anywhere;
}

.copy {
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
