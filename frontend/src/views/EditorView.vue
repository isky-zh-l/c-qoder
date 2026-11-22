<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import {
  onBeforeRouteLeave,
  onBeforeRouteUpdate,
  useRoute,
  useRouter,
} from 'vue-router'
import {
  ApiError,
  documentDownloadUrl,
  getDocument,
  getWorkspace,
  saveDocumentBlocks,
  uploadAsset,
} from '../api/client'
import { authState, clearSession } from '../auth/session'
import type { DocumentBlock, DocumentDetail, Workspace } from '../api/types'
import { siteTitle } from '../site'
import {
  createEditorModule,
  documentToModules,
  isTextModule,
  moduleKey,
  modulesToBlockInputs,
  modulesToPreviewBlocks,
  type EditorModule,
  type EditorModuleType,
} from '../utils/editorModel'
import { sourceFromModules } from '../utils/source'
import { beginProgress, endProgress } from '../utils/progress'
import ChapterPicker from '../components/ChapterPicker.vue'
import DocumentBlocks from '../components/DocumentBlocks.vue'
import EditorModuleCard from '../components/EditorModuleCard.vue'
import EditorToolbar from '../components/EditorToolbar.vue'
import InlineFormulaDialog from '../components/InlineFormulaDialog.vue'
import LinkDialog from '../components/LinkDialog.vue'
import ModalShell from '../components/ModalShell.vue'
import AiPolishEntry from '../features/aiPolish/AiPolishEntry.vue'

const route = useRoute()
const router = useRouter()

const workspace = ref<Workspace | null>(null)
const document = ref<DocumentDetail | null>(null)
const modules = ref<EditorModule[]>([])
const title = ref('')
const chapterId = ref<number | null>(null)
const version = ref(1)
const loading = ref(true)
const loadError = ref('')
const saveError = ref('')
const saving = ref(false)
const refreshingVersion = ref(false)
const uploadedModuleKey = ref<string | null>(null)

const previewOpen = ref(false)
const linkOpen = ref(false)
const formulaOpen = ref(false)
const exitPromptOpen = ref(false)
const exitSaving = ref(false)
const switchPromptOpen = ref(false)
const switchSaving = ref(false)
let pendingSwitchTarget: string | null = null
const allowLeave = ref(false)
let pendingExitTarget:
  | { name: 'document'; params: { id: string | number } }
  | null = null
const linkInitialLabel = ref('')
const loaded = ref(false)
const activeModuleKey = ref<string | null>(null)
const activeTextarea = ref<HTMLTextAreaElement | null>(null)
const moduleListRoot = ref<HTMLElement | null>(null)
const dragKey = ref<string | null>(null)
const savedSnapshot = ref('')
const historyPast = ref<string[]>([])
const historyFuture = ref<string[]>([])
let dragHistorySnapshot: string | null = null

const toast = ref<{
  id: number
  tone: 'success' | 'error' | 'info'
  message: string
} | null>(null)
let toastTimer: number | null = null
let toastId = 0
let loadToken = 0
let saveRequestId = 0

interface PendingSelection {
  key: string
  start: number
  end: number
  selected: string
}

const pendingLink = ref<PendingSelection | null>(null)
const pendingFormula = ref<PendingSelection | null>(null)

const chapters = computed(() => workspace.value?.chapters ?? [])
const previewBlocks = computed<DocumentBlock[]>(() =>
  modulesToPreviewBlocks(modules.value),
)
const editorMode = computed<'note' | 'source'>(() =>
  document.value?.kind === 'source' ? 'source' : 'note',
)
const sourceText = computed(() => sourceFromModules(modules.value))
const sourceLineCount = computed(
  () => sourceText.value.split('\n').length,
)
const pageTitle = computed(() =>
  title.value.trim()
    ? `${title.value.trim()} · ${
        editorMode.value === 'source' ? '编辑源码' : '编辑'
      } · ${siteTitle.value}`
    : `编辑 · ${siteTitle.value}`,
)
function serializeModule(module: EditorModule) {
  return {
    id: module.id,
    type: module.type,
    markdown: module.markdown,
    remarkModule: module.remarkModule,
    headers: module.headers,
    rows: module.rows,
    text: module.text,
    language: module.language,
    assetId: module.assetId,
    alt: module.alt,
    caption: module.caption,
    latex: module.latex,
  }
}

function serializeModuleList(list: EditorModule[]) {
  return list.map(serializeModule)
}

const dirty = computed(
  () =>
    loaded.value &&
    savedSnapshot.value !==
      snapshotFor(title.value, chapterId.value, modules.value),
)
const saveLabel = computed(() => {
  if (saving.value) return '保存中…'
  return '保存'
})

function notify(
  message: string,
  tone: 'success' | 'error' | 'info' = 'success',
) {
  toastId += 1
  toast.value = { id: toastId, tone, message }
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }
  toastTimer = window.setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 3200)
}

function snapshotFor(
  titleValue: string,
  chapterValue: number | null,
  moduleList: EditorModule[],
): string {
  return JSON.stringify({
    title: titleValue,
    chapterId: chapterValue,
    modules: serializeModuleList(moduleList),
  })
}

function snapshot(): string {
  return snapshotFor(title.value, chapterId.value, modules.value)
}

function cloneModulesForSave(): EditorModule[] {
  return modules.value.map((module) => ({
    ...module,
    headers: [...module.headers],
    rows: module.rows.map((row) => [...row]),
  }))
}

const canUndo = computed(() => historyPast.value.length > 0)
const canRedo = computed(() => historyFuture.value.length > 0)

function historySnapshot(): string {
  return JSON.stringify({
    modules: cloneModulesForSave(),
    activeKey: activeModuleKey.value,
  })
}

function pushHistorySnapshot(snapshot: string | null = null) {
  const value = snapshot ?? historySnapshot()
  historyPast.value.push(value)
  if (historyPast.value.length > 40) {
    historyPast.value.shift()
  }
  historyFuture.value = []
}

function applyHistorySnapshot(raw: string) {
  try {
    const parsed = JSON.parse(raw) as {
      modules?: EditorModule[]
      activeKey?: string | null
    }
    if (!Array.isArray(parsed.modules)) return
    modules.value = parsed.modules.map((module) => ({
      ...module,
      headers: [...module.headers],
      rows: module.rows.map((row) => [...row]),
    }))
    activeModuleKey.value = parsed.activeKey ?? null
  } catch {
    // 损坏的历史快照不应用
  }
}

function undo() {
  const previous = historyPast.value.pop()
  if (!previous) return
  historyFuture.value.push(historySnapshot())
  applyHistorySnapshot(previous)
}

