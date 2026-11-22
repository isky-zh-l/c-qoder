<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, createChapter, updateChapter } from '../api/client'
import type { Chapter } from '../api/types'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  mode: 'create' | 'rename'
  chapter: Chapter | null
}>()

const emit = defineEmits<{
  close: []
  saved: [chapter: Chapter]
}>()

const name = ref('')
const saving = ref(false)
const errorMessage = ref('')

const title = computed(() =>
  props.mode === 'create' ? '新建章节' : '重命名章节',
)

watch(
  () => [props.open, props.chapter?.id, props.mode],
  () => {
    if (props.open) {
      name.value = props.mode === 'rename' ? props.chapter?.name || '' : ''
      errorMessage.value = ''
      saving.value = false
    }
  },
  { immediate: true },
)

async function submit() {
  const cleaned = name.value.trim()
  if (!cleaned) {
    errorMessage.value = '章节名不能为空。'
    return
  }
  if (saving.value) {
    return
  }
  saving.value = true
  errorMessage.value = ''
  try {
    const saved =
      props.mode === 'create'
        ? await createChapter(cleaned)
        : await updateChapter(props.chapter!.id, cleaned)
    emit('saved', saved)
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError
        ? error.message
        : '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <ModalShell
    :open="open"
    :title="title"
    eyebrow="CHAPTER / ORGANIZE"
    :dismissible="!saving"
    size="small"
    @close="emit('close')"
  >
    <form class="chapter-form" @submit.prevent="submit">
      <label class="field">
        <span>章节名称</span>
        <input
          v-model="name"
          type="text"
          maxlength="120"
          autocomplete="off"
          placeholder="例如：指针与内存"
        />
      </label>
      <p class="form-note">
        章节只改变目录归属，不会删除其中的文档。
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
          {{ saving ? '正在保存…' : '保存' }}
        </button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.chapter-form {
  display: grid;
  gap: 14px;
}

.field {
  display: grid;
  gap: 7px;
  color: var(--muted-strong);
  font-size: 11.5px;
  font-weight: 650;
}

.field input {
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
}

.field input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(115, 87, 255, 0.09);
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
  line-height: 1.7;
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
