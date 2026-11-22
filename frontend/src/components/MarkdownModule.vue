<script setup lang="ts">
import { computed } from 'vue'
import { InlineMarkdown } from './RichTextNode'

const props = defineProps<{
  content: Record<string, unknown>
}>()

const moduleName = computed(() => String(props.content.module || 'paragraph'))
const markdown = computed(() =>
  typeof props.content.markdown === 'string'
    ? props.content.markdown
    : '',
)

const paragraphs = computed(() => {
  const source = markdown.value.trim()
  return source ? source.split(/\n{2,}/) : ['']
})

const quoteParagraphs = computed(() => {
  const lines = markdown.value
    .split('\n')
    .map((line) => line.replace(/^\s*>\s?/, ''))
  return lines.join('\n').split(/\n{2,}/)
})

interface ListItem {
  text: string
  checked?: boolean
}

const listItems = computed<ListItem[]>(() => {
  return markdown.value
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => {
      const todo = line.match(/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/)
      if (todo) {
        return {
          checked: todo[1].toLowerCase() === 'x',
          text: todo[2],
        }
      }
      const bullet = line.match(/^\s*[-*+]\s+(.*)$/)
      if (bullet) {
        return { text: bullet[1] }
      }
      const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/)
      if (ordered) {
        return { text: ordered[1] }
      }
      return { text: line }
    })
})

const table = computed(() => {
  const rawHeaders = props.content.headers
  const rawRows = props.content.rows
  const headers = Array.isArray(rawHeaders)
    ? rawHeaders.map((cell) => String(cell ?? ''))
    : []
  const rows = Array.isArray(rawRows)
    ? rawRows.map((row) =>
        Array.isArray(row)
          ? row.map((cell) => String(cell ?? ''))
          : [],
      )
    : []
  return { headers, rows }
})
</script>

<template>
  <div class="markdown-module" :class="`module-${moduleName}`">
    <template v-if="moduleName === 'paragraph'">
      <div class="md-paragraphs">
        <p v-for="(text, index) in paragraphs" :key="index">
          <InlineMarkdown :text="text" />
        </p>
      </div>
    </template>

    <template v-else-if="moduleName === 'heading1'">
      <h1><InlineMarkdown :text="markdown" /></h1>
    </template>
    <template v-else-if="moduleName === 'heading2'">
      <h2><InlineMarkdown :text="markdown" /></h2>
    </template>
    <template v-else-if="moduleName === 'heading3'">
      <h3><InlineMarkdown :text="markdown" /></h3>
    </template>

    <template v-else-if="moduleName === 'quote'">
      <blockquote class="md-quote">
        <p v-for="(text, index) in quoteParagraphs" :key="index">
          <InlineMarkdown :text="text" />
        </p>
      </blockquote>
    </template>

    <template v-else-if="moduleName === 'divider'">
      <hr class="md-divider" />
    </template>

    <template v-else-if="moduleName === 'bullet_list'">
      <ul class="md-list">
        <li v-for="(item, index) in listItems" :key="index">
          <InlineMarkdown :text="item.text" />
        </li>
      </ul>
    </template>

    <template v-else-if="moduleName === 'ordered_list'">
      <ol class="md-list ordered">
        <li v-for="(item, index) in listItems" :key="index">
          <InlineMarkdown :text="item.text" />
        </li>
      </ol>
    </template>

    <template v-else-if="moduleName === 'todo_list'">
      <ul class="md-todo-list">
        <li
          v-for="(item, index) in listItems"
          :key="index"
          :class="{ checked: item.checked }"
        >
          <span class="md-checkbox" aria-hidden="true">
            {{ item.checked ? '✓' : '' }}
          </span>
          <span>
            <InlineMarkdown :text="item.text" />
          </span>
        </li>
      </ul>
    </template>

    <template v-else-if="moduleName === 'table'">
      <div class="md-table-wrap">
        <table class="md-table">
          <thead>
            <tr>
              <th v-for="(cell, index) in table.headers" :key="index">
                <InlineMarkdown :text="cell" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in table.rows" :key="rowIndex">
              <td v-for="(cell, cellIndex) in row" :key="cellIndex">
                <InlineMarkdown :text="cell" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <template v-else>
      <div class="md-paragraphs">
        <p v-for="(text, index) in paragraphs" :key="index">
          <InlineMarkdown :text="text" />
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.markdown-module {
  color: #302947;
  font-size: 15px;
  line-height: 1.9;
}

