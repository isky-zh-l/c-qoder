<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, createDocument, importDocument } from '../api/client'
import type {
  Chapter,
  DocumentDetail,
  Folder,
  SourceLanguage,
} from '../api/types'
import ModalShell from './ModalShell.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    mode: 'note' | 'source' | 'import'
    chapters: Chapter[]
    folders?: Folder[]
    defaultChapterId?: number | null
    defaultFolderId?: number | null
  }>(),
  { folders: () => [], defaultChapterId: null, defaultFolderId: null },
)

const emit = defineEmits<{
  close: []
  created: [document: DocumentDetail]
}>()

const title = ref('')
const language = ref<SourceLanguage>('c')
const chapterId = ref<number | null>(null)
const folderId = ref<number | null>(null)
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const saving = ref(false)
const errorMessage = ref('')

const folderOptions = computed(() =>
  props.folders
    .filter(
      (folder) =>
        chapterId.value !== null &&
        folder.chapter_id !== null &&
        Number(folder.chapter_id) === Number(chapterId.value),
    )
    .slice()
    .sort((a, b) => String(a.path || a.name).localeCompare(String(b.path || b.name))),
)

const modeCopy = computed(() => {
  if (props.mode === 'note') {
    return {
      title: '新建笔记',
      eyebrow: 'NEW / NOTE',
      submit: '创建并打开',
      titleLabel: '笔记标题',
      placeholder: '例如：指针与内存的关系',
    }
  }
  if (props.mode === 'source') {
    return {
      title: '新建 C 文件',
      eyebrow: 'NEW / SOURCE',
      submit: '创建并打开',
      titleLabel: '文件名',
      placeholder: '例如：linked-list',
    }
  }
  return {
    title: '上传文件',
    eyebrow: 'IMPORT / FILE',
    submit: '导入并打开',
    titleLabel: '文档标题（可选）',
    placeholder: '默认使用文件名或 Markdown 一级标题',
  }
})

function reset() {
  title.value = ''
  language.value = 'c'
  chapterId.value = props.defaultChapterId
  folderId.value = props.defaultFolderId
  file.value = null
  errorMessage.value = ''
  saving.value = false
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      reset()
    }
  },
  { immediate: true },
)

watch(
  () => props.mode,
  () => {
    if (props.open) {
      reset()
    }
  },
)

watch(
  () => props.defaultChapterId,
  (value) => {
    if (props.open) {
      chapterId.value = value
    }
  },
)

watch(
  () => props.defaultFolderId,
  (value) => {
    if (props.open) {
      folderId.value = value
    }
  },
)

watch(chapterId, (value) => {
  if (
    folderId.value !== null &&
    !props.folders.some(
      (folder) =>
        folder.id === folderId.value &&
        folder.chapter_id !== null &&
        Number(folder.chapter_id) === Number(value),
    )
  ) {
    folderId.value = null
  }
})

watch(folderId, (value) => {
  if (value === null) return
  const folder = props.folders.find((item) => item.id === value)
  if (folder?.chapter_id != null) {
    chapterId.value = folder.chapter_id
  }
})

function selectLanguage(value: SourceLanguage) {
  language.value = value
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = input.files?.[0] ?? null
  file.value = selected
  errorMessage.value = ''
  if (!selected) {
    return
  }
  if (!title.value.trim()) {
    title.value = selected.name.replace(/\.[^.]+$/, '')
  }
  const suffix = selected.name.split('.').pop()?.toLowerCase()
  if (suffix === 'h') {
    language.value = 'h'
  } else if (suffix === 'c') {
    language.value = 'c'
  }
}

function errorHint(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'document_name_conflict') {
      return '你的空间里已经有同名文档，请换一个标题。'
    }
    if (error.code === 'payload_too_large') {
      return '文件超过大小限制：文档导入最多 5 MB。'
    }
    if (error.code === 'unsupported_media_type') {
      return '只允许上传 .md、.c 或 .h 文件。'
    }
    return error.message
  }
  return error instanceof Error ? error.message : '保存失败，请稍后重试'
}

