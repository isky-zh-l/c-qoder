import type {
  AccountDeletion,
  AdminAuditList,
  AdminPublicList,
  AdminSettings,
  AdminUser,
  AdminUserList,
  AssetInfo,
  BlockInput,
  Chapter,
  CreateDocumentPayload,
  DocumentDetail,
  DocumentScope,
  DocumentSummary,
  Folder,
  LoginPayload,
  MessagePayload,
  PublicationResponse,
  PublicDocument,
  RecycleItem,
  RegisterPayload,
  SearchPayload,
  SessionPayload,
  SitePayload,
  StorageUsage,
  UpdateDocumentPayload,
  UserProfile,
  Workspace,
} from './types'

const apiBase = (
  import.meta.env.VITE_API_BASE || `${import.meta.env.BASE_URL}api/v1`
).replace(/\/+$/, '')

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

let csrfToken = ''

export class ApiError extends Error {
  readonly status?: number
  readonly code?: string
  readonly details: Record<string, unknown>

  constructor(
    message: string,
    status?: number,
    code?: string,
    details: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function setCsrfToken(token: string | null | undefined) {
  csrfToken = token || ''
}

export function assetFileUrl(assetId: number): string {
  return `${apiBase}/assets/${assetId}/file`
}

export function assetDownloadUrl(assetId: number): string {
  return `${apiBase}/assets/${assetId}/download`
}

export function documentDownloadUrl(documentId: number): string {
  return `${apiBase}/documents/${documentId}/download`
}

export function publicAssetUrl(
  shareToken: string,
  assetId: number,
): string {
  return `${apiBase}/public/documents/${encodeURIComponent(shareToken)}/assets/${assetId}`
}

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method || 'GET'
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers || {}),
  }
  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData
  if (options.body !== undefined && !isFormData) {
    headers['Content-Type'] = 'application/json'
  }
  if (UNSAFE_METHODS.has(method) && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      method,
      credentials: 'include',
      headers,
      body:
        options.body === undefined
          ? undefined
          : isFormData
            ? (options.body as FormData)
            : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError('无法连接服务器，请确认后端已经启动')
  }

  if (!response.ok) {
    let message =
      response.status >= 500
        ? '服务器暂时不可用，请稍后重试'
        : `请求失败（${response.status}）`
    let code: string | undefined
    let details: Record<string, unknown> = {}
    try {
      const payload = (await response.json()) as {
        error?: {
          message?: string
          code?: string
          details?: Record<string, unknown>
        }
      }
      message = payload.error?.message || message
      code = payload.error?.code
      details = payload.error?.details || {}
    } catch {
      // 非 JSON 错误保留状态码提示
    }
    throw new ApiError(message, response.status, code, details)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function getPublicSite(): Promise<SitePayload> {
  return request<SitePayload>('/public/site')
}

export interface DemoStartPayload {
  demo: boolean
  authenticated?: boolean
  user?: UserProfile | null
  csrf_token?: string | null
}

export function startDemo(): Promise<DemoStartPayload> {
  return request<DemoStartPayload>('/public/demo/start', {
    method: 'POST',
  })
}

export function stopDemo(): Promise<{ demo: boolean }> {
  return request<{ demo: boolean }>('/public/demo/exit', {
    method: 'POST',
  })
}

export async function getSession(): Promise<SessionPayload> {
  const session = await request<SessionPayload>('/auth/session')
  setCsrfToken(session.csrf_token)
  return session
}

export async function login(
  email: string,
  password: string,
): Promise<LoginPayload> {
  const payload = await request<LoginPayload>('/auth/login', {
    method: 'POST',
    body: { email, password },
  })
  setCsrfToken(payload.csrf_token)
  return payload
}

export function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<RegisterPayload> {
  return request<RegisterPayload>('/auth/register', {
    method: 'POST',
    body: {
      email,
      password,
      ...(displayName ? { display_name: displayName } : {}),
    },
  })
}

export function verifyEmail(token: string): Promise<void> {
  return request<void>('/auth/verify-email', {
    method: 'POST',
    body: { token },
  })
}

export function resendVerification(email: string): Promise<MessagePayload> {
  return request<MessagePayload>('/auth/resend-verification', {
    method: 'POST',
    body: { email },
  })
}

export function forgotPassword(email: string): Promise<MessagePayload> {
  return request<MessagePayload>('/auth/forgot-password', {
    method: 'POST',
    body: { email },
  })
}

export function resetPassword(
  token: string,
  newPassword: string,
): Promise<void> {
  return request<void>('/auth/reset-password', {
    method: 'POST',
    body: { token, new_password: newPassword },
  })
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await request<void>('/auth/change-password', {
    method: 'POST',
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  })
  setCsrfToken('')
}

export function getMe(): Promise<UserProfile> {
  return request<UserProfile>('/me')
}

export function updateProfile(payload: {
  display_name?: string
  bio?: string
  avatar_asset_id?: number | null
}): Promise<UserProfile> {
  return request<UserProfile>('/me/profile', {
    method: 'PATCH',
    body: payload,
  })
}

export function getStorageUsage(): Promise<StorageUsage> {
  return request<StorageUsage>('/me/usage')
}

async function requestBlob(
  path: string,
): Promise<{ blob: Blob; filename: string }> {
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      credentials: 'include',
      headers: { Accept: 'application/zip' },
    })
  } catch {
    throw new ApiError('无法连接服务器，请确认后端已经启动')
  }
  if (!response.ok) {
    let message =
      response.status >= 500
        ? '服务器暂时不可用，请稍后重试'
        : `请求失败（${response.status}）`
    let code: string | undefined
    let details: Record<string, unknown> = {}
    try {
      const payload = (await response.json()) as {
        error?: {
          message?: string
          code?: string
          details?: Record<string, unknown>
        }
      }
      message = payload.error?.message || message
      code = payload.error?.code
      details = payload.error?.details || {}
    } catch {
      // 下载失败时保留状态码提示
    }
    throw new ApiError(message, response.status, code, details)
  }
  const disposition = response.headers.get('content-disposition') || ''
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const plain = disposition.match(/filename="?([^";]+)"?/i)
  const filename = encoded
    ? decodeURIComponent(encoded[1])
    : plain?.[1] || 'c-notes-export.zip'
  return { blob: await response.blob(), filename }
}

