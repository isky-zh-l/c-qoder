<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EditorModuleType } from '../utils/editorModel'

const props = withDefaults(
  defineProps<{
    mode?: 'note' | 'source'
  }>(),
  { mode: 'note' },
)

const emit = defineEmits<{
  format: [kind: string]
  highlight: [tone: string]
  link: []
  'inline-formula': []
  insert: [type: EditorModuleType]
}>()

const textTools = [
  { kind: 'bullet', symbol: '·', label: '圆点' },
  { kind: 'bold', symbol: 'B', label: '加粗' },
  { kind: 'italic', symbol: 'I', label: '斜体' },
  { kind: 'underline', symbol: 'U', label: '下划线' },
  { kind: 'strike', symbol: 'S', label: '删除线' },
  { kind: 'highlight', symbol: '◧', label: '背景色' },
  { kind: 'code', symbol: '⌘', label: '行内代码' },
  { kind: 'link', symbol: '↗', label: '超链接' },
]

const noteModules: Array<{
  type: EditorModuleType
  symbol: string
  label: string
  title: string
}> = [
  { type: 'paragraph', symbol: '¶', label: '段落', title: '插入段落' },
  { type: 'heading1', symbol: 'H1', label: '大标题', title: '插入大标题' },
  { type: 'heading2', symbol: 'H2', label: '中标题', title: '插入中标题' },
  { type: 'heading3', symbol: 'H3', label: '小标题', title: '插入小标题' },
  { type: 'quote', symbol: '❝', label: '紫色引用框', title: '插入紫色引用框' },
  { type: 'divider', symbol: '―', label: '分隔线', title: '插入分隔线' },
  { type: 'bullet_list', symbol: '•', label: '圆点列表', title: '插入圆点列表' },
  { type: 'ordered_list', symbol: '1.', label: '编号列表', title: '插入编号列表' },
  { type: 'todo_list', symbol: '☑', label: '待办列表', title: '插入待办列表' },
  { type: 'table', symbol: '▦', label: '表格', title: '插入表格' },
  { type: 'code', symbol: '</>', label: '代码块', title: '插入代码模块' },
  { type: 'image', symbol: '▧', label: '图片', title: '插入图片模块' },
]

const sourceModules: typeof noteModules = [
  { type: 'code', symbol: '</>', label: '代码块', title: '插入代码块' },
  { type: 'remark', symbol: '✎', label: '备注', title: '插入备注' },
  { type: 'result', symbol: '›_', label: '运行结果', title: '插入运行结果' },
  { type: 'image', symbol: '▧', label: '图片', title: '插入图片模块' },
]

const insertModules = computed(() =>
  props.mode === 'source' ? sourceModules : noteModules,
)

const formulaTools = computed(() =>
  props.mode === 'source'
    ? [{ kind: 'inline-formula', symbol: '$x$', label: '行内公式' }]
    : [
        { kind: 'inline-formula', symbol: '$x$', label: '行内公式' },
        { kind: 'block-formula', symbol: 'ƒx', label: '块级公式' },
      ],
)

const highlightTones = [
  { tone: 'yellow', label: '淡黄' },
  { tone: 'purple', label: '淡紫' },
  { tone: 'mint', label: '薄荷绿' },
  { tone: 'pink', label: '浅粉' },
]

const highlightOpen = ref(false)

const TOOLBAR_KEY = 'cq.editor.toolbarCollapsed'
const collapsed = ref(readToolbarCollapsed())

function readToolbarCollapsed(): boolean {
  try {
    const stored = window.localStorage.getItem(TOOLBAR_KEY)
    if (stored === null) {
      return window.innerWidth <= 960
    }
    return stored === '1'
  } catch {
    return window.innerWidth <= 960
  }
}

watch(collapsed, (value) => {
  try {
    window.localStorage.setItem(TOOLBAR_KEY, value ? '1' : '0')
  } catch {
    // 隐私模式下忽略
  }
})

