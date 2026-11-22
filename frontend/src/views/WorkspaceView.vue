<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import { RouterLink, onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import {
  ApiError,
  favoriteDocument,
  getDocuments,
  getWorkspace,
  importDocument,
  reorderChapters,
  reorderDocuments,
  reorderFolders,
  searchDocuments,
  stopDemo,
  unfavoriteDocument,
  updateDocument,
} from '../api/client'
import { authState, clearSession, logoutAndRedirect } from '../auth/session'
import type {
  Chapter,
  DocumentDetail,
  DocumentScope,
  DocumentSummary,
  Folder,
  SearchPayload,
  Workspace,
} from '../api/types'
import { siteTitle } from '../site'
import { formatBytes } from '../utils/format'
import { beginProgress, endProgress } from '../utils/progress'
import { bootStage } from '../utils/boot'
import {
  rememberHomeReturn,
  restoreScrollPosition,
} from '../utils/scrollMemory'
import AppTopBar from '../components/AppTopBar.vue'
import AuthorCard from '../components/AuthorCard.vue'
import ChapterDialog from '../components/ChapterDialog.vue'
import ChapterNav from '../components/ChapterNav.vue'
import CreateDocumentDialog from '../components/CreateDocumentDialog.vue'
import DeleteChapterDialog from '../components/DeleteChapterDialog.vue'
import DeleteDocumentDialog from '../components/DeleteDocumentDialog.vue'
import DeleteFolderDialog from '../components/DeleteFolderDialog.vue'
import DocumentList from '../components/DocumentList.vue'
import AiChoiceBanner from '../features/aiPolish/AiChoiceBanner.vue'
import EditDocumentDialog from '../components/EditDocumentDialog.vue'
import FolderDialog from '../components/FolderDialog.vue'
import MoveDocumentDialog from '../components/MoveDocumentDialog.vue'
import RecycleDialog from '../components/RecycleDialog.vue'
import SearchResults from '../components/SearchResults.vue'

const router = useRouter()
const route = useRoute()

const workspace = ref<Workspace | null>(null)
const documents = ref<DocumentSummary[]>([])
const initialFolderValue = Number(route.query.folder)
const initialFolderId =
  route.query.folder !== undefined && Number.isSafeInteger(initialFolderValue)
    ? initialFolderValue
    : null
const initialChapterValue = Number(route.query.chapter)
const initialChapterId =
  route.query.chapter !== undefined &&
  Number.isSafeInteger(initialChapterValue)
    ? initialChapterValue
    : null
const scope = ref<DocumentScope>(
  route.query.scope === 'favorites'
    ? 'favorites'
    : initialFolderId !== null
      ? 'folder'
      : initialChapterId !== null
        ? 'chapter'
        : 'library',
)
const selectedChapterId = ref<number | null>(initialChapterId)
const selectedFolderId = ref<number | null>(initialFolderId)
const folderDialogOpen = ref(false)
const folderDialogMode = ref<'create' | 'rename'>('create')
const folderDialogParentId = ref(0)
const folderDialogChapterId = ref<number | null>(null)
const folderTarget = ref<Folder | null>(null)
const deleteFolderOpen = ref(false)
const deleteFolderTarget = ref<Folder | null>(null)
const moveOpen = ref(false)
const moveTarget = ref<DocumentSummary | null>(null)
const searchQuery = ref('')
const searchPayload = ref<SearchPayload | null>(null)
const searchLoading = ref(false)
const searchLoadingMore = ref(false)
const searchError = ref('')
let searchTimer: number | null = null
let searchToken = 0

const workspaceLoading = ref(true)
const workspaceError = ref('')
const listLoading = ref(true)
const listError = ref('')
const sorting = ref(false)
const favoriteBusyId = ref<number | null>(null)

const createOpen = ref(false)
const createMode = ref<'note' | 'source' | 'import'>('note')
const editOpen = ref(false)
const editTarget = ref<DocumentSummary | null>(null)
const deleteOpen = ref(false)
const deleteTarget = ref<DocumentSummary | null>(null)
const recycleOpen = ref(false)
const chapterDialogOpen = ref(false)
const chapterDialogMode = ref<'create' | 'rename'>('create')
const chapterTarget = ref<Chapter | null>(null)
const deleteChapterOpen = ref(false)
const deleteChapterTarget = ref<Chapter | null>(null)

const mobileSheetOpen = ref(false)
const mobileAddOpen = ref(false)

const dragImportActive = ref(false)
const importing = ref(false)
const importProgress = ref({ done: 0, total: 0 })
const folderDropTargetId = ref<number | null>(null)
let dragDepth = 0

const toast = ref<{
  id: number
  tone: 'success' | 'error' | 'info'
  message: string
} | null>(null)
let toastTimer: number | null = null
let toastId = 0
let loadToken = 0

const user = computed(() => authState.user)
const chapters = computed(() => workspace.value?.chapters ?? [])
const folders = computed(() => workspace.value?.folders ?? [])
const favoriteCount = computed(() => workspace.value?.favorite_count ?? 0)
const libraryCount = computed(() => workspace.value?.library_count ?? 0)
const recycleCount = computed(() => workspace.value?.recycle_count ?? 0)
const retentionDays = computed(() => workspace.value?.recycle_retention_days ?? 7)
const storage = computed(
  () => workspace.value?.storage ?? { asset_count: 0, total_bytes: 0 },
)
const currentChapter = computed(
  () =>
    chapters.value.find(
      (chapter) => chapter.id === selectedChapterId.value,
    ) ?? null,
)
const currentFolder = computed(
  () =>
    folders.value.find((folder) => folder.id === selectedFolderId.value) ??
    null,
)
const chapterFolders = computed(() => {
  if (!currentChapter.value) return []
  return folders.value
    .filter(
      (folder) =>
        Number(folder.chapter_id) === Number(currentChapter.value!.id) &&
        Number(folder.parent_id || 0) === 0,
    )
    .slice()
    .sort(
      (a, b) =>
        Number(a.sort_order || 0) - Number(b.sort_order || 0) ||
        a.name.localeCompare(b.name),
    )
})
const childFolders = computed(() => {
  if (!currentFolder.value) return []
  return folders.value
    .filter(
      (folder) =>
        Number(folder.chapter_id) === Number(currentFolder.value!.chapter_id) &&
        Number(folder.parent_id || 0) === Number(currentFolder.value!.id),
    )
    .slice()
    .sort(
      (a, b) =>
        Number(a.sort_order || 0) - Number(b.sort_order || 0) ||
        a.name.localeCompare(b.name),
    )
})
const visibleFolders = computed(() => {
  if (scope.value === 'chapter') return chapterFolders.value
  if (scope.value === 'folder') return childFolders.value
  return []
})
const folderBreadcrumbs = computed(() => {
  if (!currentFolder.value) return []
  const byId = new Map(folders.value.map((folder) => [folder.id, folder]))
  const output: Folder[] = []
  let current: Folder | undefined = currentFolder.value
  const seen = new Set<number>()
  while (current && !seen.has(current.id)) {
    seen.add(current.id)
    output.unshift(current)
    current = byId.get(Number(current.parent_id || 0))
  }
  return output
})
const chapterRootCount = computed(() => {
  if (!currentChapter.value) return 0
  const inFolders = folders.value
    .filter(
      (folder) =>
        Number(folder.chapter_id) === Number(currentChapter.value!.id),
    )
    .reduce((sum, folder) => sum + Number(folder.document_count || 0), 0)
  return Math.max(0, Number(currentChapter.value.document_count || 0) - inFolders)
})
const currentChapterName = computed(() => {
  const id = currentFolder.value?.chapter_id ?? currentChapter.value?.id ?? null
  if (id === null) return ''
  return (
    chapters.value.find((chapter) => chapter.id === Number(id))?.name || ''
  )
})
const searchActive = computed(() => searchQuery.value.trim().length > 0)
const searchScope = computed<'all' | 'chapter' | 'folder'>(() => {
  if (scope.value === 'chapter' && selectedChapterId.value !== null) {
    return 'chapter'
  }
  if (scope.value === 'folder' && selectedFolderId.value !== null) {
    return 'folder'
  }
  return 'all'
})
const currentTitle = computed(() => {
  if (scope.value === 'favorites') {
    return '收藏'
  }
  if (scope.value === 'chapter') {
    return currentChapter.value?.name || '章节'
  }
  if (scope.value === 'folder') {
    return currentFolder.value?.name || '文件夹'
  }
  return '全部文件'
})
const scopeEyebrow = computed(() => {
  if (scope.value === 'favorites') {
    return 'FAVORITES / GOLD SHELF'
  }
  if (scope.value === 'chapter') {
    return 'CHAPTER / NOTES'
  }
  if (scope.value === 'folder') {
    return 'FOLDER / NOTES'
  }
  return 'LIBRARY / ALL NOTES'
})
const scopeDescription = computed(() => {
  if (scope.value === 'favorites') {
    return '独立保存的金色书架。收藏和取消收藏不会改变普通列表顺序。'
  }
  if (scope.value === 'chapter') {
    return '章节内顺序独立保存；换章节会追加到新章节末尾。'
  }
  if (scope.value === 'folder') {
    return '文件夹在章节内组织文档；移动、重命名或排序都不会改变稳定 ID。'
  }
  return ''
})
const currentCount = computed(() => {
  if (workspaceLoading.value) {
    return 0
  }
  if (scope.value === 'favorites') {
    return favoriteCount.value
  }
  if (scope.value === 'chapter') {
    return chapterRootCount.value
  }
  if (scope.value === 'folder') {
    return currentFolder.value?.document_count ?? 0
  }
  return libraryCount.value
})
const activeTopbar = computed(() =>
  scope.value === 'favorites' ? 'favorites' : 'workspace',
)
const navScope = computed(() =>
  scope.value === 'folder' ? 'chapter' : scope.value,
)
const createDefaultChapter = computed(() => {
  if (scope.value === 'chapter') return selectedChapterId.value
  if (scope.value === 'folder') return currentFolder.value?.chapter_id ?? null
  return null
})
const createDefaultFolder = computed(() =>
  scope.value === 'folder' && selectedFolderId.value
    ? selectedFolderId.value
    : null,
)
const appTitle = computed(() =>
  workspaceLoading.value ? siteTitle.value : `${currentTitle.value} · ${siteTitle.value}`,
)

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

async function handleUnauthorized(error: unknown): Promise<boolean> {
  if (error instanceof ApiError && error.status === 401) {
    clearSession()
    await router.replace({
      name: 'login',
      query: { next: router.currentRoute.value.fullPath },
    })
    return true
  }
  return false
}

function clearSearchState() {
  searchQuery.value = ''
  searchPayload.value = null
  searchError.value = ''
  searchLoading.value = false
  searchLoadingMore.value = false
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer)
    searchTimer = null
  }
  searchToken += 1
}

