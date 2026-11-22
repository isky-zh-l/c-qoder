<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import {
  adminUnpublish,
  ApiError,
  getAdminAudit,
  getAdminPublications,
  getAdminSettings,
  getAdminUsers,
  updateAdminRegistration,
  updateAdminUserQuota,
  updateAdminUserStatus,
} from '../api/client'
import type {
  AdminAudit,
  AdminPublicDocument,
  AdminUser,
} from '../api/types'
import { authState } from '../auth/session'
import { formatBytes, formatDateTime } from '../utils/format'

const settingsEnabled = ref(false)
const users = ref<AdminUser[]>([])
const totalUsers = ref(0)
const publications = ref<AdminPublicDocument[]>([])
const audit = ref<AdminAudit[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const savingRegistration = ref(false)
const userQuery = ref('')
const searching = ref(false)
const quotaInputs = ref<Record<number, string>>({})
const busyUserId = ref<number | null>(null)
const busyDocumentId = ref<number | null>(null)

const actionLabels: Record<string, string> = {
  'registration.set': '注册开关',
  'user.status': '用户状态',
  'user.quota': '调整额度',
  'publication.unpublish': '下架公开内容',
  'admin.grant': '授予管理员',
  'admin.revoke': '撤销管理员',
}

function syncQuotaInputs() {
  const next: Record<number, string> = {}
  for (const user of users.value) {
    next[user.id] =
      user.storage_quota_bytes === null
        ? ''
        : String(Math.round(user.storage_quota_bytes / (1024 * 1024)))
  }
  quotaInputs.value = next
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [settings, userList, publicList, auditList] = await Promise.all([
      getAdminSettings(),
      getAdminUsers(userQuery.value),
      getAdminPublications(),
      getAdminAudit(),
    ])
    settingsEnabled.value = settings.registration_enabled
    users.value = userList.users
    totalUsers.value = userList.total
    publications.value = publicList.documents
    audit.value = auditList.entries
    syncQuotaInputs()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '运营数据读取失败'
  } finally {
    loading.value = false
  }
}

async function refreshAudit() {
  try {
    audit.value = (await getAdminAudit()).entries
  } catch {
    // 保留上一次审计结果
  }
}

async function toggleRegistration() {
  if (savingRegistration.value) return
  savingRegistration.value = true
  error.value = ''
  notice.value = ''
  const next = !settingsEnabled.value
  try {
    const settings = await updateAdminRegistration(next)
    settingsEnabled.value = settings.registration_enabled
    notice.value = settings.registration_enabled
      ? '注册已开放'
      : '注册已暂停'
    await refreshAudit()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '注册开关更新失败'
  } finally {
    savingRegistration.value = false
  }
}

async function searchUsers() {
  if (searching.value) return
  searching.value = true
  error.value = ''
  try {
    const result = await getAdminUsers(userQuery.value)
    users.value = result.users
    totalUsers.value = result.total
    syncQuotaInputs()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '用户搜索失败'
  } finally {
    searching.value = false
  }
}

function replaceUser(updated: AdminUser) {
  users.value = users.value.map((user) =>
    user.id === updated.id ? updated : user,
  )
  quotaInputs.value = {
    ...quotaInputs.value,
    [updated.id]:
      updated.storage_quota_bytes === null
        ? ''
        : String(Math.round(updated.storage_quota_bytes / (1024 * 1024))),
  }
}

async function toggleUser(user: AdminUser) {
  if (busyUserId.value !== null) return
  const enabling = !user.is_enabled
  if (
    !enabling &&
    !window.confirm(
      `暂停 ${user.email}？暂停后该账号登录被撤销，公开内容也会立即下架。`,
    )
  ) {
    return
  }
  busyUserId.value = user.id
  error.value = ''
  notice.value = ''
  try {
    const updated = await updateAdminUserStatus(user.id, enabling)
    replaceUser(updated)
    if (!enabling) {
      publications.value = publications.value.filter(
        (item) => item.owner_user_id !== updated.id,
      )
    }
    notice.value = enabling ? '账号已恢复' : '账号已暂停并撤销登录'
    await refreshAudit()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '账号状态更新失败'
  } finally {
    busyUserId.value = null
  }
}

