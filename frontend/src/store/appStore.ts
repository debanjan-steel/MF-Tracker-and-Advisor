import { create } from 'zustand'
import { TacticalPlan, TimingScore, GoalPlan, SavedInvestmentPlanPayload, SavedGoalPlan } from '../types'
import { userAPI, plannerAPI, getAuthToken } from '../lib/api'

type Tab = 'planner' | 'portfolio' | 'explorer' | 'alerts' | 'settings'

export interface WatchlistItem {
  scheme_code: number
  scheme_name: string
  fund_house?: string
  scheme_category?: string
  added_at?: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Client-side Schema Auto-Migration & Normalization Transformers
// ─────────────────────────────────────────────────────────────────────────────

export const normalizeWatchlistItem = (item: any): WatchlistItem | null => {
  if (!item) return null
  if (typeof item === 'number' || (typeof item === 'string' && /^\d+$/.test(item.trim()))) {
    const code = Number(item)
    return {
      scheme_code: code,
      scheme_name: `Scheme ${code}`,
      added_at: new Date().toISOString(),
    }
  }
  const code = Number(item.scheme_code || item.code || item.id || 0)
  if (!code || isNaN(code)) return null
  return {
    scheme_code: code,
    scheme_name: String(item.scheme_name || item.name || `Scheme ${code}`).trim(),
    fund_house: item.fund_house ? String(item.fund_house).trim() : undefined,
    scheme_category: (item.scheme_category || item.category) ? String(item.scheme_category || item.category).trim() : undefined,
    added_at: item.added_at ? String(item.added_at) : new Date().toISOString(),
  }
}

export const normalizeWatchlistList = (list: any[]): WatchlistItem[] => {
  if (!Array.isArray(list)) return []
  const seen = new Set<number>()
  const res: WatchlistItem[] = []
  for (const it of list) {
    const norm = normalizeWatchlistItem(it)
    if (norm && !seen.has(norm.scheme_code)) {
      seen.add(norm.scheme_code)
      res.push(norm)
    }
  }
  return res
}

export const normalizeSavedPlan = (raw: any): SavedInvestmentPlanPayload | null => {
  if (!raw || typeof raw !== 'object') return null

  // If raw contains the payload in .plan or .plan_data, extract it
  const src = raw.plan_data || raw.plan || raw
  if (!src || typeof src !== 'object') return null

  const capital = Number(src.capital || raw.capital || src.tacticalPlan?.capital || 100000)
  const tacticalPlan = src.tacticalPlan || (src.category_allocations ? src : null)

  if (!tacticalPlan) {
    return null
  }

  return {
    capital: isNaN(capital) ? 100000 : capital,
    hasMonthlyBudget: Boolean(src.hasMonthlyBudget),
    monthlyLimit: String(src.monthlyLimit ?? '30000'),
    hasGoal: Boolean(src.hasGoal),
    goalMode: src.goalMode === 'retirement' ? 'retirement' : 'target',
    goalTarget: String(src.goalTarget ?? '10000000'),
    goalYears: String(src.goalYears ?? '10'),
    currentAge: String(src.currentAge ?? '30'),
    strategyMode: src.strategyMode === 'tactical' ? 'tactical' : 'strict_equity',
    tacticalPlan: tacticalPlan,
    timing: src.timing || null,
    goal: src.goal || null,
    savedAt: src.savedAt || raw.saved_at || new Date().toISOString(),
  }
}

export const normalizeSavedGoal = (raw: any): SavedGoalPlan | null => {
  if (!raw || typeof raw !== 'object') return null
  const target = Number(raw.target_corpus ?? raw.target_amount ?? raw.target ?? 1000000)
  const years = Math.max(1, Number(raw.years ?? raw.duration_years ?? 10))
  const sip = Number(raw.required_monthly_sip ?? raw.monthly_sip ?? raw.sip ?? 0)
  const projected = Number(raw.projected_corpus ?? raw.projected ?? target)
  const eq = Number(raw.equity_pct ?? 70)
  const liq = Number(raw.liquid_pct ?? 30)

  const glidePath = Array.isArray(raw.glide_path) ? raw.glide_path : (raw.goal_data?.glide_path || [])
  const alerts = Array.isArray(raw.milestone_alerts) ? raw.milestone_alerts : (raw.goal_data?.milestone_alerts || [])

  return {
    id: String(raw.id || `goal_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`),
    goal_name: String(raw.goal_name || raw.name || 'Financial Goal').trim(),
    target_corpus: isNaN(target) ? 1000000 : target,
    years: isNaN(years) ? 10 : years,
    required_monthly_sip: isNaN(sip) ? 0 : sip,
    projected_corpus: isNaN(projected) ? 1000000 : projected,
    equity_pct: isNaN(eq) ? 70 : eq,
    liquid_pct: isNaN(liq) ? 30 : liq,
    glide_path: glidePath,
    milestone_alerts: alerts,
    created_at: raw.created_at || new Date().toISOString(),
  }
}

export const normalizeGoalsList = (list: any[]): SavedGoalPlan[] => {
  if (!Array.isArray(list)) return []
  const seen = new Set<string>()
  const res: SavedGoalPlan[] = []
  for (const it of list) {
    const norm = normalizeSavedGoal(it)
    if (norm && !seen.has(norm.id)) {
      seen.add(norm.id)
      res.push(norm)
    }
  }
  return res
}

const loadSavedWatchlist = (): WatchlistItem[] => {
  try {
    const raw = localStorage.getItem('mf_watchlist')
    return raw ? normalizeWatchlistList(JSON.parse(raw)) : []
  } catch {
    return []
  }
}

const persistWatchlist = (list: WatchlistItem[]) => {
  try {
    const norm = normalizeWatchlistList(list)
    localStorage.setItem('mf_watchlist', JSON.stringify(norm))
  } catch {
    // ignore
  }
}

const loadSavedPlanFromStorage = (): SavedInvestmentPlanPayload | null => {
  try {
    const raw = localStorage.getItem('mf_saved_investment_plan')
    return raw ? normalizeSavedPlan(JSON.parse(raw)) : null
  } catch {
    return null
  }
}

const persistSavedPlanToStorage = (plan: SavedInvestmentPlanPayload | null) => {
  try {
    if (plan) {
      const norm = normalizeSavedPlan(plan)
      localStorage.setItem('mf_saved_investment_plan', JSON.stringify(norm))
    } else {
      localStorage.removeItem('mf_saved_investment_plan')
    }
  } catch {
    // ignore
  }
}

const loadSavedGoalsFromStorage = (): SavedGoalPlan[] => {
  try {
    const raw = localStorage.getItem('mf_saved_goals')
    return raw ? normalizeGoalsList(JSON.parse(raw)) : []
  } catch {
    return []
  }
}

const persistSavedGoalsToStorage = (goals: SavedGoalPlan[]) => {
  try {
    const norm = normalizeGoalsList(goals)
    localStorage.setItem('mf_saved_goals', JSON.stringify(norm))
  } catch {
    // ignore
  }
}

interface AppState {
  // ── Navigation ─────────────────────────────────────────────────
  activeTab: Tab
  setTab: (t: Tab) => void
  explorerSection: 'search' | 'watchlist' | 'thermo' | 'backtest'
  setExplorerSection: (s: 'search' | 'watchlist' | 'thermo' | 'backtest') => void

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