function selectScope(
  next: DocumentScope,
  chapterId: number | null = null,
  folderId: number | null = null,
) {
  const folder =
    next === 'folder' && folderId !== null
      ? folders.value.find((item) => item.id === folderId) ?? null
      : null
  scope.value = next
  selectedChapterId.value =
    next === 'chapter'
      ? chapterId
      : next === 'folder'
        ? folder?.chapter_id ?? null
        : null
  selectedFolderId.value = next === 'folder' ? folderId : null
  clearSearchState()
  mobileSheetOpen.value = false
  mobileAddOpen.value = false
  router.replace({
    name: 'workspace',
    query:
      next === 'favorites'
        ? { scope: 'favorites' }
        : next === 'chapter' && chapterId !== null
          ? { chapter: String(chapterId) }
          : next === 'folder' && folderId !== null
            ? { folder: String(folderId) }
            : {},
  })
  loadDocuments(true)
  if (window.innerWidth < 960) {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

function selectLibrary() {
  selectScope('library')
}

function selectFavorites() {
  selectScope('favorites')
}

function selectChapter(chapterId: number) {
  selectScope('chapter', chapterId)
}

function selectFolder(folderId: number) {
  if (!folders.value.some((folder) => folder.id === folderId)) {
    return
  }
  mobileSheetOpen.value = false
  mobileAddOpen.value = false
  selectScope('folder', null, folderId)
}

async function loadWorkspace(updateLoading = false) {
  if (updateLoading) {
    workspaceLoading.value = true
  }
  try {
    const data = await getWorkspace()
    workspace.value = data
    workspaceError.value = ''
    if (
      scope.value === 'chapter' &&
      selectedChapterId.value !== null &&
      !data.chapters.some(
        (chapter) => chapter.id === selectedChapterId.value,
      )
    ) {
      scope.value = 'library'
      selectedChapterId.value = null
    }
    if (
      scope.value === 'folder' &&
      selectedFolderId.value !== null &&
      !data.folders.some(
        (folder) => folder.id === selectedFolderId.value,
      )
    ) {
      scope.value = 'library'
      selectedFolderId.value = null
      selectedChapterId.value = null
    } else if (scope.value === 'folder' && selectedFolderId.value !== null) {
      selectedChapterId.value =
        data.folders.find((folder) => folder.id === selectedFolderId.value)
          ?.chapter_id ?? null
    }
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    if (updateLoading) {
      workspaceError.value =
        error instanceof ApiError
          ? error.message
          : '工作区读取失败，请稍后重试'
    } else {
      notify('工作区统计刷新失败', 'error')
    }
  } finally {
    if (updateLoading) {
      workspaceLoading.value = false
    }
  }
}

async function loadDocuments(showSkeleton = false) {
  const token = ++loadToken
  if (showSkeleton) {
    listLoading.value = true
    documents.value = []
  }
  listError.value = ''
  try {
    const data =
      scope.value === 'chapter'
        ? await getDocuments(
            'folder',
            selectedChapterId.value ?? undefined,
            0,
          )
        : scope.value === 'folder'
          ? await getDocuments(
              'folder',
              undefined,
              selectedFolderId.value ?? undefined,
            )
          : await getDocuments(scope.value)
    if (token !== loadToken) {
      return
    }
    documents.value = data
  } catch (error) {
    if (token !== loadToken) {
      return
    }
    if (await handleUnauthorized(error)) {
      return
    }
    listError.value =
      error instanceof ApiError
        ? error.message
        : '笔记读取失败，请稍后重试'
  } finally {
    if (token === loadToken) {
      listLoading.value = false
    }
  }
}

async function runSearch(offset = 0, append = false) {
  const query = searchQuery.value.trim()
  if (!query) {
    searchPayload.value = null
    searchLoading.value = false
    searchError.value = ''
    return
  }
  const token = ++searchToken
  if (append) searchLoadingMore.value = true
  else searchLoading.value = true
  searchError.value = ''
  try {
    const payload = await searchDocuments({
      query,
      scope: searchScope.value,
      chapterId:
        searchScope.value === 'chapter' ? selectedChapterId.value : null,
      folderId:
        searchScope.value === 'folder' ? selectedFolderId.value ?? 0 : null,
      offset,
      limit: 20,
    })
    if (token !== searchToken) return
    if (append && searchPayload.value) {
      searchPayload.value = {
        ...payload,
        items: [...searchPayload.value.items, ...payload.items],
      }
    } else {
      searchPayload.value = payload
    }
  } catch (error) {
    if (token !== searchToken) return
    if (await handleUnauthorized(error)) return
    searchError.value =
      error instanceof ApiError ? error.message : '搜索失败，请稍后重试'
  } finally {
    if (token === searchToken) {
      searchLoading.value = false
      searchLoadingMore.value = false
    }
  }
}

function loadMoreSearch() {
  const next = searchPayload.value?.next_offset
  if (next === null || next === undefined || searchLoadingMore.value) return
  void runSearch(next, true)
}

watch(
  searchQuery,
  (value) => {
    searchToken += 1
    if (searchTimer !== null) {
      window.clearTimeout(searchTimer)
      searchTimer = null
    }
    const query = value.trim()
    if (!query) {
      searchToken += 1
      searchPayload.value = null
      searchLoading.value = false
      searchError.value = ''
      return
    }
    searchTimer = window.setTimeout(() => {
      void runSearch(0, false)
    }, 320)
  },
)

async function bootstrap() {
  workspaceLoading.value = true
  beginProgress()
  bootStage('正在读取笔记', 72)
  try {
    await Promise.all([loadWorkspace(true), loadDocuments(true)])
    if (!workspaceError.value) {
      await nextTick()
      restoreScrollPosition(route.fullPath)
      bootStage('正在打开工作区', 94)
    }
  } finally {
    workspaceLoading.value = false
    endProgress()
  }
}

async function refreshWorkspaceAndList() {
  await Promise.all([loadWorkspace(), loadDocuments(false)])
}

function openCreate(mode: 'note' | 'source' | 'import') {
  createMode.value = mode
  createOpen.value = true
  mobileAddOpen.value = false
  mobileSheetOpen.value = false
}

function hasDraggedFiles(event: DragEvent): boolean {
  return Boolean(event.dataTransfer?.types.includes('Files'))
}

function supportedImportFiles(files: FileList | File[]): File[] {
  return Array.from(files).filter((file) =>
    /\.(md|c|h)$/i.test(file.name),
  )
}

function onWindowDragEnter(event: DragEvent) {
  if (!hasDraggedFiles(event)) return
  event.preventDefault()
  dragDepth += 1
  if (!importing.value) {
    dragImportActive.value = true
  }
}

function onWindowDragOver(event: DragEvent) {
  if (!hasDraggedFiles(event)) return
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
  if (!importing.value) {
    dragImportActive.value = true
  }
}

function onWindowDragLeave(event: DragEvent) {
  if (!hasDraggedFiles(event)) return
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) {
    dragImportActive.value = false
  }
}

function onWindowDragEnd() {
  dragDepth = 0
  dragImportActive.value = false
}

async function importDroppedFiles(fileList: FileList | File[]) {
  const supported = supportedImportFiles(fileList)
  if (!supported.length) {
    notify('只支持拖入 .md、.c 或 .h 文件', 'error')
    return
  }
  importing.value = true
  importProgress.value = { done: 0, total: supported.length }
  const chapterId = createDefaultChapter.value
  const folderId = createDefaultFolder.value
  const failures: string[] = []
  let succeeded = 0

  for (let index = 0; index < supported.length; index += 1) {
    const file = supported[index]
    importProgress.value = { done: index, total: supported.length }
    if (file.size > 5 * 1024 * 1024) {
      failures.push(`${file.name} 超过 5 MB`)
      importProgress.value = { done: index + 1, total: supported.length }
      continue
    }
    try {
      await importDocument(file, null, chapterId, folderId)
      succeeded += 1
    } catch (error) {
      if (await handleUnauthorized(error)) {
        importing.value = false
        return
      }
      failures.push(
        `${file.name}：${
          error instanceof ApiError ? error.message : '导入失败'
        }`,
      )
    }
    importProgress.value = { done: index + 1, total: supported.length }
  }

  importProgress.value = { done: supported.length, total: supported.length }
  importing.value = false
  await loadWorkspace()
  if (scope.value === 'favorites') {
    selectLibrary()
  } else {
    await loadDocuments(false)
  }
  if (failures.length) {
    notify(
      `已导入 ${succeeded} 个，失败 ${failures.length} 个；${failures[0]}`,
      'error',
    )
  } else {
    notify(`已导入 ${succeeded} 个文件`)
  }
}

function onWindowDrop(event: DragEvent) {
  if (!hasDraggedFiles(event)) return
  event.preventDefault()
  dragDepth = 0
  dragImportActive.value = false
  const files = event.dataTransfer?.files
  if (files?.length) {
    void importDroppedFiles(files)
  }
}

function hasDocumentDrag(event: DragEvent): boolean {
  return Boolean(
    event.dataTransfer?.types.includes('application/x-cqoder-document'),
  )
}

function onFolderDragOver(folderId: number, event: DragEvent) {
  if (!hasDocumentDrag(event)) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  folderDropTargetId.value = folderId
}

function onFolderDragLeave(folderId: number, event: DragEvent) {
  if (folderDropTargetId.value !== folderId) return
  const next = event.relatedTarget as Node | null
  if (!next || !(event.currentTarget as Node).contains(next)) {
    folderDropTargetId.value = null
  }
}

async function handleFolderDrop(folderId: number, event: DragEvent) {
  if (!hasDocumentDrag(event)) return
  event.preventDefault()
  folderDropTargetId.value = null
  const documentId = Number(
    event.dataTransfer?.getData('application/x-cqoder-document'),
  )
  if (!Number.isSafeInteger(documentId)) return
  const doc = documents.value.find((item) => item.id === documentId)
  if (!doc || doc.folder_id === folderId) return
  try {
    await updateDocument(doc.id, { folder_id: folderId }, doc.version)
    notify('文档已移动到文件夹')
    await loadWorkspace()
    await loadDocuments(false)
  } catch (error) {
    if (await handleUnauthorized(error)) return
    notify(
      error instanceof ApiError ? error.message : '移动失败，请稍后重试',
      'error',
    )
    await loadDocuments(false)
  }
}

function clearFolderDrop() {
  folderDropTargetId.value = null
}

async function handleCreated(document: { id: number }) {
  createOpen.value = false
  notify(
    createMode.value === 'import' ? '文件已导入' : '文档已创建',
  )
  await loadWorkspace()
  await router.push({ name: 'document', params: { id: document.id } })
}

function openEdit(document: DocumentSummary) {
  editTarget.value = document
  editOpen.value = true
}

async function handleSaved() {
  editOpen.value = false
  editTarget.value = null
  notify('修改已保存')
  await refreshWorkspaceAndList()
}

function openDelete(document: DocumentSummary) {
  deleteTarget.value = document
  deleteOpen.value = true
}

async function handleDeleted(document: DocumentSummary) {
  deleteOpen.value = false
  deleteTarget.value = null
  notify(`「${document.title}」已移入回收站`)
  await refreshWorkspaceAndList()
}

async function handleFavorite(document: DocumentSummary) {
  if (favoriteBusyId.value !== null) {
    return
  }
  favoriteBusyId.value = document.id
  const nextFavorite = !document.is_favorite
  const wasFavoritesScope = scope.value === 'favorites'
  documents.value = documents.value
    .map((item) =>
      item.id === document.id
        ? { ...item, is_favorite: nextFavorite }
        : item,
    )
    .filter((item) =>
      wasFavoritesScope && !nextFavorite ? item.id !== document.id : true,
    )
  if (workspace.value) {
    workspace.value = {
      ...workspace.value,
      favorite_count: Math.max(
        0,
        workspace.value.favorite_count + (nextFavorite ? 1 : -1),
      ),
    }
  }
  try {
    if (nextFavorite) {
      await favoriteDocument(document.id)
      notify('已加入收藏')
    } else {
      await unfavoriteDocument(document.id)
      notify('已移出收藏')
    }
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    notify(
      error instanceof ApiError ? error.message : '收藏操作失败',
      'error',
    )
    await refreshWorkspaceAndList()
  } finally {
    favoriteBusyId.value = null
  }
}

async function handleReorder(documentIds: number[]) {
  if (sorting.value) {
    return
  }
  sorting.value = true
  try {
    if (scope.value === 'chapter') {
      await reorderDocuments(
        'folder',
        documentIds,
        selectedChapterId.value ?? undefined,
        0,
      )
    } else if (scope.value === 'folder') {
      await reorderDocuments(
        'folder',
        documentIds,
        undefined,
        selectedFolderId.value ?? undefined,
      )
    } else {
      await reorderDocuments(scope.value, documentIds)
    }
    const byId = new Map(documents.value.map((item) => [item.id, item]))
    documents.value = documentIds
      .map((id) => byId.get(id))
      .filter((item): item is DocumentSummary => Boolean(item))
    notify('顺序已保存', 'info')
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    notify(
      error instanceof ApiError
        ? error.message
        : '排序保存失败，已恢复服务器顺序',
      'error',
    )
    await loadDocuments(false)
  } finally {
    sorting.value = false
  }
}

async function handleRestored(document: DocumentDetail) {
  notify(document.restore_notice || '文档已恢复')
  await refreshWorkspaceAndList()
}

function openCreateChapter() {
  mobileSheetOpen.value = false
  chapterDialogMode.value = 'create'
  chapterTarget.value = null
  chapterDialogOpen.value = true
}

function openRenameChapter(chapter: Chapter) {
  mobileSheetOpen.value = false
  chapterDialogMode.value = 'rename'
  chapterTarget.value = chapter
  chapterDialogOpen.value = true
}

async function handleChapterSaved(chapter: Chapter) {
  const mode = chapterDialogMode.value
  chapterDialogOpen.value = false
  chapterTarget.value = null
  await loadWorkspace()
  if (mode === 'create') {
    selectChapter(chapter.id)
    notify('章节已创建')
    return
  }
  notify('章节名称已更新')
  await loadDocuments(false)
}

function openDeleteChapter(chapter: Chapter) {
  mobileSheetOpen.value = false
  deleteChapterTarget.value = chapter
  deleteChapterOpen.value = true
}

async function handleChapterDeleted(chapter: Chapter) {
  deleteChapterOpen.value = false
  deleteChapterTarget.value = null
  const wasSelected =
    scope.value === 'chapter' && selectedChapterId.value === chapter.id
  notify('章节已删除，章节内文档已转为未分类')
  if (wasSelected) {
    scope.value = 'library'
    selectedChapterId.value = null
  }
  await refreshWorkspaceAndList()
}

async function handleReorderChapters(chapterIds: number[]) {
  if (!workspace.value) {
    return
  }
  const byId = new Map(
    workspace.value.chapters.map((chapter) => [chapter.id, chapter]),
  )
  const next = chapterIds
    .map((id) => byId.get(id))
    .filter((chapter): chapter is Chapter => Boolean(chapter))
  workspace.value = { ...workspace.value, chapters: next }
  try {
    await reorderChapters(chapterIds)
    notify('章节顺序已保存', 'info')
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    notify('章节排序保存失败', 'error')
    await loadWorkspace()
  }
}

async function handleMoveChapter(chapter: Chapter, direction: -1 | 1) {
  if (!workspace.value) {
    return
  }
  const index = workspace.value.chapters.findIndex(
    (item) => item.id === chapter.id,
  )
  const target = index + direction
  if (index < 0 || target < 0 || target >= workspace.value.chapters.length) {
    return
  }
  const next = workspace.value.chapters.slice()
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  workspace.value = { ...workspace.value, chapters: next }
  try {
    await reorderChapters(next.map((item) => item.id))
  } catch (error) {
    if (await handleUnauthorized(error)) {
      return
    }
    notify('章节排序保存失败', 'error')
    await loadWorkspace()
  }
}

function openCreateFolder(parentId = 0) {
  const chapterId =
    scope.value === 'folder'
      ? currentFolder.value?.chapter_id ?? null
      : scope.value === 'chapter'
        ? selectedChapterId.value
        : null
  if (chapterId === null) {
    notify('请先进入一个章节再新建文件夹', 'info')
    return
  }
  folderDialogMode.value = 'create'
  folderDialogParentId.value = Number(parentId || 0)
  folderDialogChapterId.value = chapterId
  folderTarget.value = null
  folderDialogOpen.value = true
  mobileSheetOpen.value = false
}

function createFolderFromMobile() {
  mobileAddOpen.value = false
  openCreateFolder(scope.value === 'folder' ? selectedFolderId.value ?? 0 : 0)
}

function openEditFolder(folder: Folder) {
  folderDialogMode.value = 'rename'
  folderDialogParentId.value = Number(folder.parent_id || 0)
  folderDialogChapterId.value = folder.chapter_id
  folderTarget.value = folder
  folderDialogOpen.value = true
  mobileSheetOpen.value = false
}

async function handleFolderSaved(folder: Folder) {
  const mode = folderDialogMode.value
  folderDialogOpen.value = false
  folderTarget.value = null
  await loadWorkspace()
  selectFolder(folder.id)
  notify(mode === 'create' ? '文件夹已创建' : '文件夹已更新')
}

function openDeleteFolder(folder: Folder) {
  deleteFolderTarget.value = folder
  deleteFolderOpen.value = true
  mobileSheetOpen.value = false
}

async function handleFolderDeleted(folder: Folder) {
  deleteFolderOpen.value = false
  deleteFolderTarget.value = null
  const parentId = Number(folder.parent_id || 0)
  if (scope.value === 'folder' && selectedFolderId.value === folder.id) {
    if (parentId !== 0 && folders.value.some((item) => item.id === parentId)) {
      selectFolder(parentId)
    } else if (
      folder.chapter_id !== null &&
      chapters.value.some((chapter) => chapter.id === Number(folder.chapter_id))
    ) {
      selectChapter(Number(folder.chapter_id))
    } else {
      selectLibrary()
    }
  }
  await loadWorkspace()
  await loadDocuments(false)
  notify('文件夹已删除，内容已移到上级目录')
}

async function handleMoveFolder(folder: Folder, direction: -1 | 1) {
  const parentId = Number(folder.parent_id || 0)
  const siblings = folders.value
    .filter(
      (item) =>
        Number(item.parent_id || 0) === parentId &&
        Number(item.chapter_id) === Number(folder.chapter_id),
    )
    .slice()
    .sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))
  const index = siblings.findIndex((item) => item.id === folder.id)
  const target = index + direction
  if (index < 0 || target < 0 || target >= siblings.length) return
  const next = siblings.slice()
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  if (workspace.value) {
    const nextFolders = folders.value.map((item) => {
      const order = next.findIndex((entry) => entry.id === item.id)
      return order >= 0 ? { ...item, sort_order: order } : item
    })
    workspace.value = { ...workspace.value, folders: nextFolders }
  }
  try {
    await reorderFolders(
      parentId,
      next.map((item) => item.id),
      folder.chapter_id,
    )
    notify('文件夹顺序已保存', 'info')
  } catch (error) {
    if (await handleUnauthorized(error)) return
    notify('文件夹排序保存失败', 'error')
    await loadWorkspace()
  }
}