function redo() {
  const next = historyFuture.value.pop()
  if (!next) return
  historyPast.value.push(historySnapshot())
  applyHistorySnapshot(next)
}

function onHistoryKeydown(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'z') {
    return
  }
  const target = event.target as HTMLElement | null
  if (target?.closest('input, textarea, select, [contenteditable="true"]')) {
    return
  }
  event.preventDefault()
  if (event.shiftKey) redo()
  else undo()
}


async function handleUnauthorized(error: unknown): Promise<boolean> {
  if (error instanceof ApiError && error.status === 401) {
    clearSession()
    await router.replace({
      name: 'login',
      query: { next: route.fullPath },
    })
    return true
  }
  return false
}

async function loadWorkspace() {
  try {
    workspace.value = await getWorkspace()
  } catch {
    // 编辑内容优先；章节加载失败不阻断正文
  }
}

async function loadDocument(showLoading = true) {
  const token = ++loadToken
  saveRequestId += 1
  saving.value = false
  if (showLoading) {
    loading.value = true
    loadError.value = ''
    beginProgress()
  }
  try {
    const id = Number(route.params.id)
    if (!Number.isInteger(id) || id <= 0) {
      loadError.value = '文档地址无效。'
      return
    }
    const data = await getDocument(id)
    if (token !== loadToken) {
      return
    }
    document.value = data
    title.value = data.title
    chapterId.value = data.chapter_id
    version.value = data.version
    modules.value = documentToModules(data)
    loaded.value = false
    await nextTick()
    savedSnapshot.value = snapshot()
    loaded.value = true
    activeModuleKey.value = null
    activeTextarea.value = null
    historyPast.value = []
    historyFuture.value = []
    dragHistorySnapshot = null
    loadError.value = ''
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) {
    if (token !== loadToken) {
      return
    }
    if (await handleUnauthorized(error)) {
      return
    }
    loadError.value =
      error instanceof ApiError
        ? error.status === 404
          ? '文档不存在，可能已移入回收站或不属于当前账号。'
          : error.message
        : '文档读取失败，请稍后重试'
  } finally {
    if (token === loadToken) {
      loading.value = false
    }
    if (showLoading) {
      endProgress()
    }
  }
}

function activateModule(module: EditorModule) {
  activeModuleKey.value = module.key
}

function onTextareaFocus(
  module: EditorModule,
  element: HTMLTextAreaElement,
) {
  activeModuleKey.value = module.key
  activeTextarea.value = element
}

function resolveTextTarget(): {
  module: EditorModule
  element: HTMLTextAreaElement
} | null {
  const focused =
    window.document.activeElement instanceof HTMLTextAreaElement
      ? window.document.activeElement
      : null
  const element = focused || activeTextarea.value
  if (!element || !element.isConnected) {
    return null
  }
  const card = element.closest<HTMLElement>('[data-module-key]')
  const key = card?.dataset.moduleKey
  const module = modules.value.find((item) => item.key === key)
  if (!module || !isTextModule(module)) {
    return null
  }
  return { module, element }
}

function updateTextModule(
  module: EditorModule,
  value: string,
  selectionStart: number,
  selectionEnd: number,
) {
  module.markdown = value
  nextTick(() => {
    const card = moduleListRoot.value?.querySelector<HTMLElement>(
      `[data-module-key="${module.key}"]`,
    )
    const element = card?.querySelector<HTMLTextAreaElement>('textarea')
    if (!element) {
      return
    }
    element.value = value
    element.focus()
    element.setSelectionRange(selectionStart, selectionEnd)
  })
}

function applyWrap(before: string, after: string, placeholder: string) {
  const target = resolveTextTarget()
  if (!target) {
    notify('请先点进一个文本模块再使用文字样式。', 'info')
    return
  }
  const { module, element } = target
  const value = module.markdown
  const start = element.selectionStart
  const end = element.selectionEnd
  const selected = value.slice(start, end)
  const inner = selected || placeholder
  const nextValue =
    value.slice(0, start) + before + inner + after + value.slice(end)
  updateTextModule(
    module,
    nextValue,
    start + before.length,
    start + before.length + inner.length,
  )
}

function toggleBullet() {
  const target = resolveTextTarget()
  if (!target) {
    notify('请先点进一个文本模块再使用圆点列表。', 'info')
    return
  }
  const { module, element } = target
  const value = module.markdown
  const start = element.selectionStart
  const end = element.selectionEnd
  const lineStart = value.lastIndexOf('\n', Math.max(0, start - 1)) + 1
  const nextBreak = value.indexOf('\n', end)
  const lineEnd = nextBreak === -1 ? value.length : nextBreak
  const block = value.slice(lineStart, lineEnd)
  const lines = block.split('\n')
  const nonEmpty = lines.filter((line) => line.trim())
  const allBullet =
    nonEmpty.length > 0 &&
    nonEmpty.every((line) => /^\s*[-*+]\s+/.test(line))
  if (
    module.type === 'remark'
  ) {
    const nextLines = lines.map((line) => {
      if (allBullet) {
        return line.replace(/^(\s*)[-*+]\s+/, '$1')
      }
      return /^\s*[-*+]\s+/.test(line) ? line : `- ${line}`
    })
    const nextBlock = nextLines.join('\n')
    module.remarkModule =
      module.remarkModule === 'bullet_list' && allBullet
        ? 'paragraph'
        : 'bullet_list'
    updateTextModule(
      module,
      value.slice(0, lineStart) + nextBlock + value.slice(lineEnd),
      lineStart,
      lineStart + nextBlock.length,
    )
    return
  }
  if (!['paragraph', 'bullet_list'].includes(module.type)) {
    notify('圆点工具用于段落、备注或圆点列表模块。', 'info')
    return
  }
  const nextLines = lines.map((line) => {
    if (allBullet) {
      return line.replace(/^(\s*)[-*+]\s+/, '$1')
    }
    return /^\s*[-*+]\s+/.test(line) ? line : `- ${line}`
  })
  const nextBlock = nextLines.join('\n')
  const nextValue =
    value.slice(0, lineStart) + nextBlock + value.slice(lineEnd)
  module.type =
    module.type === 'bullet_list' && allBullet
      ? 'paragraph'
      : 'bullet_list'
  updateTextModule(
    module,
    nextValue,
    lineStart,
    lineStart + nextBlock.length,
  )
}

function applyHighlight(tone: string) {
  applyWrap(
    `<mark data-tone="${tone}">`,
    '</mark>',
    '高亮文字',
  )
}

function openLinkDialog() {
  const target = resolveTextTarget()
  if (!target) {
    notify('请先点进一个文本模块再插入链接。', 'info')
    return
  }
  pendingLink.value = {
    key: target.module.key,
    start: target.element.selectionStart,
    end: target.element.selectionEnd,
    selected: target.module.markdown.slice(
      target.element.selectionStart,
      target.element.selectionEnd,
    ),
  }
  linkInitialLabel.value = pendingLink.value.selected
  linkOpen.value = true
}

