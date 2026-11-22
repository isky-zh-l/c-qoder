import { createRouter, createWebHashHistory } from 'vue-router'
import { ensureSession, authState } from './auth/session'
import {
  consumePostLogin,
  rememberPostLogin,
} from './utils/navigation'
import { saveScrollPosition } from './utils/scrollMemory'
import WorkspaceView from './views/WorkspaceView.vue'
import { beginProgress, endProgress } from './utils/progress'
import { clearPageLoading, startPageLoading } from './utils/pageLoading'

const routerBase =
  import.meta.env.VITE_ROUTER_BASE || import.meta.env.BASE_URL

const CONTENT_ROUTES = new Set(['document', 'document-edit', 'source-edit'])

function contentLoadingLabel(name: unknown): string {
  return name === 'source-edit' ? '源码编辑器正在加载…' : name === 'document-edit' ? '编辑器正在加载…' : '笔记正在加载中…'
}

const router = createRouter({
  history: createWebHashHistory(routerBase),
  routes: [
    {
      path: '/',
      name: 'workspace',
      component: WorkspaceView,
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:id/edit',
      name: 'document-edit',
      component: () => import('./views/EditorView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:id/source-edit',
      name: 'source-edit',
      component: () => import('./views/EditorView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:id',
      name: 'document',
      component: () => import('./views/DocumentView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/settings/account',
      name: 'account',
      component: () => import('./views/AccountSettingsView.vue'),
      meta: { requiresAuth: true, title: '账号设置' },
    },
    {
      path: '/p/:shareToken',
      name: 'public-document',
      component: () => import('./views/PublicDocumentView.vue'),
      meta: { public: true, title: '公开分享' },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to, from) => {
  beginProgress()
  if (CONTENT_ROUTES.has(String(to.name))) {
    startPageLoading(contentLoadingLabel(to.name))
  }
  if (from.name && from.fullPath !== to.fullPath) {
    saveScrollPosition(from.fullPath)
  }
  if (to.meta.public) {
    return true
  }
  await ensureSession()
  if (to.meta.requiresAuth && !authState.user) {
    rememberPostLogin(to.fullPath)
    return {
      name: 'login',
      query: { next: to.fullPath },
    }
  }
  if (authState.user && (to.name === 'login' || to.name === 'workspace')) {
    const next = consumePostLogin()
    if (next !== '/') {
      return next
    }
    if (to.name === 'login') {
      return { name: 'workspace' }
    }
  }
  if (to.meta.admin && !authState.user?.is_admin) {
    return { name: 'workspace' }
  }
  return true
})

router.afterEach((to, from, failure) => {
  if (failure) {
    endProgress()
    clearPageLoading()
    return
  }
  endProgress()
  if (!CONTENT_ROUTES.has(String(to.name))) {
    clearPageLoading()
  }
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · C 语言学习笔记` : 'C 语言学习笔记'
})

router.onError(() => {
  endProgress()
  clearPageLoading()
})

export default router
