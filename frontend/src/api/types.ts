export type DocumentKind = 'note' | 'source'
export type SourceLanguage = 'c' | 'h'
export type Visibility = 'private' | 'public'
export type DocumentScope = 'library' | 'favorites' | 'chapter' | 'folder'
export type BlockType =
  | 'rich_text'
  | 'code'
  | 'remark'
  | 'result'
  | 'image'
  | 'formula'

export interface UserProfile {
  id: number
  email: string
  display_name: string
  bio: string
  avatar_asset_id: number | null
  email_verified_at: string | null
  is_enabled: boolean
  is_admin: boolean
  is_demo: boolean
  created_at: string
}

export interface Chapter {
  id: number
  name: string
  sort_order: number
  document_count: number
}

export interface Folder {
  id: number
  chapter_id: number | null
  parent_id: number
  name: string
  sort_order: number
  document_count: number
  child_count: number
  path: string | null
}

export interface DocumentSummary {
  id: number
  kind: DocumentKind
  title: string
  summary: string
  chapter_id: number | null
  chapter_name: string | null
  folder_id: number | null
  folder_name: string | null
  folder_path: string | null
  language: SourceLanguage | null
  visibility: Visibility
  is_favorite: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface DocumentBlock {
  id: number
  block_type: BlockType
  content: Record<string, unknown>
  asset_id: number | null
  sort_order: number
}

export interface BlockInput {
  id?: number
  block_type: BlockType
  content: Record<string, unknown>
  asset_id: number | null
}

export interface AssetInfo {
  id: number
  original_name: string
  mime_type: string
  size_bytes: number
}

export interface DocumentDetail extends DocumentSummary {
  share_token: string | null
  share_url: string | null
  published_at: string | null
  published_version: number | null
  blocks: DocumentBlock[]
  restore_notice?: string | null
}

export interface PublicationResponse {
  visibility: Visibility
  share_token: string | null
  share_url: string | null
  published_at: string | null
  published_version: number | null
}

export interface PublicAuthor {
  display_name: string
}

export interface PublicBlock {
  block_type: BlockType
  content: Record<string, unknown>
  asset_id: number | null
  sort_order: number
}

export interface PublicDocument {
  title: string
  kind: DocumentKind
  language: SourceLanguage | null
  author: PublicAuthor
  published_at: string
  blocks: PublicBlock[]
}

export interface WorkspaceStorage {
  asset_count: number
  total_bytes: number
}

export interface Workspace {
  user: UserProfile
  chapters: Chapter[]
  folders: Folder[]
  favorite_count: number
  library_count: number
  recycle_count: number
  storage: WorkspaceStorage
  usage?: StorageUsage
  recycle_retention_days: number
}

export interface RecycleItem {
  id: number
  document_id: number
  title: string
  kind: DocumentKind
  original_chapter_id: number | null
  original_chapter_name: string | null
  original_folder_id: number | null
  original_folder_name: string | null
  original_folder_path: string | null
  deleted_at: string
  expires_at: string
  days_remaining: number
}

export interface SitePayload {
  site_title: string
  registration_enabled: boolean
}

export interface StorageLimits {
  max_file_bytes: number
  max_image_bytes: number
  image_max_dimension: number
}

export interface StorageUsage {
  quota_bytes: number
  used_bytes: number
  reserved_bytes: number
  remaining_bytes: number
  source_bytes: number
  note_bytes: number
  image_bytes: number
  recycle_bytes: number
  publication_bytes: number
  asset_count: number
  document_count: number
  recycle_count: number
  folder_count?: number
  over_quota: boolean
  limits: StorageLimits
  recycle_retention_days: number
  account_deletion_retention_days: number
}

export interface AccountDeletion {
  message: string
  purge_after: string
  retention_days: number
}

export interface AdminSettings {
  registration_enabled: boolean
}

export interface AdminUser {
  id: number
  email: string
  display_name: string
  is_enabled: boolean
  is_admin: boolean
  email_verified_at: string | null
  created_at: string
  storage_quota_bytes: number | null
  effective_quota_bytes: number
  used_bytes: number
  reserved_bytes: number
  document_count: number
  recycle_count: number
  deletion_requested_at: string | null
  purge_after: string | null
}

export interface AdminUserList {
  users: AdminUser[]
  total: number
}

export interface AdminPublicDocument {
  document_id: number
  title: string
  owner_user_id: number
  owner_email: string
  author_display_name: string
  published_at: string
  source_version: number
  share_url: string | null
}

export interface AdminPublicList {
  documents: AdminPublicDocument[]
}

export interface AdminAudit {
  id: number
  action: string
  admin_user_id: number | null
  admin_email: string | null
  target_user_id: number | null
  target_user_email: string | null
  target_document_id: number | null
  target_document_title: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface AdminAuditList {
  entries: AdminAudit[]
}

export interface LoginPayload {
  user: UserProfile
  csrf_token: string
}

export interface SessionPayload {
  authenticated: boolean
  user: UserProfile | null
  csrf_token: string | null
}

export interface RegisterPayload {
  message: string
  email: string
}

export interface MessagePayload {
  message: string
}

export interface CreateDocumentPayload {
  kind: DocumentKind
  title: string
  chapter_id: number | null
  folder_id?: number | null
  language?: SourceLanguage
}

export interface UpdateDocumentPayload {
  title?: string
  chapter_id?: number | null
  folder_id?: number | null
}

export interface SearchResult {
  id: number
  title: string
  kind: DocumentKind
  language: SourceLanguage | null
  chapter_id: number | null
  chapter_name: string | null
  folder_id: number | null
  folder_path: string | null
  updated_at: string
  title_hit: boolean
  snippet: string
}

export interface SearchPayload {
  items: SearchResult[]
  total: number
  offset: number
  limit: number
  next_offset: number | null
  query: string
  scope: string
}