export function downloadMyExport(): Promise<{ blob: Blob; filename: string }> {
  return requestBlob('/me/export')
}

export function deleteMyAccount(
  currentPassword: string,
  confirmation: string,
): Promise<AccountDeletion> {
  return request<AccountDeletion>('/me/delete', {
    method: 'POST',
    body: {
      current_password: currentPassword,
      confirmation,
    },
  })
}

export function getWorkspace(): Promise<Workspace> {
  return request<Workspace>('/workspace')
}

export function getAdminSettings(): Promise<AdminSettings> {
  return request<AdminSettings>('/admin/settings')
}

export function updateAdminRegistration(
  enabled: boolean,
): Promise<AdminSettings> {
  return request<AdminSettings>('/admin/settings/registration', {
    method: 'PUT',
    body: { enabled },
  })
}

export function getAdminUsers(query = ''): Promise<AdminUserList> {
  const params = new URLSearchParams()
  if (query.trim()) {
    params.set('query', query.trim())
  }
  const suffix = params.toString()
  return request<AdminUserList>(`/admin/users${suffix ? `?${suffix}` : ''}`)
}

export function updateAdminUserStatus(
  userId: number,
  enabled: boolean,
): Promise<AdminUser> {
  return request<AdminUser>(`/admin/users/${userId}/status`, {
    method: 'PUT',
    body: { enabled },
  })
}

export function updateAdminUserQuota(
  userId: number,
  quotaBytes: number | null,
): Promise<AdminUser> {
  return request<AdminUser>(`/admin/users/${userId}/quota`, {
    method: 'PUT',
    body: { quota_bytes: quotaBytes },
  })
}

export function getAdminPublications(): Promise<AdminPublicList> {
  return request<AdminPublicList>('/admin/publications')
}

export function adminUnpublish(documentId: number): Promise<void> {
  return request<void>(`/admin/publications/${documentId}`, {
    method: 'DELETE',
  })
}

export function getAdminAudit(): Promise<AdminAuditList> {
  return request<AdminAuditList>('/admin/audit')
}

export function getChapters(): Promise<Chapter[]> {
  return request<Chapter[]>('/chapters')
}

export function createChapter(name: string): Promise<Chapter> {
  return request<Chapter>('/chapters', {
    method: 'POST',
    body: { name },
  })
}

export function updateChapter(
  chapterId: number,
  name: string,
): Promise<Chapter> {
  return request<Chapter>(`/chapters/${chapterId}`, {
    method: 'PATCH',
    body: { name },
  })
}

export function deleteChapter(chapterId: number): Promise<void> {
  return request<void>(`/chapters/${chapterId}`, { method: 'DELETE' })
}

export function reorderChapters(chapterIds: number[]): Promise<void> {
  return request<void>('/chapters/order', {
    method: 'PUT',
    body: { chapter_ids: chapterIds },
  })
}

export function getDocuments(
  scope: DocumentScope = 'library',
  chapterId?: number,
  folderId?: number,
): Promise<DocumentSummary[]> {
  const params = new URLSearchParams({ scope })
  if (chapterId !== undefined) {
    params.set('chapter_id', String(chapterId))
  }
  if (folderId !== undefined) {
    params.set('folder_id', String(folderId))
  }
  return request<DocumentSummary[]>(`/documents?${params.toString()}`)
}

export function searchDocuments(params: {
  query: string
  scope: 'all' | 'chapter' | 'folder'
  chapterId?: number | null
  folderId?: number | null
  offset?: number
  limit?: number
}): Promise<SearchPayload> {
  const search = new URLSearchParams({
    q: params.query,
    scope: params.scope,
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 20),
  })
  if (params.chapterId != null) {
    search.set('chapter_id', String(params.chapterId))
  }
  if (params.folderId != null) {
    search.set('folder_id', String(params.folderId))
  }
  return request<SearchPayload>(`/search?${search.toString()}`)
}

