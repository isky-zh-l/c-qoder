<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { authState, ensureSession, startDemoSession } from '../auth/session'
import { siteTitle } from '../site'
import {
  consumePostLogin,
  rememberPostLogin,
  safeInternalPath,
} from '../utils/navigation'

const route = useRoute()
const router = useRouter()

const nextPath = computed(() => safeInternalPath(route.query.next, '/'))
const loginHref = computed(
  () =>
    `/__qoder_auth/start?return_path=${encodeURIComponent(nextPath.value)}`,
)

const loggedOut = computed(() => route.query.loggedOut === '1')
const enteringDemo = ref(false)
const demoError = ref('')
const checking = ref(false)
const checked = ref(false)
const checkFailed = ref(false)
const authProbe = ref<'signed_in' | 'signed_out' | 'unavailable' | ''>('')
let disposed = false

async function probeQoder() {
  try {
    const response = await fetch('/__qoder_auth/me', {
      credentials: 'same-origin',
      cache: 'no-store',
    })
    if (response.status === 401) {
      authProbe.value = 'signed_out'
      return
    }
    if (!response.ok) {
      authProbe.value = 'unavailable'
      return
    }
    const data = (await response.json()) as { user_id?: unknown }
    authProbe.value =
      typeof data?.user_id === 'string' && data.user_id
        ? 'signed_in'
        : 'signed_out'
  } catch {
    authProbe.value = 'unavailable'
  }
}

async function checkLogin(force = true) {
  if (checking.value) {
    return
  }
  checking.value = true
  checkFailed.value = false
  try {
    await ensureSession(force)
    if (disposed) {
      return
    }
    if (authState.user) {
      const target = consumePostLogin()
      await router.replace(target === '/' ? nextPath.value : target)
      return
    }
    await probeQoder()
    if (disposed) {
      return
    }
    checkFailed.value = Boolean(authState.error)
    checked.value = true
  } finally {
    if (!disposed) {
      checking.value = false
    }
  }
}

function recheckWhenVisible() {
  if (document.visibilityState === 'visible') {
    void checkLogin(true)
  }
}

async function enterDemo() {
  if (enteringDemo.value) return
  enteringDemo.value = true
  demoError.value = ''
  try {
    await startDemoSession()
    const target = consumePostLogin()
    await router.replace(target === '/' ? nextPath.value : target)
  } catch (error) {
    demoError.value =
      error instanceof Error ? error.message : '示例空间暂时不可用，请稍后重试'
  } finally {
    enteringDemo.value = false
  }
}

onMounted(() => {
  rememberPostLogin(nextPath.value)
  void checkLogin(true)
  window.addEventListener('focus', recheckWhenVisible)
  document.addEventListener('visibilitychange', recheckWhenVisible)
})

onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('focus', recheckWhenVisible)
  document.removeEventListener('visibilitychange', recheckWhenVisible)
})
</script>

<template>
  <AuthShell
    title="使用 Qoder 登录"
    subtitle="每个 Qoder 账号拥有独立的章节、笔记、源码和图片空间。"
  >
    <div class="qoder-login">
      <p v-if="loggedOut" class="form-notice">已退出 Qoder 登录。</p>
      <a class="auth-submit qoder-button" :href="loginHref">
        <span class="qoder-mark" aria-hidden="true">Q</span>
        继续使用 Qoder
      </a>
      <p class="qoder-note">
        点击后会打开 qoder.cn 完成登录。登录成功会自动回到这里；如果停在本页，请点下方重新检查。
      </p>
      <p v-if="checking" class="form-notice">正在检查登录状态…</p>
      <p v-else-if="checkFailed" class="form-notice login-error">
        登录状态读取失败，请稍后重新检查。
      </p>
      <p v-else-if="authProbe === 'signed_in'" class="form-notice login-error">
        Qoder 已登录，但本站没有识别到身份。请点“重新检查”；仍失败说明是站点会话问题。
      </p>
      <p v-else-if="authProbe === 'signed_out' && !loggedOut" class="form-notice">
        Qoder 授权尚未完成。请在打开的 qoder.cn 页面完成登录后回来。
      </p>
      <p v-else-if="checked" class="form-notice">
        暂未检测到 Qoder 登录。完成登录后点下方重新检查。
      </p>
      <button
        v-if="!checking"
        class="login-recheck"
        type="button"
        @click="checkLogin(true)"
      >
        重新检查登录状态
      </button>

      <div class="visitor-entry">
        <span class="visitor-divider" aria-hidden="true">或</span>
        <button
          class="visitor-button"
          type="button"
          :disabled="enteringDemo"
          @click="enterDemo"
        >
          {{ enteringDemo ? '正在进入示例空间…' : '以访客身份进入示例空间' }}
        </button>
        <p class="qoder-note">
          示例空间共享可编辑，只用于体验；AI 润色需要登录 Qoder 账号。
        </p>
        <p v-if="demoError" class="form-notice login-error">{{ demoError }}</p>
      </div>
    </div>

    <div class="auth-links">
      <span>无需邮箱注册</span>
      <span>每个账号独立空间</span>
    </div>

    <template #footer>{{ siteTitle }} · Qoder Sites 托管</template>
  </AuthShell>
</template>

<style scoped>
.qoder-login {
  display: grid;
  gap: 14px;
}

.qoder-button {
  display: inline-flex;
  gap: 9px;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.qoder-mark {
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 7px;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
  background: #fff;
}

.qoder-note {
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.8;
  text-align: center;
}

.login-error {
  color: var(--danger, #b42318);
}

.login-recheck {
  justify-self: center;
  padding: 6px 10px;
  border: 0;
  color: var(--accent-strong);
  font-size: 12px;
  background: transparent;
  cursor: pointer;
}

.login-recheck:hover,
.login-recheck:focus-visible {
  text-decoration: underline;
}

.visitor-entry {
  display: grid;
  gap: 10px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
}

.visitor-divider {
  justify-self: center;
  margin-top: -18px;
  padding: 0 10px;
  color: var(--muted);
  font-size: 11px;
  background: var(--surface, #fff);
}

.visitor-button {
  justify-self: stretch;
  padding: 11px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text, #322b46);
  font-size: 13.5px;
  font-weight: 650;
  background: #fff;
  cursor: pointer;
}

.visitor-button:hover,
.visitor-button:focus-visible {
  border-color: var(--accent);
  color: var(--accent-strong);
  outline: none;
}

.visitor-button:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
