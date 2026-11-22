<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Folder } from '../api/types'

const props = withDefaults(
  defineProps<{
    folders: Folder[]
    selectedFolderId: number | null
    canManage?: boolean
  }>(),
  { canManage: true },
)

const emit = defineEmits<{
  select: [folderId: number]
  create: [parentId: number]
  rename: [folder: Folder]
  delete: [folder: Folder]
  'move-up': [folder: Folder]
  'move-down': [folder: Folder]
}>()

const expanded = ref<Set<number>>(new Set())

const byParent = computed(() => {
  const result = new Map<number, Folder[]>()
  for (const folder of props.folders) {
    const parent = Number(folder.parent_id || 0)
    const list = result.get(parent) || []
    list.push(folder)
    result.set(parent, list)
  }
  for (const list of result.values()) {
    list.sort(
      (a, b) =>
        Number(a.sort_order || 0) - Number(b.sort_order || 0) ||
        a.name.localeCompare(b.name),
    )
  }
  return result
})

const rows = computed(() => {
  const output: Array<{ folder: Folder; depth: number }> = []
  const walk = (parentId: number, depth: number) => {
    for (const folder of byParent.value.get(parentId) || []) {
      output.push({ folder, depth })
      if (expanded.value.has(folder.id)) {
        walk(folder.id, depth + 1)
      }
    }
  }
  walk(0, 0)
  return output
})

const selected = computed(
  () => props.folders.find((folder) => folder.id === props.selectedFolderId) || null,
)
const selectedSiblings = computed(() => {
  if (!selected.value) return []
  return byParent.value.get(Number(selected.value.parent_id || 0)) || []
})
const selectedIndex = computed(() =>
  selected.value ? selectedSiblings.value.findIndex((item) => item.id === selected.value!.id) : -1,
)

function toggle(folder: Folder) {
  const next = new Set(expanded.value)
  if (next.has(folder.id)) next.delete(folder.id)
  else next.add(folder.id)
  expanded.value = next
}

function select(folderId: number) {
  emit('select', folderId)
}

watch(
  () => props.folders.map((folder) => folder.id).join(','),
  () => {
    const ids = new Set(props.folders.map((folder) => folder.id))
    const next = new Set<number>()
    for (const id of expanded.value) {
      if (ids.has(id)) next.add(id)
    }
    if (!expanded.value.size) {
      for (const id of ids) next.add(id)
    }
    expanded.value = next
  },
  { immediate: true },
)
</script>

<template>
  <div class="folder-tree">
    <button
      type="button"
      class="folder-row root"
      :class="{ active: selectedFolderId === 0 }"
      @click="select(0)"
    >
      <span class="folder-glyph" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none">
          <path d="M2.5 4.5h4l1.4 1.6h5.6v6.4H2.5V4.5Z" stroke="currentColor" stroke-width="1.2" />
        </svg>
      </span>
      <span class="folder-name">根目录</span>
      <span class="folder-count">{{ folders.filter((f) => f.parent_id === 0).length }}</span>
    </button>

    <button
      v-for="row in rows"
      :key="row.folder.id"
      type="button"
      class="folder-row"
      :class="{ active: row.folder.id === selectedFolderId }"
      :style="{ paddingLeft: `${10 + row.depth * 14}px` }"
      @click="select(row.folder.id)"
    >
      <span
        v-if="row.folder.child_count > 0"
        class="folder-toggle"
        role="button"
        tabindex="0"
        :aria-label="expanded.has(row.folder.id) ? '收起' : '展开'"
        @click.stop="toggle(row.folder)"
        @keydown.enter.stop="toggle(row.folder)"
      >
        <svg viewBox="0 0 12 12" fill="none" :class="{ open: expanded.has(row.folder.id) }">
          <path d="m4 2.5 3 3.5-3 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
        </svg>
      </span>
      <span v-else class="folder-toggle spacer"></span>
      <span class="folder-glyph" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none">
          <path d="M2.5 4.5h4l1.4 1.6h5.6v6.4H2.5V4.5Z" stroke="currentColor" stroke-width="1.2" />
        </svg>
      </span>
      <span class="folder-name">{{ row.folder.name }}</span>
      <span class="folder-count">{{ row.folder.document_count }}</span>
    </button>

    <div v-if="canManage" class="folder-actions">
      <button
        type="button"
        class="folder-action"
        :title="selected ? '新建子文件夹' : '新建根文件夹'"
        :aria-label="selected ? '新建子文件夹' : '新建根文件夹'"
        @click="emit('create', selected?.id || 0)"
      >
        ＋
      </button>
      <template v-if="selected">
        <button type="button" class="folder-action" title="重命名" aria-label="重命名" @click="emit('rename', selected)">✎</button>
        <button type="button" class="folder-action" title="删除" aria-label="删除" @click="emit('delete', selected)">×</button>
        <button
          type="button"
          class="folder-action"
          title="上移"
          aria-label="上移"
          :disabled="selectedIndex <= 0"
          @click="emit('move-up', selected)"
        >↑</button>
        <button
          type="button"
          class="folder-action"
          title="下移"
          aria-label="下移"
          :disabled="selectedIndex < 0 || selectedIndex >= selectedSiblings.length - 1"
          @click="emit('move-down', selected)"
        >↓</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.folder-tree {
  display: grid;
  gap: 2px;
}

.folder-row {
  display: grid;
  grid-template-columns: 14px 15px minmax(0, 1fr) auto;
  gap: 5px;
  align-items: center;
  width: 100%;
  min-height: 32px;
  padding: 5px 9px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.folder-row.root {
  grid-template-columns: 15px minmax(0, 1fr) auto;
  padding-left: 9px;
}

.folder-row:hover,
.folder-row.active {
  color: var(--accent-strong);
  border-color: var(--border);
  background: rgba(255, 255, 255, 0.78);
}

.folder-row.active {
  border-color: #d7c9fb;
  background: var(--accent-soft);
}

.folder-toggle {
  display: grid;
  width: 14px;
  height: 20px;
  place-items: center;
  color: var(--muted);
  cursor: pointer;
}

.folder-toggle svg {
  width: 11px;
  height: 11px;
  transition: transform 0.16s ease;
}

.folder-toggle svg.open {
  transform: rotate(90deg);
}

.folder-toggle.spacer {
  cursor: default;
}

.folder-glyph {
  color: #a99fc4;
}

.folder-glyph svg {
  width: 15px;
  height: 15px;
}

.folder-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-count {
  color: #aaa2bc;
  font-family: var(--font-mono);
  font-size: 9px;
}

.folder-actions {
  display: flex;
  gap: 3px;
  padding: 4px 6px 2px;
}

.folder-action {
  display: grid;
  width: 26px;
  height: 24px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
}

.folder-action:hover:not(:disabled) {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.folder-action:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