function insertLink(label: string, url: string) {
  const pending = pendingLink.value
  if (pending) {
    const module = modules.value.find((item) => item.key === pending.key)
    if (module) {
      const value = module.markdown
      const markdown = `[${label}](${url})`
      const nextValue =
        value.slice(0, pending.start) +
        markdown +
        value.slice(pending.end)
      updateTextModule(
        module,
        nextValue,
        pending.start + markdown.length,
        pending.start + markdown.length,
      )
    }
  }
  linkOpen.value = false
  pendingLink.value = null
}

function openFormulaDialog() {
  const target = resolveTextTarget()
  if (!target) {
    notify('请先点进一个文本模块再插入行内公式。', 'info')
    return
  }
  pendingFormula.value = {
    key: target.module.key,
    start: target.element.selectionStart,
    end: target.element.selectionEnd,
    selected: target.module.markdown.slice(
      target.element.selectionStart,
      target.element.selectionEnd,
    ),
  }
  formulaOpen.value = true
}

function insertInlineFormula(latex: string) {
  const pending = pendingFormula.value
  if (pending) {
    const module = modules.value.find((item) => item.key === pending.key)
    if (module) {
      const value = module.markdown
      const markdown = `$${latex}$`
      const nextValue =
        value.slice(0, pending.start) +
        markdown +
        value.slice(pending.end)
      updateTextModule(
        module,
        nextValue,
        pending.start + markdown.length,
        pending.start + markdown.length,
      )
    }
  }
  formulaOpen.value = false
  pendingFormula.value = null
}

function insertModule(type: EditorModuleType, atIndex?: number) {
  pushHistorySnapshot()
  const module = createEditorModule(type)
  if (
    type === 'code' &&
    editorMode.value === 'source' &&
    document.value?.language
  ) {
    module.language = document.value.language
  }
  const activeIndex = modules.value.findIndex(
    (item) => item.key === activeModuleKey.value,
  )
  const insertIndex =
    atIndex ?? (activeIndex >= 0 ? activeIndex + 1 : modules.value.length)
  modules.value.splice(insertIndex, 0, module)
  activeModuleKey.value = module.key
  nextTick(() => {
    if (type === 'image') {
      return
    }
    const card = moduleListRoot.value?.querySelector<HTMLElement>(
      `[data-module-key="${module.key}"]`,
    )
    const field =
      card?.querySelector<HTMLTextAreaElement>('textarea') ??
      card?.querySelector<HTMLInputElement>('input')
    field?.focus()
  })
}

function onModuleDragOver(event: DragEvent) {
  if (!event.dataTransfer?.types.includes('application/x-cqoder-module')) {
    return
  }
  event.preventDefault()
  event.dataTransfer.dropEffect = 'copy'
}

function onModuleDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData(
    'application/x-cqoder-module',
  ) as EditorModuleType | ''
  if (!type) {
    return
  }
  event.preventDefault()
  const allowed =
    editorMode.value === 'source'
      ? new Set<EditorModuleType>([
          'code',
          'remark',
          'result',
          'image',
        ])
      : new Set<EditorModuleType>([
          'paragraph',
          'heading1',
          'heading2',
          'heading3',
          'quote',
          'divider',
          'bullet_list',
          'ordered_list',
          'todo_list',
          'table',
          'code',
          'image',
          'formula',
        ])
  if (!allowed.has(type)) {
    return
  }
  const cards = Array.from(
    moduleListRoot.value?.querySelectorAll<HTMLElement>('.module-card') ??
      [],
  )
  let index = cards.findIndex((card) => {
    const rect = card.getBoundingClientRect()
    return event.clientY < rect.top + rect.height / 2
  })
  if (index < 0) {
    index = cards.length
  }
  insertModule(type, index)
}

function moveModule(module: EditorModule, direction: -1 | 1) {
  const index = modules.value.findIndex((item) => item.key === module.key)
  const target = index + direction
  if (index < 0 || target < 0 || target >= modules.value.length) {
    return
  }
  pushHistorySnapshot()
  const copy = modules.value.slice()
  const [moved] = copy.splice(index, 1)
  copy.splice(target, 0, moved)
  modules.value = copy
}

function duplicateModule(module: EditorModule) {
  pushHistorySnapshot()
  const copy = JSON.parse(JSON.stringify(module)) as EditorModule
  copy.key = moduleKey()
  copy.id = null
  copy.assetName = module.assetName
  const index = modules.value.findIndex((item) => item.key === module.key)
  modules.value.splice(index + 1, 0, copy)
  activeModuleKey.value = copy.key
}

function deleteModule(module: EditorModule) {
  const index = modules.value.findIndex((item) => item.key === module.key)
  if (index < 0) {
    return
  }
  pushHistorySnapshot()
  modules.value.splice(index, 1)
  if (activeModuleKey.value === module.key) {
    activeModuleKey.value =
      modules.value[Math.min(index, modules.value.length - 1)]?.key ?? null
  }
}

async function copySourceCode() {
  if (!sourceText.value) {
    notify('完整源码为空。', 'info')
    return
  }
  try {
    await navigator.clipboard.writeText(sourceText.value)
  } catch {
    const area = window.document.createElement('textarea')
    area.value = sourceText.value
    area.style.position = 'fixed'
    area.style.opacity = '0'
    window.document.body.appendChild(area)
    area.select()
    window.document.execCommand('copy')
    area.remove()
  }
  notify('已复制完整源码')
}

function downloadSourceCode() {
  if (!document.value) {
    return
  }
  window.location.href = documentDownloadUrl(document.value.id)
}

async function uploadModuleImage(module: EditorModule, file: File) {
  if (uploadedModuleKey.value !== null) {
    return
  }
  uploadedModuleKey.value = module.key
  try {
    const asset = await uploadAsset(file)
    module.assetId = asset.id
    module.assetName = asset.original_name
    if (!module.alt) {
      module.alt = asset.original_name
    }
    notify('图片已上传')
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    notify(
      error instanceof ApiError ? error.message : '图片上传失败',
      'error',
    )
  } finally {
    uploadedModuleKey.value = null
  }
}

