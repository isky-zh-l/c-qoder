<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { changePassword, ApiError } from '../api/client'
import { clearSession } from '../auth/session'

const router = useRouter()
const currentPassword = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  if (currentPassword.value.length < 10 || password.value.length < 10) {
    error.value = '当前密码和新密码都至少 10 位'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  submitting.value = true
  try {
    await changePassword(currentPassword.value, password.value)
    clearSession()
    await router.replace({
      name: 'login',
      query: { passwordChanged: '1' },
    })
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '修改失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell
    title="修改密码"
    subtitle="修改成功后，包括当前设备在内的所有旧会话都会失效，需要重新登录。"
  >
    <form class="auth-form" @submit.prevent="submit">
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="form-field">
        <label for="current-password">当前密码</label>
        <input
          id="current-password"
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
          minlength="10"
          required
        />
      </div>
      <div class="form-field">
        <label for="new-password">新密码</label>
        <input
          id="new-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="10"
          placeholder="至少 10 位"
          required
        />
      </div>
      <div class="form-field">
        <label for="confirm-new-password">确认新密码</label>
        <input
          id="confirm-new-password"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="10"
          required
        />
      </div>
      <button class="auth-submit" type="submit" :disabled="submitting">
        {{ submitting ? '修改中…' : '修改密码' }}
      </button>
    </form>

    <div class="auth-links">
      <RouterLink :to="{ name: 'account' }">返回账号设置</RouterLink>
      <RouterLink :to="{ name: 'workspace' }">返回笔记空间</RouterLink>
    </div>

    <template #footer>所有旧会话将失效 · 需重新登录</template>
  </AuthShell>
</template>
