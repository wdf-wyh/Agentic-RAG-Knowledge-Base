<template>
  <div class="login-page">
    <div class="aurora" aria-hidden="true"></div>
    <canvas ref="starfield" class="starfield" aria-hidden="true"></canvas>

    <main class="card" role="main">
      <svg class="emblem" viewBox="0 0 64 64" aria-hidden="true">
        <line class="link" x1="32" y1="32" x2="32" y2="14" />
        <line class="link" x1="32" y1="32" x2="50" y2="42" />
        <line class="link" x1="32" y1="32" x2="14" y2="42" />
        <line class="link" x1="32" y1="32" x2="46" y2="20" />
        <circle class="ring" cx="32" cy="32" r="14" />
        <circle class="node core" cx="32" cy="32" r="6" />
        <circle class="node" cx="32" cy="14" r="3.4" />
        <circle class="node s" cx="50" cy="42" r="3.4" />
        <circle class="node s2" cx="14" cy="42" r="3.4" />
        <circle class="node s" cx="46" cy="20" r="3.4" />
      </svg>

      <div class="brand-name"><b>RAG</b> 知识库助手</div>
      <div class="tagline">
        {{ auth.currentUser ? '账号中心 · 已登录' : '企业级检索增强 · 智能工作台' }}
      </div>

      <div class="divider"></div>

      <template v-if="!auth.currentUser">
        <button
          v-if="auth.authStatus.oidc_enabled"
          type="button"
          class="sso"
          @click="loginWithSso"
        >
          企业 SSO 登录
        </button>

        <div
          v-if="auth.authStatus.oidc_enabled && auth.authStatus.password_login_enabled"
          class="or"
        >
          或使用账号密码
        </div>

        <form
          v-if="auth.authStatus.password_login_enabled !== false || !auth.authStatus.oidc_enabled"
          class="form"
          autocomplete="off"
          novalidate
          @submit.prevent="login"
        >
          <div class="field">
            <label for="login-username">用户名</label>
            <div class="input">
              <input
                id="login-username"
                v-model="loginForm.username"
                type="text"
                placeholder="请输入用户名"
                autocomplete="username"
              />
              <span class="underline"></span>
            </div>
          </div>

          <div class="field">
            <label for="login-password">密码</label>
            <div class="input">
              <input
                id="login-password"
                v-model="loginForm.password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                autocomplete="current-password"
              />
              <button
                type="button"
                class="toggle"
                :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <svg
                  v-if="!showPassword"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M17.94 17.94A10 10 0 0 1 12 20C5 20 1 12 1 12a18 18 0 0 1 5.06-5.94M9.9 4.24A9 9 0 0 1 12 4c7 0 11 8 11 8a18 18 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
                  />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              </button>
              <span class="underline"></span>
            </div>
          </div>

          <button
            type="submit"
            class="submit"
            :class="{ loading: authLoading }"
            :disabled="authLoading"
            @click="addRipple"
          >
            <span class="label">
              登录并进入
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M5 12h14" />
                <path d="M13 6l6 6-6 6" />
              </svg>
            </span>
          </button>
        </form>

        <p v-else class="muted">当前未启用任何登录方式，请联系管理员。</p>
      </template>

      <template v-else>
        <div class="profile">
          <div class="profile__avatar">{{ auth.currentUser.username?.charAt(0)?.toUpperCase() }}</div>
          <div>
            <h3>{{ auth.currentUser.username }}</h3>
            <p>租户 {{ auth.currentUser.tenant_id }}</p>
          </div>
        </div>
        <div class="kv">
          <span>角色</span>
          <span>{{ (auth.currentUser.roles || []).join(', ') || '-' }}</span>
        </div>
        <div class="kv">
          <span>User ID</span>
          <span>{{ auth.currentUser.user_id }}</span>
        </div>
        <div class="actions">
          <button type="button" class="submit" @click="enterWorkspace">进入工作台</button>
        </div>
      </template>

      <div class="foot">
        <i></i>
        服务状态：{{ auth.authStatus.enabled ? '已启用' : '未启用' }} · © 2026
      </div>
    </main>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE, authHeaders } from '../utils/api'
import {
  useAuthState,
  loadAuthState,
  setAuthSession,
  clearAuthSession,
  ensureAuthStatus
} from '../stores/auth'