function openMoveDocument(document: DocumentSummary) {
  moveTarget.value = document
  moveOpen.value = true
}

async function handleDocumentMoved(
  documentId: number,
  folderId: number | null,
) {
  moveOpen.value = false
  moveTarget.value = null
  notify(folderId ? '文档已移动到文件夹' : '文档已移动到章节根目录')
  await loadWorkspace()
  if (scope.value === 'folder' && selectedFolderId.value !== folderId) {
    await loadDocuments(false)
  } else {
    await loadDocuments(false)
  }
}

async function handleLogout() {
  try {
    await logoutAndRedirect()
  } catch (error) {
    notify(
      error instanceof Error ? error.message : '退出失败，请稍后重试',
      'error',
    )
  }
}

async function loginFromDemo() {
  try {
    await stopDemo()
    clearSession()
    await router.push({ name: 'login' })
  } catch {
    notify('暂时无法切换到 Qoder 登录，请稍后重试', 'error')
  }
}

function closeMobileOverlays() {
  mobileSheetOpen.value = false
  mobileAddOpen.value = false
}

function handleResize() {
  if (window.innerWidth >= 960) {
    closeMobileOverlays()
  }
}

watch(
  () => [mobileSheetOpen.value, mobileAddOpen.value],
  ([sheet, add]) => {
    document.body.classList.toggle('drawer-open', sheet || add)
  },
)

