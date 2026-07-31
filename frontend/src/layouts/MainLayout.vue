<template>
  <div class="app-container enterprise-shell" :class="{ 'sidebar-open': sidebarOpen }">
    <button
      type="button"
      class="sidebar-toggle"
      :aria-label="sidebarOpen ? '收起侧边栏' : '展开侧边栏'"
      @click="sidebarOpen = !sidebarOpen"
    >
      <span>{{ sidebarOpen ? '✕' : '☰' }}</span>
    </button>

    <div
      v-if="sidebarOpen"
      class="sidebar-backdrop"
      @click="sidebarOpen = false"
    />

    <aside class="enterprise-sidebar">
      <router-link to="/" class="logo-section logo-link" @click="closeSidebarOnMobile">
        <div class="logo-icon floating">
          <img src="/logo.svg" alt="RAG 知识库助手" class="logo-image" />
        </div>
        <div class="logo-text">
          <h1 class="gradient-text">RAG 知识库助手</h1>
          <p>企业级智能知识工作台</p>
        </div>
      </router-link>

      <nav class="enterprise-nav">
        <div
          v-if="isChatRoute"
          class="custom-select full-width sidebar-mode-select"
          :class="{ 'is-open': modeDropdownOpen }"
          v-click-outside="() => (modeDropdownOpen = false)"
        >
          <div class="custom-select__trigger" @click="modeDropdownOpen = !modeDropdownOpen">
            <span class="custom-select__value">{{ currentModeLabel }}</span>
            <span class="custom-select__arrow">▾</span>
          </div>
          <div class="custom-select__dropdown" v-show="modeDropdownOpen">
            <div
              v-for="mode in modeOptions"
              :key="mode.value"
              class="custom-select__option"
              :class="{ 'is-selected': queryMode === mode.value }"
              @click="selectMode(mode.value)"
            >
              {{ mode.icon }} {{ mode.label }}
            </div>
          </div>
        </div>

        <div class="enterprise-nav__group">
          <p class="enterprise-nav__label">功能</p>
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-pill"
            :class="{ 'is-active': isActive(item.to) }"
            @click="closeSidebarOnMobile"
          >
            <span class="nav-pill__icon">{{ item.icon }}</span>
            <span class="nav-pill__text">{{ item.label }}</span>
          </router-link>

          <button
            v-if="isChatRoute"
            type="button"
            class="nav-pill"
            title="开始新对话"
            @click="startNewConversation"
          >
            <span class="nav-pill__icon">✨</span>
            <span class="nav-pill__text">新对话</span>
          </button>
        </div>

        <div class="enterprise-nav__spacer" />

        <div class="enterprise-nav__group enterprise-nav__group--footer">
          <router-link
            to="/admin"
            class="nav-pill"
            :class="{ 'is-active': $route.path === '/admin' }"
            @click="closeSidebarOnMobile"
          >
            <span class="nav-pill__icon">🏢</span>
            <span class="nav-pill__text">管理台</span>
          </router-link>

          <router-link
            to="/settings"
            class="nav-pill"
            :class="{ 'is-active': $route.path === '/settings' }"
            @click="closeSidebarOnMobile"
          >
            <span class="nav-pill__icon">⚙️</span>
            <span class="nav-pill__text">设置</span>
          </router-link>
        </div>
      </nav>
    </aside>

    <div class="main-container enterprise-main">
      <header class="enterprise-topbar">
        <div class="enterprise-topbar__spacer" />
        <div class="enterprise-topbar__actions">
          <button
            type="button"
            class="topbar-btn topbar-btn--icon"
            :title="theme.isDark ? '切换到浅色模式' : '切换到深色模式'"
            @click="onToggleTheme"
          >
            <span>{{ theme.isDark ? '☀️' : '🌙' }}</span>
          </button>

          <router-link
            v-if="!auth.currentUser"
            to="/login"
            class="topbar-btn topbar-btn--user"
            :class="{ 'is-active': $route.path === '/login' }"
          >
            <span class="topbar-btn__avatar">🔐</span>
            <span class="topbar-btn__label">登录</span>
          </router-link>

          <div
            v-else
            class="topbar-user-menu"
            :class="{ 'is-open': userMenuOpen }"
            v-click-outside="() => (userMenuOpen = false)"
          >
            <button
              type="button"
              class="topbar-btn topbar-btn--user"
              :class="{ 'is-active': userMenuOpen }"
              :aria-expanded="userMenuOpen"
              aria-haspopup="true"
              @click="userMenuOpen = !userMenuOpen"
            >
              <span class="topbar-btn__avatar">👤</span>
              <span class="topbar-btn__label">{{ auth.currentUser.username }}</span>
              <span class="topbar-user-menu__arrow">▾</span>
            </button>
            <div class="topbar-user-menu__dropdown" v-show="userMenuOpen">
              <button
                type="button"
                class="topbar-user-menu__item"
                title="退出登录"
                @click="logout"
              >
                退出
              </button>
            </div>
          </div>
        </div>
      </header>
      <router-view />
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { useAuthState, loadAuthState, clearAuthSession } from '../stores/auth'
import { useThemeState, loadTheme, toggleTheme } from '../stores/theme'

