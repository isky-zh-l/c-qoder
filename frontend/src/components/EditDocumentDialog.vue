<script setup lang="ts">
import { ref, watch } from 'vue'
import { ApiError, getDocument, updateDocument } from '../api/client'
import type {
  Chapter,
  DocumentDetail,
  DocumentSummary,
} from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  document: DocumentSummary | null
  chapters: Chapter[]
}>()

const emit = defineEmits<{
  close: []
  saved: [document: DocumentDetail]
}>()

const title = ref('')
const chapterId = ref<number | null>(null)
const version = ref(1)
const saving = ref(false)
const errorMessage = ref('')
const refreshing = ref(false)

function syncFromDocument() {
  if (!props.document) {
    return
  }
  title.value = props.document.title
  chapterId.value = props.document.chapter_id
  version.value = props.document.version
  errorMessage.value = ''
}

watch(
  () => [props.open, props.document?.id, props.document?.updated_at],
  () => {
    if (props.open) {
      syncFromDocument()
    }
  },
  { immediate: true },
)

function errorHint(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'document_name_conflict') {
      return '你的空间里已经有同名文档，请换一个标题。'
    }
    if (error.code === 'version_conflict') {
      return '文档已在其他设备更新。当前输入仍保留；点击“刷新版本”后可再次保存。'
    }
    return error.message
  }
  return error instanceof Error ? error.message : '保存失败，请稍后重试'
}

async function submit() {
  if (!props.document || saving.value) {
    return
  }
  const cleanedTitle = title.value.trim()
  if (!cleanedTitle) {
    errorMessage.value = '标题不能为空。'
    return
  }
  saving.value = true
  errorMessage.value = ''
  try {
    const saved = await updateDocument(
      props.document.id,
      { title: cleanedTitle, chapter_id: chapterId.value },
      version.value,
    )
    emit('saved', saved)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'version_conflict') {
      const currentVersion = error.details.current_version
      if (typeof currentVersion === 'number') {
        version.value = currentVersion
      }
    }
    errorMessage.value = errorHint(error)
  } finally {
    saving.value = false
  }
}

async function refreshVersion() {
  if (!props.document || refreshing.value) {
    return
  }
  refreshing.value = true
  try {
    const latest = await getDocument(props.document.id)
    version.value = latest.version
    errorMessage.value = '已同步服务器版本，输入内容没有清空。可以再次保存。'
  } catch (error) {
    errorMessage.value = errorHint(error)
  } finally {
    refreshing.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    title="管理文档"
    eyebrow="DOCUMENT / METADATA"
    :dismissible="!saving"
    size="small"
    @close="emit('close')"
  >
    <form class="edit-form" @submit.prevent="submit">
      <label class="field">
        <span>标题</span>
        <input
          v-model="title"
          type="text"
          maxlength="200"
          autocomplete="off"
          placeholder="文档标题"
        />
      </label>

      <label class="field">
        <span>所属章节</span>
        <select v-model="chapterId">
          <option :value="null">未分类</option>
          <option
            v-for="chapter in chapters"
            :key="chapter.id"
            :value="chapter.id"
          >
            {{ chapter.name }}
          </option>
        </select>
      </label>

      <p class="identity-note">
        稳定 ID：#{{ document?.id }}。改名、换章节不会改变链接，也不会丢失模块、图片或收藏。
      </p>

      <p v-if="errorMessage" class="form-error" role="alert">
        {{ errorMessage }}
        <button
          v-if="errorMessage.includes('刷新版本')"
          type="button"
          class="inline-action"
          :disabled="refreshing"
          @click="refreshVersion"
        >
          {{ refreshing ? '同步中…' : '刷新版本' }}
        </button>
      </p>

      <div class="form-actions">
        <button
          type="button"
          class="button secondary"
          :disabled="saving"
          @click="emit('close')"
        >
          取消
        </button>
        <button type="submit" class="button primary" :disabled="saving">
          {{ saving ? '正在保存…' : '保存修改' }}
        </button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.edit-form {
  display: grid;
  gap: 15px;
}

.field {
  display: grid;
  gap: 7px;
  color: var(--muted-strong);
  font-size: 11.5px;
  font-weight: 650;
}

.field input,
.field select {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 13px;
  font-weight: 450;
  background: #fff;
  outline: none;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.field input:focus,
.field select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(115, 87, 255, 0.09);
}

.identity-note {
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.7;
}

.form-error {
  padding: 10px 12px;
  border: 1px solid #f0cccc;
  border-radius: 9px;
  color: #a43e3e;
  font-size: 11px;
  line-height: 1.7;
  background: #fff5f5;
}

.inline-action {
  margin-left: 6px;
  padding: 2px 0;
  border: 0;
  color: var(--accent-strong);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  text-decoration: underline;
  background: transparent;
  cursor: pointer;
}

.form-actions {
  display: flex;
  gap: 9px;
  justify-content: flex-end;
  margin-top: 3px;
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

.button.primary {
  border: 1px solid var(--accent-strong);
  color: #fff;
  background: linear-gradient(145deg, #846aff, #5436e8);
  box-shadow: 0 10px 24px -16px rgba(84, 54, 232, 0.85);
}
</style>
