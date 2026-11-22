const POST_LOGIN_KEY = 'c-notes:post-login'

export function safeInternalPath(
  value: unknown,
  fallback = '/',
): string {
  if (typeof value !== 'string') {
    return fallback
  }
  if (
    !value.startsWith('/') ||
    value.startsWith('//') ||
    value.includes('\\') ||
    value.includes('://')
  ) {
    return fallback
  }
  return value
}

export function rememberPostLogin(value: unknown): void {
  const next = safeInternalPath(value, '')
  if (!next || next === '/') {
    return
  }
  try {
    sessionStorage.setItem(POST_LOGIN_KEY, next)
  } catch {
    // 隐私模式禁用存储时仍可完成登录，只丢失深链回跳
  }
}

export function consumePostLogin(): string {
  try {
    const next = sessionStorage.getItem(POST_LOGIN_KEY)
    sessionStorage.removeItem(POST_LOGIN_KEY)
    return safeInternalPath(next, '/')
  } catch {
    return '/'
  }
}
