import { defineStore } from 'pinia'

const THEME_KEY = 'crusher_theme'

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
          return
        }
        // 未显式选择时跟随系统
        const prefersDark =
          window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        this.theme = prefersDark ? 'dark' : 'light'
      } catch {
        this.theme = 'light'
      }
    },
    toggle() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      this._persist()
    },
    setTheme(theme) {
      this.theme = theme === 'dark' ? 'dark' : 'light'
      this._persist()
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