function runTextTool(kind: string) {
  if (kind === 'highlight') {
    highlightOpen.value = !highlightOpen.value
    return
  }
  highlightOpen.value = false
  if (kind === 'link') {
    emit('link')
    return
  }
  if (kind === 'inline-formula') {
    emit('inline-formula')
    return
  }
  emit('format', kind)
}

function chooseHighlight(tone: string) {
  highlightOpen.value = false
  emit('highlight', tone)
}

function runFormulaTool(kind: string) {
  if (kind === 'inline-formula') {
    emit('inline-formula')
    return
  }
  emit('insert', 'formula')
}

function startModuleDrag(event: DragEvent, type: EditorModuleType) {
  if (!event.dataTransfer) {
    return
  }
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('application/x-cqoder-module', type)
  event.dataTransfer.setData('text/plain', type)
}
</script>

<template>
  <aside class="editor-toolbar" :class="{ 'is-collapsed': collapsed }" aria-label="编辑工具">
    <div class="toolbar-head">
      <h2>编辑工具</h2>
      <button
        type="button"
        class="toolbar-toggle"
        :aria-expanded="!collapsed"
        @click="collapsed = !collapsed"
      >
        {{ collapsed ? '展开' : '收起' }}
        <span class="toolbar-chevron" :class="{ open: !collapsed }" aria-hidden="true">
          <svg viewBox="0 0 16 16" fill="none">
            <path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </button>
    </div>

    <div class="tool-body">
    <section class="tool-group">
      <h3>文字样式</h3>
      <div class="tool-grid">
        <button
          v-for="tool in textTools"
          :key="tool.kind"
          type="button"
          class="tool-button"
          :class="`tool-${tool.kind}`"
          :aria-label="tool.label"
          :aria-expanded="tool.kind === 'highlight' ? highlightOpen : undefined"
          @mousedown.prevent
          @click="runTextTool(tool.kind)"
        >
          <span class="tool-symbol" aria-hidden="true">{{ tool.symbol }}</span>
          <span class="tool-label">{{ tool.label }}</span>
        </button>
      </div>

      <div v-if="highlightOpen" class="highlight-popover" role="group" aria-label="背景色">
        <button
          v-for="color in highlightTones"
          :key="color.tone"
          type="button"
          class="highlight-choice"
          @mousedown.prevent
          @click="chooseHighlight(color.tone)"
        >
          <span class="highlight-swatch" :class="`tone-${color.tone}`"></span>
          {{ color.label }}
        </button>
      </div>
    </section>

    <section class="tool-group">
      <h3>{{ mode === 'source' ? '源码模块' : '插入模块' }}</h3>
      <div class="tool-grid">
        <button
          v-for="module in insertModules"
          :key="module.type"
          type="button"
          class="tool-button module-button"
          :title="`${module.title}；也可拖入文档`"
          :aria-label="module.title"
          draggable="true"
          @dragstart="startModuleDrag($event, module.type)"
          @click="emit('insert', module.type)"
        >
          <span class="tool-symbol" aria-hidden="true">{{ module.symbol }}</span>
          <span class="tool-label">{{ module.label }}</span>
        </button>
      </div>
    </section>

    <section class="tool-group">
      <h3>公式</h3>
      <div class="tool-grid">
        <button
          v-for="tool in formulaTools"
          :key="tool.kind"
          type="button"
          class="tool-button"
          @mousedown.prevent
          @click="runFormulaTool(tool.kind)"
        >
          <span class="tool-symbol" aria-hidden="true">{{ tool.symbol }}</span>
          <span class="tool-label">{{ tool.label }}</span>
        </button>
      </div>
    </section>

    <p class="toolbar-hint">
      {{ mode === 'source'
        ? '在备注中选中文字即可设置样式。代码块按顺序组成源码，运行结果可以直接粘贴终端输出。'
        : '选中文字即可设置样式。拖住模块左上角可以换位，代码块也可以从这里拖入正文。' }}
    </p>
    </div>
  </aside>
</template>