export function getFolders(): Promise<Folder[]> {
  return request<Folder[]>('/folders')
}

export function createFolder(
  name: string,
  parentId = 0,
  chapterId?: number | null,
): Promise<Folder> {
  return request<Folder>('/folders', {
    method: 'POST',
    body: {
      name,
      parent_id: parentId,
      ...(chapterId != null ? { chapter_id: chapterId } : {}),
    },
  })
}

export function updateFolder(
  folderId: number,
  payload: { name?: string; parent_id?: number | null },
): Promise<Folder> {
  return request<Folder>(`/folders/${folderId}`, {
    method: 'PATCH',
    body: payload,
  })
}

export function deleteFolder(folderId: number): Promise<void> {
  return request<void>(`/folders/${folderId}`, { method: 'DELETE' })
}

export function reorderFolders(
  parentId: number,
  folderIds: number[],
  chapterId?: number | null,
): Promise<void> {
  return request<void>('/folders/order', {
    method: 'PUT',
    body: {
      parent_id: parentId,
      folder_ids: folderIds,
      ...(chapterId != null ? { chapter_id: chapterId } : {}),
    },
  })
}

export function getDocument(documentId: number): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/documents/${documentId}`)
}

export function createDocument(
  payload: CreateDocumentPayload,
): Promise<DocumentDetail> {
  return request<DocumentDetail>('/documents', {
    method: 'POST',
    body: payload,
  })
}

export function importDocument(
  file: File,
  title: string | null,
  chapterId: number | null,
  folderId: number | null = null,
): Promise<DocumentDetail> {
  const form = new FormData()
  form.append('file', file)
  if (title?.trim()) {
    form.append('title', title.trim())
  }
  if (chapterId !== null) {
    form.append('chapter_id', String(chapterId))
  }
  if (folderId !== null) {
    form.append('folder_id', String(folderId))
  }
  return request<DocumentDetail>('/documents/import', {
    method: 'POST',
    body: form,
  })
}

export function updateDocument(
  documentId: number,
  payload: UpdateDocumentPayload,
  version: number,
): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/documents/${documentId}`, {
    method: 'PATCH',
    body: payload,
    headers: { 'If-Match': String(version) },
  })
}

export function saveDocumentBlocks(
  documentId: number,
  blocks: BlockInput[],
  version: number,
  title?: string,
  chapterId?: number | null,
): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/documents/${documentId}/blocks`, {
    method: 'PUT',
    body: {
      blocks,
      ...(title !== undefined ? { title } : {}),
      ...(chapterId !== undefined ? { chapter_id: chapterId } : {}),
    },
    headers: { 'If-Match': String(version) },
  })
}

export function deleteDocument(documentId: number): Promise<void> {
  return request<void>(`/documents/${documentId}`, { method: 'DELETE' })
}

export function uploadAsset(file: File): Promise<AssetInfo> {
  const form = new FormData()
  form.append('file', file)
  return request<AssetInfo>('/assets', {
    method: 'POST',
    body: form,
  })
}

export function favoriteDocument(documentId: number): Promise<void> {
  return request<void>(`/documents/${documentId}/favorite`, {
    method: 'PUT',
  })
}

export function unfavoriteDocument(documentId: number): Promise<void> {
  return request<void>(`/documents/${documentId}/favorite`, {
    method: 'DELETE',
  })
}

export function reorderDocuments(
  scope: DocumentScope,
  documentIds: number[],
  chapterId?: number,
  folderId?: number,
): Promise<void> {
  const path =
    scope === 'favorites'
      ? '/orders/favorites'
      : scope === 'chapter' && chapterId !== undefined
        ? `/orders/chapters/${chapterId}`
        : scope === 'folder' && folderId !== undefined
          ? `/orders/folders/${folderId}`
          : '/orders/library'
  return request<void>(path, {
    method: 'PUT',
    body: {
      document_ids: documentIds,
      ...(scope === 'folder' && folderId === 0 && chapterId != null
        ? { chapter_id: chapterId }
        : {}),
    },
  })
}

export function getRecycle(): Promise<RecycleItem[]> {
  return request<RecycleItem[]>('/recycle')
}

export function restoreRecycle(
  recycleId: number,
  title?: string,
): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/recycle/${recycleId}/restore`, {
    method: 'POST',
    body: title?.trim() ? { title: title.trim() } : {},
  })
}

export function updateVisibility(
  documentId: number,
  visibility: 'public' | 'private',
): Promise<PublicationResponse> {
  return request<PublicationResponse>(
    `/documents/${documentId}/visibility`,
    {
      method: 'PUT',
      body: { visibility },
    },
  )
}

export function getPublicDocument(
  shareToken: string,
): Promise<PublicDocument> {
  return request<PublicDocument>(
    `/public/documents/${encodeURIComponent(shareToken)}`,
  )
}

export { request as apiRequest }
