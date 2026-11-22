<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type {
  DocumentScope,
  DocumentSummary,
} from '../api/types'
import DocumentRow from './DocumentRow.vue'

const props = withDefaults(
  defineProps<{
    documents: DocumentSummary[]
    loading: boolean
    errorMessage: string
    scope: DocumentScope
    sorting?: boolean
    favoriteBusyId?: number | null
  }>(),
  {
    sorting: false,
    favoriteBusyId: null,
  },
)

const emit = defineEmits<{
  retry: []
  favorite: [doc: DocumentSummary]
  rename: [doc: DocumentSummary]
  move: [doc: DocumentSummary]
  delete: [doc: DocumentSummary]
  reorder: [documentIds: number[]]
}>()

const listRoot = ref<HTMLElement | null>(null)
const localDocs = ref<DocumentSummary[]>([])
const dragId = ref<number | null>(null)

interface DragState {
  id: number
  pointerId: number
  startClientY: number
  grabOffset: number
  height: number
  width: number
  left: number
  ghost: HTMLElement
  source: HTMLElement
  handle: HTMLElement
  heights: Map<number, number>
  gap: number
  originOrder: number[]
  moved: boolean
  lastClientY: number
  frame: number | null
  keyHandler: (event: KeyboardEvent) => void
}

let drag: DragState | null = null

watch(
  () => props.documents,
  (value) => {
    if (drag) {
      return
    }
    localDocs.value = value.slice()
  },
  { immediate: true },
)

const isEmpty = computed(() => !props.loading && !props.errorMessage && !localDocs.value.length)
const emptyTitle = computed(() => {
  if (props.scope === 'favorites') {
    return '收藏架还是空的'
  }
  if (props.scope === 'chapter') {
    return '这个章节还没有内容'
  }
  if (props.scope === 'folder') {
    return '这个文件夹还是空的'
  }
  return '这里还没有笔记'
})
const emptyCopy = computed(() => {
  if (props.scope === 'favorites') {
    return '在任意笔记卡片上点亮金色星标，它就会成为独立书架，不影响原列表顺序。'
  }
  if (props.scope === 'chapter') {
    return '换一个章节看看，或回到全部笔记。'
  }
  if (props.scope === 'folder') {
    return '新建子文件夹、移动文档进来，或回到上级目录。'
  }
  return '新建笔记、上传 Markdown，或导入 C/H 源码，马上开始整理。'
})

function arrayMove<T>(items: T[], from: number, to: number): T[] {
  const copy = items.slice()
  const [moved] = copy.splice(from, 1)
  copy.splice(to, 0, moved)
  return copy
}

function moveByButton(doc: DocumentSummary, direction: -1 | 1) {
  if (props.sorting) {
    return
  }
  const index = localDocs.value.findIndex((item) => item.id === doc.id)
  const target = index + direction
  if (index < 0 || target < 0 || target >= localDocs.value.length) {
    return
  }
  localDocs.value = arrayMove(localDocs.value, index, target)
  emit(
    'reorder',
    localDocs.value.map((item) => item.id),
  )
}

function rowElement(docId: number): HTMLElement | null {
  return (
    listRoot.value?.querySelector<HTMLElement>(
      `[data-doc-id="${docId}"]`,
    ) ?? null
  )
}

