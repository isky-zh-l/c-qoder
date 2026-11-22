import { reactive } from 'vue'
import { getSession, setCsrfToken, startDemo, stopDemo } from '../api/client'
import type { UserProfile } from '../api/types'

const routerBase =
  import.meta.env.VITE_ROUTER_BASE || import.meta.env.BASE_URL

export const authState = reactive({
  user: null as UserProfile | null,
  csrfToken: '',
  ready: false,
  error: '',
})

let sessionPromise: Promise<void> | null = null

function onLoginPage(): boolean {
  return /^#\/login(?:[?/]|$)/.test(window.location.hash)
}

export async function ensureSession(force = false): Promise<void> {
  if (authState.ready && !force) {
    return
  }
  if (sessionPromise && !force) {
    return sessionPromise
  }
  sessionPromise = (async () => {
    try {
      let session = await getSession()
      if (session.user?.is_demo && onLoginPage()) {
        await stopDemo().catch(() => undefined)
        session = { authenticated: false, user: null, csrf_token: null }
      } else if (!session.user && !onLoginPage()) {
        try {
          await startDemo()
          session = await getSession()
        } catch {
          // 演示入口不可用时仍显示登录页
        }
      }
      authState.user = session.user
      authState.csrfToken = session.csrf_token || ''
      authState.error = ''
      setCsrfToken(session.csrf_token)
    } catch {
      authState.user = null
      authState.csrfToken = ''
      authState.error = '登录状态读取失败'
      setCsrfToken('')
    } finally {
      authState.ready = true
      sessionPromise = null
    }
  })()
  return sessionPromise
}

export async function logout(): Promise<void> {
  await stopDemo().catch(() => undefined)
  let response: Response
  try {
    response = await fetch('/__qoder_auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'manual',
    })
  } catch {
    throw new Error('退出请求失败，当前 Qoder 登录可能仍然有效')
  }
  if (!response.ok && response.status !== 0) {
    if (response.status === 401) {
      clearSession()
      return
    }
    throw new Error('退出未确认，当前 Qoder 登录可能仍然有效')
  }
  clearSession()
}

export async function logoutAndRedirect(): Promise<void> {
  await logout()
  window.location.replace(`${routerBase}#/login?loggedOut=1`)
}

export async function startDemoSession(): Promise<void> {
  await startDemo()
  const session = await getSession()
  if (!session.user) {
    throw new Error('示例空间暂时不可用，请稍后重试')
  }
  authState.user = session.user
  authState.csrfToken = session.csrf_token || ''
  authState.error = ''
  authState.ready = true
  setCsrfToken(session.csrf_token)
}

export function clearSession(): void {
  authState.user = null
  authState.csrfToken = ''
  authState.ready = true
  authState.error = ''
  setCsrfToken('')
}
