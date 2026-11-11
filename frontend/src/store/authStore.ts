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
  loading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      loading: false,
      error: null,

      login: async (email, password) => {
        set({ loading: true, error: null })
        try {
          const { data } = await authAPI.login(email, password)
          localStorage.setItem('access_token', data.access_token)
          const userObj = data.user || { id: data.user_id, email: data.email }
          set({ user: userObj, token: data.access_token, loading: false })
        } catch (e: any) {
          set({ error: e.response?.data?.detail || 'Login failed', loading: false })
          throw e
        }
      },

      signup: async (email, password) => {
        set({ loading: true, error: null })
        try {
          const { data } = await authAPI.signup(email, password)
          localStorage.setItem('access_token', data.access_token)
          const userObj = data.user || { id: data.user_id, email: data.email }
          set({ user: userObj, token: data.access_token, loading: false })
        } catch (e: any) {
          set({ error: e.response?.data?.detail || 'Signup failed', loading: false })
          throw e
        }
      },

      logout: async () => {
        try { await authAPI.logout() } catch { /* ignore */ }
        localStorage.removeItem('access_token')
        set({ user: null, token: null })
      },

      deleteAccount: async () => {
        set({ loading: true })
        await authAPI.deleteAccount()
        localStorage.removeItem('access_token')
        set({ user: null, token: null, loading: false })
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'mf-auth',
      partialize: (s) => ({ user: s.user, token: s.token }),
    }
  )
)

if (typeof window !== 'undefined') {
  window.addEventListener('mf-auth-unauthorized', () => {
    useAuthStore.getState().logout()
  })
}

