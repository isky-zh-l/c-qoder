<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { highlightC } from '../utils/cHighlight'

const props = defineProps<{
  modelValue: string
  language?: 'c' | 'h' | 'text' | string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  focus: []
}>()

const highlightLayer = ref<HTMLElement | null>(null)
const textarea = ref<HTMLTextAreaElement | null>(null)
const composing = ref(false)

const highlighted = computed(() => highlightC(props.modelValue))
const editorHeight = computed(() => {
  const lines = Math.max(1, props.modelValue.split('\n').length)
  return Math.min(600, Math.max(126, lines * 22 + 36))
})

function syncScroll() {
  if (!textarea.value || !highlightLayer.value) {
    return
  }
  highlightLayer.value.scrollTop = textarea.value.scrollTop
  highlightLayer.value.scrollLeft = textarea.value.scrollLeft
}

function onInput(event: Event) {
  const value = (event.target as HTMLTextAreaElement).value
  emit('update:modelValue', value)
  nextTick(syncScroll)
}

function onCompositionStart() {
  composing.value = true
}

function onCompositionEnd(event: CompositionEvent) {
  composing.value = false
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  nextTick(syncScroll)
}

watch(
  () => props.modelValue,
  async (value) => {
    if (textarea.value && textarea.value.value !== value) {
      textarea.value.value = value
    }
    await nextTick()
    syncScroll()
  },
)

defineExpose({
  focus() {
    textarea.value?.focus()
  },
  textarea,
})
</script>

<template>
  <div
    class="code-editor"
    :class="[
      `language-${language || 'text'}`,
      { composing },
    ]"
    :style="{ height: `${editorHeight}px` }"
  >
    <pre
      ref="highlightLayer"
      class="code-highlight"
      aria-hidden="true"
    ><code v-html="highlighted"></code></pre>
    <textarea
      ref="textarea"
      class="code-input"
      :value="modelValue"
      spellcheck="false"
      autocapitalize="off"
      autocorrect="off"
      wrap="off"
      :aria-label="`${language || 'text'} 代码编辑器`"
      @input="onInput"
      @scroll="syncScroll"
      @focus="emit('focus')"
      @compositionstart="onCompositionStart"
      @compositionend="onCompositionEnd"
    ></textarea>
  </div>
</template>

<style scoped>
.code-editor {
  position: relative;
  width: 100%;
  min-height: 126px;
  overflow: hidden;
  border: 1px solid #2d2743;
  border-radius: 11px;
  background: #1e1e2e;
}

.code-highlight,
.code-input {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  padding: 16px 18px 18px;
  border: 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.75;
  tab-size: 2;
  white-space: pre;
}

.code-highlight {
  margin: 0;
  overflow: hidden;
  color: #d4d4d4;
  pointer-events: none;
}

.code-highlight code {
  font: inherit;
  white-space: inherit;
}

.code-input {
  overflow: auto;
  color: transparent;
  caret-color: #f3eeff;
  resize: none;
  background: transparent;
  outline: none;
  -webkit-text-fill-color: transparent;
}

.code-input::selection {
  background: rgba(115, 87, 255, 0.38);
}

.code-editor.composing .code-highlight {
  opacity: 0;
}

.code-editor.composing .code-input {
  color: #f3eeff;
  -webkit-text-fill-color: #f3eeff;
}

.code-editor:focus-within {
  border-color: #5f4ca8;
  box-shadow: 0 0 0 3px rgba(115, 87, 255, 0.12);
}

@media (max-width: 640px) {
  .code-highlight,
  .code-input {
    padding: 13px 14px 15px;
    font-size: 11.5px;
  }
}
</style>
