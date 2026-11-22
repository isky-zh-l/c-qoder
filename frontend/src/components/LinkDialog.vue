<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  initialLabel: string
}>()

const emit = defineEmits<{
  close: []
  insert: [label: string, url: string]
}>()

const label = ref('')
const url = ref('')
const errorMessage = ref('')

const canSubmit = computed(
  () => label.value.trim().length > 0 && url.value.trim().length > 0,
)

watch(
  () => props.open,
  (open) => {
    if (open) {
      label.value = props.initialLabel
      url.value = ''
      errorMessage.value = ''
    }
  },
  { immediate: true },
)

function safeUrl(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed || /[\u0000-\u001f]/.test(trimmed)) {
    return false
  }
  if (/^(https?:\/\/|mailto:)/i.test(trimmed)) {
    return true
  }
  return trimmed.startsWith('/') && !trimmed.startsWith('//')
}

function submit() {
  if (!canSubmit.value) {
    errorMessage.value = '请填写标题和地址。'
    return
  }
  if (!safeUrl(url.value)) {
    errorMessage.value = '地址只允许 http、https、mailto 或站内 / 路径。'
    return
  }
  emit('insert', label.value.trim(), url.value.trim())
}
</script>

<template>
  <ModalShell
    :open="open"
    title="插入链接"
    eyebrow="LINK / INLINE"
    size="small"
    @close="emit('close')"
  >
    <form class="link-form" @submit.prevent="submit">
      <label class="field">
        <span>标题</span>
        <input
          v-model="label"
          type="text"
          maxlength="300"
          autocomplete="off"
          placeholder="链接显示文字"
        />
      </label>
      <label class="field">
        <span>地址</span>
        <input
          v-model="url"
          type="text"
          maxlength="2048"
          autocomplete="off"
          placeholder="https://example.com"
        />
      </label>
      <p v-if="errorMessage" class="form-error" role="alert">
        {{ errorMessage }}
      </p>
      <div class="form-actions">
        <button
          type="button"
          class="button secondary"
          @click="emit('close')"
        >
          取消
        </button>
        <button type="submit" class="button primary" :disabled="!canSubmit">
          插入链接
        </button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.link-form {
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
  height: 41px;
  padding: 0 12px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  color: var(--text);
  font: inherit;
  font-size: 12.5px;
  font-weight: 450;
  background: #fff;
  outline: none;
}

.field input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(115, 87, 255, 0.09);
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

.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 2px;
}

.button {
  padding: 8px 15px;
  border-radius: 9px;
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  cursor: pointer;
}

.button:disabled {
  opacity: 0.5;
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
}
</style>
