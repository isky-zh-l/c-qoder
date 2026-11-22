<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import {
  ApiError,
  downloadMyExport,
  getMe,
  getStorageUsage,
  updateProfile,
} from '../api/client'
import { authState, clearSession, ensureSession } from '../auth/session'
import type { StorageUsage, UserProfile } from '../api/types'
import { formatBytes } from '../utils/format'

const router = useRouter()
const user = ref<UserProfile | null>(authState.user)
const usage = ref<StorageUsage | null>(null)
const loading = ref(true)
const loadError = ref('')
const profileError = ref('')
const profileNotice = ref('')
const savingProfile = ref(false)
const displayName = ref('')
const exporting = ref(false)
const exportError = ref('')

const usedTotal = computed(() =>
  usage.value ? usage.value.used_bytes + usage.value.reserved_bytes : 0,
)
const usedPercent = computed(() => {
  if (!usage.value || usage.value.quota_bytes <= 0) return 0
  return Math.min(
    100,
    Math.round((usedTotal.value / usage.value.quota_bytes) * 100),
  )
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    await ensureSession()
    if (!authState.user) {
      await router.replace({
        name: 'login',
        query: { next: '/settings/account' },
      })
      return
    }
    const [profile, storage] = await Promise.all([
      getMe(),
      getStorageUsage(),
    ])
    user.value = profile
    authState.user = profile
    displayName.value = profile.display_name
    usage.value = storage
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) {
      clearSession()
      await router.replace({
        name: 'login',
        query: { next: '/settings/account' },
      })
      return
    }
    loadError.value =
      cause instanceof ApiError ? cause.message : '账号设置读取失败'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (savingProfile.value) return
  profileError.value = ''
  profileNotice.value = ''
  const name = displayName.value.trim()
  if (!name) {
    profileError.value = '显示名不能为空'
    return
  }
  savingProfile.value = true
  try {
    const updated = await updateProfile({ display_name: name })
    user.value = updated
    authState.user = updated
    displayName.value = updated.display_name
    profileNotice.value = '显示名已保存'
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) {
      clearSession()
      await router.replace({ name: 'login' })
      return
    }
    profileError.value =
      cause instanceof ApiError ? cause.message : '资料保存失败'
  } finally {
    savingProfile.value = false
  }
}