async function save(): Promise<boolean> {
  if (!document.value || saving.value) {
    return false
  }
  const cleanedTitle = title.value.trim()
  if (!cleanedTitle) {
    saveError.value = '标题不能为空。'
    notify('标题不能为空。', 'error')
    return false
  }
  const missingAsset = modules.value.find(
    (module) => module.type === 'image' && module.assetId === null,
  )
  if (missingAsset) {
    activeModuleKey.value = missingAsset.key
    saveError.value = '还有图片模块没有上传图片。'
    notify('请先为所有图片模块上传图片。', 'error')
    return false
  }
  const submittedTitle = cleanedTitle
  const submittedChapterId = chapterId.value
  const submittedModules = cloneModulesForSave()
  const requestId = ++saveRequestId
  const sourceDocumentId = document.value.id
  const sourceLoadToken = loadToken
  saving.value = true
  saveError.value = ''
  try {
    const saved = await saveDocumentBlocks(
      document.value.id,
      modulesToBlockInputs(submittedModules),
      version.value,
      submittedTitle,
      submittedChapterId,
    )
    if (
      sourceLoadToken !== loadToken ||
      document.value?.id !== sourceDocumentId
    ) {
      return false
    }

    const serverIdsByKey = new Map<string, number>()
    submittedModules.forEach((module, index) => {
      const block = saved.blocks[index]
      if (!block) return
      module.id = block.id
      serverIdsByKey.set(module.key, block.id)
    })
    for (const module of modules.value) {
      const serverId = serverIdsByKey.get(module.key)
      if (serverId !== undefined) {
        module.id = serverId
      }
    }

    document.value = saved
    if (title.value === submittedTitle) {
      title.value = saved.title
    }
    if (chapterId.value === submittedChapterId) {
      chapterId.value = saved.chapter_id
    }
    version.value = saved.version
    savedSnapshot.value = snapshotFor(
      saved.title,
      saved.chapter_id,
      submittedModules,
    )
    await nextTick()
    if (dirty.value) {
      notify('已保存本次提交，仍有未保存的新修改', 'info')
    } else {
      notify('已保存')
    }
    return true
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return false
    }
    if (error instanceof ApiError && error.code === 'version_conflict') {
      const currentVersion = error.details.current_version
      if (typeof currentVersion === 'number') {
        version.value = currentVersion
      }
      saveError.value =
        '文档已在其他设备更新。当前输入仍保留；可刷新版本后再次保存。'
    } else {
      saveError.value =
        error instanceof ApiError ? error.message : '保存失败，请稍后重试'
    }
    notify(saveError.value, 'error')
    return false
  } finally {
    if (requestId === saveRequestId) {
      saving.value = false
    }
  }
}

async function refreshVersion() {
  if (!document.value || refreshingVersion.value) {
    return
  }
  refreshingVersion.value = true
  try {
    const latest = await getDocument(document.value.id)
    version.value = latest.version
    saveError.value = '已同步服务器版本号，本地输入没有清空。'
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    saveError.value =
      error instanceof ApiError ? error.message : '版本同步失败'
  } finally {
    refreshingVersion.value = false
  }
}

function readingTarget() {
  return {
    name: 'document' as const,
    params: { id: route.params.id as string },
  }
}

function completeExit() {
  const target = pendingExitTarget ?? readingTarget()
  pendingExitTarget = null
  exitPromptOpen.value = false
  allowLeave.value = true
  router.replace(target)
}

function requestExit() {
  if (saving.value) return
  pendingExitTarget = readingTarget()
  if (!dirty.value) {
    completeExit()
    return
  }
  exitPromptOpen.value = true
}

async function saveAndExit() {
  if (exitSaving.value || saving.value) return
  exitSaving.value = true
  try {
    const ok = await save()
    if (!ok) return
    if (dirty.value) {
      notify('已保存本次提交，但仍有新修改，暂未退出', 'info')
      return
    }
    completeExit()
  } finally {
    exitSaving.value = false
  }
}

function discardAndExit() {
  completeExit()
}

function cancelExit() {
  pendingExitTarget = null
  exitPromptOpen.value = false
}

function completeSwitch() {
  const target = pendingSwitchTarget
  pendingSwitchTarget = null
  switchPromptOpen.value = false
  allowLeave.value = true
  if (target) {
    router.push(target)
  }
}

async function saveAndSwitch() {
  if (switchSaving.value || saving.value) return
  switchSaving.value = true
  try {
    const ok = await save()
    if (!ok) return
    if (dirty.value) {
      notify('已保存本次提交，但仍有新修改，暂未切换', 'info')
      return
    }
    completeSwitch()
  } finally {
    switchSaving.value = false
  }
}

function discardAndSwitch() {
  completeSwitch()
}

function cancelSwitch() {
  pendingSwitchTarget = null
  switchPromptOpen.value = false
}

// Module drag sorting
interface DragState {
  key: string
  pointerId: number
  startClientY: number
  grabOffset: number
  height: number
  ghost: HTMLElement
  source: HTMLElement
  handle: HTMLElement
  heights: Map<string, number>
  gap: number
  originOrder: string[]
  moved: boolean
  lastClientY: number
  frame: number | null
  keyHandler: (event: KeyboardEvent) => void
}

let drag: DragState | null = null

function moduleRow(key: string): HTMLElement | null {
  return (
    moduleListRoot.value?.querySelector<HTMLElement>(
      `[data-module-key="${key}"]`,
    ) ?? null
  )
}

function startModuleDrag(event: PointerEvent, module: EditorModule) {
  if (drag || event.button !== 0) {
    return
  }
  const source = moduleRow(module.key)
  const handle = event.currentTarget as HTMLElement | null
  if (!source || !handle) {
    return
  }
  dragHistorySnapshot = historySnapshot()
  const rect = source.getBoundingClientRect()
  const heights = new Map<string, number>()
  for (const item of modules.value) {
    const row = moduleRow(item.key)
    if (row) {
      heights.set(item.key, row.getBoundingClientRect().height)
    }
  }
  const listElement =
    moduleListRoot.value?.querySelector<HTMLElement>('.module-list') ||
    moduleListRoot.value!
  const gap =
    Number.parseFloat(getComputedStyle(listElement).rowGap || '11') || 11
  const ghost = source.cloneNode(true) as HTMLElement
  ghost.classList.add('module-drag-ghost')
  ghost.querySelectorAll<HTMLElement>('button, input, textarea, select, a').forEach(
    (element) => {
      element.setAttribute('tabindex', '-1')
      element.setAttribute('aria-hidden', 'true')
    },
  )
  ghost.style.width = `${rect.width}px`
  ghost.style.height = `${rect.height}px`
  ghost.style.left = `${rect.left}px`
  ghost.style.top = `${rect.top}px`
  window.document.body.appendChild(ghost)

  drag = {
    key: module.key,
    pointerId: event.pointerId,
    startClientY: event.clientY,
    grabOffset: event.clientY - rect.top,
    height: rect.height,
    ghost,
    source,
    handle,
    heights,
    gap,
    originOrder: modules.value.map((item) => item.key),
    moved: false,
    lastClientY: event.clientY,
    frame: null,
    keyHandler: (keyEvent: KeyboardEvent) => {
      if (keyEvent.key === 'Escape') {
        keyEvent.preventDefault()
        finishModuleDrag(false)
      }
    },
  }
  dragKey.value = module.key
  source.classList.add('drag-source')
  window.document.body.classList.add('module-dragging')
  handle.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', onModulePointerMove, {
    passive: false,
  })
  window.addEventListener('pointerup', onModulePointerUp)
  window.addEventListener('pointercancel', onModulePointerCancel)
  window.addEventListener('keydown', drag.keyHandler)
  drag.frame = requestAnimationFrame(moduleAutoScrollStep)
}

