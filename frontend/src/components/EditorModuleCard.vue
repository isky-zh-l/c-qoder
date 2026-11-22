<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { assetFileUrl } from '../api/client'
import CodeEditor from './CodeEditor.vue'
import FormulaView from './FormulaView.vue'
import type { EditorModule } from '../utils/editorModel'
import { isTextModule, moduleLabel } from '../utils/editorModel'

const props = withDefaults(
  defineProps<{
    module: EditorModule
    index: number
    total: number
    active: boolean
    fixedLanguage?: boolean
  }>(),
  { fixedLanguage: false },
)

const emit = defineEmits<{
  activate: [module: EditorModule]
  focus: [module: EditorModule, element: HTMLTextAreaElement]
  'drag-start': [event: PointerEvent, module: EditorModule]
  'move-up': [module: EditorModule]
  'move-down': [module: EditorModule]
  duplicate: [module: EditorModule]
  delete: [module: EditorModule]
  history: []
  'upload-image': [module: EditorModule, file: File]
}>()

const textarea = ref<HTMLTextAreaElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const textModule = computed(() => isTextModule(props.module))
const label = computed(() => moduleLabel(props.module.type))
const placeholder = computed(() => {
  if (props.module.type === 'heading1') return '大标题'
  if (props.module.type === 'heading2') return '中标题'
  if (props.module.type === 'heading3') return '小标题'
  if (props.module.type === 'quote') return '引用内容'
  if (props.module.type === 'remark') return '备注（支持 Markdown 文字样式）'
  if (props.module.type === 'bullet_list') return '- 第一项\n- 第二项'
  if (props.module.type === 'ordered_list') return '1. 第一项\n2. 第二项'
  if (props.module.type === 'todo_list') return '- [ ] 待办\n- [x] 已完成'
  return '开始写 Markdown…'
})

const textareaStyleClass = computed(() => {
  if (props.module.type === 'heading1') return 'text-h1'
  if (props.module.type === 'heading2') return 'text-h2'
  if (props.module.type === 'heading3') return 'text-h3'
  if (props.module.type === 'quote') return 'text-quote'
  if (props.module.type === 'remark') {
    return props.module.remarkModule === 'bullet_list'
      ? 'text-list'
      : 'text-paragraph'
  }
  if (props.module.type === 'bullet_list') return 'text-list'
  if (props.module.type === 'ordered_list') return 'text-list'
  if (props.module.type === 'todo_list') return 'text-list'
  return 'text-paragraph'
})

function autosize() {
  const element = textarea.value
  if (!element) {
    return
  }
  element.style.height = 'auto'
  element.style.height = `${Math.max(38, element.scrollHeight)}px`
}

function onFocus(event: FocusEvent) {
  const element = event.currentTarget as HTMLTextAreaElement
  emit('activate', props.module)
  emit('focus', props.module, element)
}

function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    emit('upload-image', props.module, file)
  }
  input.value = ''
}

function addRow() {
  emit('history')
  const width = props.module.headers.length || 1
  props.module.rows = [
    ...props.module.rows,
    Array.from({ length: width }, () => ''),
  ]
}

function addColumn() {
  emit('history')
  props.module.headers = [...props.module.headers, '']
  props.module.rows = props.module.rows.map((row) => [...row, ''])
}

function removeRow(index: number) {
  emit('history')
  if (props.module.rows.length <= 1) {
    if (props.module.rows[0]) {
      props.module.rows[0] = props.module.rows[0].map(() => '')
    }
    return
  }
  props.module.rows = props.module.rows.filter(
    (_row, rowIndex) => rowIndex !== index,
  )
}

function removeColumn(index: number) {
  if (props.module.headers.length <= 1) {
    return
  }
  emit('history')
  props.module.headers = props.module.headers.filter(
    (_cell, cellIndex) => cellIndex !== index,
  )
  props.module.rows = props.module.rows.map((row) =>
    row.filter((_cell, cellIndex) => cellIndex !== index),
  )
}