async function saveQuota(user: AdminUser) {
  if (busyUserId.value !== null) return
  const raw = (quotaInputs.value[user.id] ?? '').trim()
  let quotaBytes: number | null = null
  if (raw !== '') {
    const megabytes = Number(raw)
    if (!Number.isFinite(megabytes) || megabytes < 0) {
      error.value = '额度必须是大于等于 0 的 MB 数'
      return
    }
    quotaBytes = Math.round(megabytes * 1024 * 1024)
  }
  busyUserId.value = user.id
  error.value = ''
  notice.value = ''
  try {
    const updated = await updateAdminUserQuota(user.id, quotaBytes)
    replaceUser(updated)
    notice.value = '额度已更新'
    await refreshAudit()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '额度更新失败'
  } finally {
    busyUserId.value = null
  }
}

async function unpublish(document: AdminPublicDocument) {
  if (busyDocumentId.value !== null) return
  if (
    !window.confirm(
      `下架《${document.title}》？旧公开链接和公开图片会立即失效。`,
    )
  ) {
    return
  }
  busyDocumentId.value = document.document_id
  error.value = ''
  notice.value = ''
  try {
    await adminUnpublish(document.document_id)
    publications.value = publications.value.filter(
      (item) => item.document_id !== document.document_id,
    )
    notice.value = '公开内容已下架'
    await refreshAudit()
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '下架失败'
  } finally {
    busyDocumentId.value = null
  }
}

function setQuotaDraft(userId: number, event: Event) {
  const value = (event.target as HTMLInputElement).value
  quotaInputs.value = {
    ...quotaInputs.value,
    [userId]: value,
  }
}

function shareHref(shareUrl: string | null): string {
  return shareUrl ? new URL(shareUrl, window.location.origin).href : '#'
}

onMounted(load)
</script>