watch(
  appTitle,
  (value) => {
    document.title = value
  },
  { immediate: true },
)

onMounted(() => {
  bootstrap()
  window.addEventListener('resize', handleResize, { passive: true })
  window.addEventListener('dragenter', onWindowDragEnter)
  window.addEventListener('dragover', onWindowDragOver)
  window.addEventListener('dragleave', onWindowDragLeave)
  window.addEventListener('drop', onWindowDrop)
  window.addEventListener('dragend', onWindowDragEnd)
  window.addEventListener('dragend', clearFolderDrop)
})

onBeforeRouteLeave((to, from) => {
  closeMobileOverlays()
  dragImportActive.value = false
  if (to.name === 'document') {
    rememberHomeReturn(from.fullPath)
  }
  return true
})

onBeforeUnmount(() => {
  window.removeEventListener('dragenter', onWindowDragEnter)
  window.removeEventListener('dragover', onWindowDragOver)
  window.removeEventListener('dragleave', onWindowDragLeave)
  window.removeEventListener('drop', onWindowDrop)
  window.removeEventListener('dragend', onWindowDragEnd)
  window.removeEventListener('dragend', clearFolderDrop)
  closeMobileOverlays()
  window.removeEventListener('resize', handleResize)
  document.body.classList.remove('drawer-open')
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }
})
</script>

