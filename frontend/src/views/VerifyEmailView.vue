<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { resendVerification, verifyEmail, ApiError } from '../api/client'

const route = useRoute()
const token = computed(() =>
  typeof route.query.token === 'string' ? route.query.token : '',
)
const email = ref(
  typeof route.query.email === 'string' ? route.query.email : '',
)
const status = ref<'idle' | 'verifying' | 'success' | 'error'>('idle')
const message = ref('')
const resending = ref(false)
const resendMessage = ref('')

onMounted(async () => {
  if (!token.value) {
    return
  }
  status.value = 'verifying'
  try {
    await verifyEmail(token.value)
    status.value = 'success'
  } catch (cause) {
    status.value = 'error'
    message.value =
      cause instanceof ApiError
        ? cause.message
        : '验证失败，请重新发送验证邮件'
  }
})

async function resend() {
  if (!email.value.trim()) {
    message.value = '请先填写注册邮箱'
    return
  }
  resending.value = true
  resendMessage.value = ''
  try {
    const result = await resendVerification(email.value.trim())
    resendMessage.value = result.message
  } catch (cause) {
    message.value =
      cause instanceof ApiError ? cause.message : '重发失败，请稍后重试'
  } finally {
    resending.value = false
  }
}
</script>

<template>
  <AuthShell
    title="验证邮箱"
    subtitle="验证链接一次性有效；过期或已使用的链接需要重新发送。"
  >
    <div v-if="status === 'verifying'" class="form-notice">正在验证…</div>

    <div v-else-if="status === 'success'" class="auth-success">
      <h2>邮箱已验证</h2>
      <p>现在可以使用该邮箱登录个人笔记空间。</p>
      <RouterLink class="auth-submit" :to="{ name: 'login' }">
        去登录
      </RouterLink>
    </div>

    <div v-else class="auth-form">
      <p v-if="message" class="form-error" role="alert">{{ message }}</p>
      <p v-if="resendMessage" class="form-notice">{{ resendMessage }}</p>
      <p v-if="status === 'error'" class="form-hint">
        链接无效、过期或已使用。可以重新发送一封验证邮件。
      </p>

      <div class="form-field">
        <label for="verify-email">注册邮箱</label>
        <input
          id="verify-email"
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          required
        />
      </div>

      <button
        class="auth-submit"
        type="button"
        :disabled="resending"
        @click="resend"
      >
        {{ resending ? '发送中…' : '重发验证邮件' }}
      </button>

      <div class="auth-links">
        <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
        <RouterLink :to="{ name: 'register' }">重新注册</RouterLink>
      </div>
    </div>

    <template #footer>链接只指向本站 · 一次性令牌</template>
  </AuthShell>
</template>
