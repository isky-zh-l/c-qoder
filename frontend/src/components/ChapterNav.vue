<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Chapter, DocumentScope } from '../api/types'

const props = withDefaults(
  defineProps<{
    chapters: Chapter[]
    scope: DocumentScope
    selectedChapterId: number | null
    favoriteCount: number
    libraryCount: number
    canManage?: boolean
  }>(),
  { canManage: true },
)

const emit = defineEmits<{
  'select-library': []
  'select-favorites': []
  'select-chapter': [chapterId: number]
  'create-chapter': []
  'rename-chapter': [chapter: Chapter]
  'delete-chapter': [chapter: Chapter]
  'move-chapter': [chapter: Chapter, direction: -1 | 1]
  'reorder-chapters': [chapterIds: number[]]
}>()

const openMenuId = ref<number | null>(null)
const localChapters = ref<Chapter[]>([])
const chapterListRoot = ref<HTMLElement | null>(null)
const dragId = ref<number | null>(null)

interface ChapterDragState {
  id: number
  pointerId: number
  startClientY: number
  grabOffset: number
  height: number
  ghost: HTMLElement
  source: HTMLElement
  handle: HTMLElement
  heights: Map<number, number>
  gap: number
  originOrder: number[]
  moved: boolean
  lastClientY: number
  frame: number | null
  scrollContainer: HTMLElement | null
  keyHandler: (event: KeyboardEvent) => void
}

let drag: ChapterDragState | null = null

watch(
  () => props.chapters,
  (value) => {
    if (!drag) {
      localChapters.value = value.slice()
    }
  },
  { immediate: true },
)

function arrayMove<T>(items: T[], from: number, to: number): T[] {
  const copy = items.slice()
  const [moved] = copy.splice(from, 1)
  copy.splice(to, 0, moved)
  return copy
}

function chapterRow(chapterId: number): HTMLElement | null {
  return (
    chapterListRoot.value?.querySelector<HTMLElement>(
      `[data-chapter-id="${chapterId}"]`,
    ) ?? null
  )
}

function startChapterDrag(event: PointerEvent, chapter: Chapter) {
  if (!props.canManage || drag || event.button !== 0) {
    return
  }
  const source = chapterRow(chapter.id)
  const handle = event.currentTarget as HTMLElement | null
  if (!source || !handle) {
    return
  }
  const rect = source.getBoundingClientRect()
  const heights = new Map<number, number>()
  for (const item of localChapters.value) {
    const row = chapterRow(item.id)
    if (row) {
      heights.set(item.id, row.getBoundingClientRect().height)
    }
  }
  const listElement =
    chapterListRoot.value?.querySelector<HTMLElement>('.chapter-list') ??
    chapterListRoot.value!
  const gap =
    Number.parseFloat(getComputedStyle(listElement).rowGap || '3') || 3
  const ghost = source.cloneNode(true) as HTMLElement
  ghost.classList.add('chapter-drag-ghost')
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
    id: chapter.id,
    pointerId: event.pointerId,
    startClientY: event.clientY,
    grabOffset: event.clientY - rect.top,
    height: rect.height,
    ghost,
    source,
    handle,
    heights,
    gap,
    originOrder: localChapters.value.map((item) => item.id),
    moved: false,
    lastClientY: event.clientY,
    frame: null,
    scrollContainer:
      (chapterListRoot.value?.closest(
        '.sidebar-section, .sheet-body',
      ) as HTMLElement | null) ?? null,
    keyHandler: (keyEvent: KeyboardEvent) => {
      if (keyEvent.key === 'Escape') {
        keyEvent.preventDefault()
        finishChapterDrag(false)
      }
    },
  }

  openMenuId.value = null
  dragId.value = chapter.id
  source.classList.add('drag-source')
  document.body.classList.add('chapter-dragging')
  handle.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', onChapterPointerMove, {
    passive: false,
  })
  window.addEventListener('pointerup', onChapterPointerUp)
  window.addEventListener('pointercancel', onChapterPointerCancel)
  window.addEventListener('keydown', drag.keyHandler)
  drag.frame = requestAnimationFrame(chapterAutoScrollStep)
}

