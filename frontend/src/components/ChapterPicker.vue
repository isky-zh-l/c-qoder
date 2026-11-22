<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Chapter } from '../api/types'

const props = defineProps<{
  chapters: Chapter[]
  modelValue: number | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

interface PickerOption {
  id: number | null
  name: string
  count: number | null
}

const open = ref(false)
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const optionElements = ref<HTMLElement[]>([])
const focusIndex = ref(0)

const options = computed<PickerOption[]>(() => [
  { id: null, name: '未分类', count: null },
  ...props.chapters.map((chapter) => ({
    id: chapter.id,
    name: chapter.name,
    count: chapter.document_count,
  })),
])

const selectedLabel = computed(
  () =>
    options.value.find((option) => option.id === props.modelValue)?.name ||
    '未分类',
)

function setOptionRef(element: Element | null, index: number) {
  if (element instanceof HTMLElement) {
    optionElements.value[index] = element
  }
}

function openPicker() {
  if (props.disabled) {
    return
  }
  open.value = true
  const selected = options.value.findIndex(
    (option) => option.id === props.modelValue,
  )
  focusIndex.value = Math.max(0, selected)
  nextTick(() => optionElements.value[focusIndex.value]?.focus())
}

function closePicker(returnFocus = true) {
  open.value = false
  if (returnFocus) {
    nextTick(() => trigger.value?.focus())
  }
}

function selectOption(option: PickerOption | undefined) {
  if (!option) {
    return
  }
  emit('update:modelValue', option.id)
  closePicker()
}

function focusOption(index: number) {
  const count = options.value.length
  focusIndex.value = Math.min(count - 1, Math.max(0, index))
  nextTick(() => optionElements.value[focusIndex.value]?.focus())
}

function onKeydown(event: KeyboardEvent) {
  if (!open.value) {
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    closePicker()
    return
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    selectOption(options.value[focusIndex.value])
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    focusOption(0)
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    focusOption(options.value.length - 1)
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    focusOption(focusIndex.value + 2)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    focusOption(focusIndex.value - 2)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    focusOption(focusIndex.value + 1)
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    focusOption(focusIndex.value - 1)
  }
}

watch(open, (value) => {
  if (value) {
    nextTick(() => panel.value?.focus())
  }
})
</script>

<template>
  <div class="chapter-picker">
    <button
      ref="trigger"
      type="button"
      class="picker-trigger"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="openPicker"
    >
      <span class="trigger-label">章节</span>
      <strong>{{ selectedLabel }}</strong>
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path
          d="m4.5 6.5 3.5 3 3.5-3"
          stroke="currentColor"
          stroke-width="1.3"
          stroke-linecap="round"
        />
      </svg>
    </button>

    <Teleport to="body">
      <Transition name="picker">
        <div v-if="open" class="picker-root">
          <div class="picker-backdrop" @click="closePicker()"></div>
          <section
            ref="panel"
            class="picker-panel"
            role="dialog"
            aria-modal="true"
            aria-label="选择章节"
            @keydown="onKeydown"
          >
            <header class="picker-head">
              <div>
                <p>CHAPTER / SELECT</p>
                <h2>选择章节</h2>
              </div>
              <button
                type="button"
                class="picker-close"
                aria-label="关闭章节菜单"
                @click="closePicker()"
              >
                <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path
                    d="m5 5 8 8M13 5l-8 8"
                    stroke="currentColor"
                    stroke-width="1.4"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
            </header>

            <div class="picker-grid" role="listbox" aria-label="章节">
              <button
                v-for="(option, index) in options"
                :key="option.id ?? 'uncategorized'"
                :ref="(element) => setOptionRef(element as Element | null, index)"
                type="button"
                class="picker-option"
                :class="{
                  selected: option.id === modelValue,
                  focused: index === focusIndex,
                }"
                role="option"
                :aria-selected="option.id === modelValue"
                :tabindex="index === focusIndex ? 0 : -1"
                @focus="focusIndex = index"
                @click="selectOption(option)"
              >
                <span class="option-mark" aria-hidden="true"></span>
                <span class="option-name">{{ option.name }}</span>
                <span v-if="option.count !== null" class="option-count">
                  {{ option.count }}
                </span>
              </button>
            </div>

            <p class="picker-hint">
              方向键移动，Enter 选择，Esc 关闭
            </p>
          </section>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.chapter-picker {
  position: relative;
  flex: none;
}