export default {
  name: 'LoginView',
  data() {
    return {
      auth: useAuthState(),
      authLoading: false,
      showPassword: false,
      loginForm: {
        username: 'admin',
        password: 'admin123'
      },
      _starfieldRaf: 0,
      _starfieldCleanup: null
    }
  },
  mounted() {
    loadAuthState()
    this.fetchAuthStatus()
    this.handleOidcCallback()
    this.initStarfield()
  },
  beforeUnmount() {
    if (typeof this._starfieldCleanup === 'function') {
      this._starfieldCleanup()
      this._starfieldCleanup = null
    }
  },
  methods: {
    initStarfield() {
      const canvas = this.$refs.starfield
      if (!canvas) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      let width = 0
      let height = 0
      let dpr = 1
      let stars = []
      let meteors = []
      let running = true

      const rand = (min, max) => min + Math.random() * (max - min)

      const createStar = () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: rand(0.4, 1.8),
        baseAlpha: rand(0.25, 0.9),
        twinkleSpeed: rand(0.6, 2.2),
        twinklePhase: Math.random() * Math.PI * 2,
        driftX: rand(-0.03, 0.03),
        driftY: rand(0.01, 0.08),
        hue: Math.random() > 0.82 ? 250 : 210
      })

      const createMeteor = () => {
        const fromLeft = Math.random() > 0.35
        return {
          x: fromLeft ? rand(-80, width * 0.55) : rand(width * 0.45, width + 80),
          y: rand(-40, height * 0.35),
          len: rand(70, 160),
          speed: rand(6, 11),
          angle: fromLeft ? rand(0.35, 0.7) : rand(Math.PI - 0.7, Math.PI - 0.35),
          alpha: rand(0.45, 0.85),
          life: 0,
          maxLife: rand(45, 90)
        }
      }

      const resize = () => {
        dpr = Math.min(window.devicePixelRatio || 1, 2)
        width = window.innerWidth
        height = window.innerHeight
        canvas.width = Math.floor(width * dpr)
        canvas.height = Math.floor(height * dpr)
        canvas.style.width = `${width}px`
        canvas.style.height = `${height}px`
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

        const count = Math.round(Math.min(220, Math.max(90, (width * height) / 14000)))
        stars = Array.from({ length: count }, createStar)
        meteors = []
        if (reduceMotion) {
          draw(0)
        }
      }

      const draw = (time) => {
        if (!running) return
        ctx.clearRect(0, 0, width, height)

        for (const star of stars) {
          const twinkle =
            0.55 + 0.45 * Math.sin(time * 0.001 * star.twinkleSpeed + star.twinklePhase)
          const alpha = star.baseAlpha * twinkle

          if (!reduceMotion) {
            star.x += star.driftX
            star.y += star.driftY
            if (star.x < -2) star.x = width + 2
            if (star.x > width + 2) star.x = -2
            if (star.y > height + 2) {
              star.y = -2
              star.x = Math.random() * width
            }
          }

          ctx.beginPath()
          ctx.fillStyle = `hsla(${star.hue}, 70%, 88%, ${alpha})`
          ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2)
          ctx.fill()

          if (star.r > 1.2) {
            ctx.beginPath()
            ctx.fillStyle = `hsla(${star.hue}, 80%, 92%, ${alpha * 0.18})`
            ctx.arc(star.x, star.y, star.r * 3.2, 0, Math.PI * 2)
            ctx.fill()
          }
        }

        if (!reduceMotion) {
          if (meteors.length < 2 && Math.random() < 0.008) {
            meteors.push(createMeteor())
          }

          meteors = meteors.filter((m) => {
            m.life += 1
            m.x += Math.cos(m.angle) * m.speed
            m.y += Math.sin(m.angle) * m.speed
            const fade = 1 - m.life / m.maxLife
            const alpha = m.alpha * fade

            const tx = m.x - Math.cos(m.angle) * m.len
            const ty = m.y - Math.sin(m.angle) * m.len
            const grad = ctx.createLinearGradient(tx, ty, m.x, m.y)
            grad.addColorStop(0, `rgba(199, 210, 254, 0)`)
            grad.addColorStop(0.55, `rgba(199, 210, 254, ${alpha * 0.35})`)
            grad.addColorStop(1, `rgba(255, 255, 255, ${alpha})`)

            ctx.strokeStyle = grad
            ctx.lineWidth = 1.4
            ctx.lineCap = 'round'
            ctx.beginPath()
            ctx.moveTo(tx, ty)
            ctx.lineTo(m.x, m.y)
            ctx.stroke()

            ctx.beginPath()
            ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
            ctx.arc(m.x, m.y, 1.5, 0, Math.PI * 2)
            ctx.fill()

            return m.life < m.maxLife && m.x > -200 && m.x < width + 200 && m.y < height + 200
          })
        }

        if (!reduceMotion) {
          this._starfieldRaf = requestAnimationFrame(draw)
        }
      }

      resize()
      if (!reduceMotion) {
        this._starfieldRaf = requestAnimationFrame(draw)
      }

      const onResize = () => resize()
      window.addEventListener('resize', onResize)

      this._starfieldCleanup = () => {
        running = false
        cancelAnimationFrame(this._starfieldRaf)
        window.removeEventListener('resize', onResize)
      }
    },
    workspaceTarget() {
      const redirect = this.$route.query.redirect
      return typeof redirect === 'string' && redirect && redirect !== '/login' ? redirect : '/'
    },
    enterWorkspace() {
      this.$router.push(this.workspaceTarget())
    },
    async fetchAuthStatus() {
      try {
        await ensureAuthStatus()
        if (this.auth.accessToken) await this.fetchCurrentUser()
      } catch (e) {
        console.error('加载认证状态失败:', e)
      }
    },
    handleOidcCallback() {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('oidc_token')
      if (!token) return
      setAuthSession(token, null)
      this.fetchCurrentUser().then(() => {
        ElMessage.success('SSO 登录成功')
        this.$router.replace(this.workspaceTarget())
      })
    },
    loginWithSso() {
      window.location.href = `${API_BASE}/auth/oidc/login`
    },
    async fetchCurrentUser() {
      if (!this.auth.accessToken) return
      try {
        const res = await axios.get(`${API_BASE}/auth/me`, { headers: authHeaders() })
        if (res.data.user) {
          setAuthSession(this.auth.accessToken, res.data.user)
        }
      } catch {
        if (!this.auth.currentUser) clearAuthSession()
      }
    },
    addRipple(e) {
      const s = e.currentTarget
      const r = s.getBoundingClientRect()
      const d = document.createElement('span')
      d.className = 'ripple'
      const size = Math.max(r.width, r.height)
      d.style.width = `${size}px`
      d.style.height = `${size}px`
      d.style.left = `${e.clientX - r.left - size / 2}px`
      d.style.top = `${e.clientY - r.top - size / 2}px`
      s.appendChild(d)
      setTimeout(() => d.remove(), 600)
    },
    async login() {
      if (this.authLoading) return
      this.authLoading = true
      try {
        const res = await axios.post(`${API_BASE}/auth/login`, this.loginForm)
        const user = {
          username: res.data.username,
          tenant_id: res.data.tenant_id,
          roles: res.data.roles || [],
          user_id: res.data.username
        }
        setAuthSession(res.data.access_token, user)
        await this.fetchCurrentUser()
        ElMessage.success(`已登录为 ${res.data.username}`)
        this.$router.push(this.workspaceTarget())
      } catch (e) {
        ElMessage.error(`登录失败: ${e.response?.data?.detail || e.message}`)
      } finally {
        this.authLoading = false
      }
    }
  }
}
</script>

