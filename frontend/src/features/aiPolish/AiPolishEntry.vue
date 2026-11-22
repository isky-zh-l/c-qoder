<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import ModalShell from '../../components/ModalShell.vue'
import { authState } from '../../auth/session'
import { ApiError } from '../../api/client'
import { choosePolishVersion, polishDocument, type AiPolishResult } from './api'
import { announceAiChange, saveAiError } from './storage'

const props = defineProps<{
  documentId: number
  dirty: boolean
  saving: boolean
}>()

const router = useRouter()
const open = ref(false)
const phase = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const message = ref('')
const result = ref<AiPolishResult | null>(null)
const choosing = ref(false)
const elapsed = ref(0)
let timer: number | null = null

const visible = computed(() => Boolean(authState.user))
const demoUser = computed(() => authState.user?.is_demo === true)
const blocked = computed(() => props.dirty || props.saving || demoUser.value)
const running = computed(() => phase.value === 'running')
const triggerHint = computed(() => {
  if (demoUser.value) return '登录 Qoder 账号后可用 AI 润色'
  if (props.saving) return '保存中，完成后再使用 AI 润色'
  if (props.dirty) return '请先保存当前修改'
  if (running.value) return 'AI 正在后台整理，完成后可在笔记页选择版本'
  if (result.value) return 'AI 版已生成，点开选择保留哪一版'
  if (message.value) return '上次整理失败，点开重试'
  return '用 Qoder AI 整理排版'
})

function stopTimer() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function startTimer() {
  stopTimer()
  elapsed.value = 0
  timer = window.setInterval(() => {
    elapsed.value += 1
  }, 1000)
}

onBeforeUnmount(stopTimer)

function openDialog() {
  if (blocked.value) return
  phase.value = running.value
    ? 'running'
    : result.value
      ? 'done'
      : message.value
        ? 'error'
        : 'idle'
  open.value = true
}

function closeDialog() {
  if (choosing.value) return
  open.value = false
  stopTimer()
}

async function startPolish() {
  if (phase.value === 'running') return
  phase.value = 'running'
  message.value = ''
  startTimer()
  try {
    result.value = await polishDocument(props.documentId)
    phase.value = 'done'
    announceAiChange()
  } catch (error) {
    message.value =
      error instanceof ApiError ? error.message : 'AI 润色失败，请稍后重试'
    phase.value = 'error'
    if (authState.user?.id) {
      saveAiError(authState.user.id, message.value)
    }
    announceAiChange()
  } finally {
    stopTimer()
  }
}

async function keep(which: 'ai' | 'original') {
  if (!result.value || choosing.value) return
  choosing.value = true
  const keepDoc = which === 'ai' ? result.value.polished : result.value.original
  const discardDoc =
    which === 'ai' ? result.value.original : result.value.polished
  try {
    await choosePolishVersion(keepDoc.id, discardDoc.id)
    open.value = false
    await router.push({ name: 'document', params: { id: keepDoc.id } })
  } catch (error) {
    message.value =
      error instanceof ApiError ? error.message : '选择失败，请稍后重试'
  } finally {
    choosing.value = false
  }
}
</script>