<style scoped>
.editor-toolbar {
  position: sticky;
  top: calc(80px + env(safe-area-inset-top));
  display: grid;
  gap: 8px;
  align-self: start;
  width: 238px;
  max-height: calc(100dvh - 96px - env(safe-area-inset-top));
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.editor-toolbar h2 {
  margin: 0 0 2px;
  font-size: 14px;
}

.toolbar-head {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.toolbar-head h2 {
  margin: 0;
}

.toolbar-toggle {
  display: none;
  gap: 4px;
  align-items: center;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  background: #fbfaff;
  cursor: pointer;
}

.toolbar-chevron {
  display: grid;
  width: 14px;
  height: 14px;
  place-items: center;
  transition: transform 0.2s ease;
}

.toolbar-chevron svg {
  width: 14px;
  height: 14px;
}

.toolbar-chevron.open {
  transform: rotate(180deg);
}

.tool-body {
  display: grid;
  gap: 8px;
}

.tool-group {
  display: grid;
  gap: 4px;
}

.tool-group h3 {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  font-weight: 650;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
}

.tool-button,
.highlight-choice {
  display: flex;
  gap: 5px;
  align-items: center;
  min-height: 35px;
  padding: 4px 5px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--text);
  font: inherit;
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
  background: #fbfaff;
  cursor: pointer;
}

.tool-button:hover,
.highlight-choice:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

.tool-button.tool-bold {
  font-weight: 800;
}

.tool-button.tool-italic {
  font-style: italic;
}

.tool-button.tool-underline {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.tool-button.tool-strike {
  text-decoration: line-through;
}

.tool-button.tool-code {
  font-family: var(--font-mono);
}

.tool-button.tool-inline-formula .tool-symbol {
  font-size: 10px;
}

.tool-symbol {
  display: grid;
  place-items: center;
  flex: 0 0 23px;
  width: 23px;
  height: 23px;
  border-radius: 5px;
  color: var(--accent);
  font: 700 13px/1 var(--font-mono);
  background: var(--accent-soft);
}

.module-button {
  cursor: grab;
}

.module-button:active {
  cursor: grabbing;
}

.highlight-popover {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--surface-soft);
}

.highlight-choice {
  min-height: 31px;
  padding: 4px 6px;
  font-size: 11px;
}

.highlight-swatch {
  flex: 0 0 16px;
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.highlight-swatch.tone-yellow {
  background: #fff3a3;
}

.highlight-swatch.tone-purple {
  background: #eee4ff;
}

.highlight-swatch.tone-mint {
  background: #d8f5df;
}

.highlight-swatch.tone-pink {
  background: #ffe0ef;
}

.toolbar-hint {
  margin: 3px 0 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 960px) {
  .editor-toolbar {
    position: static;
    order: -1;
    display: grid;
    gap: 10px;
    width: 100%;
    max-height: none;
    padding: 9px;
    overflow: visible;
    border-radius: 12px;
    box-shadow: 0 12px 30px -24px rgba(33, 27, 51, 0.55);
  }

  .toolbar-hint {
    display: none;
  }

  .toolbar-toggle {
    display: inline-flex;
  }

  .tool-body {
    max-height: 1400px;
    overflow: hidden;
    transition:
      max-height 0.24s ease,
      opacity 0.18s ease;
  }

  .editor-toolbar.is-collapsed {
    position: sticky;
    top: calc(64px + env(safe-area-inset-top));
    z-index: 30;
  }

  .editor-toolbar.is-collapsed .tool-body {
    max-height: 0;
    opacity: 0;
  }

  .tool-group {
    display: grid;
    gap: 5px;
    padding: 0;
    border: 0;
  }

  .tool-group h3 {
    font-size: 10px;
  }

  .tool-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 4px;
    padding: 0;
    overflow: visible;
  }

  .tool-button {
    min-height: 36px;
    padding: 4px 6px;
    gap: 4px;
    font-size: 11px;
  }

  .tool-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tool-symbol {
    flex-basis: 22px;
    width: 22px;
    height: 22px;
    font-size: 11px;
  }

  .highlight-popover {
    position: static;
    width: 100%;
    margin-top: 2px;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    box-shadow: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .tool-button,
  .highlight-choice,
  .tool-body,
  .toolbar-chevron {
    transition: none;
  }
}
</style>