function startDrag(event: PointerEvent, doc: DocumentSummary) {
  if (props.sorting || drag || event.button !== 0) {
    return
  }
  const source = rowElement(doc.id)
  const handle = event.currentTarget as HTMLElement | null
  if (!source || !handle) {
    return
  }
  const rect = source.getBoundingClientRect()
  const heights = new Map<number, number>()
  for (const item of localDocs.value) {
    const element = rowElement(item.id)
    if (element) {
      heights.set(item.id, element.getBoundingClientRect().height)
    }
  }
  const listElement =
    listRoot.value?.querySelector<HTMLElement>('.doc-list') ?? listRoot.value!
  const gap =
    Number.parseFloat(getComputedStyle(listElement).rowGap || '9') || 9

  const ghost = source.cloneNode(true) as HTMLElement
  ghost.classList.add('doc-drag-ghost')
  ghost.classList.remove('is-sorting')
  ghost.removeAttribute('data-doc-id')
  ghost.querySelectorAll<HTMLElement>('button, a').forEach((element) => {
    element.setAttribute('tabindex', '-1')
    element.setAttribute('aria-hidden', 'true')
  })
  ghost.style.width = `${rect.width}px`
  ghost.style.height = `${rect.height}px`
  ghost.style.left = `${rect.left}px`
  ghost.style.top = `${rect.top}px`
  document.body.appendChild(ghost)

  drag = {
    id: doc.id,
    pointerId: event.pointerId,
    startClientY: event.clientY,
    grabOffset: event.clientY - rect.top,
    height: rect.height,
    width: rect.width,
    left: rect.left,
    ghost,
    source,
    handle,
    heights,
    gap,
    originOrder: localDocs.value.map((item) => item.id),
    moved: false,
    lastClientY: event.clientY,
    frame: null,
    keyHandler: (keyEvent: KeyboardEvent) => {
      if (keyEvent.key === 'Escape') {
        keyEvent.preventDefault()
        finishDrag(false)
      }
    },
  }

  dragId.value = doc.id
  source.classList.add('drag-source')
  document.body.classList.add('doc-dragging')
  handle.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', onPointerMove, { passive: false })
  window.addEventListener('pointerup', onPointerUp)
  window.addEventListener('pointercancel', onPointerCancel)
  window.addEventListener('keydown', drag.keyHandler)
  drag.frame = requestAnimationFrame(autoScrollStep)
}

function onPointerMove(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  event.preventDefault()
  drag.lastClientY = event.clientY
  const delta = Math.abs(event.clientY - drag.startClientY)
  if (delta > 4) {
    drag.moved = true
  }
  drag.ghost.style.top = `${event.clientY - drag.grabOffset}px`
  updateTargetIndex()
}

function onPointerUp(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishDrag(true)
}

function onPointerCancel(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishDrag(false)
}

function updateTargetIndex() {
  if (!drag || !listRoot.value) {
    return
  }
  const rootRect = listRoot.value.getBoundingClientRect()
  const ghostCenter =
    drag.lastClientY - drag.grabOffset + drag.height / 2
  const relativeCenter = ghostCenter - rootRect.top
  const others = localDocs.value.filter((item) => item.id !== drag!.id)
  let offset = 0
  let target = 0
  for (const item of others) {
    const height = drag.heights.get(item.id) ?? 60
    if (offset + height / 2 < relativeCenter) {
      target += 1
    }
    offset += height + drag.gap
  }
  const currentIndex = localDocs.value.findIndex(
    (item) => item.id === drag!.id,
  )
  if (currentIndex < 0 || target === currentIndex) {
    return
  }
  localDocs.value = arrayMove(localDocs.value, currentIndex, target)
}

function autoScrollStep() {
  if (!drag) {
    return
  }
  const threshold = 96
  const y = drag.lastClientY
  let speed = 0
  if (y < threshold) {
    speed = -Math.min(18, Math.ceil((threshold - y) / 4))
  } else if (y > window.innerHeight - threshold) {
    speed = Math.min(
      18,
      Math.ceil((y - (window.innerHeight - threshold)) / 4),
    )
  }
  if (speed !== 0) {
    window.scrollBy(0, speed)
    updateTargetIndex()
  }
  drag.frame = requestAnimationFrame(autoScrollStep)
}

function finishDrag(save: boolean) {
  if (!drag) {
    return
  }
  const state = drag
  if (state.frame !== null) {
    cancelAnimationFrame(state.frame)
  }
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  window.removeEventListener('pointercancel', onPointerCancel)
  window.removeEventListener('keydown', state.keyHandler)
  try {
    state.handle.releasePointerCapture?.(state.pointerId)
  } catch {
    // 指针可能已经被浏览器释放
  }
  state.ghost.remove()
  state.source.classList.remove('drag-source')
  document.body.classList.remove('doc-dragging')
  drag = null
  dragId.value = null

  if (!save) {
    const byId = new Map(localDocs.value.map((item) => [item.id, item]))
    localDocs.value = state.originOrder
      .map((id) => byId.get(id))
      .filter((item): item is DocumentSummary => Boolean(item))
    return
  }
  if (!state.moved) {
    return
  }
  const ids = localDocs.value.map((item) => item.id)
  if (ids.join(',') === state.originOrder.join(',')) {
    return
  }
  emit('reorder', ids)
}

function isDragging(docId: number): boolean {
  return dragId.value === docId
}

