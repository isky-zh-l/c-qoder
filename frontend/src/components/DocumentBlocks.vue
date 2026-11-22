<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  assetDownloadUrl,
  assetFileUrl,
  documentDownloadUrl,
  publicAssetUrl,
} from '../api/client'
import type { DocumentBlock, DocumentKind, SourceLanguage } from '../api/types'
import { sourceFromBlocks } from '../utils/source'
import CodeView from './CodeView.vue'
import FormulaView from './FormulaView.vue'
import MarkdownModule from './MarkdownModule.vue'
import RichTextNode, { type RichNode } from './RichTextNode'

const props = withDefaults(
  defineProps<{
    blocks: DocumentBlock[]
    kind: DocumentKind
    language?: SourceLanguage | null
    documentId?: number | null
    publicShareToken?: string | null
  }>(),
  { language: null, documentId: null, publicShareToken: null },
)

const copiedKey = ref<string | null>(null)

function richNode(block: DocumentBlock): RichNode {
  return block.content as unknown as RichNode
}

function codeText(block: DocumentBlock): string {
  return typeof block.content.text === 'string' ? block.content.text : ''
}

function codeLanguage(block: DocumentBlock): string {
  const language = block.content.language
  if (language === 'c' || language === 'h') {
    return language.toUpperCase()
  }
  return String(language || 'TEXT').toUpperCase()
}

function resultText(block: DocumentBlock): string {
  return typeof block.content.text === 'string' ? block.content.text : ''
}

function formulaText(block: DocumentBlock): string {
  return typeof block.content.latex === 'string' ? block.content.latex : ''
}

function isMarkdownModule(block: DocumentBlock): boolean {
  return typeof block.content.module === 'string'
}

function imageUrl(block: DocumentBlock): string {
  if (block.asset_id === null) {
    return ''
  }
  return props.publicShareToken
    ? publicAssetUrl(props.publicShareToken, block.asset_id)
    : assetFileUrl(block.asset_id)
}

function imageAlt(block: DocumentBlock): string {
  return typeof block.content.alt === 'string' ? block.content.alt : '文档图片'
}

function imageCaption(block: DocumentBlock): string {
  return typeof block.content.caption === 'string' ? block.content.caption : ''
}

const sourceCode = computed(() => sourceFromBlocks(props.blocks))

const codeCount = computed(
  () => props.blocks.filter((block) => block.block_type === 'code').length,
)

async function copyText(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    document.execCommand('copy')
    area.remove()
  }
  copiedKey.value = key
  window.setTimeout(() => {
    if (copiedKey.value === key) {
      copiedKey.value = null
    }
  }, 1600)
}
</script>

<template>
  <div class="document-blocks" :class="`kind-${kind}`">
    <template v-for="(block, index) in blocks" :key="block.id">
      <section v-if="block.block_type === 'rich_text'" class="rich-section">
        <MarkdownModule
          v-if="isMarkdownModule(block)"
          :content="block.content"
        />
        <RichTextNode v-else :node="richNode(block)" />
      </section>

      <section
        v-else-if="block.block_type === 'remark'"
        class="remark-section"
      >
        <p class="block-label">样式备注</p>
        <MarkdownModule
          v-if="isMarkdownModule(block)"
          :content="block.content"
        />
        <RichTextNode v-else :node="richNode(block)" />
      </section>

      <section v-else-if="block.block_type === 'code'" class="code-section">
        <div class="code-head">
          <span class="code-language">
            {{ codeLanguage(block) }}
            <span v-if="codeCount > 1" class="code-index">模块 {{ index + 1 }}</span>
          </span>
          <button
            type="button"
            class="copy-button dark"
            @click="copyText(codeText(block), `block-${block.id}`)"
          >
            {{ copiedKey === `block-${block.id}` ? '已复制' : '复制代码' }}
          </button>
        </div>
        <CodeView
          :source="codeText(block)"
          :language="String(block.content.language || 'text')"
        />
      </section>

      <section v-else-if="block.block_type === 'result'" class="result-section">
        <div class="result-head">
          <span>运行结果</span>
          <button
            type="button"
            class="copy-button"
            @click="copyText(resultText(block), `result-${block.id}`)"
          >
            {{ copiedKey === `result-${block.id}` ? '已复制' : '复制' }}
          </button>
        </div>
        <pre class="result-body">{{ resultText(block) }}</pre>
      </section>

      <figure v-else-if="block.block_type === 'image'" class="image-section">
        <img
          v-if="block.asset_id !== null"
          :src="imageUrl(block)"
          :alt="imageAlt(block)"
          loading="lazy"
          decoding="async"
        />
        <figcaption>
          <span v-if="imageCaption(block)">{{ imageCaption(block) }}</span>
          <a
            v-if="block.asset_id !== null && publicShareToken === null"
            :href="assetDownloadUrl(block.asset_id)"
            class="image-download"
          >
            下载原图
          </a>
        </figcaption>
      </figure>

      <section v-else-if="block.block_type === 'formula'" class="formula-section">
        <p class="block-label">公式</p>
        <div class="formula-body">
          <FormulaView :latex="formulaText(block)" display="block" />
        </div>
      </section>
    </template>

    <div v-if="kind === 'source'" class="source-copy">
      <div>
        <strong>完整源码</strong>
        <span>
          {{ codeCount }} 个代码模块按顺序拼接；缺少结尾换行时自动补一个
        </span>
      </div>
      <div class="source-actions">
        <button
          type="button"
          class="copy-button"
          @click="copyText(sourceCode, 'source-all')"
        >
          {{ copiedKey === 'source-all' ? '已复制完整源码' : '复制完整源码' }}
        </button>
        <a
          v-if="documentId !== null"
          class="copy-button"
          :href="documentDownloadUrl(documentId)"
        >
          下载源码
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.document-blocks {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
}

