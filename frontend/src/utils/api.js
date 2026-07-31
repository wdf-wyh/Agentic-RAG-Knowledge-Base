import axios from 'axios'
import { clearAuthSession, getAccessToken } from '../stores/auth'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export function authHeaders() {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const api = axios.create({
  baseURL: API_BASE
})

api.interceptors.request.use((config) => {
  Object.assign(config.headers, authHeaders())
  return config
})

let authRedirecting = false

/** 401 时清会话并跳转登录页（在 main.js 挂载 router 后调用） */
export function setupAuthInterceptor(router) {
  const onUnauthorized = (error) => {
    if (error.response?.status !== 401) return Promise.reject(error)

    const url = String(error.config?.url || '')
    // 登录接口本身的 401（密码错误）不触发跳转
    if (url.includes('/auth/login') || url.includes('/auth/status')) {
      return Promise.reject(error)
    }

    clearAuthSession()
    const route = router.currentRoute.value
    if (!authRedirecting && route.name !== 'login') {
      authRedirecting = true
      const redirect = route.fullPath && route.fullPath !== '/' ? route.fullPath : undefined
      router
        .replace({ name: 'login', query: redirect ? { redirect } : {} })
        .finally(() => {
          authRedirecting = false
        })
    }
    return Promise.reject(error)
  }

  axios.interceptors.response.use((res) => res, onUnauthorized)
  api.interceptors.response.use((res) => res, onUnauthorized)
}
