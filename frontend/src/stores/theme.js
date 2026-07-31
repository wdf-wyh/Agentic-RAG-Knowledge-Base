import { reactive } from 'vue'

const state = reactive({
  isDark: false
})

export function useThemeState() {
  return state
}

export function loadTheme() {
  try {
    const t = localStorage.getItem('siteTheme') || 'light'
    state.isDark = t === 'dark'
  } catch {
    state.isDark = false
  }
  applyTheme()
}

export function applyTheme() {
  try {
    if (state.isDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('siteTheme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('siteTheme', 'light')
    }
  } catch {
    // ignore
  }
}

export function toggleTheme() {
  state.isDark = !state.isDark
  applyTheme()
  return state.isDark
}