<template>
  <AuthShell
    class="admin-page"
    eyebrow="ADMIN / OPERATIONS"
    title="运营控制台"
    subtitle="注册、账号、额度和公开内容集中管理；所有变更写入审计日志。"
  >
    <div v-if="loading" class="admin-state">正在读取运营数据…</div>
    <div v-else class="admin-stack">
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="notice" class="form-notice">{{ notice }}</p>

      <section class="admin-section admin-overview">
        <div>
          <p class="admin-eyebrow">REGISTRATION</p>
          <h2>开放注册</h2>
          <p class="admin-copy">
            关闭后新账号注册返回暂停状态，已有用户登录和私有空间不受影响。
          </p>
        </div>
        <label class="switch">
          <input
            type="checkbox"
            :checked="settingsEnabled"
            :disabled="savingRegistration"
            @change="toggleRegistration"
          />
          <span>{{ settingsEnabled ? '开放中' : '已暂停' }}</span>
        </label>
      </section>

      <section class="admin-section">
        <div class="admin-section-head">
          <div>
            <p class="admin-eyebrow">USERS</p>
            <h2>用户与额度</h2>
            <p class="admin-copy">
              共 {{ totalUsers }} 个账号；额度留空表示使用站点默认值。
            </p>
          </div>
          <form class="admin-search" @submit.prevent="searchUsers">
            <input
              v-model="userQuery"
              type="search"
              placeholder="邮箱或显示名"
              aria-label="搜索用户"
            />
            <button type="submit" class="secondary-button" :disabled="searching">
              {{ searching ? '搜索中…' : '搜索' }}
            </button>
          </form>
        </div>

        <div class="user-list">
          <article v-for="user in users" :key="user.id" class="user-row">
            <div class="user-identity">
              <div class="user-line">
                <strong>{{ user.display_name }}</strong>
                <span v-if="user.is_admin" class="tag admin">管理员</span>
                <span v-if="!user.is_enabled" class="tag danger">已暂停</span>
                <span v-if="user.deletion_requested_at" class="tag pending">
                  注销待清理
                </span>
              </div>
              <span>{{ user.email }}</span>
              <small>
                {{ formatBytes(user.used_bytes) }} /
                {{ formatBytes(user.effective_quota_bytes) }}
                <template v-if="user.reserved_bytes > 0">
                  · 预留 {{ formatBytes(user.reserved_bytes) }}
                </template>
                · {{ user.document_count }} 篇 · 回收 {{ user.recycle_count }}
              </small>
            </div>
            <div class="quota-control">
              <label :for="`quota-${user.id}`">额度 MB</label>
              <input
                :id="`quota-${user.id}`"
                :value="quotaInputs[user.id] ?? ''"
                type="number"
                min="0"
                step="1"
                placeholder="默认"
                @input="setQuotaDraft(user.id, $event)"
              />
              <button
                type="button"
                class="mini-button"
                :disabled="busyUserId === user.id"
                @click="saveQuota(user)"
              >
                保存
              </button>
            </div>
            <div class="user-actions">
              <button
                type="button"
                class="mini-button"
                :class="{ danger: user.is_enabled }"
                :disabled="
                  busyUserId === user.id ||
                  user.id === authState.user?.id ||
                  Boolean(user.deletion_requested_at)
                "
                @click="toggleUser(user)"
              >
                {{ user.is_enabled ? '暂停' : '恢复' }}
              </button>
            </div>
          </article>
          <p v-if="users.length === 0" class="empty-copy">没有匹配的账号。</p>
        </div>
      </section>

      <section class="admin-section">
        <div class="admin-section-head">
          <div>
            <p class="admin-eyebrow">PUBLIC CONTENT</p>
            <h2>当前公开内容</h2>
            <p class="admin-copy">
              只显示作者主动发布的快照；下架不改动作者正文。
            </p>
          </div>
        </div>
        <div class="public-list">
          <article
            v-for="document in publications"
            :key="document.document_id"
            class="public-row"
          >
            <div>
              <div class="user-line">
                <strong>{{ document.title }}</strong>
                <span class="tag">v{{ document.source_version }}</span>
              </div>
              <span>
                {{ document.author_display_name }} · {{ document.owner_email }}
              </span>
              <small>{{ formatDateTime(document.published_at) }}</small>
            </div>
            <div class="public-actions">
              <a
                v-if="document.share_url"
                class="mini-button"
                :href="shareHref(document.share_url)"
                target="_blank"
                rel="noopener"
              >
                查看
              </a>
              <button
                type="button"
                class="mini-button danger"
                :disabled="busyDocumentId === document.document_id"
                @click="unpublish(document)"
              >
                下架
              </button>
            </div>
          </article>
          <p v-if="publications.length === 0" class="empty-copy">
            当前没有公开内容。
          </p>
        </div>
      </section>

      <section class="admin-section">
        <div class="admin-section-head">
          <div>
            <p class="admin-eyebrow">AUDIT</p>
            <h2>最近操作</h2>
            <p class="admin-copy">只记录管理动作，不记录密码、会话或邮件令牌。</p>
          </div>
        </div>
        <div class="audit-list">
          <article v-for="entry in audit" :key="entry.id" class="audit-row">
            <span class="tag">{{ actionLabels[entry.action] || entry.action }}</span>
            <div>
              <strong>
                {{ entry.admin_email || '已删除管理员' }}
                <template v-if="entry.target_user_email">
                  → {{ entry.target_user_email }}
                </template>
              </strong>
              <span v-if="entry.target_document_title">
                《{{ entry.target_document_title }}》
              </span>
              <small>{{ formatDateTime(entry.created_at) }}</small>
            </div>
          </article>
          <p v-if="audit.length === 0" class="empty-copy">还没有管理操作。</p>
        </div>
      </section>
    </div>

    <div class="admin-links">
      <RouterLink :to="{ name: 'account' }">返回账号设置</RouterLink>
      <RouterLink :to="{ name: 'workspace' }">返回笔记空间</RouterLink>
    </div>

    <template #footer>管理员权限集中校验 · 关键操作写入审计</template>
  </AuthShell>
