<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { register, resendVerification, ApiError } from '../api/client'
import { registrationEnabled } from '../site'

const email = ref('')
const displayName = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const notice = ref('')
const submitting = ref(false)
const successEmail = ref('')
const resending = ref(false)

async function submit() {
  error.value = ''
  notice.value = ''
  if (!email.value.trim()) {
    error.value = '请输入邮箱'
    return
  }
  if (password.value.length < 10) {
    error.value = '密码至少 10 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    const result = await register(
      email.value.trim(),
      password.value,
      displayName.value.trim() || undefined,
    )
    successEmail.value = result.email
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '注册失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function resend() {
  if (!successEmail.value) {
    return
  }
  resending.value = true
  notice.value = ''
  try {
    const result = await resendVerification(successEmail.value)
    notice.value = result.message
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '重发失败，请稍后重试'
  } finally {
    resending.value = false
  }
}
</script>

<template>
  <AuthShell
    title="创建账号"
    subtitle="注册后会自动建立你的资料、十二个默认章节和空文档库。"
  >
    <div v-if="successEmail" class="auth-success">
      <h2>验证邮件已发送</h2>
      <p>
        请打开 <strong>{{ successEmail }}</strong> 的收件箱，
        点击本站验证链接完成邮箱验证。
      </p>
      <p class="form-notice">
        在完成验证前不能登录，也不能写入笔记。
      </p>
      <p v-if="notice" class="form-notice">{{ notice }}</p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <button
        class="secondary-button"
        type="button"
        :disabled="resending"
        @click="resend"
      >
        {{ resending ? '发送中…' : '重发验证邮件' }}
      </button>
      <div class="auth-links">
        <RouterLink :to="{ name: 'login' }">去登录</RouterLink>
      </div>
    </div>

    <div v-else-if="!registrationEnabled" class="form-notice">
      注册暂未开放。已有账号可以直接登录；开放时间由站点管理员控制。
    </div>

    <form v-else class="auth-form" @submit.prevent="submit">
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <p v-if="error && email" class="form-hint">
        如果账号已经创建但没收到邮件，可以
        <RouterLink
          class="auth-inline-link"
          :to="{ name: 'verify-email', query: { email } }"
        >
          去验证页重发
        </RouterLink>
        。
      </p>

      <div class="form-field">
        <label for="register-email">邮箱</label>
        <input
          id="register-email"
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          required
        />
        <span class="form-hint">邮箱不区分大小写，注册后需要验证。</span>
      </div>

      <div class="form-field">
        <label for="register-name">显示名（可选）</label>
        <input
          id="register-name"
          v-model="displayName"
          type="text"
          autocomplete="nickname"
          maxlength="80"
          placeholder="留空则使用邮箱前缀"
        />
      </div>

      <div class="form-field">
        <label for="register-password">密码</label>
        <input
          id="register-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="10"
          placeholder="至少 10 位"
          required
        />
      </div>

      <div class="form-field">
        <label for="register-confirm">确认密码</label>
        <input
          id="register-confirm"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="10"
          placeholder="再输入一次"
          required
        />
      </div>

      <button class="auth-submit" type="submit" :disabled="submitting">
        {{ submitting ? '创建中…' : '创建账号' }}
      </button>
    </form>

    <div v-if="!successEmail" class="auth-links">
      <RouterLink :to="{ name: 'login' }">已有账号，去登录</RouterLink>
    </div>

    <template #footer>默认私有 · 仅验证邮箱后可写入</template>
  </AuthShell>
</template>
