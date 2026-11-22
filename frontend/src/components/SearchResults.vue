<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { SearchPayload } from '../api/types'
import { formatRelativeTime } from '../utils/format'

const props = defineProps<{
  query: string
  payload: SearchPayload | null
  loading: boolean
  error: string
  loadingMore?: boolean
}>()

const emit = defineEmits<{
  retry: []
  'load-more': []
  clear: []
}>()

const items = computed(() => props.payload?.items ?? [])

function segments(text: string): Array<{ text: string; match: boolean }> {
  const query = props.query.trim()
  if (!query) return [{ text, match: false }]
  const source = text.toLowerCase()
  const needle = query.toLowerCase()
  const output: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  while (cursor < text.length) {
    const index = source.indexOf(needle, cursor)
    if (index < 0) {
      output.push({ text: text.slice(cursor), match: false })
      break
    }
    if (index > cursor) {
      output.push({ text: text.slice(cursor, index), match: false })
    }
    output.push({ text: text.slice(index, index + query.length), match: true })
    cursor = index + query.length
  }
  return output
}
</script>

<template>
  <section class="search-results" aria-label="搜索结果">
    <header class="result-head">
      <div>
        <p class="eyebrow">SEARCH / ALL FIELDS</p>
        <h2>搜索结果</h2>
      </div>
      <div class="result-summary">
        <span v-if="payload">{{ payload.total }} 条命中</span>
        <span class="result-query">“{{ query }}”</span>
        <button type="button" class="clear-button" @click="emit('clear')">清除搜索</button>
      </div>
    </header>

    <div v-if="error" class="result-state error" role="alert">
      <p>{{ error }}</p>
      <button type="button" @click="emit('retry')">重试</button>
    </div>

    <div v-else-if="loading" class="result-state" aria-busy="true">
      正在搜索…
    </div>

    <div v-else-if="!items.length" class="result-state empty">
      没有找到包含“{{ query }}”的标题、正文、源码、备注、结果、表格或公式。
    </div>

    <template v-else>
      <div class="result-list">
        <RouterLink
          v-for="item in items"
          :key="item.id"
          class="result-card"
          :to="{ name: 'document', params: { id: item.id } }"
        >
          <div class="result-top">
            <span class="kind" :class="item.kind">
              {{ item.kind === 'source' ? (item.language === 'h' ? 'H 源码' : 'C 源码') : '笔记' }}
            </span>
            <span v-if="item.title_hit" class="title-hit">标题命中</span>
            <time :datetime="item.updated_at">{{ formatRelativeTime(item.updated_at) }}</time>
          </div>
          <h3>
            <template v-for="(part, index) in segments(item.title)" :key="index">
              <mark v-if="part.match">{{ part.text }}</mark>
              <template v-else>{{ part.text }}</template>
            </template>
          </h3>
          <p class="snippet">
            <template v-for="(part, index) in segments(item.snippet)" :key="index">
              <mark v-if="part.match">{{ part.text }}</mark>
              <template v-else>{{ part.text }}</template>
            </template>
          </p>
          <p class="result-meta">
            <span>{{ item.folder_path || '根目录' }}</span>
            <span class="dot" aria-hidden="true"></span>
            <span>{{ item.chapter_name || '未分类' }}</span>
          </p>
        </RouterLink>
      </div>
      <button
        v-if="payload?.next_offset !== null && payload?.next_offset !== undefined"
        type="button"
        class="load-more"
        :disabled="loadingMore"
        @click="emit('load-more')"
      >
        {{ loadingMore ? '加载中…' : '加载更多' }}
      </button>
    </template>
  </section>
</template>

<style scoped>
.search-results {
  display: grid;
  gap: 12px;
}

.result-head {
  display: flex;
  gap: 14px;
  align-items: flex-end;
  justify-content: space-between;
  padding: 2px 3px 6px;
}

.eyebrow {
  margin-bottom: 4px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.result-head h2 {
  font-size: 20px;
  letter-spacing: -0.02em;
}

.result-summary {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--muted);
  font-size: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.result-query {
  max-width: 220px;
  overflow: hidden;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.clear-button {
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 9.5px;
  background: #fff;
  cursor: pointer;
}

.result-state {
  padding: 28px 20px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  background: rgba(255, 255, 255, 0.58);
}

.result-state.error {
  display: grid;
  gap: 10px;
  color: #a43e3e;
  border-color: #f0cccc;
  background: #fff5f5;
}

.result-state button {
  justify-self: center;
  padding: 7px 13px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--accent-strong);
  font: inherit;
  background: #fff;
  cursor: pointer;
}

.result-list {
  display: grid;
  gap: 8px;
}

.result-card {
  display: grid;
  gap: 7px;
  padding: 15px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 12px 30px -28px rgba(61, 42, 120, 0.5);
}

.result-card:hover {
  border-color: var(--border-strong);
  background: #fff;
}

.result-top {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--muted);
  font-size: 9px;
}

.result-top time {
  margin-left: auto;
  font-family: var(--font-mono);
}

.kind,
.title-hit {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 8.5px;
  font-weight: 700;
}

.kind.note {
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.kind.source {
  color: var(--source-text);
  background: var(--source-badge);
}

.title-hit {
  color: #8a651f;
  background: var(--favorite-gold-soft);
}

.result-card h3 {
  font-size: 15px;
  font-weight: 720;
  letter-spacing: -0.01em;
}

.snippet {
  display: -webkit-box;
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.result-card mark {
  padding: 0 1px;
  color: inherit;
  border-radius: 2px;
  background: #fff3a3;
}

.result-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #9b93ab;
  font-size: 9px;
}

.dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.load-more {
  justify-self: center;
  margin-top: 4px;
  padding: 8px 18px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  color: var(--accent-strong);
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.load-more:disabled {
  opacity: 0.55;
  cursor: wait;
}

@media (max-width: 760px) {
  .result-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .result-summary {
    justify-content: flex-start;
  }

  .result-card {
    padding: 13px 14px;
  }
}
</style>