function onChapterPointerMove(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  event.preventDefault()
  drag.lastClientY = event.clientY
  if (
    Math.abs(event.clientY - drag.startClientY) > 3
  ) {
    drag.moved = true
  }
  drag.ghost.style.top = `${event.clientY - drag.grabOffset}px`
  updateChapterTarget()
}

function onChapterPointerUp(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishChapterDrag(true)
}

function onChapterPointerCancel(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishChapterDrag(false)
}

function updateChapterTarget() {
  if (!drag || !chapterListRoot.value) {
    return
  }
  const rootRect = chapterListRoot.value.getBoundingClientRect()
  const ghostCenter =
    drag.lastClientY - drag.grabOffset + drag.height / 2
  const relativeCenter = ghostCenter - rootRect.top
  const others = localChapters.value.filter((item) => item.id !== drag!.id)
  let offset = 0
  let target = 0
  for (const item of others) {
    const height = drag.heights.get(item.id) ?? 38
    if (offset + height / 2 < relativeCenter) {
      target += 1
    }
    offset += height + drag.gap
  }
  const currentIndex = localChapters.value.findIndex(
    (item) => item.id === drag!.id,
  )
  if (currentIndex < 0 || currentIndex === target) {
    return
  }
  localChapters.value = arrayMove(
    localChapters.value,
    currentIndex,
    target,
  )
}

function chapterAutoScrollStep() {
  if (!drag) {
    return
  }
  const y = drag.lastClientY
  if (drag.scrollContainer) {
    const rect = drag.scrollContainer.getBoundingClientRect()
    const threshold = 44
    let delta = 0
    if (y < rect.top + threshold) {
      delta = -Math.min(12, Math.ceil((rect.top + threshold - y) / 4))
    } else if (y > rect.bottom - threshold) {
      delta = Math.min(12, Math.ceil((y - (rect.bottom - threshold)) / 4))
    }
    if (delta !== 0) {
      drag.scrollContainer.scrollTop += delta
      updateChapterTarget()
    }
  }
  drag.frame = requestAnimationFrame(chapterAutoScrollStep)
}

function finishChapterDrag(save: boolean) {
  if (!drag) {
    return
  }
  const state = drag
  if (state.frame !== null) {
    cancelAnimationFrame(state.frame)
  }
  window.removeEventListener('pointermove', onChapterPointerMove)
  window.removeEventListener('pointerup', onChapterPointerUp)
  window.removeEventListener('pointercancel', onChapterPointerCancel)
  window.removeEventListener('keydown', state.keyHandler)
  try {
    state.handle.releasePointerCapture?.(state.pointerId)
  } catch {
    // 浏览器可能已释放指针
  }
  state.ghost.remove()
  state.source.classList.remove('drag-source')
  document.body.classList.remove('chapter-dragging')
  drag = null
  dragId.value = null

  if (!save) {
    const byId = new Map(
      localChapters.value.map((chapter) => [chapter.id, chapter]),
    )
    localChapters.value = state.originOrder
      .map((id) => byId.get(id))
      .filter((chapter): chapter is Chapter => Boolean(chapter))
    return
  }
  if (!state.moved) {
    return
  }
  const ids = localChapters.value.map((chapter) => chapter.id)
  if (ids.join(',') === state.originOrder.join(',')) {
    return
  }
  emit('reorder-chapters', ids)
}

function onDocumentPointerDown(event: PointerEvent) {
  if (openMenuId.value === null) {
    return
  }
  const target = event.target as Element | null
  if (!target?.closest('.chapter-menu')) {
    openMenuId.value = null
  }
}

function toggleMenu(chapterId: number) {
  openMenuId.value = openMenuId.value === chapterId ? null : chapterId
}

function runMenuAction(action: () => void) {
  openMenuId.value = null
  action()
}

onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown))
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  if (drag) {
    finishChapterDrag(false)
  }
})
</script>

<template>
  <nav class="chapter-nav" aria-label="目录">
    <button
      type="button"
      class="nav-item favorite-entry"
      :class="{ active: scope === 'favorites' }"
      :aria-current="scope === 'favorites' ? 'page' : undefined"
      @click="emit('select-favorites')"
    >
      <span class="favorite-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20">
          <path
            d="m10 2.6 2.1 4.3 4.8.7-3.5 3.4.8 4.7L10 13.5l-4.2 2.2.8-4.7L3.1 7.6l4.8-.7L10 2.6Z"
          />
        </svg>
      </span>
      <span class="nav-copy">
        <strong>收藏</strong>
        <span>独立的金色书架</span>
      </span>
      <span class="nav-count gold">{{ favoriteCount }}</span>
    </button>

    <div class="nav-heading">
      <span class="heading-label">
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <rect x="3" y="3" width="5.5" height="5.5" rx="1.4" />
          <rect x="11.5" y="3" width="5.5" height="5.5" rx="1.4" />
          <rect x="3" y="11.5" width="5.5" height="5.5" rx="1.4" />
          <rect x="11.5" y="11.5" width="5.5" height="5.5" rx="1.4" />
        </svg>
        章节
      </span>
      <span class="heading-count">{{ localChapters.length }}</span>
    </div>

    <ul class="chapter-list">
      <li>
        <button
          type="button"
          class="nav-item"
          :class="{ active: scope === 'library' }"
          :aria-current="scope === 'library' ? 'page' : undefined"
          @click="emit('select-library')"
        >
          <span class="item-dot"></span>
          <span class="item-name">全部笔记</span>
          <span class="nav-count">{{ libraryCount }}</span>
        </button>
      </li>
    </ul>

    <div ref="chapterListRoot" class="chapter-list-wrap">
      <TransitionGroup
        tag="ul"
        name="chapter-list"
        class="chapter-list"
        aria-label="章节排序列表"
      >
        <li
          v-for="(chapter, index) in localChapters"
          :key="chapter.id"
          class="chapter-item"
          :data-chapter-id="chapter.id"
          :class="{
            'menu-open': openMenuId === chapter.id,
            'drag-source': dragId === chapter.id,
          }"
        >
          <button
            v-if="canManage"
            type="button"
            class="chapter-drag-handle"
            :aria-label="`拖动章节 ${chapter.name}`"
            title="拖动排序"
            @pointerdown.stop.prevent="startChapterDrag($event, chapter)"
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

          <button
            type="button"
            class="nav-item chapter-main"
            :class="{
              active:
                scope === 'chapter' && selectedChapterId === chapter.id,
              'with-drag': canManage,
            }"
            :aria-current="
              scope === 'chapter' && selectedChapterId === chapter.id
                ? 'page'
                : undefined
            "
            @click="emit('select-chapter', chapter.id)"
          >
            <span class="item-dot"></span>
            <span class="item-name">{{ chapter.name }}</span>
            <span class="nav-count">{{ chapter.document_count }}</span>
          </button>

          <div v-if="canManage" class="chapter-menu">
            <button
              type="button"
              class="chapter-menu-trigger"
              :aria-label="`管理章节 ${chapter.name}`"
              :aria-expanded="openMenuId === chapter.id"
              @click.stop="toggleMenu(chapter.id)"
            >
              <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <circle cx="3" cy="8" r="1.2" />
                <circle cx="8" cy="8" r="1.2" />
                <circle cx="13" cy="8" r="1.2" />
              </svg>
            </button>
            <Transition name="pop">
              <div v-if="openMenuId === chapter.id" class="chapter-menu-pop">
                <button
                  type="button"
                  @click="
                    runMenuAction(() => emit('rename-chapter', chapter))
                  "
                >
                  重命名
                </button>
                <button
                  type="button"
                  :disabled="index === 0"
                  @click="
                    runMenuAction(() => emit('move-chapter', chapter, -1))
                  "
                >
                  上移
                </button>
                <button
                  type="button"
                  :disabled="index === localChapters.length - 1"
                  @click="
                    runMenuAction(() => emit('move-chapter', chapter, 1))
                  "
                >
                  下移
                </button>
                <button
                  type="button"
                  class="danger"
                  @click="
                    runMenuAction(() => emit('delete-chapter', chapter))
                  "
                >
                  删除章节
                </button>
              </div>
            </Transition>
          </div>
        </li>
      </TransitionGroup>
    </div>

    <button
      v-if="canManage"
      type="button"
      class="add-chapter"
      @click="emit('create-chapter')"
    >
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="M8 3v10M3 8h10"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
        />
      </svg>
      新建章节
    </button>

    <p v-if="!localChapters.length" class="chapter-empty">
      还没有章节。新建一个，或直接把笔记放进“全部笔记”。
    </p>
  </nav>
