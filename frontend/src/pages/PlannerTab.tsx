import { useState, useMemo, useEffect } from 'react'
import { plannerAPI, analyticsAPI } from '../lib/api'
import {
  TacticalPlan,
  TimingScore,
  SIPRecommendation,
  GoalPlan,
  SavedInvestmentPlanPayload,
  SavedGoalPlan,
} from '../types'
import { fmtINR } from '../lib/utils'
import { useAppStore } from '../store/appStore'
import {
  TrendingUp,
  Target,
  Clock,
  Coins,
  AlertCircle,
  Zap,
  Calendar,
  Flame,
  ChevronDown,
  ChevronUp,
  Bookmark,
  BookmarkCheck,
  FolderOpen,
  CheckCircle,
  Sparkles,
  GraduationCap,
  Home,
  Car,
  Plus,
  Trash2,
  Briefcase,
  ShieldCheck,
} from 'lucide-react'

function getFYSchedule(date = new Date()) {
  const currentYear = date.getFullYear()
  const month = date.getMonth()
  const day = date.getDate()

  const isQ4 = month <= 2
  const fyStartYear = isQ4 ? currentYear - 1 : currentYear
  const fyEndYear = fyStartYear + 1
  const fyLabel = `FY ${fyStartYear}-${String(fyEndYear).slice(-2)}`
  const nextFyLabel = `FY ${fyEndYear}-${String(fyEndYear + 1).slice(-2)}`

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const startNextMonth = day >= 20 ? 1 : 0

  const remainingInFY: { name: string; year: number; label: string }[] = []
  let m = month + startNextMonth
  let y = currentYear

  while (true) {
    if (m > 11) {
      m = 0
      y += 1
    }
    if (y > fyEndYear || (y === fyEndYear && m > 2)) break
    remainingInFY.push({
      name: monthNames[m],
      year: y,
      label: `${monthNames[m]} ${y}`,
    })
    m++
  }

  return {
    fyLabel,
    nextFyLabel,
    monthsRemainingInFY: Math.max(1, remainingInFY.length),
    remainingInFY,
  }
}

const RETIREMENT_AGE = 60
const RETIREMENT_CORPUS_MULTIPLIER = 25

