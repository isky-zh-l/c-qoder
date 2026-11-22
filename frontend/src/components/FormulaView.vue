<script setup lang="ts">
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

type KatexLike = {
  render: (
    latex: string,
    element: HTMLElement,
    options: Record<string, unknown>,
  ) => void
}

let katexPromise: Promise<KatexLike | null> | null = null
let renderToken = 0

function loadKatex(): Promise<KatexLike | null> {
  if (!katexPromise) {
    katexPromise = Promise.all([
      import('katex'),
      import('katex/dist/katex.min.css'),
    ])
      .then(([module]) => module.default as unknown as KatexLike)
      .catch(() => null)
  }
  return katexPromise
}

async function renderFormula() {
  const element = root.value
  if (!element) {
    return
  }
  const token = ++renderToken
  failed.value = false
  // 先显示原文，KaTeX 到达后再替换，避免整块空白等待脚本。
  element.textContent = props.latex || ''
  const katex = await loadKatex()
  const target = root.value
  if (token !== renderToken || !target) {
    return
  }
  if (!katex) {
    failed.value = true
    return
  }
  try {
    katex.render(props.latex || '', target, {      displayMode: props.display === 'block',
      throwOnError: false,
      trust: false,
      strict: 'ignore',
    })
  } catch {
    failed.value = true
    target.textContent = props.latex || ''
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
