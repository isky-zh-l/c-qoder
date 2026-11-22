<script setup lang="ts">
import 'katex/dist/katex.min.css'
import katex from 'katex'
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    latex: string
    display?: 'inline' | 'block'
  }>(),
  { display: 'inline' },
)

const root = ref<HTMLElement | null>(null)
const failed = ref(false)

function renderFormula() {
  if (!root.value) {
    return
  }
  failed.value = false
  try {
    katex.render(props.latex || '', root.value, {
      displayMode: props.display === 'block',
      throwOnError: false,
      trust: false,
      strict: 'ignore',
    })
  } catch {
    failed.value = true
    root.value.textContent = props.latex || ''
  }
}

onMounted(renderFormula)
watch(() => [props.latex, props.display], renderFormula)
</script>

<template>
  <span
    ref="root"
    class="formula-render"
    :class="[display, { failed }]"
    role="math"
    :aria-label="latex"
  ></span>
</template>

<style scoped>
.formula-render {
  display: inline-block;
  max-width: 100%;
}

.formula-render.block {
  display: block;
  overflow-x: auto;
  padding: 7px 2px;
  text-align: center;
}

.formula-render.failed {
  padding: 2px 5px;
  border: 1px solid #f0cccc;
  border-radius: 5px;
  color: #a43e3e;
  font-family: var(--font-mono);
  font-size: 0.9em;
  background: #fff5f5;
}

:deep(.katex) {
  color: #3f2f79;
  font-size: 1.05em;
}

:deep(.katex-display) {
  margin: 0;
}
</style>
