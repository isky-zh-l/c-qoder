<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, updateDocument } from '../api/client'
import type { DocumentSummary, Folder } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  document: DocumentSummary | null
  folders: Folder[]
}>()

const emit = defineEmits<{
  close: []
  moved: [documentId: number, folderId: number | null]
}>()

const folderId = ref<number | null>(null)
const moving = ref(false)
const errorMessage = ref('')

const options = computed(() =>
  props.folders
    .filter(
      (folder) =>
        props.document?.chapter_id != null &&
        folder.chapter_id != null &&
        Number(folder.chapter_id) === Number(props.document.chapter_id),
    )
    .slice()
    .sort((a, b) => String(a.path || a.name).localeCompare(String(b.path || b.name))),
)

watch(
  () => [props.open, props.document?.id, props.document?.folder_id],
  () => {
    if (props.open && props.document) {
      folderId.value = props.document.folder_id
      errorMessage.value = ''
      moving.value = false
    }
  },
  { immediate: true },
)

async function submit() {
  if (!props.document || moving.value) return
  moving.value = true
  errorMessage.value = ''
  try {
    const target = folderId.value
    await updateDocument(
      props.document.id,
      { folder_id: target },
      props.document.version,
    )
    emit('moved', props.document.id, target)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'version_conflict') {
      errorMessage.value = '文档已在其他页面更新。请返回列表刷新后再移动。'
    } else {
      errorMessage.value =
        error instanceof ApiError ? error.message : '移动失败，请稍后重试'
    }
  } finally {
    moving.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="移动到文件夹"
    eyebrow="DOCUMENT / MOVE"
    :dismissible="!moving"
    size="small"
    @close="emit('close')"
  >
    <div class="move-form">
      <p class="lead">
        「<strong>{{ document?.title }}</strong>」当前位于
        {{ document?.folder_path || '章节根目录' }}
      </p>
      <label class="field">
        <span>目标文件夹</span>
        <select v-model="folderId">
          <option :value="null">章节根目录</option>
          <option v-for="folder in options" :key="folder.id" :value="folder.id">
            {{ folder.path || folder.name }}
          </option>
        </select>
      </label>
      <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
      <p class="hint">只能移动到同一章节的文件夹；章节、收藏、内容、稳定 ID 和公开链接不变。</p>
      <div class="actions">
        <button type="button" class="button secondary" :disabled="moving" @click="emit('close')">
          取消
        </button>
        <button type="button" class="button primary" :disabled="moving" @click="submit">
          {{ moving ? '移动中…' : '移动' }}
        </button>
      </div>
    </div>
  </ModalShell>
</template>

<style scoped>
.move-form {
  display: grid;
  gap: 14px;
}

.lead {
  color: var(--muted-strong);
  font-size: 12px;
  line-height: 1.7;
}

.lead strong {
  overflow-wrap: anywhere;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 650;
}

.field select {
  min-height: 40px;
  padding: 9px 11px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  background: #fff;
}

.hint {
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.7;
}

.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.button {
  padding: 9px 16px;
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

.button.primary {
  border: 1px solid var(--accent-strong);
  color: #fff;
  background: var(--accent-strong);
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