</template>

<style scoped>
.chapter-nav {
  display: grid;
  gap: 5px;
  min-height: 0;
}

.nav-item {
  display: flex;
  gap: 9px;
  align-items: center;
  width: 100%;
  padding: 10px 10px;
  border: 1px solid transparent;
  border-radius: 11px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12.5px;
  text-align: left;
  background: transparent;
  cursor: pointer;
  transition:
    color 0.18s ease,
    background 0.18s ease,
    border-color 0.18s ease,
    transform 0.18s ease;
}

.nav-item:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.72);
  transform: translateX(2px);
}

.nav-item.active {
  border-color: #e3dbff;
  color: var(--accent-strong);
  font-weight: 650;
  background: linear-gradient(90deg, var(--accent-soft), #faf8ff);
  box-shadow: inset 3px 0 0 var(--accent);
}

.favorite-entry {
  gap: 11px;
  padding: 12px 11px;
  border-color: #eddfc0;
  color: #8b6424;
  background:
    radial-gradient(120px 80px at 100% 0%, rgba(255, 255, 255, 0.7), transparent 75%),
    var(--favorite-gold-soft);
  box-shadow: 0 10px 26px -24px rgba(134, 94, 20, 0.55);
}

.favorite-entry:hover,
.favorite-entry.active {
  border-color: #debf82;
  color: #745017;
  background:
    radial-gradient(120px 80px at 100% 0%, rgba(255, 255, 255, 0.76), transparent 75%),
    #f8eed7;
  box-shadow:
    inset 3px 0 0 var(--favorite-gold),
    0 12px 28px -24px rgba(134, 94, 20, 0.65);
}

.favorite-icon {
  display: grid;
  flex: none;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid rgba(184, 134, 47, 0.25);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.66);
}

.favorite-icon svg {
  width: 15px;
  height: 15px;
  fill: currentColor;
}

.nav-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.nav-copy strong {
  font-size: 12.5px;
  font-weight: 750;
}

.nav-copy span {
  color: #aa8a51;
  font-size: 9.5px;
}

.nav-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
  margin-top: 10px;
  margin-bottom: 4px;
}