<template>
  <button
    v-if="visible"
    type="button"
    class="topbar-button ai-entry"
    :disabled="blocked"
    :title="triggerHint"
    @click="openDialog"
  >
    <span class="ai-spark" aria-hidden="true">✦</span>
    <span class="ai-label-full">AI 润色</span>
    <span class="ai-label-short">AI</span>
  </button>

  <ModalShell
    :open="open"
    title="AI 润色"
    eyebrow="EDITOR / AI"
    :dismissible="!choosing"
    @close="closeDialog"
  >
    <div class="ai-dialog">
      <div v-if="phase === 'idle'" class="ai-block">
        <p>
          把这篇笔记交给 Qoder AI，只调整结构与排版：补充小标题、整理列表和表格、给关键词加高亮。
        </p>
        <ul>
          <li>代码块、公式和链接原样保留；</li>
          <li>不会新增技术结论，也不会删除原有内容；</li>
          <li>图片会保留原样，不参与 AI 改写；</li>
          <li>完成后在「AI 版」和「原版」之间选择，未被选中的那篇进入回收站。</li>
        </ul>
        <p class="ai-hint">
          需要登录 Qoder 账号；处理约需 20–40 秒，可以后台进行，
          完成后在笔记页选择保留哪一版。
        </p>
      </div>

      <div v-else-if="phase === 'running'" class="ai-block ai-running">
        <span class="ai-spinner" aria-hidden="true"></span>
        <p>AI 正在整理排版…</p>
        <p class="ai-hint">
          已用时 {{ elapsed }} 秒。可以关闭对话框或切换到其他页面，
          完成后在笔记页选择保留哪一版。
        </p>
      </div>

      <div v-else-if="phase === 'done' && result" class="ai-block">
        <p>AI 版已生成。选择保留哪一版，另一版会进入回收站。</p>
        <div class="ai-cards">
          <button
            type="button"
            class="ai-card"
            :disabled="choosing"
            @click="keep('original')"
          >
            <span class="ai-card-tag">原版</span>
            <strong>{{ result.original.title }}</strong>
            <small>
              {{ result.original.block_count }} 个模块 · v{{ result.original.version }}
            </small>
            <span class="ai-card-action">保留原版</span>
          </button>
          <button
            type="button"
            class="ai-card ai-card-highlight"
            :disabled="choosing"
            @click="keep('ai')"
          >
            <span class="ai-card-tag">AI 版</span>
            <strong>{{ result.polished.title }}</strong>
            <small>
              {{ result.polished.block_count }} 个模块 · v{{ result.polished.version }}
            </small>
            <span class="ai-card-action">保留 AI 版</span>
          </button>
        </div>
        <p class="ai-hint">
          关闭对话框会保留两篇，稍后可在笔记列表手动处理。
        </p>
      </div>

      <div v-else-if="phase === 'error'" class="ai-block">
        <p class="ai-error">{{ message || 'AI 润色失败，请稍后重试' }}</p>
        <p class="ai-hint">本次没有生成副本，原文不受影响。</p>
      </div>

      <p v-if="message && phase === 'done'" class="ai-error">{{ message }}</p>
    </div>

    <template #footer>
      <div class="ai-foot">
        <template v-if="phase === 'idle'">
          <button type="button" class="secondary-button" @click="closeDialog">
            取消
          </button>
          <button type="button" class="primary-button" @click="startPolish">
            开始整理
          </button>
        </template>
        <template v-else-if="phase === 'error'">
          <button type="button" class="secondary-button" @click="closeDialog">
            关闭
          </button>
          <button type="button" class="primary-button" @click="startPolish">
            重试
          </button>
        </template>
        <template v-else-if="phase === 'running'">
          <button type="button" class="secondary-button" @click="closeDialog">
            后台运行并关闭
          </button>
        </template>
        <template v-else-if="phase === 'done'">
          <button
            type="button"
            class="secondary-button"
            :disabled="choosing"
            @click="closeDialog"
          >
            稍后决定
          </button>
        </template>
      </div>
    </template>
  </ModalShell>
</template>

<style scoped>
.ai-entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ai-spark {
  color: #7c5cff;
}

.ai-label-short {
  display: none;
}

.ai-dialog {
  display: grid;
  gap: 12px;
  font-size: 14px;
  line-height: 1.7;
  color: #3c3552;
}

.ai-block {
  display: grid;
  gap: 10px;
}

.ai-block p {
  margin: 0;
}

.ai-block ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
}

.ai-hint {
  color: #8a839c;
  font-size: 12.5px;
}

.ai-running {
  justify-items: center;
  padding: 18px 0 8px;
  text-align: center;
}

.ai-spinner {
  width: 26px;
  height: 26px;
  border: 2px solid #e4dcfb;
  border-top-color: #6f4df0;
  border-radius: 50%;
  animation: ai-spin 0.9s linear infinite;
}

@keyframes ai-spin {
  to {
    transform: rotate(360deg);
  }
}

.ai-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.ai-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e4dcf6;
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.ai-card:hover,
.ai-card:focus-visible {
  border-color: #a58ff5;
  outline: none;
}

.ai-card-highlight {
  border-color: #c9b8ff;
  background: #faf7ff;
}

.ai-card-tag {
  width: fit-content;
  padding: 1px 7px;
  border-radius: 999px;
  background: #f1ecff;
  color: #6f4df0;
  font-size: 11px;
  font-weight: 700;
}

.ai-card strong {
  font-size: 13.5px;
  line-height: 1.45;
  word-break: break-word;
}

.ai-card small {
  color: #8a839c;
  font-size: 11.5px;
}

.ai-card-action {
  margin-top: 2px;
  color: #5b3ee8;
  font-size: 12px;
  font-weight: 700;
}

.ai-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ai-foot .primary-button,
.ai-foot .secondary-button {
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.ai-foot .primary-button {
  border: 1px solid #5b3ee8;
  background: #5b3ee8;
  color: #fff;
}

.ai-foot .secondary-button {
  border: 1px solid #e0d8f6;
  background: #fff;
  color: #4b435e;
}

.ai-foot .primary-button:disabled,
.ai-foot .secondary-button:disabled {
  opacity: 0.5;
  cursor: default;
}

.ai-error {
  padding: 9px 11px;
  border-radius: 9px;
  background: #fff3f3;
  color: #b3261e;
  font-size: 13px;
}

@media (max-width: 640px) {
  .ai-label-full {
    display: none;
  }

  .ai-label-short {
    display: inline;
  }

  .ai-cards {
    grid-template-columns: 1fr;
  }
}
</style>