function focusTextarea() {
  textarea.value?.focus()
}

defineExpose({ focusTextarea })

watch(
  () => [props.module.markdown, props.module.type],
  () => nextTick(autosize),
)

onMounted(autosize)
</script>

<template>
  <article
    class="module-card"
    :class="{
      active,
      [`type-${module.type}`]: true,
    }"
    :data-module-key="module.key"
    @click="emit('activate', module)"
  >
    <header class="module-head">
      <button
        type="button"
        class="module-drag"
        aria-label="拖动模块"
        title="拖动模块"
        @pointerdown.stop.prevent="emit('drag-start', $event, module)"
      >
        <svg viewBox="0 0 12 18" fill="currentColor" aria-hidden="true">
          <circle cx="3.5" cy="4" r="1" />
          <circle cx="8.5" cy="4" r="1" />
          <circle cx="3.5" cy="9" r="1" />
          <circle cx="8.5" cy="9" r="1" />
          <circle cx="3.5" cy="14" r="1" />
          <circle cx="8.5" cy="14" r="1" />
        </svg>
      </button>
      <span class="module-type">{{ label }}</span>
      <span v-if="module.id !== null" class="module-id">#{{ module.id }}</span>
      <div class="module-tools">
        <button
          type="button"
          :disabled="index === 0"
          aria-label="模块上移"
          title="上移"
          @click.stop="emit('move-up', module)"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="m4 9.5 4-4 4 4"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          :disabled="index === total - 1"
          aria-label="模块下移"
          title="下移"
          @click.stop="emit('move-down', module)"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="m4 6.5 4 4 4-4"
              stroke="currentColor"
              stroke-width="1.4"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          aria-label="复制模块"
          title="复制"
          @click.stop="emit('duplicate', module)"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <rect
              x="5"
              y="5"
              width="8"
              height="8"
              rx="1.5"
              stroke="currentColor"
              stroke-width="1.3"
            />
            <path
              d="M3.5 10.5H3A1.5 1.5 0 0 1 1.5 9V3A1.5 1.5 0 0 1 3 1.5h6A1.5 1.5 0 0 1 10.5 3v.5"
              stroke="currentColor"
              stroke-width="1.3"
            />
          </svg>
        </button>
        <button
          type="button"
          class="delete-tool"
          aria-label="删除模块"
          title="删除"
          @click.stop="emit('delete', module)"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path
              d="M4 5h8m-6.5 0V3.8h3V5m-4.2 0 .7 8h4.4l.7-8"
              stroke="currentColor"
              stroke-width="1.3"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </div>
    </header>

    <div class="module-body">
      <template v-if="textModule">
        <textarea
          ref="textarea"
          v-model="module.markdown"
          class="module-textarea"
          :class="textareaStyleClass"
          :placeholder="placeholder"
          rows="1"
          spellcheck="false"
          @focus="onFocus"
          @input="autosize"
          @click="emit('activate', module)"
        ></textarea>
        <p
          v-if="module.type === 'bullet_list' || module.type === 'ordered_list' || module.type === 'todo_list'"
          class="module-tip"
        >
          {{
            module.type === 'todo_list'
              ? '每行使用 - [ ] 或 - [x]，渲染时显示复选框。'
              : '每行一项，保留 Markdown 列表标记。'
          }}
        </p>
      </template>

      <template v-else-if="module.type === 'divider'">
        <div class="divider-preview">
          <span aria-hidden="true"></span>
          <small>分隔线</small>
          <span aria-hidden="true"></span>
        </div>
      </template>

      <template v-else-if="module.type === 'table'">
        <div class="table-editor-wrap">
          <table class="table-editor">
            <thead>
              <tr>
                <th
                  v-for="(cell, cellIndex) in module.headers"
                  :key="cellIndex"
                  class="head-cell"
                >
                  <input
                    v-model="module.headers[cellIndex]"
                    type="text"
                    :aria-label="`表头 ${cellIndex + 1}`"
                    placeholder="表头"
                  />
                  <button
                    type="button"
                    class="column-remove"
                    :disabled="module.headers.length <= 1"
                    aria-label="删除列"
                    title="删除列"
                    @click.stop="removeColumn(cellIndex)"
                  >
                    ×
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in module.rows" :key="rowIndex">
                <td v-for="(cell, cellIndex) in row" :key="cellIndex">
                  <input
                    v-model="module.rows[rowIndex][cellIndex]"
                    type="text"
                    :aria-label="`第 ${rowIndex + 1} 行第 ${cellIndex + 1} 列`"
                    placeholder="单元格"
                  />
                  <button
                    v-if="cellIndex === row.length - 1"
                    type="button"
                    class="row-remove"
                    aria-label="删除行"
                    title="删除行"
                    @click.stop="removeRow(rowIndex)"
                  >
                    ×
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="table-actions">
            <button type="button" @click.stop="addRow">增加一行</button>
            <button type="button" @click.stop="addColumn">增加一列</button>
          </div>
        </div>
      </template>

      <template v-else-if="module.type === 'code'">
        <div class="code-module">
          <div class="code-editor-head">
            <select
              v-if="!fixedLanguage"
              v-model="module.language"
              aria-label="代码语言"
            >
              <option value="c">C</option>
              <option value="h">H</option>
              <option value="text">Text</option>
            </select>
            <span v-else class="fixed-language">
              {{ (module.language || 'text').toUpperCase() }}
            </span>
            <span>VS Code 风格高亮 · 保留空行、缩进与滚动</span>
          </div>
          <CodeEditor
            :model-value="module.text"
            :language="module.language"
            @update:model-value="module.text = $event"
            @focus="emit('activate', module)"
          />
        </div>
      </template>

      <template v-else-if="module.type === 'result'">
        <div class="result-editor">
          <p class="result-label">运行结果 · 逐字保留</p>
          <textarea
            v-model="module.text"
            class="result-textarea"
            spellcheck="false"
            placeholder="粘贴终端输出…"
            @focus="emit('activate', module)"
          ></textarea>
        </div>
      </template>

      <template v-else-if="module.type === 'image'">
        <div class="image-editor">
          <div v-if="module.assetId !== null" class="image-preview">
            <img :src="assetFileUrl(module.assetId)" :alt="module.alt || '图片'" />
            <div class="image-actions">
              <span>{{ module.assetName || `资产 #${module.assetId}` }}</span>
              <button type="button" @click.stop="fileInput?.click()">
                更换图片
              </button>
            </div>
          </div>
          <button
            v-else
            type="button"
            class="image-upload"
            @click.stop="fileInput?.click()"
          >
            上传当前账号的图片
            <small>PNG / JPEG / WebP / GIF，最大 10 MB</small>
          </button>
          <input
            ref="fileInput"
            class="sr-only"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            @change="selectFile"
          />
          <label class="image-field">
            <span>替代文本</span>
            <input v-model="module.alt" type="text" maxlength="1000" />
          </label>
          <label class="image-field">
            <span>图片说明</span>
            <input v-model="module.caption" type="text" maxlength="2000" />
          </label>
        </div>
      </template>

      <template v-else-if="module.type === 'formula'">
        <div class="formula-editor">
          <textarea
            v-model="module.latex"
            rows="3"
            maxlength="4000"
            placeholder="例如：\int_0^1 x^2\,dx"
          ></textarea>
          <div class="formula-preview">
            <FormulaView :latex="module.latex || ''" display="block" />
          </div>
        </div>
      </template>
    </div>
  </article>