function onModulePointerMove(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  event.preventDefault()
  drag.lastClientY = event.clientY
  if (Math.abs(event.clientY - drag.startClientY) > 4) {
    drag.moved = true
  }
  drag.ghost.style.top = `${event.clientY - drag.grabOffset}px`
  updateModuleTarget()
}

function onModulePointerUp(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishModuleDrag(true)
}

function onModulePointerCancel(event: PointerEvent) {
  if (!drag || event.pointerId !== drag.pointerId) {
    return
  }
  finishModuleDrag(false)
}

function animateModuleReorder(
  before: Map<string, DOMRect>,
  sourceKey: string,
) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return
  }
  nextTick(() => {
    for (const module of modules.value) {
      if (module.key === sourceKey) continue
      const element = moduleRow(module.key)
      const oldRect = before.get(module.key)
      if (!element || !oldRect) continue
      const delta = oldRect.top - element.getBoundingClientRect().top
      if (Math.abs(delta) < 1) continue
      element
        .getAnimations()
        .filter((animation) => animation.id === 'module-reorder')
        .forEach((animation) => animation.cancel())
      const animation = element.animate(
        [
          { transform: `translateY(${delta}px)` },
          { transform: 'translateY(0)' },
        ],
        {
          duration: 260,
          easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
        },
      )
      animation.id = 'module-reorder'
    }
  })
}

function updateModuleTarget() {
  if (!drag || !moduleListRoot.value) {
    return
  }
  const rootRect = moduleListRoot.value.getBoundingClientRect()
  const ghostCenter =
    drag.lastClientY - drag.grabOffset + drag.height / 2
  const relativeCenter = ghostCenter - rootRect.top
  const others = modules.value.filter((item) => item.key !== drag!.key)
  let offset = 0
  let target = 0
  for (const item of others) {
    const height = drag.heights.get(item.key) ?? 90
    if (offset + height / 2 < relativeCenter) {
      target += 1
    }
    offset += height + drag.gap
  }
  const currentIndex = modules.value.findIndex(
    (item) => item.key === drag!.key,
  )
  if (currentIndex < 0 || currentIndex === target) {
    return
  }
  const before = new Map<string, DOMRect>()
  for (const item of modules.value) {
    const element = moduleRow(item.key)
    if (element) {
      before.set(item.key, element.getBoundingClientRect())
    }
  }
  const sourceKey = drag.key
  const copy = modules.value.slice()
  const [moved] = copy.splice(currentIndex, 1)
  copy.splice(target, 0, moved)
  modules.value = copy
  animateModuleReorder(before, sourceKey)
}

function moduleAutoScrollStep() {
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
    updateModuleTarget()
  }
  drag.frame = requestAnimationFrame(moduleAutoScrollStep)
}

function finishModuleDrag(saveOrder: boolean) {
  if (!drag) {
    return
  }
  const state = drag
  if (state.frame !== null) {
    cancelAnimationFrame(state.frame)
  }
  window.removeEventListener('pointermove', onModulePointerMove)
  window.removeEventListener('pointerup', onModulePointerUp)
  window.removeEventListener('pointercancel', onModulePointerCancel)
  window.removeEventListener('keydown', state.keyHandler)
  try {
    state.handle.releasePointerCapture?.(state.pointerId)
  } catch {
    // ignore
  }
  state.ghost.remove()
  state.source.classList.remove('drag-source')
  window.document.body.classList.remove('module-dragging')
  drag = null
  dragKey.value = null
  if (!saveOrder) {
    const byKey = new Map(modules.value.map((item) => [item.key, item]))
    modules.value = state.originOrder
      .map((key) => byKey.get(key))
      .filter((item): item is EditorModule => Boolean(item))
  } else if (state.moved && dragHistorySnapshot) {
    pushHistorySnapshot(dragHistorySnapshot)
  }
  dragHistorySnapshot = null
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) {
    return
  }
  event.preventDefault()
  event.returnValue = ''
}

watch(pageTitle, (value) => {
  window.document.title = value
}, { immediate: true })

watch(
  () => route.params.id,
  () => {
    if (route.name === 'document-edit' || route.name === 'source-edit') {
      loadDocument(true)
      loadWorkspace()
    }
  },
)

onBeforeRouteLeave((to) => {
  if (allowLeave.value || to.name === 'login') {
    return true
  }
  if (to.name === 'workspace') {
    if (!dirty.value) {
      allowLeave.value = true
      return readingTarget()
    }
    pendingExitTarget = readingTarget()
    exitPromptOpen.value = true
    return false
  }
  if (!dirty.value) {
    return true
  }
  pendingExitTarget = readingTarget()
  exitPromptOpen.value = true
  return false
})

onBeforeRouteUpdate((to, from) => {
  if (allowLeave.value) {
    allowLeave.value = false
    return true
  }
  if (to.params.id === from.params.id) {
    return true
  }
  if (saving.value) {
    return false
  }
  if (!dirty.value) {
    return true
  }
  pendingSwitchTarget = to.fullPath
  switchPromptOpen.value = true
  return false
})

onMounted(() => {
  loadDocument(true)
  loadWorkspace()
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('keydown', onHistoryKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('keydown', onHistoryKeydown)
  if (drag) {
    finishModuleDrag(false)
  }
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }
})
</script>