<template>
  <div class="workspace-page">
    <AppTopBar
      :user="user"
      :site-title="siteTitle"
      :favorite-count="favoriteCount"
      :recycle-count="recycleCount"
      :active="activeTopbar"
      @open-favorites="selectFavorites"
      @open-recycle="recycleOpen = true"
      @logout="handleLogout"
    />

    <div v-if="user?.is_demo" class="demo-banner">
      <span>
        <strong>示例模式</strong>
        可直接编辑体验，内容保存在独立示例空间；真实账号请使用 Qoder 登录。
      </span>
      <button type="button" @click="loginFromDemo">使用 Qoder 登录</button>
    </div>

    <div class="workspace-layout">
      <aside class="sidebar">
        <AuthorCard :user="user" :site-title="siteTitle" />

        <div class="sidebar-section">
          <ChapterNav
            :chapters="chapters"
            :scope="navScope"
            :selected-chapter-id="selectedChapterId"
            :favorite-count="favoriteCount"
            :library-count="libraryCount"
            @select-library="selectLibrary"
            @select-favorites="selectFavorites"
            @select-chapter="selectChapter"
            @create-chapter="openCreateChapter"
            @rename-chapter="openRenameChapter"
            @delete-chapter="openDeleteChapter"
            @move-chapter="handleMoveChapter"
            @reorder-chapters="handleReorderChapters"
          />
        </div>

        <div class="sidebar-stats">
          <div class="stat-copy">
            <span>图片空间</span>
            <strong>{{ formatBytes(storage.total_bytes) }}</strong>
            <small>{{ storage.asset_count }} 张图片 · 回收站 {{ recycleCount }} 项</small>
          </div>
          <RouterLink class="security-link" :to="{ name: 'account' }">
            账号设置
          </RouterLink>
        </div>
      </aside>

      <main class="main-content">
        <div v-if="workspaceError" class="page-error" role="alert">
          <p class="eyebrow">WORKSPACE / LOST</p>
          <h1>工作区暂时不可用</h1>
          <p>{{ workspaceError }}</p>
          <button type="button" class="primary-button" @click="bootstrap">
            重新加载
          </button>
        </div>

        <template v-else>
          <header v-if="scope === 'library'" class="intro">
            <p class="intro-by">{{ user?.display_name || '示例学习者' }} 的学习手记</p>
            <h1><span>C</span> 语言学习笔记</h1>
            <p class="intro-desc">记录语法、练习题和写代码时遇到的问题。</p>
          </header>

          <header class="content-head" :class="{ 'files-head': scope === 'library' }">
            <div class="head-copy">
              <p v-if="scope !== 'library'" class="eyebrow">{{ scopeEyebrow }}</p>
              <h1>{{ currentTitle }}</h1>
              <p v-if="scopeDescription" class="lede">{{ scopeDescription }}</p>
            </div>
            <div v-if="scope === 'library'" class="files-meta">
              <span class="storage-chip" :class="{ demo: user?.is_demo }">
                <i aria-hidden="true"></i>
                {{ user?.is_demo ? '示例空间' : '私有空间' }}
              </span>
              <span class="file-count">{{ currentCount }} 个文件</span>
            </div>
            <div class="head-actions">
              <button
                type="button"
                class="action-button primary"
                @click="openCreate('note')"
              >
                <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path
                    d="M9 3v12M3 9h12"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                </svg>
                新建笔记
              </button>
              <button
                type="button"
                class="action-button"
                @click="openCreate('source')"
              >
                <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path
                    d="m6.5 5-4 4 4 4M11.5 5l4 4-4 4"
                    stroke="currentColor"
                    stroke-width="1.4"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                新建 C 文件
              </button>
              <button
                type="button"
                class="action-button ghost"
                @click="openCreate('import')"
              >
                <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path
                    d="M9 12V3m0 0L6 6m3-3 3 3M3.5 11v2.5A1.5 1.5 0 0 0 5 15h8a1.5 1.5 0 0 0 1.5-1.5V11"
                    stroke="currentColor"
                    stroke-width="1.4"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                上传
              </button>
              <button
                type="button"
                class="action-button ghost"
                @click="openCreateFolder(scope === 'folder' ? selectedFolderId ?? 0 : 0)"
              >
                新建文件夹
              </button>
            </div>
          </header>

          <div class="workspace-search">
            <span class="search-icon" aria-hidden="true">
              <svg viewBox="0 0 20 20" fill="none">
                <circle cx="8.5" cy="8.5" r="4.8" stroke="currentColor" stroke-width="1.5" />
                <path d="m12.2 12.2 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </span>
            <input
              v-model="searchQuery"
              type="search"
              :placeholder="`在${currentTitle}中搜索标题、正文、源码、备注、结果、表格和公式`"
              aria-label="搜索笔记"
              @keydown.esc="clearSearchState"
            />
            <span class="search-scope">{{ currentTitle }}</span>
            <button
              v-if="searchActive"
              type="button"
              class="search-clear"
              aria-label="清除搜索"
              @click="clearSearchState"
            >
              ×
            </button>
          </div>

          <AiChoiceBanner @changed="refreshWorkspaceAndList" />

          <SearchResults
            v-if="searchActive"
            :query="searchQuery.trim()"
            :payload="searchPayload"
            :loading="searchLoading"
            :error="searchError"
            :loading-more="searchLoadingMore"
            @retry="runSearch(0, false)"
            @load-more="loadMoreSearch"
            @clear="clearSearchState"
          />

          <template v-else>
            <nav
              v-if="scope === 'folder' && currentFolder"
              class="folder-crumbs"
              aria-label="章节与文件夹路径"
            >
              <button type="button" @click="selectLibrary">全部</button>
              <span aria-hidden="true">/</span>
              <button
                v-if="currentFolder.chapter_id !== null"
                type="button"
                @click="selectChapter(Number(currentFolder.chapter_id))"
              >
                {{ currentChapterName }}
              </button>
              <template v-for="crumb in folderBreadcrumbs" :key="crumb.id">
                <span aria-hidden="true">/</span>
                <button type="button" @click="selectFolder(crumb.id)">
                  {{ crumb.name }}
                </button>
              </template>
            </nav>

            <div
              v-if="scope === 'folder' && currentFolder"
              class="folder-toolbar"
              aria-label="文件夹操作"
            >
              <button type="button" @click="openCreateFolder(currentFolder.id)">
                新建子文件夹
              </button>
              <button type="button" @click="openEditFolder(currentFolder)">
                重命名
              </button>
              <button
                type="button"
                @click="handleMoveFolder(currentFolder, -1)"
              >
                上移
              </button>
              <button
                type="button"
                @click="handleMoveFolder(currentFolder, 1)"
              >
                下移
              </button>
              <button
                type="button"
                class="danger"
                @click="openDeleteFolder(currentFolder)"
              >
                删除
              </button>
            </div>

            <section
              v-if="visibleFolders.length"
              class="chapter-folder-section"
              aria-labelledby="chapter-folders-title"
            >
              <div class="folder-list-head">
                <h2 id="chapter-folders-title">文件夹</h2>
                <span>{{ visibleFolders.length }} 个</span>
              </div>
              <div class="child-folder-grid">
                <button
                  v-for="folder in visibleFolders"
                  :key="folder.id"
                  type="button"
                  class="child-folder"
                  :class="{ 'drop-target': folderDropTargetId === folder.id }"
                  @click="selectFolder(folder.id)"
                  @dragover="onFolderDragOver(folder.id, $event)"
                  @dragleave="onFolderDragLeave(folder.id, $event)"
                  @drop="handleFolderDrop(folder.id, $event)"
                >
                  <span class="child-folder-icon" aria-hidden="true">▸</span>
                  <span>
                    <strong>{{ folder.name }}</strong>
                    <small>
                      {{ folder.child_count }} 个子文件夹 ·
                      {{ folder.document_count }} 篇文档
                    </small>
                  </span>
                </button>
              </div>
            </section>

            <div v-if="scope !== 'library'" class="context-bar">
            <div class="context-copy">
              <span>当前范围</span>
              <strong>{{ currentTitle }}</strong>
            </div>
            <div class="context-meta">
              <span>{{ currentCount }} 篇</span>
              <span class="context-dot" aria-hidden="true"></span>
              <span>私有空间</span>
              <span class="context-dot" aria-hidden="true"></span>
              <span>排序云端保存</span>
            </div>
          </div>

          <div class="library-wrap">
            <p
              v-if="workspaceLoading || listLoading"
              class="list-loading"
              role="status"
            >
              正在读取笔记…
            </p>
            <DocumentList
              :documents="documents"
              :loading="listLoading || workspaceLoading"
              :error-message="listError"
              :scope="scope"
              :sorting="sorting"
              :favorite-busy-id="favoriteBusyId"
              @retry="loadDocuments(true)"
              @favorite="handleFavorite"
              @rename="openEdit"
              @move="openMoveDocument"
              @delete="openDelete"
              @reorder="handleReorder"
            />
          </div>
          </template>

          <p class="drop-hint">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M4 4h16v16H4zM12 8v8m-3-3 3 3 3-3"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            可将 Markdown、C、H 文件拖入页面上传，支持一次拖入多个
          </p>

          <footer class="content-foot">
            <span class="foot-mark" aria-hidden="true">C</span>
            <span>{{ user?.display_name || '个人笔记空间' }}</span>
            <span class="foot-line" aria-hidden="true"></span>
            <span>
              {{ libraryCount }} 篇全部 · {{ favoriteCount }} 篇收藏 ·
              {{ recycleCount }} 项回收 · 图片 {{ formatBytes(storage.total_bytes) }}
            </span>
          </footer>
        </template>
      </main>
    </div>
    <nav class="mobile-dock" aria-label="手机目录">
      <button
        type="button"
        class="dock-button"
        :class="{ active: scope === 'library' || scope === 'chapter' || scope === 'folder' }"
        @click="mobileSheetOpen = true"
      >
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M4 5.5h12M4 10h12M4 14.5h8"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
        <span>目录</span>
        <small>{{ currentTitle }}</small>
      </button>
      <button
        type="button"
        class="dock-button favorite"
        :class="{ active: scope === 'favorites' }"
        @click="selectFavorites"
      >
        <svg viewBox="0 0 20 20" aria-hidden="true">
          <path
            d="m10 2.6 2.1 4.3 4.8.7-3.5 3.4.8 4.7L10 13.5l-4.2 2.2.8-4.7L3.1 7.6l4.8-.7L10 2.6Z"
          />
        </svg>
        <span>收藏</span>
        <small>{{ favoriteCount }}</small>
      </button>
      <button
        type="button"
        class="dock-button"
        @click="recycleOpen = true"
      >
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M4.5 6h11M7 6V4.6h6V6m-7.4 0 .8 9.1h7.2l.8-9.1"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
        <span>回收站</span>
        <small>{{ recycleCount }}</small>
      </button>
    </nav>

    <button
      type="button"
      class="mobile-fab"
      :class="{ open: mobileAddOpen }"
      :aria-expanded="mobileAddOpen"
      aria-label="新建内容"
      @click="mobileAddOpen = !mobileAddOpen"
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 5v14M5 12h14"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
        />
      </svg>
    </button>

      <Transition name="sheet">
        <div v-if="mobileSheetOpen" class="sheet-root">
          <div class="sheet-backdrop" @click="mobileSheetOpen = false"></div>
          <section
            class="mobile-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="目录"
          >
            <div class="sheet-grip" aria-hidden="true"></div>
            <header class="sheet-head">
              <div>
                <p class="sheet-eyebrow">LIBRARY / CHAPTERS</p>
                <h2>目录</h2>
              </div>
              <button
                type="button"
                class="sheet-close"
                aria-label="关闭目录"
                @click="mobileSheetOpen = false"
              >
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path
                    d="m5 5 10 10M15 5 5 15"
                    stroke="currentColor"
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                </svg>
              </button>
            </header>
            <div class="sheet-body">
              <ChapterNav
                :chapters="chapters"
                :scope="navScope"
                :selected-chapter-id="selectedChapterId"
                :favorite-count="favoriteCount"
                :library-count="libraryCount"
                @select-library="selectLibrary"
                @select-favorites="selectFavorites"
                @select-chapter="selectChapter"
                @create-chapter="openCreateChapter"
                @rename-chapter="openRenameChapter"
                @delete-chapter="openDeleteChapter"
                @move-chapter="handleMoveChapter"
                @reorder-chapters="handleReorderChapters"
              />
            </div>
            <footer class="sheet-foot">
              <span>图片 {{ formatBytes(storage.total_bytes) }} · {{ storage.asset_count }} 张</span>
              <span>回收站 {{ recycleCount }} 项</span>
            </footer>
          </section>
        </div>
      </Transition>

      <Transition name="add-menu">
        <div v-if="mobileAddOpen" class="mobile-add-root">
          <div class="mobile-add-backdrop" @click="mobileAddOpen = false"></div>
          <div class="mobile-add-menu" role="menu" aria-label="新建内容">
            <button type="button" @click="openCreate('note')">
              <span class="add-icon note">N</span>
              <span><strong>新建笔记</strong><small>Markdown 富文本模块</small></span>
            </button>
            <button type="button" @click="openCreate('source')">
              <span class="add-icon source">C</span>
              <span><strong>新建 C 文件</strong><small>源码与备注模块</small></span>
            </button>
            <button type="button" @click="openCreate('import')">
              <span class="add-icon upload">↑</span>
              <span><strong>上传文件</strong><small>.md / .c / .h</small></span>
            </button>
            <button type="button" @click="createFolderFromMobile">
              <span class="add-icon folder">▤</span>
              <span><strong>新建文件夹</strong><small>在章节内整理笔记与源码</small></span>
            </button>
          </div>
        </div>
      </Transition>

    <Transition name="drop-fade">
      <div
        v-if="dragImportActive && !importing"
        class="drop-overlay"
        aria-hidden="true"
      >
        <div class="drop-card">
          <span class="drop-icon">↓</span>
          <strong>松手导入文件</strong>
          <small>Markdown · C · H，可一次拖入多个</small>
        </div>
      </div>
    </Transition>

    <Transition name="drop-fade">
      <div v-if="importing" class="import-overlay" role="status" aria-live="polite">
        <div class="import-card">
          <p>正在导入文件</p>
          <strong>{{ importProgress.done }} / {{ importProgress.total }}</strong>
          <div class="import-bar" aria-hidden="true">
            <span
              :style="{
                width: `${
                  importProgress.total
                    ? Math.round(
                        (importProgress.done / importProgress.total) * 100,
                      )
                    : 0
                }%`,
              }"
            ></span>
          </div>
          <small>按当前章节和文件夹依次落库…</small>
        </div>
      </div>
    </Transition>

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

    <CreateDocumentDialog
      :open="createOpen"
      :mode="createMode"
      :chapters="chapters"
      :folders="folders"
      :default-chapter-id="createDefaultChapter"
      :default-folder-id="createDefaultFolder"
      @close="createOpen = false"
      @created="handleCreated"
    />
    <FolderDialog
      :open="folderDialogOpen"
      :mode="folderDialogMode"
      :folder="folderTarget"
      :parent-id="folderDialogParentId"
      :chapter-id="folderDialogChapterId"
      :folders="folders"
      @close="folderDialogOpen = false"
      @saved="handleFolderSaved"
    />
    <DeleteFolderDialog
      :open="deleteFolderOpen"
      :folder="deleteFolderTarget"
      @close="deleteFolderOpen = false"
      @deleted="handleFolderDeleted"
    />
    <MoveDocumentDialog
      :open="moveOpen"
      :document="moveTarget"
      :folders="folders"
      @close="moveOpen = false"
      @moved="handleDocumentMoved"
    />
    <EditDocumentDialog
      :open="editOpen"
      :document="editTarget"
      :chapters="chapters"
      @close="editOpen = false"
      @saved="handleSaved"
    />
    <DeleteDocumentDialog
      :open="deleteOpen"
      :document="deleteTarget"
      :retention-days="retentionDays"
      @close="deleteOpen = false"
      @deleted="handleDeleted"
    />
    <RecycleDialog
      :open="recycleOpen"
      :retention-days="retentionDays"
      @close="recycleOpen = false"
      @restored="handleRestored"
    />
    <ChapterDialog
      :open="chapterDialogOpen"
      :mode="chapterDialogMode"
      :chapter="chapterTarget"
      @close="chapterDialogOpen = false"
      @saved="handleChapterSaved"
    />
    <DeleteChapterDialog
      :open="deleteChapterOpen"
      :chapter="deleteChapterTarget"
      @close="deleteChapterOpen = false"
      @deleted="handleChapterDeleted"
    />
  </div>
