import { reactive } from 'vue'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const state = reactive({
  accessToken: '',
  currentUser: null,
  authStatus: {
    enabled: false,
    password_login_enabled: true,
    oidc_enabled: false,
    demo_users: []
  },
  statusLoaded: false
})

let statusPromise = null

export function getAccessToken() {
  return state.accessToken
}

export function getCurrentUser() {
  return state.currentUser
}

export function useAuthState() {
  return state
}

export function isAuthenticated() {
  return Boolean(state.accessToken)
}

export function loadAuthState() {
  const saved = localStorage.getItem('ragAuth')
  if (!saved) return
  try {
    const auth = JSON.parse(saved)
    state.accessToken = auth.accessToken || ''
    state.currentUser = auth.currentUser || null
  } catch {
    state.accessToken = ''
    state.currentUser = null
  }
}

export function saveAuthState() {
  localStorage.setItem('ragAuth', JSON.stringify({
    accessToken: state.accessToken,
    currentUser: state.currentUser
  }))
}

export function setAuthSession(token, user) {
  state.accessToken = token || ''
  state.currentUser = user || null
  saveAuthState()
}

export function clearAuthSession() {
  state.accessToken = ''
  state.currentUser = null
  saveAuthState()
}

export function setAuthStatus(status) {
  state.authStatus = {
    enabled: false,
    password_login_enabled: false,
    oidc_enabled: false,
    demo_users: [],
    ...status
  }
  state.statusLoaded = true
}

/** 拉取鉴权开关；路由守卫在进入业务页前等待结果 */
export function ensureAuthStatus() {
  if (state.statusLoaded) return Promise.resolve(state.authStatus)
  if (statusPromise) return statusPromise

  statusPromise = axios
    .get(`${API_BASE}/auth/status`)
    .then((res) => {
      setAuthStatus(res.data)
      return state.authStatus
    })
    .catch(() => {
      // 状态接口失败时按需登录处理，避免未登录直接进工作台
      setAuthStatus({
        enabled: true,
        password_login_enabled: true,
        oidc_enabled: false,
        demo_users: []
      })
      return state.authStatus
    })
    .finally(() => {
      statusPromise = null
    })

  return statusPromise
}