<template>
  <div class="editor-page">
    <header class="editor-topbar">
      <div class="topbar-left">
        <span class="editor-page-label">
          {{ editorMode === 'source' ? '源码编辑' : '笔记编辑' }}
        </span>
        <span v-if="authState.user?.is_demo" class="demo-chip">示例空间</span>
        <div class="history-controls" aria-label="结构撤销与重做">
          <button
            type="button"
            :disabled="!canUndo"
            aria-label="撤销结构操作"
            title="撤销结构操作"
            @click="undo"
          >
            ↶
          </button>
          <button
            type="button"
            :disabled="!canRedo"
            aria-label="重做结构操作"
            title="重做结构操作"
            @click="redo"
          >
            ↷
          </button>
        </div>
      </div>

      <div class="topbar-status">
        <span class="status-dot" :class="{ dirty }"></span>
        <span>{{ dirty ? '有未保存修改' : '已保存' }}</span>
      </div>

      <div class="topbar-actions">
        <AiPolishEntry
          v-if="document && editorMode === 'note'"
          :document-id="Number(document.id)"
          :dirty="dirty"
          :saving="saving"
        />
        <button
          type="button"
          class="topbar-button"
          :disabled="!document"
          @click="previewOpen = true"
        >
          预览
        </button>
        <button
          type="button"
          class="topbar-button primary"
          :disabled="saving || !dirty"
          @click="save"
        >
          {{ saveLabel }}
        </button>
        <button
          type="button"
          class="topbar-button"
          :disabled="saving"
          @click="requestExit"
        >
          退出
        </button>
      </div>
    </header>

    <main class="editor-main">
      <div v-if="loading" class="editor-loading" role="status" aria-live="polite">
        <p>正在准备编辑器…</p>
      </div>

      <section v-else-if="loadError" class="editor-error" role="alert">
        <p class="eyebrow">EDITOR / UNAVAILABLE</p>
        <h1>编辑器暂时打不开</h1>
        <p>{{ loadError }}</p>
        <div class="error-actions">
          <button
            v-if="!document || document.kind === 'note'"
            type="button"
            class="primary-button"
            @click="loadDocument(true)"
          >
            重新加载
          </button>
          <button
            type="button"
            class="secondary-button"
            @click="requestExit"
          >
            回到笔记页
          </button>
        </div>
      </section>

      <template v-else-if="document">
        <header class="editor-head">
          <div class="title-wrap">
            <p class="eyebrow">
              {{
                editorMode === 'source'
                  ? 'SOURCE / C·H MODULES'
                  : 'EDITOR / MARKDOWN MODULES'
              }}
            </p>
            <input
              v-model="title"
              class="title-input"
              type="text"
              maxlength="200"
              aria-label="文档标题"
            />
            <div class="meta-row">
              <ChapterPicker
                v-model="chapterId"
                :chapters="chapters"
                :disabled="saving"
              />
              <span class="meta-hint">
                {{ modules.length }} 个模块 · 版本 v{{ version }}
              </span>
            </div>
            <div v-if="editorMode === 'source'" class="source-tools">
              <span>
                完整源码 {{ sourceLineCount }} 行 · 仅拼接代码块
              </span>
              <button type="button" @click="copySourceCode">
                复制完整源码
              </button>
              <button type="button" @click="downloadSourceCode">
                下载源码
              </button>
            </div>
          </div>
        </header>

        <p v-if="saveError" class="save-error" role="alert">
          {{ saveError }}
          <button
            v-if="saveError.includes('刷新版本')"
            type="button"
            :disabled="refreshingVersion"
            @click="refreshVersion"
          >
            {{ refreshingVersion ? '同步中…' : '刷新版本' }}
          </button>
        </p>

        <div class="editor-layout">
          <div
            ref="moduleListRoot"
            class="module-column"
            @dragover="onModuleDragOver"
            @drop="onModuleDrop"
          >
            <div class="module-list">
              <EditorModuleCard
                v-for="(module, index) in modules"
                :key="module.key"
                :module="module"
                :index="index"
                :total="modules.length"
                :active="activeModuleKey === module.key"
                :fixed-language="editorMode === 'source'"
                :class="{ 'drag-source': dragKey === module.key }"
                @activate="activateModule"
                @focus="onTextareaFocus"
                @drag-start="startModuleDrag"
                @move-up="moveModule($event, -1)"
                @move-down="moveModule($event, 1)"
                @duplicate="duplicateModule"
                @delete="deleteModule"
                @upload-image="uploadModuleImage"
                @history="pushHistorySnapshot()"
              />
            </div>

            <div v-if="!modules.length" class="empty-modules">
              <span class="empty-mark" aria-hidden="true">＋</span>
              <h2>从第一个模块开始</h2>
              <p v-if="editorMode === 'source'">
                使用右侧工具栏插入代码、备注、运行结果或图片。
              </p>
              <p v-else>
                使用右侧工具栏插入段落、标题、列表、表格、代码或图片。
              </p>
              <button
                type="button"
                class="primary-button"
                @click="
                  insertModule(
                    editorMode === 'source' ? 'code' : 'paragraph',
                  )
                "
              >
                插入{{ editorMode === 'source' ? '代码块' : '段落' }}
              </button>
            </div>
          </div>

          <EditorToolbar
            :mode="editorMode"
            @format="
              $event === 'bullet'
                ? toggleBullet()
                : $event === 'bold'
                  ? applyWrap('**', '**', '粗体文字')
                  : $event === 'italic'
                    ? applyWrap('*', '*', '斜体文字')
                    : $event === 'underline'
                      ? applyWrap('<u>', '</u>', '下划线文字')
                      : $event === 'strike'
                        ? applyWrap('~~', '~~', '删除线文字')
                        : applyWrap('`', '`', '代码')
            "
            @highlight="applyHighlight"
            @link="openLinkDialog"
            @inline-formula="openFormulaDialog"
            @insert="insertModule"
          />
        </div>
      </template>
    </main>

    <Transition name="toast">
      <div
        v-if="toast"
        :key="toast.id"
        class="toast"
        :class="toast.tone"
        role="status"
      >
        <span aria-hidden="true">{{
          toast.tone === 'error' ? '!' : toast.tone === 'info' ? 'i' : '✓'
        }}</span>
        {{ toast.message }}
      </div>
    </Transition>

    <ModalShell
      :open="previewOpen"
      :title="title || document?.title || '预览'"
      eyebrow="PREVIEW / SHARED RENDERER"
      size="large"
      @close="previewOpen = false"
    >
      <DocumentBlocks
        v-if="previewBlocks.length"
        :blocks="previewBlocks"
        :kind="editorMode"
        :language="document?.language || null"
        :document-id="document?.id ?? null"
      />
      <p v-else class="preview-empty">还没有可预览的内容。</p>
    </ModalShell>

    <ModalShell
      :open="exitPromptOpen"
      title="有未保存的修改"
      eyebrow="EDITOR / EXIT"
      size="small"
      :dismissible="!exitSaving && !saving"
      @close="cancelExit"
    >
      <div class="exit-dialog">
        <p>退出前要保存这次修改吗？不保存退出会丢弃当前编辑内容。</p>
        <div class="exit-actions">
          <button
            type="button"
            class="secondary-button"
            :disabled="exitSaving || saving"
            @click="cancelExit"
          >
            取消
          </button>
          <button
            type="button"
            class="secondary-button danger"
            :disabled="exitSaving || saving"
            @click="discardAndExit"
          >
            不保存退出
          </button>
          <button
            type="button"
            class="primary-button"
            :disabled="exitSaving || saving"
            @click="saveAndExit"
          >
            {{ exitSaving || saving ? '保存中…' : '保存并退出' }}
          </button>
        </div>
      </div>
    </ModalShell>

    <ModalShell
      :open="switchPromptOpen"
      title="切换前要保存吗"
      eyebrow="EDITOR / SWITCH"
      size="small"
      :dismissible="!switchSaving && !saving"
      @close="cancelSwitch"
    >
      <div class="exit-dialog">
        <p>当前文档有未保存的修改。切换文档后，这些修改会丢失。</p>
        <div class="exit-actions">
          <button
            type="button"
            class="secondary-button"
            :disabled="switchSaving || saving"
            @click="cancelSwitch"
          >
            取消
          </button>
          <button
            type="button"
            class="secondary-button danger"
            :disabled="switchSaving || saving"
            @click="discardAndSwitch"
          >
            不保存切换
          </button>
          <button
            type="button"
            class="primary-button"
            :disabled="switchSaving || saving"
            @click="saveAndSwitch"
          >
            {{ switchSaving || saving ? '保存中…' : '保存并切换' }}
          </button>
        </div>
      </div>
    </ModalShell>

    <LinkDialog
      :open="linkOpen"
      :initial-label="linkInitialLabel"
      @close="linkOpen = false"
      @insert="insertLink"
    />
    <InlineFormulaDialog
      :open="formulaOpen"
      :initial-latex="''"
      @close="formulaOpen = false"
      @insert="insertInlineFormula"
    />
  </div>