</template>

<style scoped>
.workspace-page {
  position: relative;
  min-height: 100vh;
  padding-bottom: 40px;
}

.demo-banner {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  padding: 8px 20px;
  border-bottom: 1px solid #d8cef2;
  color: var(--muted-strong);
  font-size: 12px;
  background: #f3edff;
}

.demo-banner strong {
  margin-right: 5px;
  color: var(--accent-strong);
}

.demo-banner button {
  padding: 5px 10px;
  border: 1px solid #cfc0f0;
  border-radius: 7px;
  color: var(--accent-strong);
  font: inherit;
  font-size: 11.5px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.demo-banner button:hover {
  border-color: var(--accent);
}

.workspace-layout {
  display: grid;
  grid-template-columns: 318px minmax(0, 1fr);
  width: min(1380px, 100%);
  margin: 0 auto;
}

.sidebar {
  position: sticky;
  top: 66px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: calc(100vh - 66px);
  padding: 26px 22px 24px 30px;
  border-right: 1px solid rgba(231, 225, 247, 0.82);
  background: #fbfaff;
}

.sidebar-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
}

.sidebar-stats {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  justify-content: space-between;
  padding-top: 15px;
  border-top: 1px solid var(--border);
}

.stat-copy {
  display: grid;
  gap: 2px;
}

.stat-copy span {
  color: var(--muted);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.stat-copy strong {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 650;
}

.stat-copy small {
  color: #9f97b1;
  font-size: 9.5px;
  line-height: 1.5;
}

.security-link {
  flex: none;
  padding: 6px 9px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted-strong);
  font-size: 9.5px;
  font-weight: 650;
  background: rgba(255, 255, 255, 0.65);
}