async function submit() {
  if (saving.value) {
    return
  }
  errorMessage.value = ''
  const cleanedTitle = title.value.trim()
  if (props.mode !== 'import' && !cleanedTitle) {
    errorMessage.value = props.mode === 'source' ? '请填写文件名。' : '请填写笔记标题。'
    return
  }
  if (props.mode === 'import' && !file.value) {
    errorMessage.value = '请先选择一个 .md、.c 或 .h 文件。'
    return
  }
  saving.value = true
  try {
    let created: DocumentDetail
    if (props.mode === 'import') {
      created = await importDocument(
        file.value!,
        cleanedTitle || null,
        chapterId.value,
        folderId.value,
      )
    } else {
      created = await createDocument({
        kind: props.mode === 'note' ? 'note' : 'source',
        title: cleanedTitle,
        chapter_id: chapterId.value,
        folder_id: folderId.value,
        ...(props.mode === 'source' ? { language: language.value } : {}),
      })
    }
    emit('created', created)
  } catch (error) {
    errorMessage.value = errorHint(error)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    :title="modeCopy.title"
    :eyebrow="modeCopy.eyebrow"
    :dismissible="!saving"
    @close="emit('close')"
  >
    <form class="document-form" @submit.prevent="submit">
      <div v-if="mode === 'import'" class="upload-zone">
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept=".md,.c,.h,text/markdown,text/plain"
          @change="onFileChange"
        />
        <button
          type="button"
          class="upload-picker"
          @click="fileInput?.click()"
        >
          <span class="upload-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path
                d="M12 16V5m0 0-4 4m4-4 4 4M5 15v3.2A1.8 1.8 0 0 0 6.8 20h10.4a1.8 1.8 0 0 0 1.8-1.8V15"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
          <span class="upload-copy">
            <strong>{{ file ? file.name : '选择文件' }}</strong>
            <span>
              {{ file ? '点击可重新选择' : '支持 Markdown、C、H，最大 5 MB' }}
            </span>
          </span>
        </button>
      </div>

      <label class="field">
        <span>{{ modeCopy.titleLabel }}</span>
        <input
          v-model="title"
          type="text"
          maxlength="200"
          :placeholder="modeCopy.placeholder"
          autocomplete="off"
        />
      </label>

      <div v-if="mode === 'source'" class="field">
        <span>源码语言</span>
        <div class="segmented" role="group" aria-label="源码语言">
          <button
            type="button"
            :class="{ active: language === 'c' }"
            @click="selectLanguage('c')"
          >
            C
          </button>
          <button
            type="button"
            :class="{ active: language === 'h' }"
            @click="selectLanguage('h')"
          >
            H
          </button>
        </div>
      </div>

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

      <label class="field">
        <span>文件夹</span>
        <select v-model="folderId" :disabled="chapterId === null">
          <option :value="null">章节根目录</option>
          <option
            v-for="folder in folderOptions"
            :key="folder.id"
            :value="folder.id"
          >
            {{ folder.path || folder.name }}
          </option>
        </select>
      </label>

      <p v-if="mode === 'note'" class="form-note">
        笔记默认私有。文件夹在当前章节内组织，不会改变章节或公开链接。
      </p>
      <p v-else-if="mode === 'source'" class="form-note">
        源码按 C/H 类型保存，后续可继续添加代码、备注和运行结果模块。
      </p>
      <p v-else class="form-note">
        Markdown 会转换为安全的富文本模块；C/H 会作为源码模块导入。
      </p>

      <p v-if="errorMessage" class="form-error" role="alert">
        {{ errorMessage }}
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
          {{ saving ? '正在保存…' : modeCopy.submit }}
        </button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.document-form {
  display: grid;
  gap: 16px;
}

.upload-zone {
  display: grid;
}

.upload-picker {
  display: flex;
  gap: 13px;
  align-items: center;
  width: 100%;
  padding: 15px;
  border: 1px dashed #cdbdf5;
  border-radius: 13px;
  color: var(--muted-strong);
  font: inherit;
  text-align: left;
  background: var(--accent-faint);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}

.upload-picker:hover {
  border-color: var(--accent);
  background: #f2edff;
}

.upload-icon {
  display: grid;
  flex: none;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 11px;
  color: var(--accent);
  background: #fff;
  box-shadow: 0 8px 18px -15px rgba(84, 54, 232, 0.7);
}

.upload-icon svg {
  width: 20px;
  height: 20px;
}

.upload-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.upload-copy strong {
  overflow: hidden;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-copy span {
  color: var(--muted);
  font-size: 10.5px;
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

.field small {
  color: #a29ab5;
  font-size: 9.5px;
  font-weight: 450;
}

.segmented {
  display: inline-flex;
  width: fit-content;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #faf8ff;
}

.segmented button {
  width: 52px;
  padding: 7px 0;
  border: 0;
  border-radius: 7px;
  color: var(--muted);
  font: inherit;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 650;
  background: transparent;
  cursor: pointer;
}

.segmented button.active {
  color: var(--accent-strong);
  background: #fff;
  box-shadow: 0 4px 12px -9px rgba(61, 42, 120, 0.5);
}

.form-note {
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
  line-height: 1.6;
  background: #fff5f5;
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