</template>

<style scoped>
.editor-page {
  min-height: 100vh;
  min-height: 100dvh;
  padding-bottom: 50px;
}

.editor-topbar {
  position: sticky;
  top: 0;
  z-index: 80;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 16px;
  align-items: center;
  height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: #fbfaff;
}

.editor-page-label {
  color: var(--text);
  font-size: 13px;
  font-weight: 700;
}

.demo-chip {
  padding: 2px 8px;
  border: 1px solid #f0e3b8;
  border-radius: 999px;
  color: #8a6a12;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: #fff8e1;
}

.history-controls {
  display: flex;
  gap: 2px;
}

.history-controls button {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 7px;
  color: var(--muted);
  font: inherit;
  font-size: 17px;
  line-height: 1;
  background: transparent;
  cursor: pointer;
}

.history-controls button:hover:not(:disabled) {
  color: var(--accent-strong);
  border-color: var(--border);
  background: #fff;
}

.history-controls button:disabled {
  opacity: 0.3;
  cursor: default;
}

.topbar-left,
.topbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.topbar-actions {
  justify-content: flex-end;
}

.back-button,
.topbar-button {
  display: inline-flex;
  gap: 5px;
  align-items: center;
  min-height: 36px;
  padding: 7px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  font-weight: 650;
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
}

.back-button:hover,
.topbar-button:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--accent-strong);
  background: #fff;
}

.back-button svg {
  width: 14px;
  height: 14px;
}

.topbar-button.primary {
  border-color: var(--accent-strong);
  color: #fff;
  background: linear-gradient(145deg, #846aff, #5436e8);
}

.topbar-button.primary:hover:not(:disabled) {
  color: #fff;
  background: linear-gradient(145deg, #907aff, #4a2cd8);
}

.topbar-button:disabled {
  opacity: 0.5;
  cursor: default;
}

.brand-link {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text);
}

.brand-mark {
  display: grid;
  width: 29px;
  height: 29px;
  place-items: center;
  border-radius: 8px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(145deg, #a58fff, #5436e8);
}

.brand-text {
  max-width: 160px;
  overflow: hidden;
  font-size: 11.5px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-status {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--muted);
  font-size: 9.5px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6fbf8f;
  box-shadow: 0 0 0 3px rgba(111, 191, 143, 0.12);
}

.status-dot.dirty {
  background: #d19a3e;
  box-shadow: 0 0 0 3px rgba(209, 154, 62, 0.12);
}

.doc-id {
  padding-left: 7px;
  border-left: 1px solid var(--border);
  font-family: var(--font-mono);
}

.editor-main {
  width: min(1220px, 100%);
  margin: 0 auto;
  padding: 30px 28px 40px;
}

.editor-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 22px;
}

.title-wrap {
  width: 100%;
}

.eyebrow {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 8.5px;
  font-weight: 650;
  letter-spacing: 0.17em;
}

.title-input {
  width: 100%;
  margin-top: 9px;
  padding: 0;
  border: 0;
  color: var(--text);
  font: inherit;
  font-size: clamp(29px, 4vw, 46px);
  font-weight: 760;
  letter-spacing: -0.035em;
  line-height: 1.15;
  background: transparent;
  outline: none;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
}

.meta-hint {
  color: var(--muted);
  font-size: 9px;
}

.source-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.62);
}

.source-tools > span {
  margin-right: auto;
  color: var(--muted);
  font-size: 9.5px;
}

.source-tools button {
  padding: 5px 9px;
  border: 1px solid var(--border-strong);
  border-radius: 7px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 9.5px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.source-tools button:hover {
  color: var(--accent-strong);
  border-color: #cdbdf5;
  background: var(--accent-faint);
}

.editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 238px;
  gap: 18px;
  align-items: start;
}

.module-column {
  min-width: 0;
}

.module-list {
  display: grid;
  gap: 11px;
}

