<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ApiError,
  createFolder,
  updateFolder,
} from '../api/client'
import type { Folder } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    mode: 'create' | 'rename'
    folder?: Folder | null
    parentId?: number
    chapterId?: number | null
    folders: Folder[]
  }>(),
  { folder: null, parentId: 0, chapterId: null, folders: () => [] },
)

const emit = defineEmits<{
  close: []
  saved: [folder: Folder]
}>()

const name = ref('')
const parentId = ref(0)
const saving = ref(false)
const errorMessage = ref('')

const activeChapterId = computed(
  () => props.folder?.chapter_id ?? props.chapterId ?? null,
)

const parentOptions = computed(() =>
  props.folders
    .filter(
      (folder) =>
        Number(folder.id) !== Number(props.folder?.id) &&
        activeChapterId.value !== null &&
        Number(folder.chapter_id) === Number(activeChapterId.value),
    )
    .slice()
    .sort((a, b) => String(a.path || a.name).localeCompare(String(b.path || b.name))),
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    name.value = props.folder?.name || ''
    parentId.value = props.folder
      ? Number(props.folder.parent_id || 0)
      : Number(props.parentId || 0)
    errorMessage.value = ''
    saving.value = false
  },
  { immediate: true },
)

async function submit() {
  if (saving.value) return
  const clean = name.value.trim()
  if (!clean) {
    errorMessage.value = '文件夹名称不能为空'
    return
  }
  if (activeChapterId.value === null) {
    errorMessage.value = '文件夹必须从章节内创建'
    return
  }
  saving.value = true
  errorMessage.value = ''
  try {
    const saved =
      props.mode === 'create' || !props.folder
        ? await createFolder(
            clean,
            Number(parentId.value || 0),
            activeChapterId.value,
          )
        : await updateFolder(props.folder.id, {
            name: clean,
            parent_id: Number(parentId.value || 0),
          })
    emit('saved', saved)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? error.message : '文件夹保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    :title="mode === 'create' ? '新建文件夹' : '编辑文件夹'"
    eyebrow="FOLDER / ORGANIZE"
    :dismissible="!saving"
    size="small"
    @close="emit('close')"
  >
    <form class="folder-form" @submit.prevent="submit">
      <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
      <label class="field">
        <span>文件夹名称</span>
        <input v-model="name" maxlength="60" placeholder="例如：链表专题" required />
      </label>
      <label v-if="mode === 'rename'" class="field">
        <span>父目录</span>
        <select v-model="parentId">
          <option :value="0">章节根目录</option>
          <option v-for="folder in parentOptions" :key="folder.id" :value="folder.id">
            {{ folder.path || folder.name }}
          </option>
        </select>
      </label>
      <p class="hint">
        文件夹只在当前章节内组织，不会改变笔记、C 文件、收藏、稳定 ID 或公开链接。
      </p>
      <div class="actions">
        <button type="button" class="button secondary" :disabled="saving" @click="emit('close')">
          取消
        </button>
        <button type="submit" class="button primary" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.folder-form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 650;
}

.field input,
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
  line-height: 1.75;
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