.heading-label {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  color: var(--muted-strong);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.heading-label svg {
  width: 14px;
  height: 14px;
  stroke: var(--accent);
  stroke-width: 1.4;
}

.heading-count {
  min-width: 22px;
  padding: 2px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9.5px;
  text-align: center;
  background: rgba(255, 255, 255, 0.62);
}

.chapter-list-wrap {
  display: grid;
  gap: 3px;
}

.chapter-list {
  display: grid;
  gap: 3px;
}

.chapter-list-move {
  transition: transform 0.24s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.item-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border: 1px solid #c9bdf1;
  border-radius: 50%;
  background: transparent;
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.nav-item.active .item-dot {
  border-color: var(--accent);
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(115, 87, 255, 0.1);
}

.item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-item .nav-count {
  margin-left: auto;
}

.nav-count {
  flex: none;
  min-width: 20px;
  color: #a39bb8;
  font-family: var(--font-mono);
  font-size: 9.5px;
  text-align: right;
}

.nav-count.gold {
  color: var(--favorite-gold);
}

.nav-item.active .nav-count {
  color: var(--accent-strong);
}

.favorite-entry.active .nav-count {
  color: #805a1c;
}

.chapter-item {
  position: relative;
}

.chapter-main {
  padding-right: 34px;
}

.chapter-main.with-drag {
  padding-left: 22px;
}

.chapter-drag-handle {
  position: absolute;
  top: 50%;
  left: 1px;
  z-index: 2;
  display: grid;
  width: 18px;
  height: 28px;
  place-items: center;
  border: 0;
  border-radius: 5px;
  color: #c2b5e4;
  background: transparent;
  cursor: grab;
  opacity: 0;
  touch-action: none;
  transform: translateY(-50%);
  transition:
    opacity 0.15s ease,
    color 0.15s ease,
    background 0.15s ease;
}

.chapter-drag-handle svg {
  width: 10px;
  height: 16px;
}

.chapter-item:hover .chapter-drag-handle,
.chapter-item:focus-within .chapter-drag-handle {
  opacity: 1;
}

.chapter-drag-handle:hover {
  color: var(--accent);
  background: var(--accent-faint);
}

.chapter-item.drag-source {
  opacity: 0.16;
}

.chapter-item.drag-source .chapter-main {
  border-style: dashed;
  border-color: #b8a6ed;
}

:global(.chapter-drag-ghost) {
  position: fixed;
  z-index: 2000;
  margin: 0;
  pointer-events: none;
  border: 1px solid #d8ccf7;
  border-radius: 11px;
  background: #fff;
  box-shadow: 0 20px 50px -20px rgba(33, 27, 51, 0.55);
  opacity: 0.97;
  transform: rotate(0.5deg) scale(1.01);
}

:global(body.chapter-dragging) {
  cursor: grabbing;
  user-select: none;
}

.chapter-menu {
  position: absolute;
  top: 50%;
  right: 3px;
  transform: translateY(-50%);
}

.chapter-menu-trigger {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 7px;
  color: #a39bb8;
  background: transparent;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.chapter-menu-trigger svg {
  width: 13px;
  height: 13px;
}

.chapter-item:hover .chapter-menu-trigger,
.chapter-item.menu-open .chapter-menu-trigger,
.chapter-menu-trigger:focus-visible {
  opacity: 1;
}

.chapter-menu-trigger:hover,
.chapter-item.menu-open .chapter-menu-trigger {
  border-color: var(--border);
  color: var(--accent-strong);
  background: #fff;
}

.chapter-menu-pop {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 15;
  width: 124px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 16px 34px -22px rgba(33, 27, 51, 0.5);
}

.chapter-menu-pop button {
  display: block;
  width: 100%;
  padding: 7px 9px;
  border: 0;
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.chapter-menu-pop button:hover:not(:disabled) {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.chapter-menu-pop button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chapter-menu-pop button.danger {
  color: #b44d4d;
}

.chapter-menu-pop button.danger:hover {
  background: #fff1f1;
}

.add-chapter {
  display: flex;
  gap: 7px;
  align-items: center;
  justify-content: center;
  margin-top: 7px;
  padding: 8px;
  border: 1px dashed var(--border-strong);
  border-radius: 9px;
  color: var(--muted);
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  transition:
    color 0.18s ease,
    border-color 0.18s ease,
    background 0.18s ease;
}

.add-chapter:hover {
  border-color: #cdbdf5;
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.add-chapter svg {
  width: 13px;
  height: 13px;
}

.chapter-empty {
  padding: 12px;
  border: 1px dashed var(--border-strong);
  border-radius: 9px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
  text-align: center;
  background: rgba(255, 255, 255, 0.42);
}

.pop-enter-active,
.pop-leave-active {
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(-3px) scale(0.97);
}

@media (hover: none) {
  .chapter-menu-trigger,
  .chapter-drag-handle {
    opacity: 1;
  }
}
</style>
