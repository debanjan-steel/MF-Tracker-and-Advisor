import { create } from 'zustand'
import { TacticalPlan, TimingScore, GoalPlan } from '../types'

type Tab = 'planner' | 'portfolio' | 'explorer' | 'alerts' | 'settings'

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

  // Generated results
  plannerTacticalPlan: TacticalPlan | null
  setPlannerTacticalPlan: (v: TacticalPlan | null) => void
  plannerTiming: TimingScore | null
  setPlannerTiming: (v: TimingScore | null) => void
  plannerGoal: GoalPlan | null
  setPlannerGoal: (v: GoalPlan | null) => void
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

  plannerTacticalPlan: null,
  setPlannerTacticalPlan: (v) => set({ plannerTacticalPlan: v }),
  plannerTiming: null,
  setPlannerTiming: (v) => set({ plannerTiming: v }),
  plannerGoal: null,
  setPlannerGoal: (v) => set({ plannerGoal: v }),
}))
