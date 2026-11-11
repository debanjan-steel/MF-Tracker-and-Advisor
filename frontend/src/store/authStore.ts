import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authAPI } from '../lib/api'

interface User {
  id: string
  email: string
}

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  setToken: (token: string, refreshToken?: string) => void
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      loading: false,
      error: null,

      setToken: (token: string, refreshToken?: string) => {
        try {
          localStorage.setItem('access_token', token)
          if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken)
          }
        } catch {}
        set((s) => ({
          token,
          refreshToken: refreshToken || s.refreshToken,
        }))
      },

      login: async (email, password) => {
        set({ loading: true, error: null })
        try {
          const { data } = await authAPI.login(email, password)
          const accessToken = data.access_token || data.token
          const refreshToken = data.refresh_token || null
          if (accessToken) {
            localStorage.setItem('access_token', accessToken)
          }
          if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken)
          }
          const userObj = data.user || { id: data.user_id, email: data.email || email }
          set({
            user: userObj,
            token: accessToken,
            refreshToken,
            loading: false,
          })
        } catch (e: any) {
          set({ error: e.response?.data?.detail || 'Login failed', loading: false })
          throw e
        }
      },

      signup: async (email, password) => {
        set({ loading: true, error: null })
        try {
          const { data } = await authAPI.signup(email, password)
          const accessToken = data.access_token || data.token
          const refreshToken = data.refresh_token || null
          if (accessToken) {
            localStorage.setItem('access_token', accessToken)
          }
          if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken)
          }
          const userObj = data.user || { id: data.user_id, email: data.email || email }
          set({
            user: userObj,
            token: accessToken,
            refreshToken,
            loading: false,
          })
        } catch (e: any) {
          set({ error: e.response?.data?.detail || 'Signup failed', loading: false })
          throw e
        }
      },

      logout: async () => {
        try { await authAPI.logout() } catch { /* ignore */ }
        try {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        } catch {}
        set({ user: null, token: null, refreshToken: null })
      },

      deleteAccount: async () => {
        set({ loading: true })
        try {
          await authAPI.deleteAccount()
        } catch { /* ignore */ }
        try {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        } catch {}
        set({ user: null, token: null, refreshToken: null, loading: false })
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'mf-auth',
      partialize: (s) => ({ user: s.user, token: s.token, refreshToken: s.refreshToken }),
    }
  )
)

if (typeof window !== 'undefined') {
  window.addEventListener('mf-auth-unauthorized', () => {
    useAuthStore.getState().logout()
  })
}
