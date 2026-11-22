<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { DocumentSummary } from '../api/types'

const props = withDefaults(
  defineProps<{
    doc: DocumentSummary
    canReorder?: boolean
    sorting?: boolean
    favoriteBusy?: boolean
  }>(),
  {
    canReorder: true,
    sorting: false,
    favoriteBusy: false,
  },
)

const emit = defineEmits<{
  favorite: [doc: DocumentSummary]
  rename: [doc: DocumentSummary]
  move: [doc: DocumentSummary]
  delete: [doc: DocumentSummary]
  'drag-start': [event: PointerEvent, doc: DocumentSummary]
  'move-up': [doc: DocumentSummary]
  'move-down': [doc: DocumentSummary]
}>()

const menuOpen = ref(false)
const menuRoot = ref<HTMLElement | null>(null)

const kindLabel = computed(() => {
  if (props.doc.kind === 'note') {
    return '笔记'
  }
  if (props.doc.language === 'c') {
    return 'C 源码'
  }
  if (props.doc.language === 'h') {
    return 'H 源码'
  }
  return '源码'
})

const kindClass = computed(() =>
  props.doc.kind === 'source' ? 'kind-source' : 'kind-note',
)

const formattedTime = computed(() => {
  const date = new Date(props.doc.updated_at)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`
})

const languageLabel = computed(() => {
  if (props.doc.kind === 'note') {
    return 'MD'
  }
  return props.doc.language === 'h' ? 'H' : 'C'
})

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function runAction(action: () => void) {
  closeMenu()
  action()
}

function startFolderDrag(event: DragEvent) {
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('application/x-cqoder-document', String(props.doc.id))
  event.dataTransfer.setData('text/plain', props.doc.title)
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!menuOpen.value || !menuRoot.value) {
    return
  }
  if (!menuRoot.value.contains(event.target as Node)) {
    closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown)
})
</script>

<template>
  <article
    class="doc-card v2"
    :class="[kindClass, { 'is-sorting': sorting }]"
    :data-doc-id="doc.id"
  >
    <RouterLink
      class="doc-main"
      :to="{ name: 'document', params: { id: doc.id } }"
    >
      <span class="doc-icon" aria-hidden="true">
        <svg v-if="doc.kind === 'note'" viewBox="0 0 20 20" fill="none">
          <path
            d="M5 2.8h6.2L15 6.6v10.6H5z"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
          <path
            d="M11 3v4h4M7.5 10h5M7.5 12.6h4"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
        <svg v-else viewBox="0 0 20 20" fill="none">
          <path
            d="m7.5 6-4 4 4 4M12.5 6l4 4-4 4"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>

      <div class="doc-copy">
        <div class="doc-heading">
          <h3 class="doc-title">{{ doc.title }}</h3>
          <span class="kind-tag">{{ kindLabel }}</span>
          <span v-if="doc.visibility === 'public'" class="kind-tag public">
            公开
          </span>
        </div>
        <p v-if="doc.summary" class="doc-summary">{{ doc.summary }}</p>
        <p v-else class="doc-summary empty-summary">
          {{ doc.kind === 'note' ? '还没有正文' : '源码文档' }}
        </p>
        <div class="doc-meta">
          <span class="doc-chapter">{{ doc.chapter_name || '未分类' }}</span>
          <span v-if="doc.folder_path" class="meta-folder">
            / {{ doc.folder_path }}
          </span>
          <span class="meta-dot" aria-hidden="true"></span>
          <time :datetime="doc.updated_at">{{ formattedTime }}</time>
          <span class="meta-lang">{{ languageLabel }}</span>
        </div>
      </div>
    </RouterLink>

    <div class="doc-side">
      <button
        type="button"
        class="icon-button star-button"
        :class="{ active: doc.is_favorite }"
        :disabled="favoriteBusy"
        :aria-pressed="doc.is_favorite"
        :aria-label="doc.is_favorite ? '取消收藏' : '收藏'"
        :title="doc.is_favorite ? '取消收藏' : '收藏'"
        @click.stop="emit('favorite', doc)"
      >
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="m10 2.6 2.1 4.3 4.8.7-3.5 3.4.8 4.7L10 13.5l-4.2 2.2.8-4.7L3.1 7.6l4.8-.7L10 2.6Z"
          />
        </svg>
      </button>

      <button
        type="button"
        class="icon-button folder-drag-button"
        draggable="true"
        aria-label="拖到文件夹"
        title="拖到文件夹"
        @dragstart="startFolderDrag"
      >
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M3 5.5h5l1.7 2H17v8H3v-10Z"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linejoin="round"
          />
        </svg>
      </button>

      <div ref="menuRoot" class="doc-menu">
        <button
          type="button"
          class="icon-button"
          :aria-expanded="menuOpen"
          :aria-label="`管理 ${doc.title}`"
          title="更多操作"
          @click.stop="toggleMenu"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <circle cx="3" cy="8" r="1.2" />
            <circle cx="8" cy="8" r="1.2" />
            <circle cx="13" cy="8" r="1.2" />
          </svg>
        </button>

        <Transition name="menu">
          <div v-if="menuOpen" class="doc-menu-pop" role="menu">
            <button type="button" @click="runAction(() => emit('rename', doc))">
              重命名
            </button>
            <button type="button" @click="runAction(() => emit('move', doc))">
              移动到文件夹
            </button>
            <button
              type="button"
              class="danger"
              @click="runAction(() => emit('delete', doc))"
            >
              移入回收站
            </button>
          </div>
        </Transition>
      </div>

      <button
        v-if="canReorder"
        type="button"
        class="drag-handle"
        :disabled="sorting"
        :aria-label="`拖动排序 ${doc.title}`"
        title="拖动排序"
        @pointerdown.stop.prevent="emit('drag-start', $event, doc)"
      >
        <svg viewBox="0 0 14 20" fill="currentColor" aria-hidden="true">
          <circle cx="4" cy="5" r="1.1" />
          <circle cx="10" cy="5" r="1.1" />
          <circle cx="4" cy="10" r="1.1" />
          <circle cx="10" cy="10" r="1.1" />
          <circle cx="4" cy="15" r="1.1" />
          <circle cx="10" cy="15" r="1.1" />
        </svg>
      </button>
    </div>

    <div v-if="canReorder" class="sort-controls" aria-label="排序按钮">
      <button
        type="button"
        class="icon-button"
        :disabled="sorting"
        :aria-label="`上移 ${doc.title}`"
        title="上移"
        @click.stop="emit('move-up', doc)"
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
        class="icon-button"
        :disabled="sorting"
        :aria-label="`下移 ${doc.title}`"
        title="下移"
        @click.stop="emit('move-down', doc)"
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
    </div>
  </article>
</template>

<style scoped>
.doc-card {
  position: relative;
  display: flex;
  gap: 10px;
  align-items: stretch;
  min-width: 0;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 36px -34px rgba(61, 42, 120, 0.6);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    opacity 0.2s ease,
    transform 0.2s ease;
}

.doc-card::before {
  position: absolute;
  top: 16px;
  bottom: 16px;
  left: 0;
  width: 2px;
  border-radius: 999px;
  background: var(--accent);
  opacity: 0;
  content: "";
  transition: opacity 0.2s ease;
}

.doc-card:hover {
  border-color: #dcd2fb;
  box-shadow: var(--shadow-lift);
  transform: translateY(-1px);
}

.doc-card:hover::before {
  opacity: 0.85;
}

.doc-card.is-sorting {
  pointer-events: none;
}

.kind-source::before {
  background: #5d8bc8;
}

.drag-handle {
  display: grid;
  flex: none;
  width: 24px;
  place-items: center;
  margin: 7px 0 7px 2px;
  border: 0;
  border-radius: 7px;
  color: #c3bad6;
  background: transparent;
  cursor: grab;
  touch-action: none;
  transition:
    color 0.16s ease,
    background 0.16s ease;
}

.drag-handle:hover {
  color: var(--accent);
  background: var(--accent-faint);
}

.drag-handle:active {
  cursor: grabbing;
}

.drag-handle:disabled {
  opacity: 0.35;
  cursor: default;
}

.drag-handle svg {
  width: 12px;
  height: 18px;
}

.doc-main {
  display: block;
  flex: 1;
  min-width: 0;
  padding: 15px 4px 14px 2px;
  color: inherit;
}

.doc-main:hover {
  color: inherit;
}

.doc-topline {
  display: flex;
  gap: 7px;
  align-items: center;
  min-height: 19px;
  margin-bottom: 7px;
}

.kind-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.kind-note .kind-badge {
  border-color: #e4dcff;
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.kind-source .kind-badge {
  border-color: #dbe9fb;
  color: var(--source-text);
  background: var(--source-badge);
}

.favorite-mark {
  display: inline-grid;
  width: 17px;
  height: 17px;
  place-items: center;
  color: var(--favorite-gold);
}

.favorite-mark svg {
  width: 13px;
  height: 13px;
  fill: currentColor;
}

.visibility-badge {
  padding: 2px 6px;
  border-radius: 999px;
  color: #8e86a1;
  font-size: 9px;
  font-weight: 650;
  background: #f4f1fa;
}

.visibility-badge.public {
  color: #3c7a58;
  background: #edf8f1;
}

.doc-title {
  overflow-wrap: anywhere;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.45;
}

.doc-summary {
  display: -webkit-box;
  margin-top: 6px;
  overflow: hidden;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.empty-summary {
  color: #a39bb8;
  font-style: italic;
}

.doc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  margin-top: 10px;
  color: #938ba8;
  font-size: 10.5px;
}

.meta-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.doc-side {
  position: relative;
  display: flex;
  flex: none;
  gap: 1px;
  align-items: flex-start;
  padding: 9px 6px 0 0;
}

.icon-button {
  display: grid;
  width: 29px;
  height: 29px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #aaa2bd;
  background: transparent;
  cursor: pointer;
  transition:
    color 0.16s ease,
    border-color 0.16s ease,
    background 0.16s ease;
}

.icon-button svg {
  width: 14px;
  height: 14px;
}

.icon-button:hover:not(:disabled) {
  border-color: var(--border);
  color: var(--accent-strong);
  background: #fff;
}

.icon-button:disabled {
  opacity: 0.45;
  cursor: default;
}

.star-button {
  color: #b3aabc;
}

.star-button svg {
  fill: transparent;
  stroke: currentColor;
  stroke-width: 1.25;
}

.star-button.active {
  color: var(--favorite-gold);
  background: var(--favorite-gold-soft);
}

.star-button.active svg {
  fill: currentColor;
  stroke: currentColor;
}

.folder-drag-button {
  color: #9a91ad;
  cursor: grab;
}

.folder-drag-button:active {
  cursor: grabbing;
}

@media (hover: none) {
  .folder-drag-button {
    display: none;
  }
}

.doc-menu {
  position: relative;
}

.doc-menu-pop {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 20;
  width: 132px;
  padding: 5px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 16px 34px -20px rgba(33, 27, 51, 0.5);
}

.doc-menu-pop button {
  display: block;
  width: 100%;
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.doc-menu-pop button:hover {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.doc-menu-pop button.danger {
  color: #b44d4d;
}

.doc-menu-pop button.danger:hover {
  background: #fff1f1;
}

.sort-controls {
  display: grid;
  flex: none;
  gap: 1px;
  align-content: center;
  padding-right: 3px;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.doc-card:hover .sort-controls,
.doc-card:focus-within .sort-controls {
  opacity: 1;
}

.sort-controls .icon-button {
  width: 24px;
  height: 22px;
}

@media (max-width: 960px) {
  .doc-card {
    gap: 7px;
  }

  .doc-main {
    padding: 13px 0 12px;
  }

  .doc-side {
    padding: 6px 3px 0 0;
    gap: 2px;
  }

  .icon-button {
    width: 36px;
    height: 36px;
    border-radius: 10px;
  }

  .icon-button svg {
    width: 16px;
    height: 16px;
  }
}

.sort-controls .icon-button svg {
  width: 12px;
  height: 12px;
}

.menu-enter-active,
.menu-leave-active {
  transition:
    opacity 0.14s ease,
    transform 0.14s ease;
}

.menu-enter-from,
.menu-leave-to {
  opacity: 0;
  transform: translateY(-3px) scale(0.98);
}

@media (max-width: 700px) {
  .doc-card {
    gap: 4px;
    padding: 3px;
  }

  .drag-handle {
    width: 20px;
    margin-left: 0;
  }

  .doc-main {
    padding: 14px 3px 13px 1px;
  }

  .doc-side {
    padding-top: 7px;
  }

  .sort-controls {
    opacity: 1;
  }

  .sort-controls .icon-button {
    width: 22px;
  }

  .doc-title {
    font-size: 15px;
  }
}

@media (hover: none) {
  .sort-controls {
    opacity: 1;
  }
}

/* Reference-style file card */
.doc-card.v2 {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 0;
  overflow: hidden;
  border: 1px solid #e7e3f1;
  border-radius: 13px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(76, 55, 130, 0.05);
}

.doc-card.v2::before {
  content: none;
}

.doc-card.v2 .doc-main {
  display: flex;
  flex: 1 1 auto;
  gap: 14px;
  align-items: flex-start;
  min-width: 0;
  padding: 16px 10px 16px 16px;
}

.doc-card.v2 .doc-icon {
  display: grid;
  flex: 0 0 42px;
  place-items: center;
  height: 42px;
  border-radius: 11px;
  color: #5437bd;
  background: #eee8ff;
}

.doc-card.v2.kind-source .doc-icon {
  color: #325a99;
  background: #e9f1ff;
}

.doc-card.v2 .doc-icon svg {
  width: 21px;
  height: 21px;
}

.doc-card.v2 .doc-copy {
  flex: 1 1 auto;
  min-width: 0;
}

.doc-card.v2 .doc-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
}

.doc-card.v2 .doc-title {
  margin: 0;
  color: #2f2745;
  font-size: 18px;
  font-weight: 720;
  line-height: 1.42;
  overflow-wrap: anywhere;
}

.doc-card.v2 .kind-tag {
  flex: none;
  padding: 2px 6px;
  border-radius: 4px;
  color: #5437bd;
  background: #eee8ff;
  font-size: 11px;
  font-weight: 620;
  line-height: 1.45;
}

.doc-card.v2.kind-source .kind-tag {
  color: #325a99;
  background: #e9f1ff;
}

.doc-card.v2 .kind-tag.public {
  color: #3e7059;
  background: #e9f5ee;
}

.doc-card.v2 .doc-summary {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin: 6px 0 0;
  color: #636178;
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.doc-card.v2 .empty-summary {
  color: #9a93ab;
}

.doc-card.v2 .doc-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 3px 9px;
  margin-top: 8px;
  color: #8a839c;
  font-size: 12px;
}

.doc-card.v2 .doc-chapter {
  color: #5437bd;
  font-weight: 640;
}

.doc-card.v2.kind-source .doc-chapter {
  color: #325a99;
}

.doc-card.v2 .doc-side {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
  padding: 0 8px 0 0;
}

.doc-card.v2 .drag-handle {
  position: static;
  width: 30px;
  height: 42px;
  opacity: 0.55;
}

.doc-card.v2 .icon-button {
  width: 32px;
  height: 32px;
}

@media (max-width: 700px) {
  .doc-card.v2 .doc-icon {
    flex-basis: 36px;
    height: 36px;
    border-radius: 9px;
  }

  .doc-card.v2 .doc-icon svg {
    width: 18px;
    height: 18px;
  }

  .doc-card.v2 .doc-main {
    gap: 11px;
    padding: 14px 6px 14px 13px;
  }

  .doc-card.v2 .doc-title {
    font-size: 15.5px;
  }

  .doc-card.v2 .doc-summary {
    font-size: 12.5px;
  }

  .doc-card.v2 .doc-side {
    padding-right: 4px;
  }

  .doc-card.v2 .drag-handle {
    display: none;
  }
}
/* Legacy file card */
.doc-card.v2 {
  position: relative;
  align-items: center;
  border-color: #e7e3f1;
  border-radius: 13px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(76, 55, 130, 0.05);
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.doc-card.v2:hover {
  transform: translateY(-2px);
  border-color: #cbbcf0;
  box-shadow: 0 12px 26px -20px rgba(73, 55, 119, 0.42);
}

.doc-card.v2::after {
  position: absolute;
  top: 20px;
  bottom: 20px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
  opacity: 0;
  content: "";
  transition: opacity 0.18s ease;
}

.doc-card.v2.kind-source::after {
  background: #4f7fbf;
}

.doc-card.v2:hover::after {
  opacity: 0.9;
}

.doc-card.v2 .doc-main {
  align-items: center;
  gap: 16px;
  padding: 20px 10px 20px 20px;
}

.doc-card.v2 .doc-icon {
  flex-basis: 52px;
  height: 52px;
  border-radius: 13px;
  color: #5437bd;
  background: #eee8ff;
}

.doc-card.v2.kind-source .doc-icon {
  color: #3f6fae;
  background: #eaf1fb;
}

.doc-card.v2 .doc-icon svg {
  width: 24px;
  height: 24px;
}

.doc-card.v2 .doc-title {
  color: #2f2745;
  font-size: 20px;
  font-weight: 720;
  letter-spacing: -0.015em;
  line-height: 1.3;
}

.doc-card.v2 .doc-heading {
  gap: 4px 9px;
}

.doc-card.v2 .kind-tag {
  padding: 2px 7px;
  border-radius: 5px;
  color: #5437bd;
  background: #eee8ff;
  font-size: 11px;
  font-weight: 650;
}

.doc-card.v2.kind-source .kind-tag {
  color: #325a99;
  background: #e9f1ff;
}

.doc-card.v2 .doc-summary {
  display: none;
}

.doc-card.v2 .doc-meta {
  gap: 3px 8px;
  margin-top: 6px;
  color: #8a839c;
  font-size: 12.5px;
}

.doc-card.v2 .doc-chapter {
  color: #5437bd;
  font-weight: 650;
}

.doc-card.v2.kind-source .doc-chapter {
  color: #325a99;
}

.doc-card.v2 .meta-lang {
  font-family: var(--font-mono);
  font-size: 11.5px;
  letter-spacing: 0.02em;
}

.doc-card.v2 .meta-folder {
  color: #8a839c;
}

.doc-card.v2 .doc-side {
  align-items: center;
  gap: 2px;
  padding: 0 12px 0 0;
}

.doc-card.v2 .star-button {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  color: #a9a0bb;
}

.doc-card.v2 .star-button:hover {
  color: var(--favorite-gold);
  background: #fbf3df;
}

.doc-card.v2 .star-button.active {
  color: var(--favorite-gold);
  background: #fbf3df;
}

.doc-card.v2 .doc-menu .icon-button {
  width: 36px;
  height: 36px;
  border-radius: 9px;
}

.doc-card.v2 .doc-menu .icon-button svg {
  transform: rotate(90deg);
}

.doc-card.v2 .folder-drag-button {
  display: none;
}

.doc-card.v2 .drag-handle {
  width: 18px;
  height: 44px;
  margin-left: 0;
  opacity: 0;
  transition: opacity 0.16s ease;
}

.doc-card.v2:hover .drag-handle,
.doc-card.v2:focus-within .drag-handle {
  opacity: 0.45;
}

.doc-card.v2 .sort-controls {
  position: absolute;
  right: 12px;
  bottom: 3px;
  padding: 0;
  opacity: 0;
}

.doc-card.v2:hover .sort-controls,
.doc-card.v2:focus-within .sort-controls {
  opacity: 1;
}

.doc-card.v2 .sort-controls .icon-button {
  width: 22px;
  height: 18px;
}

@media (max-width: 700px) {
  .doc-card.v2 .doc-main {
    gap: 12px;
    padding: 15px 8px 15px 14px;
  }

  .doc-card.v2 .doc-icon {
    flex-basis: 42px;
    height: 42px;
    border-radius: 11px;
  }

  .doc-card.v2 .doc-icon svg {
    width: 20px;
    height: 20px;
  }

  .doc-card.v2 .doc-title {
    font-size: 17px;
  }

  .doc-card.v2 .doc-meta {
    font-size: 11.5px;
  }

  .doc-card.v2 .doc-side {
    padding-right: 4px;
  }

  .doc-card.v2 .star-button,
  .doc-card.v2 .doc-menu .icon-button {
    width: 32px;
    height: 32px;
  }
}
</style>
