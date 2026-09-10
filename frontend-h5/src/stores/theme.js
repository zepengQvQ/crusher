import { defineStore } from 'pinia'

const THEME_KEY = 'crusher_theme'

function applyToRoot(theme) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.remove('van-theme-light', 'van-theme-dark')
  root.classList.add(`van-theme-${theme}`)
  root.style.colorScheme = theme
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    theme: 'light',
  }),
  getters: {
    isDark: (s) => s.theme === 'dark',
  },
  actions: {
    restore() {
      try {
        const saved = localStorage.getItem(THEME_KEY)
        if (saved === 'dark' || saved === 'light') {
          this.theme = saved
        } else {
          // 未显式选择时跟随系统
          const prefersDark =
            window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
          this.theme = prefersDark ? 'dark' : 'light'
        }
      } catch {
        this.theme = 'light'
      }
      applyToRoot(this.theme)
    },
    toggle() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      this._persist()
      applyToRoot(this.theme)
    },
    setTheme(theme) {
      this.theme = theme === 'dark' ? 'dark' : 'light'
      this._persist()
      applyToRoot(this.theme)
    },
    _persist() {
      try {
        localStorage.setItem(THEME_KEY, this.theme)
      } catch {
        /* ignore */
      }
    },
  },
})
