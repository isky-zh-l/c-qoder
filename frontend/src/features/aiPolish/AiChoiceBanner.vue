<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getDocuments } from '../../api/client'
import type { DocumentSummary } from '../../api/types'
import { authState } from '../../auth/session'
import { choosePolishVersion } from './api'
import {
  AI_POLISH_EVENT,
  clearAiError,
  loadAiError,
  type AiPolishErrorState,
} from './storage'

interface Pair {
  base: DocumentSummary
  copy: DocumentSummary
}

const emit = defineEmits<{ changed: [] }>()
const pairs = ref<Pair[]>([])
const error = ref<AiPolishErrorState | null>(null)
const choosing = ref<number | null>(null)

const visible = computed(
  () =>
    Boolean(authState.user) &&
    !authState.user?.is_demo &&
    (pairs.value.length > 0 || Boolean(error.value)),
)

async function load() {
  const user = authState.user
  if (!user || user.is_demo) {
    pairs.value = []
    error.value = null
    return
  }
  error.value = loadAiError(user.id)
  try {
    const docs = await getDocuments('library')
    const byTitle = new Map(docs.map((doc) => [doc.title, doc]))
    const found: Pair[] = []
    for (const doc of docs) {
      const match = doc.title.match(/^(.*) · AI 润色(?: \d+)?$/)
      if (!match) continue
      const base = byTitle.get(match[1])
      if (base && base.id !== doc.id) found.push({ base, copy: doc })
    }
    pairs.value = found
  } catch {
    // The banner is optional; list errors stay in the main view.
  }
}

async function choose(pair: Pair, which: 'original' | 'ai') {
  if (choosing.value !== null) return
  choosing.value = pair.base.id
  const keep = which === 'ai' ? pair.copy : pair.base
  const discard = which === 'ai' ? pair.base : pair.copy
  try {
    await choosePolishVersion(keep.id, discard.id)
    pairs.value = pairs.value.filter((item) => item !== pair)
    emit('changed')
    await load()
  } catch {
    // Keep the banner so the user can retry.
  } finally {
    choosing.value = null
  }
}

function dismissError() {
  if (authState.user?.id) clearAiError(authState.user.id)
  error.value = null
}

function handleChange() {
  void load()
}

onMounted(() => {
  void load()
  window.addEventListener(AI_POLISH_EVENT, handleChange)
  window.addEventListener('focus', handleChange)
  document.addEventListener('visibilitychange', handleChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(AI_POLISH_EVENT, handleChange)
  window.removeEventListener('focus', handleChange)
  document.removeEventListener('visibilitychange', handleChange)
})
</script>

<template>
  <section v-if="visible" class="ai-choice">
    <div v-if="pairs.length" class="ai-choice-head">
      <p class="ai-choice-eyebrow">AI / VERSION</p>
      <strong>AI 整理完成，选择保留哪一版</strong>
      <small>落选的一篇会进入回收站，可在回收站恢复。</small>
    </div>

    <div v-for="pair in pairs" :key="pair.copy.id" class="ai-choice-row">
      <div class="ai-choice-title">
        <strong>{{ pair.base.title }}</strong>
        <small>原版与 AI 版同章节，模块数可能不同</small>
      </div>
      <div class="ai-choice-actions">
        <button
          type="button"
          :disabled="choosing !== null"
          @click="choose(pair, 'original')"
        >
          保留原版
        </button>
        <button
          type="button"
          class="primary"
          :disabled="choosing !== null"
          @click="choose(pair, 'ai')"
        >
          {{ choosing === pair.base.id ? '处理中…' : '保留 AI 版' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="ai-choice-error">
      <span>上次 AI 整理失败：{{ error.message }}</span>
      <button type="button" @click="dismissError">知道了</button>
    </div>
  </section>
</template>

<style scoped>
.ai-choice {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid #e3d9fb;
  border-radius: 14px;
  background: linear-gradient(180deg, #faf7ff, #ffffff);
}

.ai-choice-head {
  display: grid;
  gap: 2px;
}

.ai-choice-eyebrow {
  margin: 0;
  color: #7c5cff;
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.ai-choice-head strong {
  color: #332b49;
  font-size: 14px;
}

.ai-choice-head small,
.ai-choice-title small {
  color: var(--muted, #8a839c);
  font-size: 11.5px;
}

.ai-choice-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e3d9fb;
}

.ai-choice-title {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.ai-choice-title strong {
  color: #332b49;
  font-size: 13px;
  word-break: break-word;
}

.ai-choice-actions {
  display: flex;
  gap: 8px;
}

.ai-choice-actions button,
.ai-choice-error button {
  padding: 7px 12px;
  border: 1px solid #ddd3f6;
  border-radius: 9px;
  color: #4b435e;
  font-size: 12px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.ai-choice-actions button.primary {
  border-color: #5b3ee8;
  color: #fff;
  background: #5b3ee8;
}

.ai-choice-actions button:disabled {
  opacity: 0.6;
  cursor: default;
}

.ai-choice-error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 11px;
  border-radius: 9px;
  color: #b3261e;
  font-size: 12.5px;
  background: #fff3f3;
}

.ai-choice-error button {
  border-color: #f0c9c9;
  color: #b3261e;
}

@media (max-width: 640px) {
  .ai-choice-row {
    align-items: stretch;
    flex-direction: column;
  }

  .ai-choice-actions button {
    flex: 1;
  }
}
</style>