onBeforeUnmount(() => {
  if (drag) {
    finishDrag(false)
  }
})
</script>

<template>
  <section class="library" :aria-busy="loading">
    <template v-if="loading">
      <p class="sr-only" role="status">正在加载笔记</p>
      <div class="skeleton-list">
        <div v-for="index in 3" :key="index" class="skeleton-row">
          <span class="skeleton-title"></span>
          <span class="skeleton-line"></span>
          <span class="skeleton-line skeleton-line-short"></span>
        </div>
      </div>
    </template>

    <div v-else-if="errorMessage" class="state-card error-card" role="alert">
      <span class="state-icon" aria-hidden="true">
        <svg viewBox="0 0 48 48" fill="none">
          <path
            d="M15 33c-3.3 0-6-2.5-6-5.7 0-3 2.4-5.5 5.5-5.7C15.3 17.9 18.4 16 22 16c4.5 0 8.2 3.5 8.6 7.9 2.6.5 4.4 2.6 4.4 5.1 0 2.9-2.4 5.2-5.5 5.2H15Z"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linejoin="round"
          />
          <path
            d="M13 39 35 17"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
        </svg>
      </span>
      <p class="state-eyebrow">CONNECTION / LOST</p>
      <h2>暂时连不上服务器</h2>
      <p class="state-copy">{{ errorMessage }}</p>
      <button type="button" class="retry-button" @click="emit('retry')">
        重新加载
      </button>
    </div>

    <div
      v-else-if="isEmpty"
      class="state-card empty-card"
      :class="{ favorite: scope === 'favorites' }"
    >
      <div class="empty-art" aria-hidden="true">
        <svg v-if="scope === 'favorites'" viewBox="0 0 180 132" fill="none">
          <path
            d="m90 22 13.4 27.2 30 4.4-21.7 21.1 5.1 29.8L90 90.4 63.2 104.5l5.1-29.8-21.7-21.1 30-4.4L90 22Z"
            fill="#fbf3df"
            stroke="#d9b974"
            stroke-width="1.4"
          />
          <circle cx="35" cy="98" r="2.4" fill="#d9b974" />
          <circle cx="151" cy="76" r="1.8" fill="#e1c894" />
        </svg>
        <svg v-else viewBox="0 0 180 132" fill="none">
          <rect x="35" y="24" width="95" height="78" rx="10" fill="#f4efff" />
          <rect
            x="47"
            y="14"
            width="95"
            height="78"
            rx="10"
            fill="#fff"
            stroke="#ded5f6"
            stroke-width="1.2"
          />
          <path d="M63 36h54" stroke="#c9bdf1" stroke-width="2" stroke-linecap="round" />
          <path d="M63 48h42" stroke="#e1d9f5" stroke-width="2" stroke-linecap="round" />
          <path d="M63 60h48" stroke="#e1d9f5" stroke-width="2" stroke-linecap="round" />
          <path d="M63 72h30" stroke="#e1d9f5" stroke-width="2" stroke-linecap="round" />
          <path
            d="M141 28l2.2 4.5 4.5 2.2-4.5 2.2-2.2 4.5-2.2-4.5-4.5-2.2 4.5-2.2 2.2-4.5Z"
            fill="#7357ff"
            opacity=".7"
          />
          <circle cx="35" cy="99" r="2.4" fill="#b7a7ef" />
          <circle cx="154" cy="82" r="1.8" fill="#cbbdf1" />
        </svg>
      </div>
      <p class="state-eyebrow">
        {{ scope === 'favorites' ? 'FAVORITES / EMPTY' : scope === 'chapter' ? 'CHAPTER / EMPTY' : 'LIBRARY / EMPTY' }}
      </p>
      <h2>{{ emptyTitle }}</h2>
      <p class="state-copy">{{ emptyCopy }}</p>
    </div>

    <template v-else>
      <p v-if="localDocs.length > 1 && !sorting" class="sort-hint">
        <span class="hint-line" aria-hidden="true"></span>
        拖动左侧把手排序；卡片右侧文件夹图标可拖到目录
      </p>
      <div ref="listRoot" class="doc-list-wrap">
        <TransitionGroup
          tag="div"
          name="doclist"
          class="doc-list"
          aria-label="笔记列表"
        >
          <DocumentRow
            v-for="doc in localDocs"
            :key="doc.id"
            :doc="doc"
            :sorting="sorting || isDragging(doc.id)"
            :class="{ 'drag-source': isDragging(doc.id) }"
            :favorite-busy="favoriteBusyId === doc.id"
            @favorite="emit('favorite', $event)"
            @rename="emit('rename', $event)"
            @move="emit('move', $event)"
            @delete="emit('delete', $event)"
            @drag-start="startDrag"
            @move-up="moveByButton($event, -1)"
            @move-down="moveByButton($event, 1)"
          />
        </TransitionGroup>
      </div>
    </template>
  </section>
