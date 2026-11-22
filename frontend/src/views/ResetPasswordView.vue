<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AuthShell from '../components/AuthShell.vue'
import { resetPassword, ApiError } from '../api/client'
import { clearSession } from '../auth/session'

const route = useRoute()
const token = computed(() =>
  typeof route.query.token === 'string' ? route.query.token : '',
)
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const submitting = ref(false)
const success = ref(false)

async function submit() {
  error.value = ''
  if (!token.value) {
    error.value = '重置链接缺少令牌'
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
    await resetPassword(token.value, password.value)
    clearSession()
    success.value = true
  } catch (cause) {
    error.value =
      cause instanceof ApiError ? cause.message : '重置失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthShell
    title="重置密码"
    subtitle="重置成功后，该账号的所有旧会话都会失效。"
  >
    <div v-if="success" class="auth-success">
      <h2>密码已重置</h2>
      <p>请使用新密码重新登录。</p>
      <RouterLink class="auth-submit" :to="{ name: 'login' }">
        去登录
      </RouterLink>
    </div>

    <form v-else class="auth-form" @submit.prevent="submit">
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="form-field">
        <label for="reset-password">新密码</label>
        <input
          id="reset-password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="10"
          placeholder="至少 10 位"
          required
        />
      </div>
      <div class="form-field">
        <label for="reset-confirm">确认新密码</label>
        <input
          id="reset-confirm"
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          minlength="10"
          placeholder="再输入一次"
          required
        />
      </div>
      <button class="auth-submit" type="submit" :disabled="submitting">
        {{ submitting ? '重置中…' : '设置新密码' }}
      </button>
    </form>

    <div v-if="!success" class="auth-links">
      <RouterLink :to="{ name: 'login' }">返回登录</RouterLink>
    </div>

    <template #footer>一次性链接 · 过期后请重新找回</template>
  </AuthShell>
</template>
