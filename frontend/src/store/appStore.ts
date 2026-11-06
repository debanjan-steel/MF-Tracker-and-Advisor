import { create } from 'zustand'
import { TacticalPlan, TimingScore, GoalPlan } from '../types'

type Tab = 'planner' | 'portfolio' | 'explorer' | 'alerts' | 'settings'

export interface WatchlistItem {
  scheme_code: number
  scheme_name: string
  fund_house?: string
  scheme_category?: string
  added_at?: string
}

const loadSavedWatchlist = (): WatchlistItem[] => {
  try {
    const raw = localStorage.getItem('mf_watchlist')
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const persistWatchlist = (list: WatchlistItem[]) => {
  try {
    localStorage.setItem('mf_watchlist', JSON.stringify(list))
  } catch {
    // ignore
  }
}

interface AppState {
  // ── Navigation ─────────────────────────────────────────────────
  activeTab: Tab
  setTab: (t: Tab) => void

  // ── Theme ──────────────────────────────────────────────────────
  darkMode: boolean
  toggleDark: () => void

  // ── Planner Persistent State ───────────────────────────────────
  // Step 1: Capital
  plannerCapital: string
  setPlannerCapital: (v: string) => void

  // Step 2: Monthly budget
  plannerHasMonthlyBudget: boolean
  setPlannerHasMonthlyBudget: (v: boolean) => void
  plannerMonthlyLimit: string
  setPlannerMonthlyLimit: (v: string) => void

  // Step 3: Goal
  plannerHasGoal: boolean
  setPlannerHasGoal: (v: boolean) => void
  plannerGoalMode: 'target' | 'retirement'
  setPlannerGoalMode: (v: 'target' | 'retirement') => void
  plannerGoalTarget: string
  setPlannerGoalTarget: (v: string) => void
  plannerGoalYears: string
  setPlannerGoalYears: (v: string) => void
  plannerCurrentAge: string
  setPlannerCurrentAge: (v: string) => void

  // Strategy Mode: 'tactical' (Dynamic with Liquid + Flexi) vs 'strict_equity' (Pure Large/Mid/Small only)
  plannerStrategyMode: 'tactical' | 'strict_equity'
  setPlannerStrategyMode: (v: 'tactical' | 'strict_equity') => void

  // Generated results
  plannerTacticalPlan: TacticalPlan | null
  setPlannerTacticalPlan: (v: TacticalPlan | null) => void
  plannerTiming: TimingScore | null
  setPlannerTiming: (v: TimingScore | null) => void
  plannerGoal: GoalPlan | null
  setPlannerGoal: (v: GoalPlan | null) => void

  // ── Watchlist ──────────────────────────────────────────────────
  watchlist: WatchlistItem[]
  addToWatchlist: (item: WatchlistItem) => void
  removeFromWatchlist: (code: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  // ── Navigation ─────────────────────────────────────────────────
  activeTab: 'planner',
  setTab: (t) => set({ activeTab: t }),

  // ── Theme ──────────────────────────────────────────────────────
  darkMode: true,
  toggleDark: () => set((s) => ({ darkMode: !s.darkMode })),

  // ── Planner Persistent State ───────────────────────────────────
  plannerCapital: '',
  setPlannerCapital: (v) => set({ plannerCapital: v }),

  plannerHasMonthlyBudget: false,
  setPlannerHasMonthlyBudget: (v) => set({ plannerHasMonthlyBudget: v }),
  plannerMonthlyLimit: '30000',
  setPlannerMonthlyLimit: (v) => set({ plannerMonthlyLimit: v }),

  plannerHasGoal: false,
  setPlannerHasGoal: (v) => set({ plannerHasGoal: v }),
  plannerGoalMode: 'target',
  setPlannerGoalMode: (v) => set({ plannerGoalMode: v }),
  plannerGoalTarget: '10000000',
  setPlannerGoalTarget: (v) => set({ plannerGoalTarget: v }),
  plannerGoalYears: '10',
  setPlannerGoalYears: (v) => set({ plannerGoalYears: v }),
  plannerCurrentAge: '30',
  setPlannerCurrentAge: (v) => set({ plannerCurrentAge: v }),

  plannerStrategyMode: 'tactical',
  setPlannerStrategyMode: (v) => set({ plannerStrategyMode: v }),

  plannerTacticalPlan: null,
  setPlannerTacticalPlan: (v) => set({ plannerTacticalPlan: v }),
  plannerTiming: null,
  setPlannerTiming: (v) => set({ plannerTiming: v }),
  plannerGoal: null,
  setPlannerGoal: (v) => set({ plannerGoal: v }),

  // ── Watchlist ──────────────────────────────────────────────────
  watchlist: loadSavedWatchlist(),
  addToWatchlist: (item) =>
    set((state) => {
      if (state.watchlist.some((w) => w.scheme_code === item.scheme_code)) {
        return state
      }
      const updated = [item, ...state.watchlist]
      persistWatchlist(updated)
      return { watchlist: updated }
    }),
  removeFromWatchlist: (code) =>
    set((state) => {
      const updated = state.watchlist.filter((w) => w.scheme_code !== code)
      persistWatchlist(updated)
      return { watchlist: updated }
    }),
}))