.rich-section,
.remark-section {
  min-width: 0;
  padding: 5px 2px;
  color: #302947;
  font-size: 15px;
  line-height: 1.9;
}

.block-label {
  margin-bottom: 8px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.remark-section {
  padding: 17px 19px;
  border: 1px solid #e7ddff;
  border-radius: 14px;
  background: linear-gradient(135deg, #fbf8ff, #fff);
}

.code-section {
  overflow: hidden;
  border: 1px solid #2d2743;
  border-radius: 15px;
  background: #221d36;
  box-shadow: 0 20px 46px -34px rgba(34, 29, 54, 0.9);
}

.code-head {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  color: #c7b9f5;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.11em;
}

.code-language {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.code-index {
  padding-left: 8px;
  border-left: 1px solid rgba(255, 255, 255, 0.16);
  color: #8f82b7;
  letter-spacing: 0.04em;
}

.code-body {
  margin: 0;
  padding: 18px 19px 20px;
  overflow-x: auto;
  color: #f2efff;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.75;
  tab-size: 2;
  white-space: pre;
}

.copy-button {
  flex: none;
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 9.5px;
  font-weight: 600;
  background: #fff;
  cursor: pointer;
}

.copy-button:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.copy-button.dark {
  border-color: rgba(255, 255, 255, 0.17);
  color: #d6cbf8;
  background: rgba(255, 255, 255, 0.06);
}

.copy-button.dark:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
}

.result-section {
  overflow: hidden;
  border: 1px solid var(--result-border);
  border-radius: 14px;
  background: var(--result-bg);
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 13px;
  border-bottom: 1px solid rgba(99, 164, 124, 0.18);
  color: #3c7a58;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.result-body {
  margin: 0;
  padding: 15px 17px 17px;
  overflow-x: auto;
  color: #28583f;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.75;
  white-space: pre-wrap;
}

.image-section {
  margin: 0;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 16px 40px -38px rgba(61, 42, 120, 0.6);
}

.image-section img {
  width: 100%;
  max-height: 70vh;
  border-radius: 10px;
  object-fit: contain;
  background: #faf8ff;
}

.image-section figcaption {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
  padding: 9px 4px 1px;
  color: var(--muted);
  font-size: 10.5px;
  text-align: center;
}

.image-download {
  flex: none;
  padding: 3px 7px;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted-strong);
  font-size: 9.5px;
  font-weight: 600;
  background: #fff;
}

.image-download:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.formula-section {
  padding: 14px 17px 16px;
  border: 1px solid #e7ddff;
  border-radius: 14px;
  background: #fbf9ff;
}

.formula-body {
  overflow-x: auto;
  padding: 7px 2px;
}

.source-copy {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 13px 16px;
  border: 1px dashed var(--border-strong);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.65);
}

.source-copy div {
  display: grid;
  gap: 3px;
}

