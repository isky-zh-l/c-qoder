<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormulaView from './FormulaView.vue'
import ModalShell from './ModalShell.vue'

const props = defineProps<{
  open: boolean
  initialLatex: string
}>()

const emit = defineEmits<{
  close: []
  insert: [latex: string]
}>()

const latex = ref('')
const errorMessage = ref('')

const preview = computed(() => latex.value.trim())

watch(
  () => props.open,
  (open) => {
    if (open) {
      latex.value = props.initialLatex || ''
      errorMessage.value = ''
    }
  },
  { immediate: true },
)

function submit() {
  const value = latex.value.trim()
  if (!value) {
    errorMessage.value = '请输入 LaTeX。'
    return
  }
  if (value.length > 2000) {
    errorMessage.value = '行内公式不能超过 2000 字符。'
    return
  }
  emit('insert', value)
}
</script>

<template>
  <ModalShell
    :open="open"
    title="插入行内公式"
    eyebrow="FORMULA / INLINE"
    size="small"
    @close="emit('close')"
  >
    <form class="formula-form" @submit.prevent="submit">
      <label class="field">
        <span>LaTeX</span>
        <textarea
          v-model="latex"
          rows="3"
          maxlength="2000"
          placeholder="例如：E = mc^2"
        ></textarea>
      </label>
      <div class="formula-preview">
        <span class="preview-label">预览</span>
        <FormulaView v-if="preview" :latex="preview" />
        <span v-else class="preview-empty">输入 LaTeX 后显示预览</span>
      </div>
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
        <button type="submit" class="button primary">插入公式</button>
      </div>
    </form>
  </ModalShell>
</template>

<style scoped>
.formula-form {
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

.field textarea {
  width: 100%;
  padding: 10px 11px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
  background: #fff;
  outline: none;
}

.field textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(115, 87, 255, 0.09);
}

.formula-preview {
  display: grid;
  gap: 6px;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fbf9ff;
}

.preview-label {
  color: var(--muted);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.preview-empty {
  color: #a29ab5;
  font-size: 10px;
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
}

.button {
  padding: 8px 15px;
  border-radius: 9px;
  font: inherit;
  font-size: 11px;
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
  background: linear-gradient(145deg, #846aff, #5436e8);
}
</style>