</template>

<style scoped>
.library {
  display: grid;
  gap: 12px;
}

.sort-hint {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 0 3px;
  color: #9a92ad;
  font-size: 10px;
}

.hint-line {
  width: 18px;
  height: 1px;
  background: linear-gradient(90deg, var(--border-strong), transparent);
}

.doc-list {
  display: grid;
  gap: 9px;
  min-height: 20px;
}

.doclist-move {
  transition: transform 0.26s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.doclist-enter-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.doclist-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.doclist-leave-active {
  position: absolute;
  width: 100%;
}

.doclist-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

:deep(.doc-card.drag-source) {
  opacity: 0.16;
  border-style: dashed;
  border-color: #b8a6ed;
  transform: scale(0.992);
}

:global(.doc-drag-ghost) {
  position: fixed !important;
  z-index: 2000;
  margin: 0 !important;
  pointer-events: none;
  border-color: #c8b8f6 !important;
  background: #fff !important;
  box-shadow: 0 26px 70px -24px rgba(50, 32, 105, 0.5) !important;
  opacity: 0.97;
  transform: rotate(0.6deg) scale(1.012);
  cursor: grabbing;
}

:global(body.doc-dragging) {
  cursor: grabbing;
  user-select: none;
}

.skeleton-list {
  display: grid;
  gap: 9px;
}

.skeleton-row {
  display: grid;
  gap: 12px;
  padding: 21px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.66);
}

.skeleton-title,
.skeleton-line {
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #f0ebfb 20%,
    #f8f5ff 42%,
    #f0ebfb 64%
  );
  background-size: 220% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

.skeleton-title {
  width: min(60%, 280px);
  height: 20px;
}

.skeleton-line {
  width: 86%;
  height: 11px;
}

.skeleton-line-short {
  width: 52%;
}

.state-card {
  display: grid;
  justify-items: center;
  padding: 54px 28px 48px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-lg);
  text-align: center;
  background:
    radial-gradient(260px 160px at 50% 0%, rgba(115, 87, 255, 0.08), transparent 75%),
    rgba(255, 255, 255, 0.58);
  animation: section-in 0.5s ease both;
}

.state-card.favorite {
  border-color: #ead9b4;
  background:
    radial-gradient(280px 170px at 50% 0%, rgba(184, 134, 47, 0.09), transparent 75%),
    rgba(255, 253, 247, 0.7);
}

.state-icon {
  display: grid;
  width: 60px;
  height: 60px;
  margin-bottom: 20px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--accent);
  background: #fff;
  box-shadow: var(--shadow-soft);
}

.state-icon svg {
  width: 40px;
  height: 40px;
}

.empty-art {
  width: min(190px, 60vw);
  margin-bottom: 18px;
}

.state-eyebrow {
  margin-bottom: 10px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.18em;
}

.empty-card.favorite .state-eyebrow {
  color: var(--favorite-gold);
}

.state-card h2 {
  font-size: clamp(20px, 2.2vw, 25px);
  letter-spacing: -0.02em;
}

.state-copy {
  max-width: 380px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}

.error-card .state-copy {
  color: var(--muted-strong);
}

.retry-button {
  margin-top: 22px;
  padding: 10px 20px;
  border: 1px solid #d9cef8;
  border-radius: 999px;
  color: var(--accent-strong);
  font-size: 12.5px;
  font-weight: 650;
  background: #fff;
  box-shadow: 0 10px 24px -18px rgba(84, 54, 232, 0.8);
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.retry-button:hover {
  background: var(--accent-soft);
  box-shadow: 0 14px 28px -18px rgba(84, 54, 232, 0.9);
  transform: translateY(-1px);
}

@keyframes shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@keyframes section-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .state-card {
    padding: 42px 20px 38px;
  }

  .skeleton-row {
    padding: 18px;
  }

  .sort-hint {
    display: none;
  }
}
</style>