.security-link:hover {
  color: var(--accent-strong);
  border-color: var(--border-strong);
}

.main-content {
  width: 100%;
  max-width: 920px;
  min-width: 0;
  margin: 0 auto;
  padding: 44px 48px 48px;
}

.list-loading {
  margin: 0 0 8px;
  padding: 0 2px;
  color: var(--muted);
  font-size: 12px;
}

.intro {
  margin: 0 0 24px;
  padding: 0 1px;
  animation: content-in 0.32s ease both;
}

.intro-by {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.07em;
}

.intro-by::before {
  content: "";
  width: 17px;
  height: 3px;
  border-radius: 99px;
  background: var(--accent);
}

.intro h1 {
  margin: 0;
  color: #2f2745;
  font-size: clamp(30px, 3.6vw, 43px);
  font-weight: 790;
  line-height: 1.22;
  letter-spacing: -0.045em;
}

.intro h1 span {
  color: var(--accent);
  margin-right: 5px;
}

.intro-desc {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 14px;
}

.content-head {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  justify-content: space-between;
  animation: content-in 0.5s ease both;
}

.content-head.files-head {
  align-items: center;
  flex-wrap: wrap;
}

.content-head.files-head .head-copy h1 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 760;
  letter-spacing: 0;
  line-height: 1.35;
}

.content-head.files-head .head-copy h1::before {
  content: "";
  width: 4px;
  height: 15px;
  border-radius: 3px;
  background: var(--accent);
}

.files-meta {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-left: auto;
}

.storage-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  border: 1px solid #d8e9df;
  border-radius: 99px;
  color: #3e7059;
  background: #f3f8f5;
  font-size: 11px;
  line-height: 1.45;
  white-space: nowrap;
}

.storage-chip i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.storage-chip.demo {
  border-color: #f0dfb9;
  color: #8a6a12;
  background: #fff8e1;
}

