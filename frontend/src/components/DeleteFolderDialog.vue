<script setup lang="ts">
import { ref, watch } from 'vue'
import { ApiError, deleteFolder } from '../api/client'
import type { Folder } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  folder: Folder | null
}>()

const emit = defineEmits<{
  close: []
  deleted: [folder: Folder]
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
  if (!props.folder || deleting.value) return
  deleting.value = true
  errorMessage.value = ''
  try {
    await deleteFolder(props.folder.id)
    emit('deleted', props.folder)
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
    title="删除文件夹"
    eyebrow="FOLDER / DELETE"
    :dismissible="!deleting"
    size="small"
    @close="emit('close')"
  >
    <p class="lead">删除「<strong>{{ folder?.name }}</strong>」？</p>
    <p class="copy">
      文件夹内的文档和子文件夹会移到上级目录，不会删除文档。若这是空文件夹，则直接删除。
    </p>
    <p v-if="folder" class="count">
      {{ folder.document_count }} 篇文档 · {{ folder.child_count }} 个子文件夹
    </p>
    <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
    <template #footer>
      <button type="button" class="button secondary" :disabled="deleting" @click="emit('close')">
        取消
      </button>
      <button type="button" class="button danger" :disabled="deleting" @click="confirmDelete">
        {{ deleting ? '正在删除…' : '删除文件夹' }}
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

.copy,
.count {
  margin-top: 8px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.75;
}

.count {
  color: var(--muted-strong);
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.button {
  padding: 9px 17px;
  border-radius: 9px;
  font: inherit;
  font-size: 11.5px;
  font-weight: 650;
  cursor: pointer;
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

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