<style scoped>
.login-page {
  --ink: #0a0a10;
  --paper: #ffffff;
  --paper-soft: #f7f8fb;
  --line: #e8eaf0;
  --text: #0f172a;
  --text-sub: #5b6478;
  --text-faint: #9aa2b1;
  --accent: #6366f1;
  --accent-2: #8b5cf6;
  --accent-soft: rgba(99, 102, 241, 0.14);
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);

  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: var(--ink);
  color: var(--text);
  font-family: 'Noto Sans SC', 'Outfit', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.aurora {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.starfield {
  position: fixed;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.aurora::before,
.aurora::after {
  content: '';
  position: absolute;
  width: 70vmax;
  height: 70vmax;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.2;
  will-change: transform;
}

.aurora::before {
  background: radial-gradient(circle at 30% 30%, #6366f1, transparent 60%);
  top: -20vmax;
  left: -10vmax;
  animation: drift1 34s var(--ease) infinite alternate;
}

.aurora::after {
  background: radial-gradient(circle at 70% 70%, #8b5cf6, transparent 60%);
  bottom: -25vmax;
  right: -15vmax;
  animation: drift2 42s var(--ease) infinite alternate;
}

@keyframes drift1 {
  to {
    transform: translate(14vmax, 10vmax) scale(1.15);
  }
}

@keyframes drift2 {
  to {
    transform: translate(-12vmax, -8vmax) scale(1.1);
  }
}

.card {
  position: relative;
  z-index: 1;
  width: min(420px, 92vw);
  background: var(--paper);
  border-radius: 22px;
  padding: 44px 40px 34px;
  text-align: center;
  overflow: hidden;
  box-shadow:
    0 30px 80px -30px rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(255, 255, 255, 0.04);
  opacity: 0;
  transform: translateY(28px) scale(0.985);
  filter: blur(6px);
  animation: reveal 0.9s var(--ease-out) 0.15s forwards;
}

@keyframes reveal {
  to {
    opacity: 1;
    transform: none;
    filter: blur(0);
  }
}

.card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--accent-2), transparent);
  background-size: 200% 100%;
  animation: slide 6s linear infinite;
}

@keyframes slide {
  to {
    background-position: -200% 0;
  }
}

.emblem {
  width: 74px;
  height: 74px;
  margin: 0 auto 18px;
  display: block;
  opacity: 0;
  animation: fade 0.8s var(--ease) 0.45s forwards;
}

.emblem .link {
  stroke: var(--accent-2);
  stroke-width: 1.6;
  fill: none;
  stroke-linecap: round;
  stroke-dasharray: 46;
  stroke-dashoffset: 46;
  animation: draw 1.3s var(--ease-out) 0.6s forwards;
}

.emblem .link:nth-child(2) {
  animation-delay: 0.72s;
}
.emblem .link:nth-child(3) {
  animation-delay: 0.84s;
}
.emblem .link:nth-child(4) {
  animation-delay: 0.96s;
}

.emblem .node {
  fill: var(--accent);
  transform-box: fill-box;
  transform-origin: center;
  opacity: 0;
  animation: pop 0.5s var(--ease) 1.4s forwards;
}

.emblem .node.core {
  fill: var(--accent-2);
  animation-delay: 1.3s;
}

.emblem .node.s {
  fill: #c4b5fd;
  animation-delay: 1.55s;
}

.emblem .node.s2 {
  fill: #a5b4fc;
  animation-delay: 1.7s;
}

.emblem .ring {
  fill: none;
  stroke: var(--accent);
  stroke-width: 1;
  opacity: 0;
  transform-box: fill-box;
  transform-origin: center;
  animation: ring 3.2s ease-out 1.8s infinite;
}

@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes pop {
  from {
    opacity: 0;
    transform: scale(0.3);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes ring {
  0% {
    opacity: 0.5;
    transform: scale(0.6);
  }
  70% {
    opacity: 0;
    transform: scale(1.5);
  }
  100% {
    opacity: 0;
  }
}

.brand-name {
  font-family: 'Outfit', 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 20px;
  color: var(--text);
  opacity: 0;
  transform: translateY(10px);
  animation: up 0.7s var(--ease) 0.8s forwards;
}

.brand-name b {
  background: linear-gradient(120deg, #6366f1, #8b5cf6 70%, #c4b5fd);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.tagline {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-faint);
  letter-spacing: 0.3px;
  opacity: 0;
  animation: fade 0.7s var(--ease) 0.95s forwards;
}

.divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line), transparent);
  margin: 26px 0 22px;
  opacity: 0;
  animation: fade 0.7s var(--ease) 1.05s forwards;
}

.form {
  text-align: left;
}

.field {
  text-align: left;
  margin-bottom: 18px;
  opacity: 0;
  transform: translateY(10px);
}

.field:nth-of-type(1) {
  animation: up 0.7s var(--ease) 1.1s forwards;
}

.field:nth-of-type(2) {
  animation: up 0.7s var(--ease) 1.2s forwards;
}

.field label {
  display: block;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-sub);
  margin-bottom: 8px;
  letter-spacing: 0.2px;
}