.file-count {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.content-head.files-head .head-actions {
  flex-wrap: nowrap;
}

.content-head.files-head .action-button {
  padding: 5px 9px;
  border-radius: 7px;
  font-size: 12px;
}

.content-head.files-head .action-button svg {
  width: 13px;
  height: 13px;
}

.head-copy {
  min-width: 0;
}

.eyebrow {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 650;
  letter-spacing: 0.18em;
}

.content-head h1 {
  margin-top: 10px;
  font-size: clamp(30px, 3.7vw, 44px);
  font-weight: 760;
  letter-spacing: -0.035em;
  line-height: 1.08;
}

.lede {
  max-width: 560px;
  margin-top: 11px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.75;
}

.head-actions {
  display: flex;
  flex: none;
  gap: 7px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.action-button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 8px 11px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 10.5px;
  font-weight: 650;
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
}

.action-button:hover {
  border-color: #cbbcf3;
  color: var(--accent-strong);
  background: #fff;
  transform: translateY(-1px);
}

.action-button svg {
  width: 14px;
  height: 14px;
}

.action-button.primary {
  border-color: var(--accent-strong);
  color: #fff;
  background: linear-gradient(145deg, #846aff, #5436e8);
  box-shadow: 0 10px 24px -18px rgba(84, 54, 232, 0.85);
}

.action-button.primary:hover {
  color: #fff;
  background: linear-gradient(145deg, #8f78ff, #4a2cd8);
}

.action-button.ghost {
  border-style: dashed;
  background: rgba(255, 255, 255, 0.45);
}

.context-bar {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-top: 25px;
  padding: 12px 15px;
  border: 1px solid var(--border);
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.58);
  box-shadow: 0 14px 34px -34px rgba(61, 42, 120, 0.6);
}

.context-copy {
  display: flex;
  gap: 9px;
  align-items: baseline;
  min-width: 0;
}

.context-copy span {
  color: var(--muted);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.context-copy strong {
  overflow: hidden;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  align-items: center;
  color: #928aa6;
  font-size: 9.5px;
}

.context-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c8c1d8;
}

.library-wrap {
  margin-top: 18px;
}

.drop-hint {
  display: flex;
  gap: 7px;
  align-items: center;
  margin: 14px 1px 0;
  color: var(--muted);
  font-size: 12px;
}

.drop-hint svg {
  flex: none;
  width: 15px;
  height: 15px;
  color: var(--accent);
}

.drop-overlay,
.import-overlay {
  position: fixed;
  inset: 14px;
  z-index: 220;
  display: grid;
  place-items: center;
  padding: 20px;
  pointer-events: none;
}

.drop-overlay {
  border: 2px dashed #8f75ee;
  border-radius: 18px;
  background: rgba(247, 244, 250, 0.92);
}

.drop-card,
.import-card {
  display: grid;
  gap: 6px;
  justify-items: center;
  min-width: min(320px, 80vw);
  padding: 24px 28px;
  border: 1px solid #d8cef2;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 24px 70px -30px rgba(52, 33, 112, 0.55);
  text-align: center;
}

.drop-icon {
  display: grid;
  width: 46px;
  height: 46px;
  margin-bottom: 2px;
  place-items: center;
  border-radius: 13px;
  color: var(--accent);
  font-size: 25px;
  background: var(--accent-soft);
}

.drop-card strong,
.import-card strong {
  color: var(--text);
  font-size: 17px;
}

.drop-card small,
.import-card small {
  color: var(--muted);
  font-size: 12px;
}

.import-card p {
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.import-bar {
  width: min(260px, 64vw);
  height: 7px;
  overflow: hidden;
  border-radius: 99px;
  background: #eee9f8;
}

.import-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width 0.2s ease;
}

.drop-fade-enter-active,
.drop-fade-leave-active {
  transition: opacity 0.16s ease;
}

.drop-fade-enter-from,
.drop-fade-leave-to {
  opacity: 0;
}

.content-foot {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 44px;
  padding-top: 17px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 10px;
}

.foot-mark {
  display: grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border-radius: 6px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  background: var(--accent-soft);
}

.foot-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

.page-error {
  display: grid;
  gap: 13px;
  justify-items: start;
  padding: 70px 12px;
}

.page-error h1 {
  font-size: 30px;
  letter-spacing: -0.03em;
}

.page-error p:not(.eyebrow) {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.8;
}

.primary-button {
  margin-top: 6px;
  padding: 9px 16px;
  border: 1px solid var(--accent-strong);
  border-radius: 10px;
  color: #fff;
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  background: var(--accent-strong);
  cursor: pointer;
}

.mobile-dock,
.mobile-fab {
  display: none;
}

.sheet-root {
  position: fixed;
  inset: 0;
  z-index: 140;
  display: flex;
  align-items: flex-end;
}

.sheet-backdrop,
.mobile-add-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(33, 27, 51, 0.4);
}

.mobile-sheet {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: min(78vh, 720px);
  padding: 10px 18px calc(18px + env(safe-area-inset-bottom));
  border-radius: 22px 22px 0 0;
  background: linear-gradient(160deg, #fff 0%, #faf7ff 100%);
  box-shadow: 0 -22px 70px -36px rgba(33, 27, 51, 0.6);
}

.sheet-grip {
  width: 38px;
  height: 4px;
  margin: 0 auto 12px;
  border-radius: 999px;
  background: #ded6ef;
}

.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.sheet-eyebrow {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 8.5px;
  font-weight: 650;
  letter-spacing: 0.16em;
}

.sheet-head h2 {
  margin-top: 3px;
  font-size: 20px;
  letter-spacing: -0.02em;
}

.sheet-close {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--muted-strong);
  background: #fff;
  cursor: pointer;
}

.sheet-close svg {
  width: 15px;
  height: 15px;
}

.sheet-body {
  min-height: 0;
  overflow-y: auto;
}

.sheet-foot {
  display: flex;
  justify-content: space-between;
  padding-top: 13px;
  margin-top: 12px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 9.5px;
}

.mobile-add-root {
  position: fixed;
  inset: 0;
  z-index: 150;
}

.mobile-add-menu {
  position: absolute;
  right: 16px;
  bottom: calc(148px + env(safe-area-inset-bottom));
  display: grid;
  gap: 6px;
  width: min(290px, calc(100vw - 32px));
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 28px 70px -30px rgba(33, 27, 51, 0.62);
}

.mobile-add-menu button {
  display: flex;
  gap: 11px;
  align-items: center;
  padding: 11px;
  border: 0;
  border-radius: 12px;
  color: var(--text);
  font: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.mobile-add-menu button:hover {
  background: var(--accent-faint);
}

.mobile-add-menu button > span:last-child {
  display: grid;
  gap: 2px;
}

.mobile-add-menu strong {
  font-size: 12px;
}

.mobile-add-menu small {
  color: var(--muted);
  font-size: 9.5px;
}

.add-icon {
  display: grid;
  flex: none;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 10px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

.add-icon.note {
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.add-icon.source {
  color: var(--source-text);
  background: var(--source-badge);
}

.add-icon.upload {
  color: #3c7a58;
  background: #edf8f1;
}

.add-icon.folder {
  color: #8a6a12;
  background: #fff8e1;
}

.toast {
  position: fixed;
  top: 78px;
  left: 50%;
  z-index: 220;
  display: flex;
  gap: 8px;
  align-items: center;
  max-width: min(90vw, 460px);
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

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.22s ease;
}

.sheet-enter-active .mobile-sheet,
.sheet-leave-active .mobile-sheet {
  transition: transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}

.sheet-enter-from .mobile-sheet,
.sheet-leave-to .mobile-sheet {
  transform: translateY(104%);
}

.add-menu-enter-active,
.add-menu-leave-active {
  transition: opacity 0.16s ease;
}

.add-menu-enter-active .mobile-add-menu,
.add-menu-leave-active .mobile-add-menu {
  transition: transform 0.18s ease;
}

.add-menu-enter-from,
.add-menu-leave-to {
  opacity: 0;
}

.add-menu-enter-from .mobile-add-menu,
.add-menu-leave-to .mobile-add-menu {
  transform: translateY(8px) scale(0.98);
}

@keyframes content-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1150px) {
  .workspace-layout {
    grid-template-columns: 292px minmax(0, 1fr);
  }

  .sidebar {
    padding: 24px 18px 22px 24px;
  }

  .main-content {
    padding: 38px 34px 44px;
  }

  .head-actions {
    max-width: 280px;
  }
}

@media (max-width: 960px) {
  .workspace-page {
    padding-bottom: calc(112px + env(safe-area-inset-bottom));
  }

  .workspace-layout {
    display: block;
  }

  .sidebar {
    display: none;
  }

  .main-content {
    max-width: none;
    padding: 28px 18px 46px;
  }

  .content-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 18px;
  }

  .content-head.files-head {
    align-items: flex-start;
  }

  .head-actions {
    display: none;
  }

  .context-bar {
    margin-top: 20px;
  }

  .mobile-dock {
    position: fixed;
    right: 10px;
    bottom: calc(9px + env(safe-area-inset-bottom));
    left: 10px;
    z-index: 90;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding: 5px;
    border: 1px solid rgba(231, 225, 247, 0.92);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.94);
    box-shadow: 0 20px 55px -28px rgba(33, 27, 51, 0.6);
  }

  .dock-button {
    display: grid;
    gap: 1px;
    min-height: 48px;
    justify-items: center;
    padding: 7px 5px 8px;
    border: 0;
    border-radius: 13px;
    color: var(--muted);
    font: inherit;
    background: transparent;
    cursor: pointer;
  }

  .dock-button svg {
    width: 18px;
    height: 18px;
    margin-bottom: 1px;
  }

  .dock-button span {
    font-size: 10px;
    font-weight: 650;
    line-height: 1.2;
  }

  .dock-button small {
    max-width: 100%;
    overflow: hidden;
    color: #9d94b1;
    font-size: 8.5px;
    line-height: 1.3;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dock-button.active {
    color: var(--accent-strong);
    background: var(--accent-faint);
  }

  .dock-button.favorite {
    color: var(--favorite-gold);
  }

  .dock-button.favorite.active {
    color: #805a1c;
    background: var(--favorite-gold-soft);
  }

  .mobile-fab {
    position: fixed;
    right: 16px;
    bottom: calc(94px + env(safe-area-inset-bottom));
    z-index: 100;
    display: grid;
    width: 54px;
    height: 54px;
    place-items: center;
    border: 1px solid rgba(255, 255, 255, 0.34);
    border-radius: 50%;
    color: #fff;
    background: linear-gradient(145deg, #846aff, #5436e8);
    box-shadow:
      0 16px 34px -12px rgba(84, 54, 232, 0.75),
      inset 0 0 0 1px rgba(255, 255, 255, 0.18);
    cursor: pointer;
    transition:
      transform 0.2s ease,
      box-shadow 0.2s ease;
  }

  .mobile-fab svg {
    width: 22px;
    height: 22px;
    transition: transform 0.22s ease;
  }

  .mobile-fab.open {
    box-shadow:
      0 18px 38px -12px rgba(84, 54, 232, 0.85),
      inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  }

  .mobile-fab.open svg {
    transform: rotate(45deg);
  }

  .toast {
    top: 72px;
  }
}

@media (max-width: 960px) {
  .drop-overlay {
    backdrop-filter: blur(5px);
  }

  .sheet-backdrop,
  .mobile-add-backdrop {
    backdrop-filter: blur(2px);
  }

  .mobile-dock {
    backdrop-filter: blur(18px);
  }
}

@media (max-width: 640px) {
  .main-content {
    padding: 20px 14px calc(40px + env(safe-area-inset-bottom));
  }

  .sort-hint {
    display: none;
  }

  .content-head h1 {
    margin-top: 8px;
    font-size: clamp(27px, 8vw, 36px);
  }

  .lede {
    margin-top: 8px;
    font-size: 12px;
  }

  .context-bar {
    align-items: flex-start;
    flex-direction: column;
    gap: 7px;
    padding: 11px 12px;
  }

  .context-meta {
    font-size: 9px;
  }

  .content-foot {
    align-items: flex-start;
    flex-direction: column;
    gap: 7px;
    margin-top: 34px;
  }

  .foot-line {
    display: none;
  }
}

.workspace-search {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 14px 0 2px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
}

.search-icon {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  color: #9d94b3;
}

.search-icon svg {
  width: 16px;
  height: 16px;
}

.workspace-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--text);
  font: inherit;
  font-size: 12px;
  background: transparent;
}

.workspace-search input::placeholder {
  color: #a59cb8;
}

.search-scope {
  flex: none;
  padding: 3px 7px;
  border-radius: 999px;
  color: var(--accent-strong);
  font-size: 9px;
  background: var(--accent-soft);
}

.search-clear {
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  color: var(--muted);
  font: inherit;
  font-size: 16px;
  background: transparent;
  cursor: pointer;
}

.search-clear:hover {
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.folder-crumbs {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
  margin: 8px 0 4px;
  color: #9d94b3;
  font-size: 12px;
}

.folder-crumbs button {
  padding: 3px 6px;
  border: 0;
  border-radius: 5px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  background: transparent;
  cursor: pointer;
}

.folder-crumbs button:hover {
  color: var(--accent-strong);
  background: var(--accent-soft);
}

.folder-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 12px;
}

.folder-toolbar button {
  min-height: 34px;
  padding: 6px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 12px;
  background: #fff;
  cursor: pointer;
}

.folder-toolbar button:hover {
  border-color: var(--border-strong);
  color: var(--accent-strong);
  background: var(--accent-faint);
}

.folder-toolbar button.danger {
  color: #a54848;
}

.folder-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 2px;
  color: var(--muted);
  font-size: 12px;
}

.folder-list-head h2 {
  font-size: 15px;
  letter-spacing: -0.01em;
}

.chapter-folder-section {
  display: grid;
  gap: 8px;
  margin: 10px 0 16px;
}

.child-folder-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 8px;
}

.child-folder {
  display: flex;
  gap: 9px;
  align-items: center;
  min-width: 0;
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: 11px;
  color: var(--muted-strong);
  font: inherit;
  text-align: left;
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
}

.child-folder:hover {
  border-color: var(--border-strong);
  color: var(--accent-strong);
  background: #fff;
}

.child-folder.drop-target {
  border-color: var(--accent);
  color: var(--accent-strong);
  background: var(--accent-soft);
  box-shadow: 0 0 0 3px rgba(84, 55, 189, 0.1);
}

.child-folder-icon {
  color: var(--accent);
  font-size: 16px;
}

.child-folder > span:last-child {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.child-folder strong {
  overflow: hidden;
  font-size: 13.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.child-folder small {
  color: #a49bb8;
  font-size: 11px;
}

.folder-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 3px 5px;
  color: var(--muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.folder-section-head button {
  padding: 3px 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--accent-strong);
  font: inherit;
  font-size: 8.5px;
  background: #fff;
  cursor: pointer;
}

.sheet-folder-block {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

@media (max-width: 640px) {
  .workspace-search {
    margin-top: 10px;
  }

  .search-scope {
    display: none;
  }

  .child-folder-grid {
    grid-template-columns: 1fr;
  }
}
</style>
