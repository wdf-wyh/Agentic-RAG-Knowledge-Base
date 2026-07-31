import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '../layouts/MainLayout.vue'
import { ensureAuthStatus, isAuthenticated, loadAuthState } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: '对话', requiresAuth: true }
      },
      {
        path: 'knowledge',
        name: 'knowledge',
        component: () => import('../views/KnowledgeView.vue'),
        meta: { title: '知识库', requiresAuth: true }
      },
      {
        path: 'history',
        name: 'history',
        component: () => import('../views/HistoryView.vue'),
        meta: { title: '历史', requiresAuth: true }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置', requiresAuth: true }
      },
      {
        path: 'admin',
        name: 'admin',
        component: () => import('../views/AdminView.vue'),
        meta: { title: '管理台', requiresAuth: true }
      },
      {
        path: 'eval',
        name: 'eval',
        component: () => import('../views/EvalView.vue'),
        meta: { title: '评测', requiresAuth: true }
      },
      {
        path: 'traces',
        name: 'traces',
        component: () => import('../views/TraceView.vue'),
        meta: { title: '追踪', requiresAuth: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  loadAuthState()
  await ensureAuthStatus()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)

  // 未登录：先到登录页，登录成功后再进入目标页
  if (requiresAuth && !isAuthenticated()) {
    return {
      name: 'login',
      query: to.fullPath && to.fullPath !== '/' ? { redirect: to.fullPath } : {}
    }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} · RAG 知识库助手` : 'RAG 知识库助手'
})

export default router