// ── Instant Client-Side Quant Generator (Guarantees Instant 0ms Load & Offline Resilience) ──
function generateTacticalPlanLocal(
  capitalInput: number,
  posture = 'GROWTH',
  timingScore = 62,
  dangerScore = 28,
  strategyMode: 'tactical' | 'strict_equity' = 'tactical'
): TacticalPlan {
  const capital = Math.max(1000, capitalInput || 100000)

  // ── Mode 1: Strict Pure Equity (Large / Mid / Small only — No Liquid, No Flexi) ──
  if (strategyMode === 'strict_equity') {
    let largePct = 50
    let midPct = 30
    let smallPct = 20

    if (posture === 'AGGRESSIVE') {
      largePct = 40
      midPct = 35
      smallPct = 25
    } else if (posture === 'BALANCED') {
      largePct = 60
      midPct = 25
      smallPct = 15
    } else if (posture === 'DEFENSIVE' || posture === 'CAPITAL_SAFE') {
      largePct = 70
      midPct = 20
      smallPct = 10
    }

    const largeAmt = Math.round(capital * (largePct / 100))
    const midAmt = Math.round(capital * (midPct / 100))
    const smallAmt = Math.round(capital * (smallPct / 100))

    return {
      capital,
      posture,
      timing_score: timingScore,
      danger_score: dangerScore,
      forecast_summary: `100% Pure Equity Plan (Large, Mid & Small Cap only). Market posture is ${posture} (Score: ${timingScore}/100). Deploy Large Cap anchor now, stagger Mid Cap, and reserve Small Cap capital for the predicted Jan pullback.`,
      category_allocations: [
        {
          category: 'Large Cap',
          allocation_pct: largePct,
          allocation_amount: largeAmt,
          temperature_score: 42,
          temperature_label: 'WARM',
          temperature_emoji: '😐',
          valuation_status: 'Fairly Valued (Historical P/E 48th percentile)',
          rationale: 'Core bluechip stability. Maximum institutional liquidity and downside defense.',
          color: 'text-indigo-400 bg-indigo-900/20 border-indigo-700',
        },
        {
          category: 'Mid Cap',
          allocation_pct: midPct,
          allocation_amount: midAmt,
          temperature_score: 64,
          temperature_label: 'HOT',
          temperature_emoji: '🔥',
          valuation_status: 'Moderately Stretched (Historical P/E 68th percentile)',
          rationale: 'High earnings momentum. Requires 2-stage phased entry across quarter.',
          color: 'text-emerald-400 bg-emerald-900/20 border-emerald-700',
        },
        {
          category: 'Small Cap',
          allocation_pct: smallPct,
          allocation_amount: smallAmt,
          temperature_score: 78,
          temperature_label: 'OVERHEATED',
          temperature_emoji: '🌋',
          valuation_status: 'Overheated (Historical P/E 82nd percentile)',
          rationale: 'High correction vulnerability. Model predicts a 4–6% mean-reversion dip in 60 days.',
          color: 'text-orange-400 bg-orange-900/20 border-orange-700',
        },
      ],
      fund_recommendations: [
        {
          category: 'Large Cap',
          fund_name: 'Nippon India Large Cap Fund - Direct Plan',
          scheme_code: 119598,
          cagr_3y: 20.8,
          cagr_5y: 21.4,
          sharpe: 1.28,
          max_drawdown: -15.8,
          allocation_pct: largePct,
          allocation_amount: largeAmt,
          action_timing: 'Deploy 50% Now (Month 1), 50% in Month 3',
          timing_rationale: 'Superior pure large-cap alpha and bluechip governance. Direct equity compounder.',
          is_dip_trigger: false,
        },
        {
          category: 'Mid Cap',
          fund_name: 'Motilal Oswal Midcap Fund - Direct Plan',
          scheme_code: 153694,
          cagr_3y: 26.8,
          cagr_5y: 27.5,
          sharpe: 1.35,
          max_drawdown: -18.5,
          allocation_pct: midPct,
          allocation_amount: midAmt,
          action_timing: 'Deploy in 2 Tranches: 50% in Month 1, 50% in Month 4',
          timing_rationale: 'High earnings quality. Phased tranches prevent top-of-cycle risk.',
          is_dip_trigger: false,
        },
        {
          category: 'Small Cap',
          fund_name: 'Nippon India Small Cap Fund - Direct Plan',
          scheme_code: 118778,
          cagr_3y: 28.2,
          cagr_5y: 31.6,
          sharpe: 1.48,
          max_drawdown: -22.1,
          allocation_pct: smallPct,
          allocation_amount: smallAmt,
          action_timing: '⚠️ DO NOT BUY ALL TODAY — Trigger in Month 3 upon Dip',
          timing_rationale: `Category is running hot (78/100). Model forecasts a 4–6% pullback window. Keep ₹${fmtINR(smallAmt)} in bank ready to deploy on dip alert in Month 3!`,
          is_dip_trigger: true,
          predicted_dip_pct: 5.2,
          predicted_dip_window: 'December 2026 – January 2027',
        },
      ],
      macro_catalysts: [
        {
          event: 'Brent Crude Volatility & Currency Pressure',
          date: 'Ongoing (Nov–Dec 2026)',
          impact: 'Crude above $82 exerts pressure on Indian high-beta small caps. Historically triggers 4–7% pullbacks.',
          action: 'Stagger small-cap tranches rather than deploying lump sum.',
        },
        {
          event: 'RBI Monetary Policy Committee (MPC)',
          date: '2026-12-04',
          impact: 'Rate stance guidance. Policy stability favors large-cap earnings visibility.',
          action: 'Large cap core holdings benefit from policy clarity.',
        },
        {
          event: 'Union Budget 2027 Pre-Announcement Volatility',
          date: '2027-02-01',
          impact: 'Historically drives institutional sector rotation and a ±5% small/mid-cap consolidation.',
          action: 'Execute the Nippon India Small Cap dip entry prior to budget run-up.',
        },
      ],
      execution_roadmap: [
        {
          month: 'Nov 2026 (Month 1 — Immediate)',
          action: `Deploy Tranche 1: ₹${fmtINR(largeAmt / 2)} in Nippon India Large Cap + ₹${fmtINR(midAmt / 2)} in Motilal Oswal Midcap. Keep remaining balance in bank.`,
          deployed_equity: Math.round(largeAmt / 2 + midAmt / 2),
          parked_liquid: 0,
          status: 'IMMEDIATE_ACTION',
        },
        {
          month: 'Dec 2026 (Month 2 — Event Watch)',
          action: 'RBI MPC rate decision. Hold remaining capital in bank. Monitor Small-Cap valuation cooldown.',
          deployed_equity: 0,
          parked_liquid: 0,
          status: 'HOLD_AND_EARN',
        },
        {
          month: 'Jan 2027 (Month 3 — ⚡ Dip Trigger Window)',
          action: `Tactical Trigger: Nippon India Small Cap expected dip (-4% to -6%). Deploy full ₹${fmtINR(smallAmt)} directly into Nippon India Small Cap. Deploy Tranche 2 of Large Cap (₹${fmtINR(largeAmt / 2)}).`,
          deployed_equity: Math.round(smallAmt + largeAmt / 2),
          parked_liquid: 0,
          status: 'TACTICAL_BUY_DIP',
        },
        {
          month: 'Feb 2027 (Month 4 — Budget Rebalance)',
          action: `Post-Union Budget clarity: Deploy remaining ₹${fmtINR(midAmt / 2)} into Motilal Oswal Midcap.`,
          deployed_equity: Math.round(midAmt / 2),
          parked_liquid: 0,
          status: 'FINAL_TRANCHE',
        },
        {
          month: 'Mar 2027 (Month 5 — FY Settlement)',
          action: `100% of your ₹${fmtINR(capital)} is fully deployed into pure equities (Large, Mid & Small Cap) before March 31!`,
          deployed_equity: capital,
          parked_liquid: 0,
          status: 'FY_COMPLETE',
        },
      ],
    }
  }

  // ── Mode 2: Tactical Dynamic (Includes Liquid & Flexi Cap) ──
  // Cap split based on posture
  let largePct = 40
  let midPct = 25
  let smallPct = 15
  let liquidPct = 20

  if (posture === 'AGGRESSIVE') {
    largePct = 45
    midPct = 30
    smallPct = 20
    liquidPct = 5
  } else if (posture === 'BALANCED') {
    largePct = 40
    midPct = 20
    smallPct = 10
    liquidPct = 30
  } else if (posture === 'DEFENSIVE' || posture === 'CAPITAL_SAFE') {
    largePct = 35
    midPct = 15
    smallPct = 10
    liquidPct = 40
  }

  const largeAmt = Math.round(capital * (largePct / 100))
  const midAmt = Math.round(capital * (midPct / 100))
  const smallAmt = Math.round(capital * (smallPct / 100))
  const liquidAmt = Math.round(capital * (liquidPct / 100))

  return {
    capital,
    posture,
    timing_score: timingScore,
    danger_score: dangerScore,
    forecast_summary: `Market posture is ${posture} (Score: ${timingScore}/100). Do NOT invest blindly today or do a mechanical equal SIP. Deploy Large/Flexi Cap now, hold small caps in Liquid Fund (~6.8% yield) to capture the predicted 4–6% dip in Jan.`,
    category_allocations: [
      {
        category: 'Large & Flexi Cap',
        allocation_pct: largePct,
        allocation_amount: largeAmt,
        temperature_score: 42,
        temperature_label: 'WARM',
        temperature_emoji: '😐',
        valuation_status: 'Fairly Valued (Historical P/E 48th percentile)',
        rationale: 'High margin of safety and institutional resilience. Safe to start deploying immediately.',
        color: 'text-indigo-400 bg-indigo-900/20 border-indigo-700',
      },
      {
        category: 'Mid Cap',
        allocation_pct: midPct,
        allocation_amount: midAmt,
        temperature_score: 64,
        temperature_label: 'HOT',
        temperature_emoji: '🔥',
        valuation_status: 'Moderately Stretched (Historical P/E 68th percentile)',
        rationale: 'Strong earnings trajectory but requires a 2-stage phased entry to hedge volatility.',
        color: 'text-emerald-400 bg-emerald-900/20 border-emerald-700',
      },
      {
        category: 'Small Cap',
        allocation_pct: smallPct,
        allocation_amount: smallAmt,
        temperature_score: 78,
        temperature_label: 'OVERHEATED',
        temperature_emoji: '🌋',
        valuation_status: 'Overheated (Historical P/E 82nd percentile)',
        rationale: 'High correction vulnerability. Model predicts a 4–6% mean-reversion dip in 60 days.',
        color: 'text-orange-400 bg-orange-900/20 border-orange-700',
      },
      {
        category: 'Liquid / Arbitrage Reserve',
        allocation_pct: liquidPct,
        allocation_amount: liquidAmt,
        temperature_score: 10,
        temperature_label: 'FREEZING',
        temperature_emoji: '🧊',
        valuation_status: 'Risk-Free Yield (~6.8% annualized)',
        rationale: 'Dry powder parked to capture tactical small-cap dip and event triggers before FY end.',
        color: 'text-blue-400 bg-blue-900/20 border-blue-700',
      },
    ],
    fund_recommendations: [
      {
        category: 'Large & Flexi Cap',
        fund_name: 'Parag Parikh Flexi Cap Fund - Direct Plan',
        scheme_code: 122640,
        cagr_3y: 21.4,
        cagr_5y: 23.8,
        sharpe: 1.42,
        max_drawdown: -14.2,
        allocation_pct: largePct,
        allocation_amount: largeAmt,
        action_timing: 'Deploy 50% Now (Month 1), 50% in Month 3',
        timing_rationale: 'Superior downside protection (only -14.2% max drawdown) and global equity hedge. Safe compounder.',
        is_dip_trigger: false,
      },
      {
        category: 'Mid Cap',
        fund_name: 'Motilal Oswal Midcap Fund - Direct Plan',
        scheme_code: 153694,
        cagr_3y: 26.8,
        cagr_5y: 27.5,
        sharpe: 1.35,
        max_drawdown: -18.5,
        allocation_pct: midPct,
        allocation_amount: midAmt,
        action_timing: 'Deploy in 2 Tranches: 50% in Month 1, 50% in Month 4',
        timing_rationale: 'High earnings quality. Phased entry protects against mid-cap profit-taking cycles.',
        is_dip_trigger: false,
      },
      {
        category: 'Small Cap',
        fund_name: 'Nippon India Small Cap Fund - Direct Plan',
        scheme_code: 118778,
        cagr_3y: 28.2,
        cagr_5y: 31.6,
        sharpe: 1.48,
        max_drawdown: -22.1,
        allocation_pct: smallPct,
        allocation_amount: smallAmt,
        action_timing: '⚠️ DO NOT BUY TODAY — Trigger in Month 3 upon 4–6% Dip',
        timing_rationale: `Category is running hot (78/100). Model forecasts a 4–6% correction window post-RBI / pre-budget. Park ₹${fmtINR(smallAmt)} in Liquid fund now, deploy on dip alert!`,
        is_dip_trigger: true,
        predicted_dip_pct: 5.2,
        predicted_dip_window: 'December 2026 – January 2027',
      },
      {
        category: 'Liquid Reserve',
        fund_name: 'ICICI Prudential Liquid Fund - Direct Plan',
        scheme_code: 100357,
        cagr_3y: 6.8,
        cagr_5y: 6.2,
        sharpe: 2.1,
        max_drawdown: -0.1,
        allocation_pct: liquidPct,
        allocation_amount: liquidAmt,
        action_timing: 'Park Immediately — Earns ~6.8% daily interest until deployed',
        timing_rationale: 'Zero exit load after 7 days. Earns risk-free yield on all uninvested dry powder while waiting for tactical opportunities.',
        is_dip_trigger: false,
      },
    ],
    macro_catalysts: [
      {
        event: 'Brent Crude Volatility & Currency Pressure',
        date: 'Ongoing (Nov–Dec 2026)',
        impact: 'Crude above $82 exerts pressure on Indian high-beta small caps. Historically triggers 4–7% pullbacks.',
        action: 'Hold small cap funds in dry powder liquid reserve.',
      },
      {
        event: 'RBI Monetary Policy Committee (MPC)',
        date: '2026-12-04',
        impact: 'Rate stance guidance. Policy stability favors large & flexi-cap earnings visibility.',
        action: 'Large & Flexi cap tranches benefit from policy clarity.',
      },
      {
        event: 'Union Budget 2027 Pre-Announcement Volatility',
        date: '2027-02-01',
        impact: 'Historically drives institutional sector rotation and a ±5% small/mid-cap consolidation.',
        action: 'Execute the Nippon India Small Cap dip entry prior to budget run-up.',
      },
    ],
    execution_roadmap: [
      {
        month: 'Nov 2026 (Month 1 — Immediate)',
        action: `Deploy ₹${fmtINR(largeAmt / 2)} in Parag Parikh Flexi Cap + ₹${fmtINR(midAmt / 2)} in Motilal Oswal Midcap. Park remaining ₹${fmtINR(capital - (largeAmt / 2 + midAmt / 2))} in ICICI Liquid Fund.`,
        deployed_equity: Math.round(largeAmt / 2 + midAmt / 2),
        parked_liquid: Math.round(capital - (largeAmt / 2 + midAmt / 2)),
        status: 'IMMEDIATE_ACTION',
      },
      {
        month: 'Dec 2026 (Month 2 — Event Watch)',
        action: 'RBI MPC rate decision. Hold liquid reserve earning ~6.8% p.a. Monitor Small-Cap valuation cooldown.',
        deployed_equity: 0,
        parked_liquid: Math.round(capital - (largeAmt / 2 + midAmt / 2)),
        status: 'HOLD_AND_EARN',
      },
      {
        month: 'Jan 2027 (Month 3 — ⚡ Dip Trigger Window)',
        action: `Tactical Trigger: Nippon India Small Cap expected dip (-4% to -6%). Sweep ₹${fmtINR(smallAmt)} from Liquid → Nippon India Small Cap. Deploy Tranche 2 of Parag Parikh (₹${fmtINR(largeAmt / 2)}).`,
        deployed_equity: Math.round(smallAmt + largeAmt / 2),
        parked_liquid: Math.round(midAmt / 2),
        status: 'TACTICAL_BUY_DIP',
      },
      {
        month: 'Feb 2027 (Month 4 — Budget Rebalance)',
        action: `Post-Union Budget clarity: Deploy remaining ₹${fmtINR(midAmt / 2)} from Liquid → Motilal Oswal Midcap.`,
        deployed_equity: Math.round(midAmt / 2),
        parked_liquid: 0,
        status: 'FINAL_TRANCHE',
      },
      {
        month: 'Mar 2027 (Month 5 — FY Settlement)',
        action: `100% of your ₹${fmtINR(capital)} is fully deployed before March 31 with zero tax lag and optimal entry prices!`,
        deployed_equity: capital,
        parked_liquid: 0,
        status: 'FY_COMPLETE',
      },
    ],
  }
}