export default {
  name: 'MainLayout',
  directives: {
    'click-outside': {
      mounted(el, binding) {
        el._clickOutside = (event) => {
          if (!(el === event.target || el.contains(event.target))) {
            binding.value(event)
          }
        }
        document.addEventListener('click', el._clickOutside)
      },
      unmounted(el) {
        document.removeEventListener('click', el._clickOutside)
      }
    }
  },
  data() {
    return {
      auth: useAuthState(),
      theme: useThemeState(),
      modeDropdownOpen: false,
      userMenuOpen: false,
      sidebarOpen: false,
      queryMode: 'smart',
      modeOptions: [
        { value: 'rag', label: '纯 RAG', icon: '📚' },
        { value: 'smart', label: '智能模式', icon: '🧠' }
      ],
      navItems: [
        { to: '/', label: '对话', icon: '💬' },
        { to: '/eval', label: '评测', icon: '📊' },
        { to: '/traces', label: '追踪', icon: '🔍' },
        { to: '/knowledge', label: '知识库', icon: '📚' },
        { to: '/history', label: '历史', icon: '📜' }
      ]
    }
  },
  computed: {
    isChatRoute() {
      return this.$route.name === 'chat'
    },
    currentModeLabel() {
      const mode = this.modeOptions.find((m) => m.value === this.queryMode)
      return mode?.label || '智能模式'
    }
  },
  mounted() {
    loadAuthState()
    loadTheme()
    this.loadMode()
  },
  methods: {
    isActive(path) {
      return this.$route.path === path
    },
    closeSidebarOnMobile() {
      if (window.matchMedia('(max-width: 960px)').matches) {
        this.sidebarOpen = false
      }
    },
    loadMode() {
      try {
        const saved = JSON.parse(localStorage.getItem('ragSettings') || '{}')
        if (saved.queryMode === 'rag' || saved.queryMode === 'smart') {
          this.queryMode = saved.queryMode
        }
      } catch {
        this.queryMode = 'smart'
      }
    },
    selectMode(value) {
      this.queryMode = value
      this.modeDropdownOpen = false
      try {
        const saved = JSON.parse(localStorage.getItem('ragSettings') || '{}')
        saved.queryMode = value
        localStorage.setItem('ragSettings', JSON.stringify(saved))
      } catch {
        // ignore
      }
      window.dispatchEvent(new CustomEvent('rag-mode-changed', { detail: value }))
      ElMessage.success(`已切换到${this.currentModeLabel}`)
    },
    startNewConversation() {
      this.closeSidebarOnMobile()
      this.$router.push({ name: 'chat', query: { new: '1' } })
    },
    onToggleTheme() {
      const dark = toggleTheme()
      ElMessage.success(dark ? '已切换到深色模式' : '已切换到浅色模式')
    },
    logout() {
      this.userMenuOpen = false
      clearAuthSession()
      ElMessage.success('已退出登录')
      this.closeSidebarOnMobile()
      this.$router.replace({ name: 'login' })
    }
  }
}
</script>