</template>

<style scoped>
:global(.admin-page .auth-frame) {
  width: min(1100px, 100%);
}

.admin-state {
  margin-top: 24px;
  color: var(--muted);
}

.admin-stack {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}

.admin-section {
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
}

.admin-overview,
.admin-section-head,
.user-row,
.public-row,
.audit-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.admin-eyebrow {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.16em;
}

.admin-section h2 {
  margin-top: 4px;
  font-size: 18px;
  letter-spacing: -0.02em;
}

.admin-copy {
  max-width: 560px;
  margin-top: 5px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.65;
}

.switch {
  display: inline-flex;
  gap: 9px;
  align-items: center;
  padding: 9px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  color: var(--muted-strong);
  font-size: 12px;
  font-weight: 650;
  background: #fff;
  white-space: nowrap;
}

.switch input {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.admin-search {
  display: flex;
  gap: 8px;
  align-items: center;
}

.admin-search input,
.quota-control input {
  width: 150px;
  padding: 8px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  color: var(--text);
  font: inherit;
  font-size: 12px;
  background: #fff;
  outline: none;
}

.admin-search input:focus,
.quota-control input:focus {
  border-color: var(--accent);
}

.user-list,
.public-list,
.audit-list {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.user-row,
.public-row,
.audit-row {
  padding: 13px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #fff;
}

.user-identity,
.public-row > div:first-child,
.audit-row > div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.user-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.user-identity > span,
.public-row > div:first-child > span,
.audit-row span {
  color: var(--muted-strong);
  font-size: 11.5px;
  overflow-wrap: anywhere;
}

.user-identity small,
.public-row small,
.audit-row small {
  color: var(--muted);
  font-size: 10.5px;
}

.tag {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--accent-strong);
  font-size: 9.5px;
  font-weight: 650;
  white-space: nowrap;
  background: var(--accent-soft);
}

.tag.admin {
  color: #7a4b00;
  background: #fff1c8;
}

.tag.danger {
  color: #9f2f28;
  background: #fff0ee;
}

.tag.pending {
  color: #8b5a1f;
  background: #fff4df;
}

.quota-control {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 0 0 auto;
}

.quota-control label {
  color: var(--muted);
  font-size: 10px;
  white-space: nowrap;
}

.quota-control input {
  width: 76px;
}

.user-actions,
.public-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex: 0 0 auto;
}

.mini-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 5px 10px;
  border: 1px solid var(--border-strong);
  border-radius: 9px;
  color: var(--muted-strong);
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
  background: #fff;
  cursor: pointer;
}

.mini-button:hover:not(:disabled) {
  background: var(--accent-faint);
}

.mini-button.danger {
  border-color: #efc4c0;
  color: #a4362e;
  background: #fff8f7;
}

.mini-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.admin-links {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 18px;
  font-size: 12px;
}

.admin-links a {
  color: var(--accent-strong);
  font-weight: 650;
}

.empty-copy {
  padding: 14px;
  color: var(--muted);
  font-size: 11.5px;
  text-align: center;
}

@media (max-width: 760px) {
  .admin-section {
    padding: 16px;
  }

  .admin-overview,
  .admin-section-head,
  .user-row,
  .public-row,
  .audit-row {
    flex-direction: column;
  }

  .admin-search {
    width: 100%;
  }

  .admin-search input {
    width: 100%;
  }

  .quota-control,
  .user-actions,
  .public-actions {
    width: 100%;
  }

  .quota-control input {
    flex: 1;
    width: auto;
  }
}
</style>