</template>

<style scoped>
.module-card {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 38px -36px rgba(61, 42, 120, 0.55);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    opacity 0.18s ease,
    transform 0.18s ease;
}

.module-card:hover {
  border-color: #ddd3f5;
}

.module-card.active {
  border-color: #cdbdf5;
  box-shadow: 0 18px 44px -34px rgba(84, 54, 232, 0.5);
}

.module-head {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 7px 9px 6px;
  border-bottom: 1px solid rgba(231, 225, 247, 0.7);
}

.module-drag {
  display: grid;
  flex: none;
  width: 20px;
  height: 25px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #c2b5e4;
  background: transparent;
  cursor: grab;
  touch-action: none;
}

.module-drag:hover {
  color: var(--accent);
  background: var(--accent-faint);
}

.module-drag svg {
  width: 10px;
  height: 16px;
}

.module-type {
  color: var(--muted-strong);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.module-id {
  color: #b2a9c3;
  font-family: var(--font-mono);
  font-size: 8.5px;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.module-card:hover .module-id,
.module-card:focus-within .module-id {
  opacity: 1;
}

.module-tools {
  display: flex;
  gap: 1px;
  align-items: center;
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.module-card:hover .module-tools,
.module-card:focus-within .module-tools,
.module-card.active .module-tools {
  opacity: 1;
}

.module-tools button {
  display: grid;
  width: 24px;
  height: 23px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 5px;
  color: #9e95b0;
  background: transparent;
  cursor: pointer;
}

.module-tools button:hover:not(:disabled) {
  border-color: var(--border);
  color: var(--accent-strong);
  background: #fff;
}

.module-tools button:disabled {
  opacity: 0.3;
  cursor: default;
}

.module-tools button svg {
  width: 12px;
  height: 12px;
}

.module-tools button.delete-tool:hover {
  border-color: #eccaca;
  color: #b44d4d;
  background: #fff5f5;
}

.module-body {
  padding: 13px 15px 15px;
}

.module-textarea {
  width: 100%;
  min-height: 38px;
  padding: 0;
  overflow: hidden;
  border: 0;
  color: #302947;
  font: inherit;
  line-height: 1.85;
  resize: none;
  background: transparent;
  outline: none;
}

.module-textarea::placeholder {
  color: #b7afc7;
}

.text-paragraph {
  font-size: 14.5px;
}

.text-h1 {
  font-size: 29px;
  font-weight: 760;
  letter-spacing: -0.035em;
  line-height: 1.28;
}

.text-h2 {
  font-size: 23px;
  font-weight: 730;
  letter-spacing: -0.025em;
  line-height: 1.35;
}

.text-h3 {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.45;
}

.text-quote {
  padding: 3px 0 3px 13px;
  border-left: 3px solid #9d7cf3;
  color: #574b75;
}

.text-list {
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.8;
}

.module-tip {
  margin-top: 5px;
  color: #9f97b1;
  font-size: 9px;
  line-height: 1.5;
}

.divider-preview {
  display: flex;
  gap: 11px;
  align-items: center;
  padding: 6px 0;
  color: var(--muted);
  font-size: 9px;
}

.divider-preview span {
  flex: 1;
  height: 1px;
  background: var(--border-strong);
}

.table-editor-wrap {
  overflow-x: auto;
}

.table-editor {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.table-editor th,
.table-editor td {
  position: relative;
  min-width: 90px;
  padding: 0;
  border: 1px solid var(--border);
}

.table-editor input {
  width: 100%;
  height: 36px;
  padding: 0 9px;
  border: 0;
  color: var(--text);
  font: inherit;
  background: transparent;
  outline: none;
}

.table-editor th {
  background: #faf8ff;
}

.table-editor th input {
  padding-right: 21px;
  color: var(--muted-strong);
  font-weight: 650;
}

.table-editor td input {
  padding-right: 21px;
}

.table-editor input:focus {
  background: #fff;
  box-shadow: inset 0 0 0 2px rgba(115, 87, 255, 0.25);
}

.column-remove,
.row-remove {
  position: absolute;
  top: 50%;
  right: 3px;
  display: grid;
  width: 17px;
  height: 17px;
  place-items: center;
  border: 0;
  border-radius: 4px;
  color: #b5aac8;
  font-size: 12px;
  background: transparent;
  cursor: pointer;
  transform: translateY(-50%);
}

.column-remove:hover:not(:disabled),
.row-remove:hover {
  color: #b44d4d;
  background: #fff0f0;
}

.column-remove:disabled {
  opacity: 0.3;
  cursor: default;
}

.table-actions {
  display: flex;
  gap: 7px;
  margin-top: 8px;
}

.table-actions button {
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 9.5px;
  background: #fff;
  cursor: pointer;
}

.table-actions button:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.code-module {
  display: grid;
  gap: 8px;
}

.code-editor-head {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 26px;
}

.code-editor-head select {
  height: 25px;
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--muted-strong);
  font: inherit;
  font-family: var(--font-mono);
  font-size: 9.5px;
  background: #fff;
}

.fixed-language {
  padding: 3px 7px;
  border: 1px solid #d8ccff;
  border-radius: 5px;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  background: var(--accent-soft);
}

.code-editor-head span {
  color: #887ba9;
  font-size: 8.5px;
}

.code-editor-head .fixed-language {
  color: var(--accent-strong);
  font-size: 9px;
}

.result-editor {
  display: grid;
  gap: 7px;
  padding: 12px 13px;
  border: 1px solid var(--result-border);
  border-radius: 11px;
  background: var(--result-bg);
}

.result-label {
  color: #3c7a58;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.result-textarea {
  width: 100%;
  min-height: 108px;
  padding: 10px 11px;
  border: 1px solid rgba(99, 164, 124, 0.18);
  border-radius: 7px;
  color: #28583f;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.7;
  resize: vertical;
  background: rgba(255, 255, 255, 0.46);
  outline: none;
  white-space: pre-wrap;
}

.result-textarea:focus {
  border-color: #8ac9a2;
  box-shadow: 0 0 0 3px rgba(111, 191, 143, 0.1);
}

.image-editor {
  display: grid;
  gap: 11px;
}

.image-upload {
  display: grid;
  gap: 4px;
  padding: 22px;
  border: 1px dashed #cdbdf5;
  border-radius: 10px;
  color: var(--accent-strong);
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  text-align: center;
  background: var(--accent-faint);
  cursor: pointer;
}

.image-upload small {
  color: var(--muted);
  font-size: 9px;
  font-weight: 450;
}

.image-preview img {
  width: 100%;
  max-height: 360px;
  border-radius: 9px;
  object-fit: contain;
  background: #faf8ff;
}

.image-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 6px;
  color: var(--muted);
  font-size: 9.5px;
}

.image-actions button {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 9px;
  background: #fff;
  cursor: pointer;
}

.image-field {
  display: grid;
  gap: 5px;
  color: var(--muted-strong);
  font-size: 10px;
  font-weight: 650;
}

.image-field input {
  height: 34px;
  padding: 0 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--text);
  font: inherit;
  font-size: 11px;
  background: #fff;
  outline: none;
}

.image-field input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(115, 87, 255, 0.08);
}

.formula-editor {
  display: grid;
  gap: 8px;
}

.formula-editor textarea {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: #3f2f79;
  font-family: var(--font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  resize: vertical;
  background: #fbf9ff;
  outline: none;
}

.formula-editor textarea:focus {
  border-color: var(--accent);
}

.formula-preview {
  min-height: 48px;
  padding: 8px 10px;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
}

@media (max-width: 720px) {
  .module-tools {
    opacity: 1;
  }

  .module-body {
    padding: 11px 12px 13px;
  }

  .text-h1 {
    font-size: 24px;
  }

  .text-h2 {
    font-size: 20px;
  }

  .text-h3 {
    font-size: 16.5px;
  }

  .table-editor {
    font-size: 10.5px;
  }
}
</style>
