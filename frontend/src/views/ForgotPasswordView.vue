<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { forgotPassword, ApiError } from '../api/client'

const email = ref('')
const error = ref('')
const message = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  message.value = ''
  if (!email.value.trim()) {
    error.value = '请输入邮箱'
    return
  }
  submitting.value = true
  try {
    const result = await forgotPassword(email.value.trim())
    message.value = result.message
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '请求失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell
    title="找回密码"
    subtitle="如果邮箱可用，我们会发送一封一次性重置链接。"
  >
    <div v-if="message" class="auth-success">
      <h2>请检查邮箱</h2>
      <p>{{ message }}</p>
      <p class="form-hint">
        为保护账号，无论邮箱是否存在，这里都会显示相同提示。
      </p>
      <RouterLink class="auth-submit" :to="{ name: 'login' }">
        返回登录
      </RouterLink>
    </div>

    <form v-else class="auth-form" @submit.prevent="submit">
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="form-field">
        <label for="forgot-email">注册邮箱</label>
        <input
          id="forgot-email"
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="you@example.com"
          required
        />
      </div>
      <button class="auth-submit" type="submit" :disabled="submitting">
        {{ submitting ? '提交中…' : '发送重置链接' }}
      </button>
    </form>

    <div v-if="!message" class="auth-links">
      <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
      <RouterLink :to="{ name: 'register' }">注册新账号</RouterLink>
    </div>

    <template #footer>找回结果不暴露账号是否存在</template>
  </AuthShell>
</template>