.input {
  position: relative;
}

.input input {
  width: 100%;
  padding: 13px 15px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text);
  background: var(--paper-soft);
  border: 1.5px solid var(--line);
  border-radius: 12px;
  outline: none;
  transition:
    border-color 0.3s var(--ease),
    background 0.3s var(--ease),
    box-shadow 0.3s var(--ease);
}

.field:nth-of-type(2) .input input {
  padding-right: 44px;
}

.input input::placeholder {
  color: #c2c8d4;
}

.input input:hover {
  border-color: #d4d8e2;
  background: #fff;
}

.input input:focus {
  border-color: var(--accent);
  background: #fff;
  box-shadow: 0 0 0 4px var(--accent-soft);
}

.input .underline {
  position: absolute;
  left: 50%;
  bottom: 0;
  height: 2px;
  width: 0;
  border-radius: 0 0 12px 12px;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
  transform: translateX(-50%);
  transition: width 0.4s var(--ease);
}

.input input:focus ~ .underline {
  width: 100%;
}

.toggle {
  position: absolute;
  right: 11px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: none;
  color: var(--text-faint);
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  transition:
    color 0.25s,
    background 0.25s;
}

.toggle:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

.toggle svg {
  width: 17px;
  height: 17px;
}

.submit {
  margin-top: 24px;
  position: relative;
  width: 100%;
  padding: 14px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  border: none;
  border-radius: 13px;
  cursor: pointer;
  overflow: hidden;
  background: linear-gradient(120deg, var(--accent), var(--accent-2));
  background-size: 180% 100%;
  opacity: 0;
  transform: translateY(10px);
  animation: up 0.7s var(--ease) 1.3s forwards;
  transition:
    transform 0.3s var(--ease),
    box-shadow 0.3s var(--ease),
    background-position 0.5s var(--ease);
  box-shadow: 0 10px 24px -12px rgba(99, 102, 241, 0.7);
}