  // ── Saved Investment Plan Persistence ──────────────────────────
  savedPlan: SavedInvestmentPlanPayload | null
  setSavedPlan: (plan: SavedInvestmentPlanPayload | null) => void

  // ── Saved Long-Term Goals (Unlimited) ──────────────────────────
  savedGoals: SavedGoalPlan[]
  setSavedGoals: (goals: SavedGoalPlan[]) => void
  addSavedGoal: (goal: SavedGoalPlan) => void
  removeSavedGoal: (id: string) => void

  // ── Watchlist ──────────────────────────────────────────────────
  watchlist: WatchlistItem[]
  addToWatchlist: (item: WatchlistItem) => void
  removeFromWatchlist: (code: number) => void

  // ── Universal Cloud Sync ───────────────────────────────────────
  isSyncing: boolean
  syncWithCloud: () => Promise<void>
}

export const useAppStore = create<AppState>((set, get) => ({
  // ── Navigation ─────────────────────────────────────────────────
  activeTab: 'planner',
  setTab: (t) => set({ activeTab: t }),
  explorerSection: 'search',
  setExplorerSection: (s) => set({ explorerSection: s }),

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

  plannerStrategyMode: 'strict_equity',
  setPlannerStrategyMode: (v) => set({ plannerStrategyMode: v }),

  plannerTacticalPlan: null,
  setPlannerTacticalPlan: (v) => set({ plannerTacticalPlan: v }),
  plannerTiming: null,
  setPlannerTiming: (v) => set({ plannerTiming: v }),
  plannerGoal: null,
  setPlannerGoal: (v) => set({ plannerGoal: v }),

  // ── Saved Investment Plan Persistence ──────────────────────────
  savedPlan: loadSavedPlanFromStorage(),
  setSavedPlan: (plan) => {
    const norm = normalizeSavedPlan(plan)
    persistSavedPlanToStorage(norm)
    if (norm) {
      plannerAPI.savePlan(norm.capital, norm).catch(() => {})
    } else {
      plannerAPI.deleteSavedPlan().catch(() => {})
    }
    set({ savedPlan: norm })
  },

  // ── Saved Long-Term Goals (Unlimited) ──────────────────────────
  savedGoals: loadSavedGoalsFromStorage(),
  setSavedGoals: (goals) => {
    const norm = normalizeGoalsList(goals)
    persistSavedGoalsToStorage(norm)
    set({ savedGoals: norm })
  },
  addSavedGoal: (goal) => {
    const norm = normalizeSavedGoal(goal)
    if (!norm) return
    const current = loadSavedGoalsFromStorage()
    const existingIdx = current.findIndex((g) => g.id === norm.id)
    let updated: SavedGoalPlan[]
    if (existingIdx >= 0) {
      updated = [...current]
      updated[existingIdx] = norm
    } else {
      updated = [norm, ...current]
    }
    persistSavedGoalsToStorage(updated)
    plannerAPI.saveGoalPlan(norm).catch(() => {})
    set({ savedGoals: updated })
  },
  removeSavedGoal: (id) => {
    const current = loadSavedGoalsFromStorage()
    const updated = current.filter((g) => g.id !== id)
    persistSavedGoalsToStorage(updated)
    plannerAPI.deleteSavedGoal(id).catch(() => {})
    set({ savedGoals: updated })
  },

  // ── Watchlist ──────────────────────────────────────────────────
  watchlist: loadSavedWatchlist(),
  addToWatchlist: (item) =>
    set((state) => {
      const norm = normalizeWatchlistItem(item)
      if (!norm) return state
      if (state.watchlist.some((w) => w.scheme_code === norm.scheme_code)) {
        return state
      }
      const updated = [norm, ...state.watchlist]
      persistWatchlist(updated)
      userAPI.saveWatchlist(updated).catch(() => {})
      return { watchlist: updated }
    }),
  removeFromWatchlist: (code) =>
    set((state) => {
      const updated = state.watchlist.filter((w) => w.scheme_code !== code)
      persistWatchlist(updated)
      userAPI.saveWatchlist(updated).catch(() => {})
      return { watchlist: updated }
    }),

  // ── Universal Cloud Sync ───────────────────────────────────────
  isSyncing: false,
  syncWithCloud: async () => {
    const token = getAuthToken()
    if (!token) return
    set({ isSyncing: true })
    try {
      const res = await userAPI.getState()
      const cloud = res.data
      if (cloud) {
        // 1. Watchlist sync
        if (Array.isArray(cloud.watchlist)) {
          const cloudWl = normalizeWatchlistList(cloud.watchlist)
          const localWl = loadSavedWatchlist()
          const combinedWl = normalizeWatchlistList([...cloudWl, ...localWl])
          persistWatchlist(combinedWl)
          set({ watchlist: combinedWl })
          if (localWl.some((l) => !cloudWl.some((c) => c.scheme_code === l.scheme_code))) {
            userAPI.saveWatchlist(combinedWl).catch(() => {})
          }
        }

        // 2. Saved Goals sync
        if (Array.isArray(cloud.saved_goals)) {
          const cloudGoals = normalizeGoalsList(cloud.saved_goals)
          const localGoals = loadSavedGoalsFromStorage()
          const combinedGoals = normalizeGoalsList([...cloudGoals, ...localGoals])
          persistSavedGoalsToStorage(combinedGoals)
          set({ savedGoals: combinedGoals })
          // If local had goals that cloud didn't have, push them
          const missingInCloud = localGoals.filter((lg) => !cloudGoals.some((cg) => cg.id === lg.id))
          for (const mg of missingInCloud) {
            plannerAPI.saveGoalPlan(mg).catch(() => {})
          }
        }

        // 3. Saved Plan sync
        if (cloud.saved_investment_plan) {
          const cloudPlan = normalizeSavedPlan(cloud.saved_investment_plan)
          if (cloudPlan) {
            persistSavedPlanToStorage(cloudPlan)
            set({ savedPlan: cloudPlan })
          }
        }
      }
    } catch {
      // Offline or network error - local cache remains intact
    } finally {
      set({ isSyncing: false })
    }
  },
}))
