import { create } from 'zustand'

type Tab = 'planner' | 'portfolio' | 'explorer' | 'alerts' | 'settings'

interface AppState {
  activeTab: Tab
  setTab: (t: Tab) => void
  darkMode: boolean
  toggleDark: () => void
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'planner',
  setTab: (t) => set({ activeTab: t }),
  darkMode: true,
  toggleDark: () => set((s) => ({ darkMode: !s.darkMode })),
}))