async function exportData() {
  if (exporting.value) return
  exporting.value = true
  exportError.value = ''
  try {
    const result = await downloadMyExport()
    const url = URL.createObjectURL(result.blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = result.filename
    link.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) {
      clearSession()
      await router.replace({ name: 'login' })
      return
    }
    exportError.value =
      cause instanceof ApiError ? cause.message : '导出失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <AuthShell
    class="account-settings-page"
    eyebrow="ACCOUNT / QODER SPACE"
    title="账号设置"
    subtitle="账号由 Qoder 统一登录，每个 Qoder 用户拥有独立的数据空间。"
  >
    <div v-if="loading" class="account-state">正在读取账号信息…</div>
    <div v-else-if="loadError" class="account-state">
      <p class="form-error">{{ loadError }}</p>
      <button type="button" class="secondary-button" @click="load">
        重新加载
      </button>
    </div>

    <div v-else class="account-settings">
      <section class="settings-section">
        <div class="section-head">
          <div>
            <p class="section-eyebrow">PROFILE</p>
            <h2>个人显示名</h2>
          </div>
          <span class="account-email">Qoder 账号</span>
        </div>
        <form class="settings-form" @submit.prevent="saveProfile">
          <p v-if="profileError" class="form-error" role="alert">
            {{ profileError }}
          </p>
          <p v-if="profileNotice" class="form-notice">{{ profileNotice }}</p>
          <div class="form-field">
            <label for="account-display-name">显示名</label>
            <input
              id="account-display-name"
              v-model="displayName"
              maxlength="40"
              required
            />
          </div>
          <p class="settings-hint">
            显示名用于公开分享页的作者署名。登录身份、头像和会话由 Qoder 管理。
          </p>
          <div class="section-actions">
            <button
              class="auth-submit"
              type="submit"
              :disabled="savingProfile"
            >
              {{ savingProfile ? '保存中…' : '保存显示名' }}
            </button>
            <RouterLink class="text-link" :to="{ name: 'workspace' }">
              返回笔记空间
            </RouterLink>
          </div>
        </form>
      </section>

      <section v-if="usage" class="settings-section">
        <div class="section-head">
          <div>
            <p class="section-eyebrow">STORAGE</p>
            <h2>空间用量</h2>
          </div>
          <span class="quota-state" :class="{ warning: usedPercent >= 85 }">
            {{ usage.over_quota ? '额度紧张' : '正常' }}
          </span>
        </div>

        <div class="usage-total">
          <div>
            <strong>{{ formatBytes(usedTotal) }}</strong>
            <span> / {{ formatBytes(usage.quota_bytes) }}</span>
          </div>
          <small>可用 {{ formatBytes(usage.remaining_bytes) }}</small>
        </div>
        <div class="usage-meter" aria-hidden="true">
          <span :style="{ width: `${usedPercent}%` }"></span>
        </div>

        <div class="usage-grid">
          <div class="usage-cell">
            <span>笔记正文</span>
            <strong>{{ formatBytes(usage.note_bytes) }}</strong>
          </div>
          <div class="usage-cell">
            <span>源码</span>
            <strong>{{ formatBytes(usage.source_bytes) }}</strong>
          </div>
          <div class="usage-cell">
            <span>图片占用</span>
            <strong>{{ formatBytes(usage.image_bytes) }}</strong>
          </div>
          <div class="usage-cell">
            <span>回收站</span>
            <strong>{{ formatBytes(usage.recycle_bytes) }}</strong>
          </div>
          <div class="usage-cell">
            <span>公开快照</span>
            <strong>{{ formatBytes(usage.publication_bytes) }}</strong>
          </div>
          <div class="usage-cell">
            <span>文件夹</span>
            <strong>{{ usage.folder_count ?? 0 }}</strong>
          </div>
          <div class="usage-cell">
            <span>文档 / 图片</span>
            <strong>{{ usage.document_count }} / {{ usage.asset_count }}</strong>
          </div>
          <div class="usage-cell">
            <span>回收站项</span>
            <strong>{{ usage.recycle_count }}</strong>
          </div>
        </div>

        <div class="section-actions">
          <button
            type="button"
            class="secondary-button"
            :disabled="exporting"
            @click="exportData"
          >
            {{ exporting ? '打包中…' : '导出我的数据' }}
          </button>
          <span class="settings-hint">ZIP 内含 data.json、文档模块和图片文件。</span>
        </div>
        <p v-if="exportError" class="form-error" role="alert">{{ exportError }}</p>

        <p class="usage-note">
          回收站保留 {{ usage.recycle_retention_days }} 天；图片单张不超过
          {{ formatBytes(usage.limits.max_image_bytes) }}，最长边不超过
          {{ usage.limits.image_max_dimension }} 像素；导入文件不超过
          {{ formatBytes(usage.limits.max_file_bytes) }}。
        </p>
      </section>

      <section class="settings-section">
        <div class="section-head">
          <div>
            <p class="section-eyebrow">SESSION</p>
            <h2>登录与会话</h2>
          </div>
        </div>
        <p class="settings-hint">
          当前站点使用 Qoder 统一身份。顶部菜单的“退出登录”会调用 Qoder
          会话退出并刷新页面；退出后新标签页不会继续显示当前账号的私有内容。
          站点不会保存密码、邮箱验证令牌或自定义会话。
        </p>
      </section>
    </div>
  </AuthShell>
</template>

<style scoped>
.account-settings {
  display: grid;
  gap: 22px;
}

.settings-section {
  display: grid;
  gap: 16px;
  padding: 20px 0 0;
  border-top: 1px solid var(--border);
}

.settings-section:first-child {
  padding-top: 0;
  border-top: 0;
}

.section-head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.section-eyebrow {
  margin-bottom: 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.section-head h2 {
  font-size: 18px;
  letter-spacing: -0.02em;
}

.account-email,
.quota-state {
  padding: 5px 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 9px;
  background: var(--surface-soft);
}

.quota-state.warning {
  color: #a16213;
  border-color: #ead8ae;
  background: #fbf3df;
}

.settings-form {
  display: grid;
  gap: 13px;
}

.settings-hint,
.usage-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.8;
}

.section-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.text-link {
  color: var(--muted-strong);
  font-size: 11.5px;
  font-weight: 650;
}

.text-link:hover {
  color: var(--accent-strong);
}

.usage-total {
  display: flex;
  gap: 16px;
  align-items: baseline;
  justify-content: space-between;
}

.usage-total strong {
  font-family: var(--font-mono);
  font-size: 22px;
}

.usage-total span,
.usage-total small {
  color: var(--muted);
  font-size: 11px;
}

.usage-meter {
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: var(--accent-faint);
}

.usage-meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-strong));
}

.usage-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
}

.usage-cell {
  display: grid;
  gap: 4px;
  padding: 11px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-soft);
}

.usage-cell span {
  color: var(--muted);
  font-size: 9.5px;
}

.usage-cell strong {
  font-family: var(--font-mono);
  font-size: 12px;
}

.account-state {
  display: grid;
  gap: 12px;
  place-items: start;
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .usage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .usage-total {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }
}
</style>