.editor-module-move {
  transition: transform 0.26s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.editor-module-enter-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.editor-module-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.editor-module-leave-active {
  position: absolute;
  width: 100%;
  pointer-events: none;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.editor-module-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

:deep(.module-card.drag-source) {
  opacity: 0.16;
  border-style: dashed;
  border-color: #b8a6ed;
  transform: scale(0.992);
}

:deep(.module-drag-ghost) {
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

:global(body.module-dragging) {
  cursor: grabbing;
  user-select: none;
}

.empty-modules {
  display: grid;
  gap: 8px;
  justify-items: center;
  padding: 60px 24px;
  border: 1px dashed var(--border-strong);
  border-radius: 18px;
  text-align: center;
  background:
    radial-gradient(240px 150px at 50% 0%, rgba(115, 87, 255, 0.08), transparent 72%),
    rgba(255, 255, 255, 0.55);
}

.empty-mark {
  display: grid;
  width: 46px;
  height: 46px;
  margin-bottom: 4px;
  place-items: center;
  border-radius: 14px;
  color: var(--accent);
  font-size: 22px;
  background: var(--accent-soft);
}

.empty-modules h2 {
  font-size: 19px;
  letter-spacing: -0.02em;
}

.empty-modules p {
  max-width: 390px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.7;
}

.save-error {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 9px 12px;
  border: 1px solid #f0cccc;
  border-radius: 9px;
  margin-bottom: 15px;
  color: #a43e3e;
  font-size: 10.5px;
  line-height: 1.6;
  background: #fff5f5;
}

.save-error button {
  padding: 3px 7px;
  border: 1px solid #e7bebe;
  border-radius: 6px;
  color: #8f3737;
  font: inherit;
  font-size: 9.5px;
  background: #fff;
  cursor: pointer;
}

.primary-button,
.secondary-button {
  padding: 8px 15px;
  border-radius: 9px;
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  cursor: pointer;
}

.primary-button {
  border: 1px solid var(--accent-strong);
  color: #fff;
  background: var(--accent-strong);
}

.secondary-button {
  border: 1px solid var(--border-strong);
  color: var(--muted-strong);
  background: #fff;
}

.editor-error {
  display: grid;
  gap: 10px;
  justify-items: start;
  padding: 70px 10px;
}

.editor-error h1 {
  font-size: 30px;
  letter-spacing: -0.03em;
}

.editor-error > p:not(.eyebrow) {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}

.error-actions {
  display: flex;
  gap: 8px;
  margin-top: 7px;
}

.exit-dialog {
  display: grid;
  gap: 18px;
}

.exit-dialog p {
  color: var(--muted-strong);
  font-size: 13px;
  line-height: 1.75;
}

.exit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.exit-actions .secondary-button.danger {
  color: #a84949;
  border-color: #ecc7c7;
}

.exit-actions .secondary-button.danger:hover:not(:disabled) {
  background: #fff4f4;
}

.preview-empty {
  padding: 38px 20px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}

.editor-skeleton {
  display: grid;
  gap: 13px;
  padding: 20px 0;
}

.skeleton-title,
.skeleton-line,
.skeleton-block {
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    #f0ebfb 20%,
    #f9f6ff 42%,
    #f0ebfb 64%
  );
  background-size: 220% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

.skeleton-title {
  width: 55%;
  height: 44px;
}

.skeleton-line {
  width: 30%;
  height: 12px;
}

.skeleton-block {
  width: 100%;
  height: 150px;
  border-radius: 15px;
}

.skeleton-block.short {
  height: 100px;
}

.toast {
  position: fixed;
  top: 76px;
  left: 50%;
  z-index: 230;
  display: flex;
  gap: 8px;
  align-items: center;
  max-width: min(90vw, 480px);
  padding: 9px 13px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted-strong);
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 16px 40px -20px rgba(33, 27, 51, 0.5);
  transform: translateX(-50%);
}

.toast > span {
  display: grid;
  flex: none;
  width: 17px;
  height: 17px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 9px;
  background: #6fbf8f;
}

.toast.error > span {
  background: #c96363;
}

.toast.info > span {
  background: var(--accent);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

@keyframes shimmer {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

@media (max-width: 960px) {
  .editor-topbar {
    background: rgba(250, 247, 255, 0.86);
    backdrop-filter: blur(18px);
  }

  .editor-page {
    padding-bottom: calc(190px + env(safe-area-inset-bottom));
  }

  .editor-topbar {
    grid-template-columns: 1fr auto;
    height: calc(60px + env(safe-area-inset-top));
    padding: env(safe-area-inset-top) 12px 0;
  }

  .back-button,
  .topbar-button {
    min-height: 38px;
    padding: 8px 10px;
  }

  .topbar-status,
  .brand-text {
    display: none;
  }

  .editor-layout {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .editor-main {
    padding: 20px 14px 24px;
  }

  .title-input {
    font-size: clamp(27px, 8vw, 38px);
  }

  .module-tools {
    display: flex;
  }

  .toast {
    top: 68px;
  }
}

@media (max-width: 520px) {
  .editor-topbar {
    grid-template-columns: 1fr auto;
    gap: 6px;
    height: 58px;
    padding: 0 10px;
  }

  .editor-page-label {
    font-size: 12px;
  }

  .topbar-status {
    display: none;
  }

  .topbar-left {
    min-width: 0;
  }

  .topbar-actions {
    gap: 4px;
  }

  .back-button {
    padding: 7px;
    font-size: 0;
  }

  .back-button svg {
    width: 16px;
    height: 16px;
  }

  .topbar-button {
    min-height: 34px;
    padding: 6px 8px;
    font-size: 10.5px;
  }
}
/* Legacy editor shell */
.editor-topbar {
  height: 62px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.94);
}

.editor-page-label {
  color: #2f2745;
  font-size: 13.5px;
  font-weight: 700;
}

.topbar-status {
  color: #8a839c;
  font-size: 12px;
}

.topbar-button {
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 7px;
  color: var(--muted-strong);
  font-size: 12.5px;
  font-weight: 650;
  background: #fff;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    background 0.16s ease;
}

.topbar-button:hover:not(:disabled) {
  border-color: #cbbcf0;
  color: var(--accent);
  transform: translateY(-1px);
}

.topbar-button.primary {
  border-color: #4a2fa8;
  color: #fff;
  background: linear-gradient(125deg, #4e36c0, #7149cf);
  box-shadow: 0 4px 10px rgba(81, 53, 179, 0.22);
}

.topbar-button.primary:hover:not(:disabled) {
  color: #fff;
  background: #452ba9;
}

.editor-main {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 26px 32px 60px;
}

.editor-head {
  padding: 0 2px;
}

.title-input {
  color: #242139;
  font-size: clamp(26px, 3.4vw, 32px);
  font-weight: 780;
  letter-spacing: -0.035em;
}

.editor-layout {
  gap: 22px;
  grid-template-columns: minmax(0, 1fr) 238px;
}

.module-list {
  gap: 11px;
}

.editor-loading {
  margin-top: 6px;
  padding: 46px 20px;
  border: 1px dashed #d9d2e8;
  border-radius: 13px;
  color: #8a839c;
  font-size: 14px;
  text-align: center;
  background: #fff;
}

.editor-loading p {
  margin: 0;
}

@media (max-width: 960px) {
  .editor-main {
    padding: 18px 14px 50px;
  }

  .editor-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .editor-loading {
    padding: 36px 14px;
  }
}

@media (max-width: 760px) {
  .editor-topbar {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    padding: 0 12px;
  }

  .editor-page-label {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .demo-chip,
  .topbar-status {
    display: none;
  }

  .topbar-left {
    min-width: 0;
  }

  .topbar-actions {
    gap: 5px;
  }

  .topbar-button {
    padding: 0 9px;
    font-size: 12px;
  }

  .history-controls button {
    width: 26px;
    height: 26px;
  }
}
</style>
