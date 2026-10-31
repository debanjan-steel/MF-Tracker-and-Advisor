import { useEffect, useState, useMemo } from 'react'
import { plannerAPI, analyticsAPI } from '../lib/api'
import { TacticalPlan, TimingScore, SIPRecommendation, GoalPlan } from '../types'
import { fmtINR, postureColor } from '../lib/utils'
import TimingGauge from '../components/TimingGauge'
import StressTestCard from '../components/StressTestCard'
import {
  TrendingUp,
  Target,
  Clock,
  Coins,
  AlertCircle,
  ShieldCheck,
  Sparkles,
  Zap,
  CheckCircle2,
  Calendar,
  Flame,
  Snowflake,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

const STRESS_SCENARIOS = [
  { key: 'covid_crash', label: 'COVID Crash (2020)' },
  { key: 'gfc_2008', label: 'GFC (2008)' },
  { key: 'crude_spike', label: 'Crude Oil Spike' },
  { key: 'fed_hike_cycle', label: 'Fed Rate Hike Cycle' },
  { key: 'rupee_collapse', label: 'Rupee Collapse' },
  { key: 'india_election', label: 'India Election Shock' },
]

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

export default function PlannerTab() {
  // ── Step 1: Total Capital ─────────────────────────
  const [capital, setCapital] = useState<string>('100000')

  // ── Step 2: Monthly Budget Limit Option ───────────
  const [hasMonthlyBudget, setHasMonthlyBudget] = useState(false)
  const [monthlyLimit, setMonthlyLimit] = useState<string>('30000')

  // ── Step 3: Long-Term Goal / Horizon Option ───────
  const [hasGoal, setHasGoal] = useState(false)
  const [goalMode, setGoalMode] = useState<'target' | 'retirement'>('target')
  const [goalTarget, setGoalTarget] = useState<string>('10000000')
  const [goalYears, setGoalYears] = useState<string>('10')
  const [currentAge, setCurrentAge] = useState<string>('30')

  // ── Tactical Plan & Analytics States ──────────────
  const [tacticalPlan, setTacticalPlan] = useState<TacticalPlan | null>(null)
  const [timing, setTiming] = useState<TimingScore | null>(null)
  const [, setSipRec] = useState<SIPRecommendation | null>(null)
  const [goal, setGoal] = useState<GoalPlan | null>(null)
  const [stressScenario, setStressScenario] = useState('covid_crash')
  const [stressResult, setStressResult] = useState<any>(null)

  const [loading, setLoading] = useState(false)
  const [showGlidePath, setShowGlidePath] = useState(false)
  const [showRoadmap, setShowRoadmap] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fy = useMemo(() => getFYSchedule(), [])

  // Computed retirement values
  const retirementYears = Math.max(1, RETIREMENT_AGE - Number(currentAge))
  const effectiveMonthlySpend = hasMonthlyBudget ? Number(monthlyLimit) : (Number(capital) / 12)
  const retirementCorpus = effectiveMonthlySpend * 12 * RETIREMENT_CORPUS_MULTIPLIER

  const effectiveGoalTarget = goalMode === 'retirement' ? String(retirementCorpus) : goalTarget
  const effectiveGoalYears = goalMode === 'retirement' ? String(retirementYears) : goalYears

  const loadPlan = async () => {
    setLoading(true)
    setError(null)
    const capNum = Number(capital) || 100000
    const mBudgetNum = hasMonthlyBudget ? Number(monthlyLimit) : Math.round(capNum / fy.monthsRemainingInFY)

    try {
      const calls: Promise<any>[] = [
        plannerAPI.tacticalPlan(capNum, hasMonthlyBudget ? Number(monthlyLimit) : undefined),
        analyticsAPI.timingScore(122640),
        analyticsAPI.stressTest(stressScenario, capNum),
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
      if (results[0].status === 'fulfilled') setTacticalPlan(results[0].value.data)
      if (results[1].status === 'fulfilled') setTiming(results[1].value.data)
      if (results[2].status === 'fulfilled') setStressResult(results[2].value.data)

      if (hasGoal && results[3] && results[3].status === 'fulfilled') {
        const d = results[3].value.data
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
      setError('Could not load plan. Please check if the backend service is running.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPlan()
  }, [])

  return (
    <div className="space-y-4 pb-12">
      {/* ── STEP 1: Total Capital Input Card ───────────────────────────── */}
      <div className="card border-indigo-600/40 shadow-lg shadow-indigo-950/20">
        <div className="flex items-center justify-between mb-3">
          <p className="section-title flex items-center gap-2 mb-0">
            <TrendingUp className="w-5 h-5 text-indigo-400" /> Tactical Investment Planner
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
            onChange={(e) => setCapital(e.target.value)}
            placeholder="1,00,000"
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

        {/* Optional Customizer Toggles */}
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800/80 mb-4">
          <button
            onClick={() => setHasMonthlyBudget((p) => !p)}
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
            onClick={() => setHasGoal((p) => !p)}
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

        <button onClick={loadPlan} className="btn-primary w-full py-3 text-sm font-bold" disabled={loading}>
          {loading ? 'Analyzing Market Timing & Fund Data…' : '⚡ Generate Tactical Investment Plan'}
        </button>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* ── TACTICAL VERDICT & MARKET POSTURE ───────────────────────────── */}
      {tacticalPlan && (
        <div className="card border-l-4 border-l-indigo-500 bg-gradient-to-br from-slate-900 to-indigo-950/20">
          <div className="flex items-start justify-between mb-2">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Market Timing Verdict
              </span>
              <h2 className="text-lg font-bold text-white mt-0.5">
                Tactical Market Posture: {tacticalPlan.posture}
              </h2>
            </div>
            <span className={`badge text-xs font-bold px-3 py-1 rounded-xl ${postureColor(tacticalPlan.posture)}`}>
              {tacticalPlan.posture}
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            {tacticalPlan.forecast_summary}
          </p>

          <div className="grid grid-cols-2 gap-3 mt-3">
            <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800 flex flex-col items-center">
              <p className="text-[11px] text-slate-400 mb-1 font-semibold">Market Timing Gauge</p>
              {timing && <TimingGauge score={timing.score} signal={timing.signal} />}
            </div>
            <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800 flex flex-col justify-between">
              <div>
                <p className="text-[11px] text-slate-400 font-semibold mb-1">Macro Risk Exposure</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-amber-400">{tacticalPlan.danger_score.toFixed(0)}%</span>
                  <span className="text-xs text-slate-400">Downturn Risk</span>
                </div>
              </div>
              <div className="mt-2 text-[10px] text-slate-400 leading-tight">
                Crude volatility & upcoming RBI/Budget catalysts factored in.
              </div>
            </div>
          </div>
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

      {/* ── STRATEGY COMPARISON: WHY THIS OUTPERFORMS BLIND SIP / LUMP SUM ── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" /> Strategy Comparison
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
          <div className="p-3 bg-slate-900 rounded-xl border border-red-900/40">
            <p className="font-bold text-red-400 mb-1">❌ Blind Lump Sum</p>
            <p className="text-slate-400 mb-2">Deploying ₹1,00,000 all at once today.</p>
            <ul className="text-slate-500 space-y-1 text-[11px]">
              <li>• Buys overheated small-caps at peak valuation</li>
              <li>• Suffers severe drawdowns if crude shocks trigger</li>
              <li>• Zero dry powder for dip opportunities</li>
            </ul>
          </div>

          <div className="p-3 bg-slate-900 rounded-xl border border-yellow-900/40">
            <p className="font-bold text-yellow-400 mb-1">⚠️ Mechanical Equal SIP</p>
            <p className="text-slate-400 mb-2">Blind ₹20,000/mo without timing.</p>
            <ul className="text-slate-500 space-y-1 text-[11px]">
              <li>• Leaves ₹80,000 idle in 3% bank savings account</li>
              <li>• No tactical overweight on cheap categories</li>
              <li>• Ignores predictable macro dip triggers</li>
            </ul>
          </div>

          <div className="p-3 bg-emerald-950/30 rounded-xl border border-emerald-600/80 shadow-sm">
            <p className="font-bold text-emerald-400 mb-1">✅ Antigravity Tactical Plan</p>
            <p className="text-slate-300 mb-2">Market timing + high-conviction funds.</p>
            <ul className="text-slate-200 space-y-1 text-[11px]">
              <li>• Earns ~6.8% risk-free yield on idle liquid stash</li>
              <li>• Captures Nippon India Small Cap at a 4–6% discount</li>
              <li>• 100% fully deployed before March 31 with zero tax lag</li>
            </ul>
          </div>
        </div>
      </div>

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

      {/* ── HISTORICAL STRESS TEST SIMULATOR ───────────────────────────── */}
      <div className="card">
        <p className="section-title">Historical Shock Simulator</p>
        <p className="text-xs text-slate-400 mb-3">
          Simulate how your ₹{fmtINR(Number(capital) || 100000)} portfolio behaves under past market crashes:
        </p>
        <select
          className="input mb-3"
          value={stressScenario}
          onChange={(e) => setStressScenario(e.target.value)}
        >
          {STRESS_SCENARIOS.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button
          onClick={() =>
            analyticsAPI
              .stressTest(stressScenario, Number(capital) || 100000)
              .then((r) => setStressResult(r.data))
          }
          className="btn-secondary w-full mb-3"
        >
          Run Shock Simulation
        </button>
        {stressResult && <StressTestCard result={stressResult} />}
      </div>
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