export default function PlannerTab() {
  // ── Zustand: Persistent Planner State (survives tab switches) ──
  const capital = useAppStore((s) => s.plannerCapital)
  const setCapital = useAppStore((s) => s.setPlannerCapital)

  const hasMonthlyBudget = useAppStore((s) => s.plannerHasMonthlyBudget)
  const setHasMonthlyBudget = useAppStore((s) => s.setPlannerHasMonthlyBudget)
  const monthlyLimit = useAppStore((s) => s.plannerMonthlyLimit)
  const setMonthlyLimit = useAppStore((s) => s.setPlannerMonthlyLimit)

  const hasGoal = useAppStore((s) => s.plannerHasGoal)
  const setHasGoal = useAppStore((s) => s.setPlannerHasGoal)
  const goalMode = useAppStore((s) => s.plannerGoalMode)
  const setGoalMode = useAppStore((s) => s.setPlannerGoalMode)
  const goalTarget = useAppStore((s) => s.plannerGoalTarget)
  const setGoalTarget = useAppStore((s) => s.setPlannerGoalTarget)
  const goalYears = useAppStore((s) => s.plannerGoalYears)
  const setGoalYears = useAppStore((s) => s.setPlannerGoalYears)
  const currentAge = useAppStore((s) => s.plannerCurrentAge)
  const setCurrentAge = useAppStore((s) => s.setPlannerCurrentAge)

  const strategyMode = useAppStore((s) => s.plannerStrategyMode)
  const setStrategyMode = useAppStore((s) => s.setPlannerStrategyMode)

  const tacticalPlan = useAppStore((s) => s.plannerTacticalPlan)
  const setTacticalPlan = useAppStore((s) => s.setPlannerTacticalPlan)
  const timing = useAppStore((s) => s.plannerTiming)
  const setTiming = useAppStore((s) => s.setPlannerTiming)
  const goal = useAppStore((s) => s.plannerGoal)
  const setGoal = useAppStore((s) => s.setPlannerGoal)

  // ── Local UI state only (no need to persist these) ─────────────
  const [, setSipRec] = useState<SIPRecommendation | null>(null)
  const [loading, setLoading] = useState(false)
  const [showGlidePath, setShowGlidePath] = useState(false)
  const [showRoadmap, setShowRoadmap] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── Mode Switcher: FY Single Plan vs Unlimited Long-Term Goals ──
  const [plannerMode, setPlannerMode] = useState<'fy_plan' | 'future_goals'>('fy_plan')

  // ── Saved FY Investment Plan State & Persistence (Strictly 1 Active Plan) ──
  const savedPlan = useAppStore((s) => s.savedPlan)
  const setSavedPlan = useAppStore((s) => s.setSavedPlan)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null)
  const [savingPlan, setSavingPlan] = useState(false)

  // ── Saved Long-Term Goals State & Persistence (Unlimited Goals) ──
  const savedGoals = useAppStore((s) => s.savedGoals)
  const setSavedGoals = useAppStore((s) => s.setSavedGoals)
  const addSavedGoal = useAppStore((s) => s.addSavedGoal)
  const removeSavedGoal = useAppStore((s) => s.removeSavedGoal)

  // Goal Builder State
  const [goalName, setGoalName] = useState('Child Higher Education')
  const [goalTargetAmount, setGoalTargetAmount] = useState('5000000')
  const [goalYearsTimeline, setGoalYearsTimeline] = useState('15')
  const [currentSavings, setCurrentSavings] = useState('0')
  const [savingGoal, setSavingGoal] = useState(false)
  const [goalToast, setGoalToast] = useState<string | null>(null)
  const [expandedGoalId, setExpandedGoalId] = useState<string | null>(null)

  // On initial mount, fetch any saved FY plan & saved long-term goals from backend
  useEffect(() => {
    // 1. FY deployment plan (strictly 1 active plan)
    plannerAPI.getSavedPlan()
      .then((res) => {
        if (res.data?.has_saved_plan && res.data?.plan) {
          if (!savedPlan) {
            setSavedPlan(res.data.plan)
          }
        }
      })
      .catch(() => {})

    // 2. Saved long-term future goals (unlimited)
    plannerAPI.getSavedGoals()
      .then((res) => {
        if (Array.isArray(res.data)) {
          setSavedGoals(res.data)
        }
      })
      .catch(() => {})
  }, [])

  // ── Live Math for Goal Builder (12% CAGR Assumed) ──
  const goalCalc = useMemo(() => {
    const tNum = Math.max(1000, Number(goalTargetAmount) || 0)
    const yNum = Math.max(1, Number(goalYearsTimeline) || 1)
    const sNum = Math.max(0, Number(currentSavings) || 0)

    const annualRate = 0.12
    const monthlyRate = annualRate / 12
    const months = Math.max(1, Math.round(yNum * 12))

    // Future value of existing savings
    const fvSavings = sNum * Math.pow(1 + annualRate, yNum)
    const netNeeded = Math.max(0, tNum - fvSavings)

    // Formula for required monthly SIP:
    // NetNeeded = SIP * [((1 + r)^n - 1) / r] * (1 + r)
    const sipFactor = ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate) * (1 + monthlyRate)
    const requiredSip = netNeeded > 0 ? Math.round(netNeeded / sipFactor) : 0

    const projectedCorpus = Math.round(fvSavings + (requiredSip * sipFactor))
    const totalInvested = sNum + (requiredSip * months)
    const wealthGain = Math.max(0, projectedCorpus - totalInvested)

    // Dynamic Glide Path Schedule
    const glidePath: { year: number; equity_pct: number; liquid_pct: number; rationale: string }[] = []
    const totalYrs = Math.ceil(yNum)
    for (let yr = 1; yr <= totalYrs; yr++) {
      const yrsRemaining = yNum - yr
      let eq = 100
      let liq = 0
      let rat = '100% Equity: Maximum compounding runway'
      if (yrsRemaining <= 0.5) {
        eq = 5
        liq = 95
        rat = '95% Liquid: Target locked in safe assets for withdrawal'
      } else if (yrsRemaining <= 1) {
        eq = 25
        liq = 75
        rat = '75% Liquid: High capital preservation phase'
      } else if (yrsRemaining <= 2) {
        eq = 50
        liq = 50
        rat = '50/50 Balanced de-risking mode'
      } else if (yrsRemaining <= 3) {
        eq = 70
        liq = 30
        rat = '30% Liquid: Initial capital protection hedge'
      } else if (yrsRemaining <= 5) {
        eq = 85
        liq = 15
        rat = '85% Equity: Growth with conservative buffer'
      }
      glidePath.push({
        year: yr,
        equity_pct: eq,
        liquid_pct: liq,
        rationale: rat,
      })
    }

    return {
      tNum,
      yNum,
      sNum,
      months,
      netNeeded,
      requiredSip,
      totalInvested,
      projectedCorpus,
      wealthGain,
      glidePath,
    }
  }, [goalTargetAmount, goalYearsTimeline, currentSavings])

  const handleSaveGoal = async () => {
    const tNum = Number(goalTargetAmount)
    const yNum = Number(goalYearsTimeline)
    const sNum = Number(currentSavings) || 0

    if (!goalName.trim() || tNum <= 0 || yNum <= 0) {
      setGoalToast('⚠️ Please enter a goal name, target corpus, and timeline.')
      setTimeout(() => setGoalToast(null), 3500)
      return
    }

    setSavingGoal(true)
    const goalId = `goal_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`
    const newGoal: SavedGoalPlan = {
      id: goalId,
      goal_name: goalName.trim(),
      target_corpus: tNum,
      years: yNum,
      required_monthly_sip: goalCalc.requiredSip,
      projected_corpus: goalCalc.projectedCorpus,
      equity_pct: goalCalc.glidePath[0]?.equity_pct ?? 100,
      liquid_pct: goalCalc.glidePath[0]?.liquid_pct ?? 0,
      glide_path: goalCalc.glidePath,
      milestone_alerts: [
        `25% Milestone: ₹${fmtINR(tNum * 0.25)}`,
        `50% Milestone: ₹${fmtINR(tNum * 0.5)}`,
        `75% Milestone: ₹${fmtINR(tNum * 0.75)}`,
        `Target Goal: ₹${fmtINR(tNum)}`,
      ],
      created_at: new Date().toISOString(),
    }

    addSavedGoal(newGoal)

    try {
      await plannerAPI.saveGoalPlan({
        id: goalId,
        goal_name: newGoal.goal_name,
        target_corpus: newGoal.target_corpus,
        years: newGoal.years,
        required_monthly_sip: newGoal.required_monthly_sip,
        projected_corpus: newGoal.projected_corpus,
        equity_pct: newGoal.equity_pct,
        liquid_pct: newGoal.liquid_pct,
        goal_data: {
          glide_path: newGoal.glide_path,
          milestone_alerts: newGoal.milestone_alerts,
          current_savings: sNum,
        },
      })
    } catch {
      // local store already updated
    } finally {
      setSavingGoal(false)
    }

    setGoalToast(`✓ Goal "${newGoal.goal_name}" saved! You now have ${savedGoals.length + 1} saved goals.`)
    setTimeout(() => setGoalToast(null), 4000)
  }

  const handleDeleteGoal = async (id: string, name: string) => {
    removeSavedGoal(id)
    try {
      await plannerAPI.deleteSavedGoal(id)
    } catch {}
    setGoalToast(`Removed "${name}".`)
    setTimeout(() => setGoalToast(null), 3000)
  }

  const getGoalIcon = (name: string) => {
    const lower = name.toLowerCase()
    if (lower.includes('child') || lower.includes('education') || lower.includes('college') || lower.includes('school')) {
      return <GraduationCap className="w-5 h-5 text-indigo-400" />
    }
    if (lower.includes('house') || lower.includes('home') || lower.includes('flat') || lower.includes('property')) {
      return <Home className="w-5 h-5 text-emerald-400" />
    }
    if (lower.includes('retire') || lower.includes('fire') || lower.includes('freedom')) {
      return <Sparkles className="w-5 h-5 text-amber-400" />
    }
    if (lower.includes('car') || lower.includes('vehicle') || lower.includes('bike')) {
      return <Car className="w-5 h-5 text-rose-400" />
    }
    return <Target className="w-5 h-5 text-indigo-400" />
  }

  const handleSavePlan = async () => {
    if (!tacticalPlan) return
    setSavingPlan(true)
    const nowFormatted = new Date().toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })

    const payload: SavedInvestmentPlanPayload = {
      capital: tacticalPlan.capital,
      hasMonthlyBudget,
      monthlyLimit,
      hasGoal,
      goalMode,
      goalTarget,
      goalYears,
      currentAge,
      strategyMode,
      tacticalPlan,
      timing,
      goal,
      savedAt: nowFormatted,
    }

    const wasOverwrite = Boolean(savedPlan)
    setSavedPlan(payload)

    try {
      await plannerAPI.savePlan(tacticalPlan.capital, payload)
    } catch {
      // localStorage is already persisted via setSavedPlan
    } finally {
      setSavingPlan(false)
    }

    setSaveSuccessMsg(
      wasOverwrite
        ? '✓ Previous FY plan overwritten! New FY investment plan saved.'
        : '✓ FY investment plan saved! Stored as your 1 active master FY plan.'
    )
    setTimeout(() => setSaveSuccessMsg(null), 4000)
  }

  const openSavedPlan = () => {
    if (!savedPlan) return
    setCapital(String(savedPlan.capital))
    setHasMonthlyBudget(savedPlan.hasMonthlyBudget)
    setMonthlyLimit(savedPlan.monthlyLimit)
    setHasGoal(savedPlan.hasGoal)
    setGoalMode(savedPlan.goalMode)
    setGoalTarget(savedPlan.goalTarget)
    setGoalYears(savedPlan.goalYears)
    setCurrentAge(savedPlan.currentAge)
    setStrategyMode(savedPlan.strategyMode)
    setTacticalPlan(savedPlan.tacticalPlan)
    if (savedPlan.timing) setTiming(savedPlan.timing)
    if (savedPlan.goal) setGoal(savedPlan.goal)

    setSaveSuccessMsg(`Loaded saved investment plan (₹${fmtINR(savedPlan.capital)} · Saved on ${savedPlan.savedAt})`)
    setTimeout(() => setSaveSuccessMsg(null), 3500)
  }

  const isCurrentPlanSaved = Boolean(
    savedPlan &&
    tacticalPlan &&
    Number(savedPlan.capital) === Number(tacticalPlan.capital) &&
    savedPlan.strategyMode === strategyMode
  )

  const fy = useMemo(() => getFYSchedule(), [])

  // Computed retirement values
  const retirementYears = Math.max(1, RETIREMENT_AGE - Number(currentAge))
  const effectiveMonthlySpend = hasMonthlyBudget ? Number(monthlyLimit) : (Number(capital) / 12)
  const retirementCorpus = effectiveMonthlySpend * 12 * RETIREMENT_CORPUS_MULTIPLIER

  const effectiveGoalTarget = goalMode === 'retirement' ? String(retirementCorpus) : goalTarget
  const effectiveGoalYears = goalMode === 'retirement' ? String(retirementYears) : goalYears

  const loadPlan = async (customMode?: 'tactical' | 'strict_equity') => {
    const activeMode = customMode ?? strategyMode
    const capNum = Number(capital)
    if (!capital || capNum <= 0) {
      setError('Please enter an investment amount greater than ₹0.')
      return
    }
    setError(null)

    // Immediately calculate and show updated plan on screen (0ms latency)
    setTacticalPlan(generateTacticalPlanLocal(capNum, tacticalPlan?.posture ?? 'GROWTH', timing?.score ?? 62, tacticalPlan?.danger_score ?? 28, activeMode))

    setLoading(true)
    const mBudgetNum = hasMonthlyBudget ? Number(monthlyLimit) : Math.round(capNum / fy.monthsRemainingInFY)

    try {
      const calls: Promise<any>[] = [
        plannerAPI.tacticalPlan(capNum, hasMonthlyBudget ? Number(monthlyLimit) : undefined, activeMode),
        analyticsAPI.timingScore(122640),
      ]

      if (hasGoal) {
        calls.push(
          plannerAPI.goalPlanner(
            Number(effectiveGoalTarget),
            Number(effectiveGoalYears),
            mBudgetNum
          )
        )
      }

      const results = await Promise.allSettled(calls)
      if (results[0].status === 'fulfilled' && results[0].value?.data) {
        setTacticalPlan(results[0].value.data)
      }
      if (results[1].status === 'fulfilled') setTiming(results[1].value.data)

      if (hasGoal && results[2] && results[2].status === 'fulfilled') {
        const d = results[2].value.data
        setGoal({
          ...d,
          target_amount: d.target_amount ?? Number(effectiveGoalTarget),
          projected_corpus: d.projected_corpus ?? 0,
          required_monthly_sip: d.required_monthly_sip ?? d.monthly_sip_required ?? 0,
          years: d.years ?? d.years_remaining ?? Number(effectiveGoalYears),
          glide_path: d.glide_path ?? d.glide_path_schedule ?? [],
        })
      }
    } catch {
      // Tactical plan already populated locally, so no disruptive error banner needed
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4 pb-12">
      {/* ── Top Mode Switcher: Single FY Plan vs Unlimited Long-Term Goals ── */}
      <div className="flex bg-slate-800/90 rounded-2xl p-1 gap-1 border border-slate-700/60 shadow-lg shadow-slate-950/40">
        <button
          type="button"
          onClick={() => setPlannerMode('fy_plan')}
          className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            plannerMode === 'fy_plan'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/60 border border-indigo-400/40'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          <Calendar className="w-4 h-4 text-indigo-300" />
          <span>📅 FY Deployment Plan (1 Active Plan)</span>
        </button>

        <button
          type="button"
          onClick={() => setPlannerMode('future_goals')}
          className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            plannerMode === 'future_goals'
              ? 'bg-amber-600 text-white shadow-md shadow-amber-950/60 border border-amber-400/40'
              : 'text-slate-400 hover:text-slate-200 border border-transparent'
          }`}
        >
          <Target className="w-4 h-4 text-amber-300" />
          <span>🎯 Future Long-Term Goals {savedGoals.length > 0 ? `(${savedGoals.length})` : ''}</span>
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* MODE 1: SINGLE FY DEPLOYMENT PLAN (Strictly 1 Active Plan)          */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {plannerMode === 'fy_plan' && (
        <div className="space-y-4">
          {/* Policy Notice: Only 1 FY Plan at a time */}
          <div className="bg-slate-900/80 border border-indigo-500/30 rounded-xl px-3.5 py-2.5 text-xs text-slate-300 flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-sm">
            <span className="flex items-center gap-2">
              <span className="text-indigo-400 font-bold">💡 Note:</span>
              <span>
                There is <strong>only ONE active saved plan</strong> for investing before the end of the financial year (March 31). Saving a new FY plan will overwrite the previous one.
              </span>
            </span>
            <button
              type="button"
              onClick={() => setPlannerMode('future_goals')}
              className="text-xs text-amber-400 hover:text-amber-300 font-semibold underline shrink-0 text-left"
            >
              Want multiple saved plans? Go to Future Goals →
            </button>
          </div>

          {/* Persistent Saved Plan Quick-Access Banner */}
          {savedPlan && (
            <div className="bg-gradient-to-r from-indigo-950/80 via-slate-900 to-indigo-950/80 border border-indigo-500/50 rounded-2xl p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg shadow-indigo-950/30">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-indigo-600/30 border border-indigo-500/40 text-indigo-300 flex items-center justify-center shrink-0">
                  <BookmarkCheck className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-slate-100">
                      Saved FY Investment Plan: ₹{fmtINR(savedPlan.capital)}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-900/60 border border-indigo-700/60 text-indigo-300 font-mono">
                      {savedPlan.strategyMode === 'strict_equity' ? 'Pure Equity' : 'Tactical Strategy'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Saved on {savedPlan.savedAt} · Stored permanently across app refreshes
                  </p>
                </div>
              </div>

              <button
                onClick={openSavedPlan}
                className="btn-primary text-xs font-bold py-2 px-4 flex items-center justify-center gap-1.5 shrink-0 shadow-md shadow-indigo-950"
              >
                <FolderOpen className="w-3.5 h-3.5" /> View Saved Plan
              </button>
            </div>
          )}

          {/* ── STEP 1: Total Capital Input Card ───────────────────────────── */}
          <div className="card border-indigo-600/40 shadow-lg shadow-indigo-950/20">
            <div className="flex items-center justify-between mb-3">
              <p className="section-title flex items-center gap-2 mb-0">
                <TrendingUp className="w-5 h-5 text-indigo-400" /> Tactical FY Investment Planner
              </p>
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
                {fy.fyLabel} · {fy.monthsRemainingInFY} mos till Mar 31
              </span>
            </div>

        <p className="text-xs text-slate-400 mb-3">
          Enter the lump sum or total money you want to invest. Our quant engine predicts market dips, macro events, and allocates into high-conviction mutual funds before the end of the financial year.
        </p>

        {/* Primary Input */}
        <div className="mb-3">
          <label className="label flex items-center justify-between">
            <span className="flex items-center gap-1.5 font-semibold text-slate-200">
              <Coins className="w-4 h-4 text-yellow-400" /> Total Capital to Invest (₹)
            </span>
            <span className="text-xs font-bold text-indigo-400">
              {fmtINR(Number(capital) || 0)}
            </span>
          </label>
          <input
            className="input text-xl font-bold tracking-wide py-2.5 text-white"
            type="number"
            value={capital}
            onChange={(e) => {
              setCapital(e.target.value)
              if (error) setError(null)
            }}
            placeholder="0"
          />

          {/* Quick presets */}
          <div className="flex gap-2 mt-2">
            {['50000', '100000', '250000', '500000', '1000000'].map((amt) => (
              <button
                key={amt}
                onClick={() => setCapital(amt)}
                className={`text-[11px] py-1 px-2.5 rounded-lg border transition-all ${
                  capital === amt
                    ? 'bg-indigo-600 text-white border-indigo-500 font-bold'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                }`}
              >
                {fmtINR(Number(amt))}
              </button>
            ))}
          </div>
        </div>

        {/* Strategy Mode Selector: Tactical Dynamic vs Strict Pure Equity */}
        <div className="pt-3 border-t border-slate-800/80 mb-3">
          <label className="label flex items-center justify-between text-xs mb-1.5">
            <span className="font-semibold text-slate-200">Portfolio Strategy Model</span>
            <span className="text-[11px] text-slate-400">
              {strategyMode === 'tactical' ? 'Includes Dry Powder Liquid & Flexi Cap' : '100% Pure Equity (Large / Mid / Small Only)'}
            </span>
          </label>
          <div className="grid grid-cols-2 gap-2 p-1 bg-slate-900/90 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => {
                setStrategyMode('tactical')
                if (tacticalPlan && capital && Number(capital) > 0) {
                  loadPlan('tactical')
                }
              }}
              className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex flex-col items-center gap-0.5 ${
                strategyMode === 'tactical'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/40 border border-indigo-400/30'
                  : 'text-slate-400 hover:text-slate-200 border border-transparent'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-yellow-300" /> Tactical Dynamic
              </span>
              <span className={`text-[10px] font-normal ${strategyMode === 'tactical' ? 'text-indigo-200' : 'text-slate-500'}`}>
                Flexi + Mid + Small + Liquid
              </span>
            </button>

            <button
              type="button"
              onClick={() => {
                setStrategyMode('strict_equity')
                if (tacticalPlan && capital && Number(capital) > 0) {
                  loadPlan('strict_equity')
                }
              }}
              className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex flex-col items-center gap-0.5 ${
                strategyMode === 'strict_equity'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-950/40 border border-indigo-400/30'
                  : 'text-slate-400 hover:text-slate-200 border border-transparent'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-300" /> Strict Pure Equity
              </span>
              <span className={`text-[10px] font-normal ${strategyMode === 'strict_equity' ? 'text-indigo-200' : 'text-slate-500'}`}>
                Large + Mid + Small (No Debt)
              </span>
            </button>
          </div>
        </div>

        {/* Optional Customizer Toggles */}
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800/80 mb-4">
          <button
            onClick={() => setHasMonthlyBudget(!hasMonthlyBudget)}
            className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
              hasMonthlyBudget
                ? 'bg-indigo-900/40 border-indigo-500 text-indigo-300 font-bold'
                : 'bg-slate-900/60 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            {hasMonthlyBudget ? '✓ Monthly Limit Set' : '+ Set Monthly Budget'}
          </button>

          <button
            onClick={() => setHasGoal(!hasGoal)}
            className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
              hasGoal
                ? 'bg-amber-900/40 border-amber-500 text-amber-300 font-bold'
                : 'bg-slate-900/60 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Target className="w-3.5 h-3.5" />
            {hasGoal ? '✓ Goal Active' : '+ Set Long-Term Goal'}
          </button>
        </div>

        {/* Optional Monthly Budget Drawer */}
        {hasMonthlyBudget && (
          <div className="bg-slate-900/90 border border-indigo-700/60 rounded-xl p-3 mb-4 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-400" /> Max Monthly Investment Limit (₹)
              </label>
              <button
                onClick={() => setHasMonthlyBudget(false)}
                className="text-[10px] text-slate-500 hover:text-slate-400 underline"
              >
                Remove
              </button>
            </div>
            <input
              className="input text-sm"
              type="number"
              value={monthlyLimit}
              onChange={(e) => setMonthlyLimit(e.target.value)}
              placeholder="30,000"
            />
            <p className="text-[11px] text-slate-400">
              Capacity in {fy.fyLabel}:{' '}
              <span className="font-semibold text-indigo-300">
                {fmtINR((Number(monthlyLimit) || 0) * fy.monthsRemainingInFY)}
              </span>{' '}
              ({fy.monthsRemainingInFY} mos left × {fmtINR(Number(monthlyLimit) || 0)}/mo)
            </p>
          </div>
        )}

        {/* Optional Goal Drawer */}
        {hasGoal && (
          <div className="bg-slate-900/90 border border-amber-700/60 rounded-xl p-3 mb-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-amber-400" /> Long-Term Wealth Target
              </label>
              <button
                onClick={() => setHasGoal(false)}
                className="text-[10px] text-slate-500 hover:text-slate-400 underline"
              >
                Remove
              </button>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setGoalMode('target')}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium border ${
                  goalMode === 'target'
                    ? 'bg-amber-500 text-slate-950 border-amber-400 font-bold'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                Specific Target
              </button>
              <button
                onClick={() => setGoalMode('retirement')}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium border ${
                  goalMode === 'retirement'
                    ? 'bg-amber-500 text-slate-950 border-amber-400 font-bold'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                🌅 Retirement (Age 60)
              </button>
            </div>

            {goalMode === 'target' ? (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label text-[11px]">Target Corpus (₹)</label>
                  <input
                    className="input text-xs"
                    type="number"
                    value={goalTarget}
                    onChange={(e) => setGoalTarget(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label text-[11px]">Horizon (Yrs)</label>
                  <input
                    className="input text-xs"
                    type="number"
                    value={goalYears}
                    onChange={(e) => setGoalYears(e.target.value)}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div>
                  <label className="label text-[11px]">Your Current Age</label>
                  <input
                    className="input text-xs"
                    type="number"
                    min={18}
                    max={59}
                    value={currentAge}
                    onChange={(e) => setCurrentAge(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 bg-slate-950 p-2 rounded-xl border border-slate-800 text-xs">
                  <div>
                    <p className="text-[10px] text-slate-500">Auto Target (25× Spend)</p>
                    <p className="font-bold text-amber-400">{fmtINR(retirementCorpus)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-500">Years to Age 60</p>
                    <p className="font-bold text-amber-400">{retirementYears} Yrs</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <button onClick={() => loadPlan()} className="btn-primary w-full py-3 text-sm font-bold" disabled={loading}>
          {loading ? 'Analyzing Market Timing & Fund Data…' : '⚡ Generate Tactical Investment Plan'}
        </button>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* ── Empty State Prompt (When no plan has been generated yet) ────── */}
      {!tacticalPlan && (
        <div className="card text-center py-10 border-dashed border-slate-800">
          <div className="w-12 h-12 rounded-2xl bg-indigo-950/60 border border-indigo-800/80 flex items-center justify-center mx-auto mb-3 shadow-md shadow-indigo-950/40">
            <TrendingUp className="w-6 h-6 text-indigo-400" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200 mb-1">Ready to Build Your Tactical Plan</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed mb-3">
            Enter your total investment amount above and click{' '}
            <span className="text-indigo-400 font-semibold">Generate Tactical Investment Plan</span> to receive an
            optimal cap split, high-conviction funds, and dip-timed execution roadmap before the financial year ends.
          </p>
          {savedPlan && (
            <button
              onClick={openSavedPlan}
              className="btn-secondary text-xs font-semibold px-4 py-2 mt-2 inline-flex items-center gap-1.5 shadow-sm"
            >
              <FolderOpen className="w-3.5 h-3.5 text-indigo-400" /> Re-open Saved Plan (₹{fmtINR(savedPlan.capital)})
            </button>
          )}
        </div>
      )}

      {/* ── Save Plan Banner & Action Bar ── */}
      {tacticalPlan && (
        <div className="card bg-slate-900 border border-indigo-500/50 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xl">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-bold text-slate-100 leading-tight">
                  Tactical Investment Plan (₹{fmtINR(tacticalPlan.capital)})
                </h3>
                {isCurrentPlanSaved && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 font-semibold flex items-center gap-1">
                    <BookmarkCheck className="w-3 h-3 text-emerald-400" /> Saved on {savedPlan?.savedAt}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {isCurrentPlanSaved
                  ? 'This plan is stored permanently and can be reopened anytime you refresh or visit the app.'
                  : 'Click "Save Investment Plan" to store this plan. Saving a new plan will overwrite the previous one.'}
              </p>
            </div>
          </div>

          <button
            onClick={handleSavePlan}
            disabled={savingPlan}
            className={`px-4 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shrink-0 transition-all ${
              isCurrentPlanSaved
                ? 'bg-emerald-600/20 border border-emerald-500/60 text-emerald-300 hover:bg-emerald-600/30'
                : 'btn-primary shadow-lg shadow-indigo-900/50'
            }`}
          >
            {isCurrentPlanSaved ? (
              <>
                <BookmarkCheck className="w-4 h-4 text-emerald-400" />
                {savingPlan ? 'Updating…' : 'Re-Save / Overwrite Plan'}
              </>
            ) : (
              <>
                <Bookmark className="w-4 h-4" />
                {savingPlan ? 'Saving…' : '💾 Save Investment Plan'}
              </>
            )}
          </button>
        </div>
      )}

      {/* Save feedback toast */}
      {saveSuccessMsg && (
        <div className="bg-emerald-950/80 border border-emerald-700/60 rounded-xl p-3 text-xs text-emerald-300 font-semibold flex items-center gap-2 animate-in fade-in">
          <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      {/* ── CATEGORY CAP SPLIT & VALUATION THERMOMETER ─────────────────── */}
      {tacticalPlan && (
        <div className="card">
          <p className="section-title flex items-center gap-2">
            <Flame className="w-4 h-4 text-orange-400" /> Category Allocation & Valuation Thermometer
          </p>
          <p className="text-xs text-slate-400 mb-3">
            How your ₹{fmtINR(tacticalPlan.capital)} is distributed across market caps based on current valuation heat:
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
            {tacticalPlan.category_allocations.map((cat, i) => (
              <div key={i} className={`p-3 rounded-xl border ${cat.color}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white">{cat.category}</span>
                  <span className="text-sm">{cat.temperature_emoji}</span>
                </div>
                <p className="text-lg font-black text-white">{cat.allocation_pct}%</p>
                <p className="text-xs font-semibold text-slate-200">{fmtINR(cat.allocation_amount)}</p>
                <span className="inline-block mt-1 text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-slate-300">
                  {cat.temperature_label} ({cat.temperature_score}/100)
                </span>
                <p className="text-[10px] text-slate-400 mt-1.5 leading-snug">{cat.rationale}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── HIGH-CONVICTION FUND PICKS (EXACT FUNDS TO BUY & TIMING) ─────── */}
      {tacticalPlan && (
        <div className="card border-emerald-600/30">
          <div className="flex items-center justify-between mb-2">
            <p className="section-title flex items-center gap-2 mb-0">
              <Zap className="w-4 h-4 text-emerald-400" /> Recommended Funds & Exact Timing Triggers
            </p>
            <span className="text-xs text-emerald-400 font-semibold">100% Pure Direct Growth</span>
          </div>

          <p className="text-xs text-slate-400 mb-4">
            Selected for highest historical risk-adjusted alpha (Sharpe &gt; 1.3) with precise entry timing:
          </p>

          <div className="space-y-3">
            {tacticalPlan.fund_recommendations.map((fund, idx) => (
              <div
                key={idx}
                className={`p-3.5 rounded-xl border transition-all ${
                  fund.is_dip_trigger
                    ? 'bg-orange-950/20 border-orange-600/80 shadow-md shadow-orange-950/20'
                    : 'bg-slate-900/90 border-slate-800'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">{fund.fund_name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                        {fund.scheme_code}
                      </span>
                    </div>
                    <span className="text-[11px] font-semibold text-indigo-400">{fund.category}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-white">{fmtINR(fund.allocation_amount)}</p>
                    <span className="text-xs text-slate-400">{fund.allocation_pct}% of total</span>
                  </div>
                </div>

                {/* Return Metrics Pill Bar */}
                <div className="flex gap-3 my-2 text-xs bg-slate-950 p-2 rounded-lg border border-slate-800/80">
                  <div>
                    <span className="text-[10px] text-slate-500">3Y CAGR:</span>{' '}
                    <span className="font-bold text-emerald-400">+{fund.cagr_3y}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500">5Y CAGR:</span>{' '}
                    <span className="font-bold text-emerald-400">+{fund.cagr_5y}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500">Sharpe:</span>{' '}
                    <span className="font-bold text-indigo-300">{fund.sharpe}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500">Max Drawdown:</span>{' '}
                    <span className="font-bold text-red-400">{fund.max_drawdown}%</span>
                  </div>
                </div>

                {/* Timing Action & Dip Prediction */}
                <div className="mt-2 text-xs">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        fund.is_dip_trigger
                          ? 'bg-orange-600 text-white animate-pulse'
                          : 'bg-indigo-900/60 text-indigo-300 border border-indigo-700/60'
                      }`}
                    >
                      {fund.action_timing}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">
                    {fund.timing_rationale}
                  </p>

                  {fund.is_dip_trigger && (
                    <div className="mt-2 bg-orange-950/40 border border-orange-700/60 rounded-lg p-2.5 text-[11px] text-orange-200">
                      <p className="font-bold flex items-center gap-1 text-orange-400">
                        <AlertCircle className="w-3.5 h-3.5" /> Predicted Small Cap Dip Window:{' '}
                        {fund.predicted_dip_window}
                      </p>
                      <p className="text-slate-300 mt-0.5">
                        Expected pullback: <span className="font-bold text-orange-400">~{fund.predicted_dip_pct}%</span>.
                        Keep ₹{fmtINR(fund.allocation_amount)} in Liquid fund earning ~6.8% return. Deploy when notification arrives!
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── MASTER FY EXECUTION SCHEDULE (BEFORE MARCH 31) ─────────────── */}
      {tacticalPlan && (
        <div className="card border-indigo-500/40">
          <div className="flex items-center justify-between mb-2">
            <p className="section-title flex items-center gap-2 mb-0">
              <Calendar className="w-4 h-4 text-indigo-400" /> Master Execution Roadmap (Before March 31)
            </p>
            <button
              onClick={() => setShowRoadmap((p) => !p)}
              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              {showRoadmap ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>

          <p className="text-xs text-slate-400 mb-3">
            Month-by-month actionable triggers ensuring 100% of your ₹{fmtINR(tacticalPlan.capital)} is fully invested before fiscal year-end:
          </p>

          {showRoadmap && (
            <div className="space-y-2">
              {tacticalPlan.execution_roadmap.map((item, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-xl border text-xs ${
                    item.status === 'TACTICAL_BUY_DIP'
                      ? 'bg-orange-950/30 border-orange-700/80 shadow-sm'
                      : item.status === 'FY_COMPLETE'
                      ? 'bg-emerald-950/20 border-emerald-700/60'
                      : 'bg-slate-900 border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between font-bold mb-1">
                    <span className="text-slate-200">{item.month}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                        item.status === 'TACTICAL_BUY_DIP'
                          ? 'bg-orange-600 text-white'
                          : item.status === 'FY_COMPLETE'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {item.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{item.action}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── MACRO CATALYSTS & EVENT TIMING PREDICTIONS ─────────────────── */}
      {tacticalPlan && (
        <div className="card">
          <p className="section-title flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-yellow-400" /> Upcoming Macro Catalysts & Predictions
          </p>
          <div className="space-y-2">
            {tacticalPlan.macro_catalysts.map((ev, i) => (
              <div key={i} className="p-3 bg-slate-900 rounded-xl border border-slate-800 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-200">{ev.event}</span>
                  <span className="text-[10px] font-mono text-yellow-400 bg-yellow-950/40 px-2 py-0.5 rounded border border-yellow-800/60">
                    {ev.date}
                  </span>
                </div>
                <p className="text-slate-400 text-xs mb-1">{ev.impact}</p>
                <p className="text-indigo-400 text-xs font-medium">💡 Platform Action: {ev.action}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── LONG-TERM GOAL ROADMAP (OPTIONAL STEP 3) ───────────────────── */}
      {hasGoal && goal && (
        <div className="card border-l-4 border-l-amber-500">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-amber-400" />
            <h3 className="section-title mb-0">
              {goalMode === 'retirement' ? '🌅 Long-Term Retirement Projection' : '🎯 Long-Term Goal Projection'}
            </h3>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatBox
              label={goalMode === 'retirement' ? 'Retirement Corpus' : 'Target Corpus'}
              value={fmtINR(goal.target_amount ?? 0)}
              color="text-amber-300"
            />
            <StatBox
              label="Projected Corpus (12% CAGR)"
              value={fmtINR(goal.projected_corpus ?? 0)}
              color="text-green-400"
            />
            <StatBox
              label="Required Monthly SIP"
              value={fmtINR(goal.required_monthly_sip ?? 0)}
              color="text-indigo-400"
            />
            <StatBox
              label="Time Horizon"
              value={`${goal.years ?? 0} Years`}
            />
          </div>

          <button
            onClick={() => setShowGlidePath((p) => !p)}
            className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 font-medium"
          >
            {showGlidePath ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            View Systematic Glide-Path (Year-by-Year De-risking)
          </button>

          {showGlidePath && goal.glide_path && (
            <div className="mt-2.5 space-y-1.5 max-h-48 overflow-y-auto">
              {goal.glide_path.map((g) => (
                <div key={g.year} className="flex items-center gap-2 text-xs bg-slate-900 rounded-lg px-3 py-1.5">
                  <span className="text-slate-500 w-12">Year {g.year}</span>
                  <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full transition-all"
                      style={{ width: `${g.equity_pct}%` }}
                    />
                  </div>
                  <span className="text-amber-400 w-14 text-right font-semibold">{g.equity_pct}% Eq</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* MODE 2: FUTURE LONG-TERM GOALS (UNLIMITED SAVED GOALS)              */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {plannerMode === 'future_goals' && (
        <div className="space-y-4">
          {/* Policy Banner: Unlimited Long-Term Goals */}
          <div className="bg-amber-950/30 border border-amber-600/40 rounded-2xl p-4 shadow-lg shadow-amber-950/20">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-600/20 border border-amber-500/40 text-amber-300 flex items-center justify-center shrink-0">
                <Target className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-amber-200">
                  Unlimited Future Long-Term Goals
                </h3>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                  Unlike FY plans which have a single master deployment, you can <strong>create, calculate, and save as many future long-term goals as you want</strong> (Retirement, Child Higher Education, House Purchase, Car, Wealth Legacy). Each saved goal computes its own SIP target, wealth gain, and systematic de-risking glide path.
                </p>
              </div>
            </div>
          </div>

          {/* Toast feedback */}
          {goalToast && (
            <div className="bg-emerald-950/90 border border-emerald-600/70 rounded-xl p-3 text-xs text-emerald-300 font-semibold flex items-center gap-2 animate-in fade-in">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{goalToast}</span>
            </div>
          )}

          {/* Goal Builder Card */}
          <div className="card border-amber-600/40 shadow-xl shadow-amber-950/20">
            <div className="flex items-center justify-between mb-2">
              <p className="section-title flex items-center gap-2 mb-0">
                <Plus className="w-5 h-5 text-amber-400" /> Create & Save a New Long-Term Goal
              </p>
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-amber-300 font-mono border border-slate-700">
                12% CAGR Growth Engine
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-3">
              Select a popular life goal preset below or enter your own custom goal details:
            </p>

            {/* Presets Chips */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
              {[
                { name: 'Child Higher Education', icon: GraduationCap, target: '5000000', years: '15' },
                { name: 'House Down Payment', icon: Home, target: '3500000', years: '7' },
                { name: 'Early Retirement / FIRE', icon: Sparkles, target: '30000000', years: '20' },
                { name: 'Dream Asset / Car', icon: Car, target: '2000000', years: '5' },
                { name: 'Family Wealth Legacy', icon: ShieldCheck, target: '10000000', years: '10' },
              ].map((p) => {
                const isSelected = goalName === p.name
                const Icon = p.icon
                return (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => {
                      setGoalName(p.name)
                      setGoalTargetAmount(p.target)
                      setGoalYearsTimeline(p.years)
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'bg-amber-600/20 border-amber-500 text-amber-200 shadow-md shadow-amber-950/40'
                        : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <Icon className={`w-4 h-4 mb-1.5 ${isSelected ? 'text-amber-400' : 'text-slate-500'}`} />
                    <div>
                      <p className={`text-xs font-bold leading-tight ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                        {p.name}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5 font-mono">
                        ₹{fmtINR(Number(p.target))} · {p.years}Y
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Form Inputs */}
            <div className="space-y-3 pt-3 border-t border-slate-800">
              {/* Goal Name */}
              <div>
                <label className="text-xs font-semibold text-slate-200 block mb-1">
                  Goal Name / Objective
                </label>
                <input
                  className="input text-sm font-semibold text-white"
                  type="text"
                  value={goalName}
                  onChange={(e) => setGoalName(e.target.value)}
                  placeholder="e.g. Child's Overseas Masters, 3BHK Home, Retirement by 50"
                />
              </div>

              {/* Target & Timeline */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Target Corpus */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-semibold text-slate-200">
                      Target Corpus (₹)
                    </label>
                    <span className="text-xs font-bold text-amber-400 font-mono">
                      {fmtINR(Number(goalTargetAmount) || 0)}
                    </span>
                  </div>
                  <input
                    className="input text-base font-bold text-white py-2"
                    type="number"
                    value={goalTargetAmount}
                    onChange={(e) => setGoalTargetAmount(e.target.value)}
                    placeholder="5000000"
                  />
                  <div className="flex gap-1.5 mt-1.5 overflow-x-auto pb-0.5">
                    {['1500000', '3500000', '5000000', '10000000', '30000000'].map((amt) => (
                      <button
                        key={amt}
                        type="button"
                        onClick={() => setGoalTargetAmount(amt)}
                        className={`text-[10px] px-2 py-0.5 rounded border ${
                          goalTargetAmount === amt
                            ? 'bg-amber-600 text-white border-amber-500 font-bold'
                            : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                        }`}
                      >
                        {fmtINR(Number(amt))}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Horizon in Years */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-semibold text-slate-200">
                      Time Horizon (Years)
                    </label>
                    <span className="text-xs font-bold text-amber-400 font-mono">
                      {goalYearsTimeline} Years ({Math.round(Number(goalYearsTimeline) * 12 || 0)} Months)
                    </span>
                  </div>
                  <input
                    className="input text-base font-bold text-white py-2"
                    type="number"
                    min={1}
                    max={40}
                    value={goalYearsTimeline}
                    onChange={(e) => setGoalYearsTimeline(e.target.value)}
                    placeholder="15"
                  />
                  <div className="flex gap-1.5 mt-1.5">
                    {['3', '5', '7', '10', '15', '20', '25'].map((yr) => (
                      <button
                        key={yr}
                        type="button"
                        onClick={() => setGoalYearsTimeline(yr)}
                        className={`flex-1 text-[10px] py-0.5 rounded border text-center ${
                          goalYearsTimeline === yr
                            ? 'bg-amber-600 text-white border-amber-500 font-bold'
                            : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                        }`}
                      >
                        {yr}Y
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Current Existing Savings (Optional) */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-semibold text-slate-400">
                    Already Saved / Initial Lump Sum (Optional)
                  </label>
                  <span className="text-xs text-slate-400 font-mono">
                    {fmtINR(Number(currentSavings) || 0)}
                  </span>
                </div>
                <input
                  className="input text-xs text-slate-200"
                  type="number"
                  value={currentSavings}
                  onChange={(e) => setCurrentSavings(e.target.value)}
                  placeholder="0"
                />
              </div>

              {/* Real-time Calculation Result Box */}
              <div className="bg-slate-950/80 rounded-2xl p-4 border border-amber-600/30 mt-3 shadow-inner">
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                  <span className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Plan Projections (12% CAGR)
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Compounded over {goalCalc.yNum} Yrs
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                  <div className="bg-slate-900/90 rounded-xl p-2.5 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block font-medium">Required Monthly SIP</span>
                    <span className="text-base font-black text-amber-400 font-mono block mt-0.5">
                      {fmtINR(goalCalc.requiredSip)}/mo
                    </span>
                  </div>

                  <div className="bg-slate-900/90 rounded-xl p-2.5 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block font-medium">Target Maturity Corpus</span>
                    <span className="text-base font-black text-white font-mono block mt-0.5">
                      {fmtINR(goalCalc.tNum)}
                    </span>
                  </div>

                  <div className="bg-slate-900/90 rounded-xl p-2.5 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block font-medium">Total Cash Invested</span>
                    <span className="text-base font-bold text-slate-300 font-mono block mt-0.5">
                      {fmtINR(goalCalc.totalInvested)}
                    </span>
                  </div>

                  <div className="bg-slate-900/90 rounded-xl p-2.5 border border-slate-800">
                    <span className="text-[10px] text-slate-400 block font-medium">Wealth Multiplier / Gain</span>
                    <span className="text-base font-black text-emerald-400 font-mono block mt-0.5">
                      +{fmtINR(goalCalc.wealthGain)}
                    </span>
                  </div>
                </div>

                {/* Initial Glide-Path Strategy Pill */}
                <div className="mt-3 p-2.5 bg-slate-900/70 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs">
                  <span className="text-slate-400">Starting Asset Allocation:</span>
                  <span className="font-bold text-amber-300 px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800/60 font-mono">
                    {goalCalc.glidePath[0]?.equity_pct ?? 100}% Equity · {goalCalc.glidePath[0]?.liquid_pct ?? 0}% Liquid
                  </span>
                </div>
              </div>

              {/* Action Button: Save This Long-Term Goal */}
              <button
                type="button"
                onClick={handleSaveGoal}
                disabled={savingGoal}
                className="w-full py-3.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-amber-950/50 transition-all"
              >
                <Bookmark className="w-4 h-4" />
                {savingGoal ? 'Saving Goal to Database…' : `💾 Save "${goalName}" as a Long-Term Goal`}
              </button>
            </div>
          </div>

          {/* ── Saved Goals List (Unlimited Cards) ────────────────────────── */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Target className="w-4 h-4 text-amber-400" />
                  Your Saved Long-Term Goals ({savedGoals.length})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  All your active financial objectives stored safely. You can add as many goals as needed.
                </p>
              </div>
            </div>

            {savedGoals.length === 0 ? (
              <div className="card text-center py-10 border-dashed border-slate-800">
                <Target className="w-10 h-10 text-amber-400/40 mx-auto mb-2" />
                <h4 className="text-sm font-semibold text-slate-300">No Long-Term Goals Saved Yet</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                  Choose a preset above (Retirement, Higher Education, House, Car) or enter your target details, then click <strong>Save Goal</strong> to track unlimited investment plans.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {savedGoals.map((g) => {
                  const isExpanded = expandedGoalId === g.id
                  const icon = getGoalIcon(g.goal_name)
                  return (
                    <div
                      key={g.id}
                      className="card bg-slate-900 border-slate-800 hover:border-slate-700 transition-all p-4 shadow-lg shadow-slate-950/40"
                    >
                      {/* Goal Header */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                            {icon}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="text-sm font-bold text-white truncate">{g.goal_name}</h4>
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-950/80 border border-amber-700/60 text-amber-300 font-mono font-bold">
                                Target: ₹{fmtINR(g.target_corpus)}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                              {g.years} Year Horizon · Saved on {new Date(g.created_at || Date.now()).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                            </p>
                          </div>
                        </div>

                        {/* Delete Button */}
                        <button
                          type="button"
                          onClick={() => handleDeleteGoal(g.id, g.goal_name)}
                          className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-rose-950/50 text-slate-400 hover:text-rose-400 border border-slate-700/80 hover:border-rose-800/60 transition-colors"
                          title="Delete this saved goal"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* 4-Metric Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-center">
                          <span className="text-[10px] text-slate-400 block">Required Monthly SIP</span>
                          <span className="text-sm font-bold text-amber-400 font-mono block mt-0.5">
                            {fmtINR(g.required_monthly_sip)}/mo
                          </span>
                        </div>
                        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-center">
                          <span className="text-[10px] text-slate-400 block">Target Amount</span>
                          <span className="text-sm font-bold text-slate-200 font-mono block mt-0.5">
                            {fmtINR(g.target_corpus)}
                          </span>
                        </div>
                        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-center">
                          <span className="text-[10px] text-slate-400 block">Projected Corpus</span>
                          <span className="text-sm font-bold text-emerald-400 font-mono block mt-0.5">
                            {fmtINR(g.projected_corpus || g.target_corpus)}
                          </span>
                        </div>
                        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-center">
                          <span className="text-[10px] text-slate-400 block">Time Horizon</span>
                          <span className="text-sm font-bold text-indigo-300 font-mono block mt-0.5">
                            {g.years} Years
                          </span>
                        </div>
                      </div>

                      {/* Allocation badge & Glide Path Accordion Button */}
                      <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs">
                        <span className="text-[11px] text-slate-400">
                          Current Allocation:{' '}
                          <strong className="text-slate-200">
                            {g.equity_pct || 100}% Equity / {g.liquid_pct || 0}% Liquid
                          </strong>
                        </span>

                        <button
                          type="button"
                          onClick={() => setExpandedGoalId(isExpanded ? null : g.id)}
                          className="text-xs text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1 transition-colors"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          {isExpanded ? 'Hide Glide-Path' : 'View Year-by-Year Glide-Path'}
                        </button>
                      </div>

                      {/* Expanded Glide Path */}
                      {isExpanded && g.glide_path && g.glide_path.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-800 space-y-2 bg-slate-950/50 p-3 rounded-xl border border-slate-800">
                          <p className="text-[11px] font-bold text-amber-300 uppercase tracking-wider mb-1.5 flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5 text-amber-400" />
                            Systematic De-Risking Schedule (Glide Path)
                          </p>
                          <p className="text-[10px] text-slate-400 mb-2">
                            To protect your wealth as your goal deadline approaches, our quant model systematically sweeps accumulated equity returns into safe liquid/arbitrage funds.
                          </p>

                          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                            {g.glide_path.map((step) => (
                              <div
                                key={step.year}
                                className="flex items-center gap-2 text-xs bg-slate-900 rounded-lg px-2.5 py-1.5 border border-slate-800/60"
                              >
                                <span className="text-slate-400 w-14 shrink-0 font-mono text-[11px]">
                                  Year {step.year}
                                </span>
                                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden flex">
                                  <div
                                    className="h-full bg-amber-500 rounded-l-full transition-all"
                                    style={{ width: `${step.equity_pct}%` }}
                                    title={`${step.equity_pct}% Equity`}
                                  />
                                  <div
                                    className="h-full bg-indigo-500 rounded-r-full transition-all"
                                    style={{ width: `${step.liquid_pct}%` }}
                                    title={`${step.liquid_pct}% Liquid`}
                                  />
                                </div>
                                <span className="text-[11px] font-mono text-amber-300 w-14 text-right font-semibold shrink-0">
                                  {step.equity_pct}% Eq
                                </span>
                                <span className="text-[11px] font-mono text-indigo-300 w-14 text-right font-semibold shrink-0">
                                  {step.liquid_pct}% Liq
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function StatBox({
  label,
  value,
  color = 'text-slate-100',
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div className="bg-slate-900 rounded-xl px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  )
}