.picker-trigger {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 230px;
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: 9px;
  color: var(--muted-strong);
  font: inherit;
  background: #fff;
  cursor: pointer;
}

.picker-trigger:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--accent-strong);
}

.picker-trigger:disabled {
  opacity: 0.55;
  cursor: default;
}

.trigger-label {
  color: var(--muted);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.06em;
}

.picker-trigger strong {
  overflow: hidden;
  font-size: 10.5px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker-trigger svg {
  width: 12px;
  height: 12px;
  color: #a29ab5;
}

.picker-root {
  position: fixed;
  inset: 0;
  z-index: 180;
  display: grid;
  place-items: center;
  padding: 18px;
}

.picker-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(33, 27, 51, 0.34);
}

.picker-panel {
  position: relative;
  z-index: 1;
  width: min(500px, 100%);
  max-height: min(80vh, 600px);
  padding: 20px;
  overflow-y: auto;
  border: 1px solid rgba(231, 225, 247, 0.96);
  border-radius: 20px;
  background:
    radial-gradient(240px 160px at 100% 0%, rgba(115, 87, 255, 0.1), transparent 72%),
    #fff;
  box-shadow: 0 30px 80px -30px rgba(33, 27, 51, 0.6);
}

.picker-head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.picker-head p {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 8.5px;
  font-weight: 650;
  letter-spacing: 0.17em;
}

.picker-head h2 {
  margin-top: 3px;
  font-size: 21px;
  letter-spacing: -0.02em;
}

.picker-close {
  display: grid;
  width: 33px;
  height: 33px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 9px;
  color: var(--muted-strong);
  background: #fff;
  cursor: pointer;
}

.picker-close svg {
  width: 15px;
  height: 15px;
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}

.picker-option {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--border);
  border-radius: 11px;
  color: var(--muted-strong);
  font: inherit;
  text-align: left;
  background: #fff;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease;
}

.picker-option:hover,
.picker-option.focused {
  border-color: #cdbdf5;
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.picker-option.selected {
  border-color: #d8ccf7;
  color: var(--accent-strong);
  background: linear-gradient(135deg, var(--accent-soft), #fbf9ff);
  box-shadow: inset 3px 0 0 var(--accent);
}

.option-mark {
  flex: none;
  width: 6px;
  height: 6px;
  border: 1px solid #c9bdf1;
  border-radius: 50%;
}

.picker-option.selected .option-mark {
  border-color: var(--accent);
  background: var(--accent);
}

.option-name {
  flex: 1;
  overflow: hidden;
  font-size: 11px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.option-count {
  flex: none;
  color: #a39bb8;
  font-family: var(--font-mono);
  font-size: 9px;
}

.picker-hint {
  margin-top: 14px;
  color: var(--muted);
  font-size: 9px;
  text-align: center;
}

.picker-enter-active,
.picker-leave-active {
  transition: opacity 0.16s ease;
}

.picker-enter-active .picker-panel,
.picker-leave-active .picker-panel {
  transition: transform 0.2s ease;
}

.picker-enter-from,
.picker-leave-to {
  opacity: 0;
}

.picker-enter-from .picker-panel,
.picker-leave-to .picker-panel {
  transform: translateY(8px) scale(0.98);
}

@media (max-width: 960px) {
  .picker-backdrop {
    backdrop-filter: blur(3px);
  }
}

@media (max-width: 640px) {
  .picker-root {
    align-items: end;
    padding: 0;
  }

  .picker-panel {
    width: 100%;
    max-height: 82vh;
    border-radius: 22px 22px 0 0;
  }

  .picker-trigger {
    max-width: 150px;
  }
}

@media (max-width: 360px) {
  .option-name {
    overflow: visible;
    line-height: 1.35;
    white-space: normal;
  }
}
</style>