.md-paragraphs {
  display: grid;
  gap: 13px;
}

.md-paragraphs p {
  margin: 0;
}

.markdown-module h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: -0.03em;
  line-height: 1.28;
}

.markdown-module h2 {
  margin: 0;
  font-size: 23px;
  letter-spacing: -0.02em;
  line-height: 1.35;
}

.markdown-module h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.45;
}

.md-quote {
  margin: 0;
  padding: 13px 17px;
  border-left: 3px solid #9d7cf3;
  border-radius: 0 10px 10px 0;
  color: #574b75;
  background: linear-gradient(
    90deg,
    rgba(239, 234, 255, 0.9),
    rgba(251, 248, 255, 0.78)
  );
}

.md-quote p {
  margin: 0;
}

.md-quote p + p {
  margin-top: 9px;
}

.md-divider {
  width: 100%;
  margin: 3px 0;
  border: 0;
  border-top: 1px solid var(--border-strong);
}

.md-list {
  display: grid;
  gap: 6px;
  padding-left: 24px;
  margin: 0;
  list-style: disc;
}

.md-list.ordered {
  list-style: decimal;
}

.md-list li {
  padding-left: 2px;
}

.md-todo-list {
  display: grid;
  gap: 7px;
  margin: 0;
}

.md-todo-list li {
  display: flex;
  gap: 9px;
  align-items: flex-start;
}

.md-todo-list li.checked {
  color: #8f879f;
  text-decoration: line-through;
  text-decoration-color: #c7bdd9;
}

.md-checkbox {
  display: grid;
  flex: none;
  width: 17px;
  height: 17px;
  margin-top: 4px;
  place-items: center;
  border: 1px solid #cbbdf1;
  border-radius: 5px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  background: #fff;
}

.md-todo-list li.checked .md-checkbox {
  border-color: var(--accent);
  background: var(--accent);
}

.md-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 11px;
}

.md-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.md-table th,
.md-table td {
  padding: 9px 11px;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

.md-table th {
  color: var(--muted-strong);
  font-weight: 700;
  background: #faf8ff;
}

.md-table tr:last-child td {
  border-bottom: 0;
}

.md-table td:last-child,
.md-table th:last-child {
  border-right: 0;
}

:deep(.inline-markdown) {
  white-space: pre-wrap;
}

:deep(.inline-markdown strong) {
  font-weight: 760;
}

:deep(.inline-markdown em) {
  font-style: italic;
}

:deep(.inline-markdown u) {
  text-decoration: underline;
  text-underline-offset: 3px;
}

:deep(.inline-markdown s) {
  text-decoration: line-through;
}

:deep(.inline-markdown code) {
  padding: 2px 5px;
  border: 1px solid #e7e0f6;
  border-radius: 5px;
  color: #5637c8;
  font-family: var(--font-mono);
  font-size: 0.88em;
  white-space: pre-wrap;
  background: #f8f5ff;
}

:deep(.inline-markdown a) {
  color: var(--accent-strong);
  text-decoration: underline;
  text-decoration-color: rgba(84, 54, 232, 0.32);
  text-underline-offset: 3px;
}

:deep(.inline-markdown mark) {
  padding: 1px 3px;
  border-radius: 4px;
  color: inherit;
}

:deep(.inline-markdown .inline-image) {
  display: inline-grid;
  gap: 4px;
  max-width: min(100%, 520px);
  vertical-align: middle;
}

:deep(.inline-markdown .inline-image img) {
  max-height: 320px;
  border-radius: 9px;
  object-fit: contain;
  background: #faf8ff;
}

:deep(.inline-markdown .inline-image small) {
  color: var(--muted);
  font-size: 10px;
  text-align: center;
}

:deep(.inline-markdown .blocked-inline-image) {
  padding: 2px 6px;
  border: 1px dashed #e5cad0;
  border-radius: 5px;
  color: #a35a67;
  font-size: 0.9em;
  background: #fff8f8;
}

@media (max-width: 640px) {
  .markdown-module {
    font-size: 14px;
  }

  .markdown-module h1 {
    font-size: 25px;
  }

  .markdown-module h2 {
    font-size: 20px;
  }

  .markdown-module h3 {
    font-size: 17px;
  }
}
</style>