.source-copy strong {
  font-size: 11.5px;
}

.source-copy span {
  color: var(--muted);
  font-size: 9.5px;
}

.source-actions {
  display: flex;
  flex: none;
  gap: 7px;
  align-items: center;
}

.source-copy .copy-button {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

:deep(.rich-doc) {
  display: grid;
  gap: 13px;
}

:deep(.rich-doc > p),
:deep(.rich-doc > h1),
:deep(.rich-doc > h2),
:deep(.rich-doc > h3),
:deep(.rich-doc > h4) {
  margin: 0;
}

:deep(.rich-doc h1) {
  margin-top: 10px;
  font-size: 28px;
  letter-spacing: -0.03em;
  line-height: 1.3;
}

:deep(.rich-doc h2) {
  margin-top: 9px;
  font-size: 22px;
  letter-spacing: -0.02em;
  line-height: 1.35;
}

:deep(.rich-doc h3) {
  font-size: 18px;
  line-height: 1.4;
}

:deep(.rich-doc h4) {
  font-size: 15.5px;
  line-height: 1.5;
}

:deep(.rich-doc p) {
  margin: 0;
}

:deep(.rich-doc a) {
  color: var(--accent-strong);
  text-decoration: underline;
  text-decoration-color: rgba(84, 54, 232, 0.32);
  text-underline-offset: 3px;
}

:deep(.rich-doc strong) {
  font-weight: 760;
}

:deep(.rich-doc code) {
  padding: 2px 5px;
  border: 1px solid #e7e0f6;
  border-radius: 5px;
  color: #5637c8;
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: #f8f5ff;
}

:deep(.rich-doc mark) {
  padding: 1px 3px;
  border-radius: 4px;
  color: inherit;
}

:deep(.hl-yellow) {
  background: #fff3a3;
}

:deep(.hl-green) {
  background: #d8f5df;
}

:deep(.hl-blue) {
  background: #dbeafe;
}

:deep(.hl-pink) {
  background: #ffe0ef;
}

:deep(.rich-list) {
  display: grid;
  gap: 5px;
  padding-left: 22px;
  list-style: disc;
}

:deep(.rich-list.ordered) {
  list-style: decimal;
}

:deep(.rich-list li) {
  padding-left: 2px;
}

:deep(.rich-doc blockquote) {
  margin: 2px 0;
  padding: 10px 15px;
  border-left: 3px solid #c8b8f6;
  border-radius: 0 8px 8px 0;
  color: #5d5572;
  background: #faf8ff;
}

:deep(.rich-rule) {
  width: 100%;
  margin: 6px 0;
  border: 0;
  border-top: 1px solid var(--border-strong);
}

:deep(.rich-table-wrap) {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
}

:deep(.rich-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

:deep(.rich-table th),
:deep(.rich-table td) {
  padding: 8px 10px;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

:deep(.rich-table th) {
  color: var(--muted-strong);
  font-weight: 700;
  background: #faf8ff;
}

:deep(.rich-table tr:last-child td) {
  border-bottom: 0;
}

:deep(.rich-table td:last-child),
:deep(.rich-table th:last-child) {
  border-right: 0;
}

:deep(.rich-table p) {
  margin: 0;
}

:deep(.inline-formula) {
  display: inline-flex;
  gap: 3px;
  align-items: baseline;
  padding: 1px 5px;
  border: 1px solid #e3d9fb;
  border-radius: 5px;
  color: #4d359c;
  font-family: var(--font-mono);
  font-size: 0.88em;
  background: #faf7ff;
}

:deep(.inline-formula-mark) {
  color: var(--accent);
  font-family: Georgia, serif;
  font-style: italic;
}

:deep(.rich-empty-line) {
  min-height: 1em;
}

@media (max-width: 640px) {
  .rich-section,
  .remark-section {
    font-size: 14px;
  }

  .code-body {
    padding: 14px 14px 16px;
    font-size: 11.5px;
  }

  .source-copy {
    align-items: flex-start;
    flex-direction: column;
  }

  .source-copy .copy-button {
    align-self: flex-end;
  }

  :deep(.rich-doc) {
    gap: 11px;
  }

  :deep(.rich-doc h1) {
    font-size: 24px;
  }

  :deep(.rich-doc h2) {
    font-size: 20px;
  }
}
</style>