.submit:hover:not(:disabled) {
  transform: translateY(-2px);
  background-position: 100% 0;
  box-shadow: 0 16px 32px -12px rgba(99, 102, 241, 0.8);
}

.submit:active:not(:disabled) {
  transform: translateY(0) scale(0.99);
}

.submit .label {
  position: relative;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.submit .label svg {
  transition: transform 0.3s var(--ease);
}

.submit:hover .label svg {
  transform: translateX(4px);
}

.submit::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(
    110deg,
    transparent 30%,
    rgba(255, 255, 255, 0.22) 50%,
    transparent 70%
  );
  transform: translateX(-120%);
  animation: sheen 5.5s var(--ease) 2s infinite;
}

@keyframes sheen {
  0%,
  55% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(120%);
  }
}

.submit :deep(.ripple) {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  transform: scale(0);
  animation: rip 0.6s var(--ease-out);
  pointer-events: none;
  z-index: 1;
}

@keyframes rip {
  to {
    transform: scale(4);
    opacity: 0;
  }
}

.submit.loading .label {
  visibility: hidden;
}

.submit.loading::before {
  content: '';
  position: absolute;
  z-index: 2;
  width: 18px;
  height: 18px;
  top: 50%;
  left: 50%;
  margin: -9px 0 0 -9px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.sso {
  width: 100%;
  padding: 13px;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1.5px solid rgba(99, 102, 241, 0.25);
  border-radius: 12px;
  cursor: pointer;
  transition:
    background 0.25s,
    border-color 0.25s,
    transform 0.25s;
  opacity: 0;
  animation: fade 0.7s var(--ease) 1.1s forwards;
}

.sso:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}

.or {
  margin: 16px 0;
  font-size: 12px;
  color: var(--text-faint);
  display: flex;
  align-items: center;
  gap: 12px;
  opacity: 0;
  animation: fade 0.7s var(--ease) 1.15s forwards;
}

.or::before,
.or::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--line);
}

.muted {
  color: var(--text-faint);
  font-size: 14px;
  line-height: 1.6;
}

.profile {
  display: flex;
  align-items: center;
  gap: 14px;
  text-align: left;
  margin-bottom: 18px;
}

.profile__avatar {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 20px;
  color: #fff;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  flex-shrink: 0;
}

.profile h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--text);
}

.profile p,
.kv {
  color: var(--text-sub);
  font-size: 13px;
}

.kv {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.actions {
  display: grid;
  gap: 10px;
  margin-top: 8px;
}

.actions .submit {
  margin-top: 12px;
  opacity: 1;
  transform: none;
  animation: none;
}

.foot {
  margin-top: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-size: 12px;
  color: var(--text-faint);
  opacity: 0;
  animation: fade 0.7s var(--ease) 1.45s forwards;
}

.foot i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #34d399;
  display: inline-block;
  animation: beat 2.4s ease infinite;
}

@keyframes beat {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(52, 211, 153, 0);
  }
}

@keyframes up {
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes fade {
  to {
    opacity: 1;
  }
}

@media (max-width: 420px) {
  .card {
    padding: 36px 26px 28px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-page *,
  .login-page *::before,
  .login-page *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
</style>
