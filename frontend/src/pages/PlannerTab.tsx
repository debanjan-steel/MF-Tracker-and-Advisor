import { useEffect, useState, useMemo } from 'react'
import { plannerAPI, analyticsAPI } from '../lib/api'
import { AllocationAdvice, MacroDanger, TimingScore, SIPRecommendation, GoalPlan } from '../types'
import { fmtINR, postureColor, ordinal } from '../lib/utils'
import TimingGauge from '../components/TimingGauge'
import MacroBar from '../components/MacroBar'
import StressTestCard from '../components/StressTestCard'
import {
  TrendingUp,
  Calendar,
  ChevronDown,
  ChevronUp,
  Target,
  Clock,
  Coins,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

const STRESS_SCENARIOS = [
  { key: 'covid_crash', label: 'COVID Crash (2020)' },
  { key: 'gfc_2008', label: 'GFC (2008)' },
  { key: 'crude_spike', label: 'Crude Oil Spike' },
  { key: 'fed_hike_cycle', label: 'Fed Rate Hike Cycle' },
  { key: 'rupee_collapse', label: 'Rupee Collapse' },
  { key: 'india_election', label: 'India Election Shock' },
]

// ── Financial Year Helper (Indian FY: April 1 – March 31) ───────────────────
function getFYSchedule(date = new Date()) {
  const currentYear = date.getFullYear()
  const month = date.getMonth() // 0 = Jan, ..., 9 = Oct, 11 = Dec
  const day = date.getDate()

  // In India: FY starts April 1, ends March 31
  const isQ4 = month <= 2 // Jan, Feb, Mar
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

  // Next FY first 12 months for spillover
  const nextFYMonths: { name: string; year: number; label: string }[] = []
  let nm = 3 // April
  let ny = fyEndYear
  for (let i = 0; i < 12; i++) {
    nextFYMonths.push({
      name: monthNames[nm],
      year: ny,
      label: `${monthNames[nm]} ${ny}`,
    })
    nm++
    if (nm > 11) {
      nm = 0
      ny++
    }
  }

  return {
    fyLabel,
    nextFyLabel,
    monthsRemainingInFY: Math.max(1, remainingInFY.length),
    remainingInFY,
    nextFYMonths,
  }
}

const RETIREMENT_AGE = 60
const RETIREMENT_CORPUS_MULTIPLIER = 25 // 25× annual spend (4% safe withdrawal rule)

export default function PlannerTab() {
  // ── Step 1: Total Capital ─────────────────────────
  const [capital, setCapital] = useState<string>('1000000')

  // ── Step 2: Monthly Budget Limit Option ───────────
  const [hasMonthlyBudget, setHasMonthlyBudget] = useState(false)
  const [monthlyLimit, setMonthlyLimit] = useState<string>('150000')

  // ── Step 3: Long-Term Goal / Horizon Option ───────
  const [hasGoal, setHasGoal] = useState(false)
  const [goalMode, setGoalMode] = useState<'target' | 'retirement'>('target')
  const [goalTarget, setGoalTarget] = useState<string>('10000000')
  const [goalYears, setGoalYears] = useState<string>('10')
  const [currentAge, setCurrentAge] = useState<string>('30')

  // ── Market Signals & Strategy States ──────────────
  const [schemeCode] = useState<string>('122640')
  const [stressScenario, setStressScenario] = useState('covid_crash')

  const [advice, setAdvice] = useState<AllocationAdvice | null>(null)
  const [macro, setMacro] = useState<MacroDanger | null>(null)
  const [timing, setTiming] = useState<TimingScore | null>(null)
  const [sipRec, setSipRec] = useState<SIPRecommendation | null>(null)
  const [goal, setGoal] = useState<GoalPlan | null>(null)
  const [stressResult, setStressResult] = useState<any>(null)

  const [loading, setLoading] = useState(false)
  const [showGlidePath, setShowGlidePath] = useState(false)
  const [showSchedule, setShowSchedule] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fy = useMemo(() => getFYSchedule(), [])

  // Computed values for retirement
  const retirementYears = Math.max(1, RETIREMENT_AGE - Number(currentAge))
  const effectiveMonthlySpend = hasMonthlyBudget ? Number(monthlyLimit) : (Number(capital) / 24)
  const retirementCorpus = effectiveMonthlySpend * 12 * RETIREMENT_CORPUS_MULTIPLIER

  const effectiveGoalTarget = goalMode === 'retirement' ? String(retirementCorpus) : goalTarget
  const effectiveGoalYears = goalMode === 'retirement' ? String(retirementYears) : goalYears

  // Load macro + timing on mount
  useEffect(() => {
    analyticsAPI.macroDanger().then((r) => setMacro(r.data)).catch(() => {})
    analyticsAPI.timingScore(Number(schemeCode)).then((r) => setTiming(r.data)).catch(() => {})
  }, [schemeCode])

  const loadPlan = async () => {
    setLoading(true)
    setError(null)
    const capNum = Number(capital) || 0
    const mBudgetNum = hasMonthlyBudget ? Number(monthlyLimit) : Math.round(capNum / fy.monthsRemainingInFY)

    try {
      const calls: Promise<any>[] = [
        plannerAPI.allocationAdvice(capNum),
        plannerAPI.sipRecommendation(mBudgetNum, Number(schemeCode)),
        analyticsAPI.stressTest(stressScenario, 500000),
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
      if (results[0].status === 'fulfilled') setAdvice(results[0].value.data)
      if (results[1].status === 'fulfilled') setSipRec(results[1].value.data)
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
  }, [hasMonthlyBudget, hasGoal, goalMode])

  // ── Strategy Calculation for FY Deployment ───────────────────────────────
  const strategyDetails = useMemo(() => {
    const totalCap = Number(capital) || 0
    const monthsRemaining = fy.monthsRemainingInFY
    const posture = advice?.posture || 'GROWTH'

    // Scenario without monthly budget limit:
    if (!hasMonthlyBudget) {
      if (posture === 'AGGRESSIVE' || monthsRemaining <= 1) {
        return {
          type: 'LUMP_SUM',
          title: 'One-Time Lump Sum Deployment',
          badge: '🚀 Upfront Deployment',
          summary: `Deploy entire ₹${fmtINR(totalCap)} immediately before March 31 (${fy.fyLabel}).`,
          description:
            'Market timing and valuations are in a deeply attractive zone. Deploying 100% upfront maximizes equity compounding before fiscal year-end.',
          staggerMonths: 1,
          schedule: [
            {
              month: fy.remainingInFY[0]?.label || 'Immediate',
              amount: totalCap,
              fy: fy.fyLabel,
              note: '100% Lump Sum into diversified equity funds',
              equityPct: 100,
              liquidPct: 0,
            },
          ],
        }
      }

      if (posture === 'DEFENSIVE' || posture === 'CAPITAL_SAFE') {
        // 2-3 month gap tranches with liquid buffer
        const trancheCount = Math.min(3, Math.max(2, Math.ceil(monthsRemaining / 2)))
        const perTranche = Math.round(totalCap / trancheCount)
        const schedule = []

        for (let i = 0; i < trancheCount; i++) {
          const monthIndex = Math.min(i * 2, monthsRemaining - 1)
          schedule.push({
            month: fy.remainingInFY[monthIndex]?.label || `Month ${i * 2 + 1}`,
            amount: i === trancheCount - 1 ? totalCap - perTranche * (trancheCount - 1) : perTranche,
            fy: fy.fyLabel,
            note: i === 0 ? 'Tranche 1 (Immediate)' : `Tranche ${i + 1} (2-month gap)`,
            equityPct: 70,
            liquidPct: 30,
          })
        }

        return {
          type: 'SPACED_GAP',
          title: 'Spaced 2-Month Tranches + Liquid Park',
          badge: '🛡️ Phased De-Risking',
          summary: `Deploy ₹${fmtINR(totalCap)} in ${trancheCount} tranches spaced 2 months apart before March 31.`,
          description:
            'Elevated macro risk or volatility detected. Spacing deployments protects your entry price while uninvested capital earns ~6.8% in a Liquid / Arbitrage fund.',
          staggerMonths: trancheCount,
          schedule,
        }
      }

      // Default: GROWTH or BALANCED → Monthly systematic tranches before March 31
      const perMonth = Math.round(totalCap / monthsRemaining)
      const schedule = fy.remainingInFY.map((m, idx) => ({
        month: m.label,
        amount: idx === monthsRemaining - 1 ? totalCap - perMonth * (monthsRemaining - 1) : perMonth,
        fy: fy.fyLabel,
        note: `Systematic Tranche ${idx + 1} of ${monthsRemaining}`,
        equityPct: 90,
        liquidPct: 10,
      }))

      return {
        type: 'SYSTEMATIC_MONTHLY',
        title: 'Systematic Monthly Tranches (SIP till FY End)',
        badge: '📈 Monthly Tranches',
        summary: `Deploy ₹${fmtINR(totalCap)} evenly across ${monthsRemaining} monthly tranches before March 31 (${fy.fyLabel}).`,
        description: `Evenly averages your purchase cost across the remaining ${monthsRemaining} months of this financial year with zero timing anxiety.`,
        staggerMonths: monthsRemaining,
        schedule,
      }
    }

    // ── When Monthly Budget Limit is Enabled ──────────────────────────────
    const limit = Number(monthlyLimit) || 0
    const maxDeployableThisFY = limit * monthsRemaining
    const canCompleteThisFY = totalCap <= maxDeployableThisFY

    if (canCompleteThisFY) {
      const monthsNeeded = Math.max(1, Math.ceil(totalCap / limit))
      const perMonth = Math.round(totalCap / monthsNeeded)
      const schedule = fy.remainingInFY.slice(0, monthsNeeded).map((m, idx) => ({
        month: m.label,
        amount: idx === monthsNeeded - 1 ? totalCap - perMonth * (monthsNeeded - 1) : perMonth,
        fy: fy.fyLabel,
        note: `Budget Tranche ${idx + 1} of ${monthsNeeded}`,
        equityPct: 90,
        liquidPct: 10,
      }))

      return {
        type: 'BUDGET_FITS_FY',
        title: 'Full Deployment Within Current FY',
        badge: '✅ Fits in Current FY',
        summary: `Deploy your full ₹${fmtINR(totalCap)} across ${monthsNeeded} month(s) before March 31 (${fy.fyLabel}).`,
        description: `Your monthly limit of ₹${fmtINR(limit)} is sufficient to comfortably invest all available capital before the end of the financial year.`,
        canCompleteThisFY: true,
        deployedThisFY: totalCap,
        spillover: 0,
        schedule,
      }
    }

    // Budget exceeded → Capital spills over to Next FY
    const deployedThisFY = maxDeployableThisFY
    const spillover = totalCap - deployedThisFY
    const monthsNextFY = Math.ceil(spillover / limit)

    const thisFYSchedule = fy.remainingInFY.map((m, idx) => ({
      month: m.label,
      amount: limit,
      fy: fy.fyLabel,
      note: `This FY Installment ${idx + 1}/${monthsRemaining}`,
      equityPct: 90,
      liquidPct: 10,
    }))

    let remainingSpill = spillover
    const nextFYSchedule = fy.nextFYMonths.slice(0, monthsNextFY).map((m, idx) => {
      const amt = idx === monthsNextFY - 1 ? remainingSpill : limit
      remainingSpill -= amt
      return {
        month: m.label,
        amount: amt,
        fy: fy.nextFyLabel,
        note: `Next FY Rollover Installment ${idx + 1}/${monthsNextFY}`,
        equityPct: 90,
        liquidPct: 10,
      }
    })

    return {
      type: 'BUDGET_SPILLOVER',
      title: 'Phased Multi-FY Capital Rollover',
      badge: '⚠️ Spills to Next FY',
      summary: `Invest ₹${fmtINR(deployedThisFY)} in ${fy.fyLabel} (till March 31). Roll over remaining ₹${fmtINR(spillover)} into ${fy.nextFyLabel}.`,
      description: `At your budget limit of ₹${fmtINR(limit)}/month, you can invest ₹${fmtINR(deployedThisFY)} before March 31. The remaining ₹${fmtINR(spillover)} pushes smoothly into next financial year over ${monthsNextFY} months.`,
      canCompleteThisFY: false,
      deployedThisFY,
      spillover,
      monthsNextFY,
      schedule: [...thisFYSchedule, ...nextFYSchedule],
    }
  }, [capital, hasMonthlyBudget, monthlyLimit, advice?.posture, fy])

  return (
    <div className="space-y-4 pb-10">
      {/* ── STEP 1: Core Capital Input & FY Strategy Card ──────────────── */}
      <div className="card border-indigo-600/30">
        <div className="flex items-center justify-between mb-3">
          <p className="section-title flex items-center gap-2 mb-0">
            <TrendingUp className="w-5 h-5 text-indigo-400" /> Investment Planner
          </p>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
            {fy.fyLabel} · {fy.monthsRemainingInFY} mos till Mar 31
          </span>
        </div>

        <p className="text-xs text-slate-400 mb-3">
          Enter the total capital you want to invest. We will design the optimal strategy to deploy it before the end of the financial year.
        </p>

        {/* Primary Input: Total Capital */}
        <div className="mb-4">
          <label className="label flex items-center gap-1.5">
            <Coins className="w-3.5 h-3.5 text-yellow-400" /> Total Capital to Invest (₹)
          </label>
          <input
            className="input text-lg font-bold tracking-wide"
            type="number"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            placeholder="10,00,000"
          />
          <p className="text-xs text-slate-500 mt-1">
            Amount: <span className="font-semibold text-slate-300">{fmtINR(Number(capital) || 0)}</span>
          </p>
        </div>

        {/* ── Optional Feature Toggles ────────────────────────────── */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800 mb-4">
          <button
            onClick={() => setHasMonthlyBudget((p) => !p)}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
              hasMonthlyBudget
                ? 'bg-indigo-900/40 border-indigo-500 text-indigo-300 shadow-sm shadow-indigo-950'
                : 'bg-slate-900/60 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            {hasMonthlyBudget ? '✓ Monthly Budget Set' : '+ Set Monthly Budget'}
          </button>

          <button
            onClick={() => setHasGoal((p) => !p)}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-medium transition-all ${
              hasGoal
                ? 'bg-amber-900/40 border-amber-500 text-amber-300 shadow-sm shadow-amber-950'
                : 'bg-slate-900/60 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Target className="w-3.5 h-3.5" />
            {hasGoal ? '✓ Goal Active' : '+ Set Target Goal'}
          </button>
        </div>

        {/* ── STEP 2 (Conditional Drawer): Monthly Budget Limit ─────── */}
        {hasMonthlyBudget && (
          <div className="bg-slate-900/80 border border-indigo-700/50 rounded-2xl p-3 mb-4 space-y-2 animate-in fade-in">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-400" /> Max Monthly Investment Limit (₹)
              </label>
              <button
                onClick={() => setHasMonthlyBudget(false)}
                className="text-[10px] text-slate-500 hover:text-slate-400 underline"
              >
                Remove Limit
              </button>
            </div>
            <input
              className="input text-sm"
              type="number"
              value={monthlyLimit}
              onChange={(e) => setMonthlyLimit(e.target.value)}
              placeholder="1,50,000"
            />
            <p className="text-[11px] text-slate-400">
              Capacity in {fy.fyLabel}:{' '}
              <span className="font-semibold text-indigo-300">
                {fmtINR((Number(monthlyLimit) || 0) * fy.monthsRemainingInFY)}
              </span>{' '}
              ({fy.monthsRemainingInFY} months left × {fmtINR(Number(monthlyLimit) || 0)}/mo)
            </p>
          </div>
        )}

        {/* ── STEP 3 (Conditional Drawer): Long-Term Goal / Retirement */}
        {hasGoal && (
          <div className="bg-slate-900/80 border border-amber-700/50 rounded-2xl p-3 mb-4 space-y-3 animate-in fade-in">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-amber-400" /> Long-Term Wealth Goal
              </label>
              <button
                onClick={() => setHasGoal(false)}
                className="text-[10px] text-slate-500 hover:text-slate-400 underline"
              >
                Remove Goal
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
                  <label className="label text-[11px]">Goal Corpus (₹)</label>
                  <input
                    className="input text-xs"
                    type="number"
                    value={goalTarget}
                    onChange={(e) => setGoalTarget(e.target.value)}
                    placeholder="1,00,00,000"
                  />
                </div>
                <div>
                  <label className="label text-[11px]">Horizon (Years)</label>
                  <input
                    className="input text-xs"
                    type="number"
                    value={goalYears}
                    onChange={(e) => setGoalYears(e.target.value)}
                    placeholder="10"
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

        {/* Generate / Recalculate Button */}
        <button onClick={loadPlan} className="btn-primary w-full" disabled={loading}>
          {loading ? 'Computing Strategy…' : '⚡ Generate Investment Strategy'}
        </button>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* ── STRATEGY VERDICT CARD (FY-End Focus) ───────────────────────── */}
      <div className="card border-l-4 border-l-indigo-500">
        <div className="flex items-start justify-between mb-2">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Recommended FY Strategy
            </span>
            <h3 className="text-base font-bold text-white mt-0.5">{strategyDetails.title}</h3>
          </div>
          <span className="badge bg-indigo-900/60 text-indigo-300 border border-indigo-700/60 text-xs font-semibold px-2.5 py-0.5 rounded-lg">
            {strategyDetails.badge}
          </span>
        </div>

        <p className="text-xs text-slate-300 mb-3">{strategyDetails.summary}</p>
        <p className="text-xs text-slate-400 bg-slate-900/80 rounded-xl p-3 border border-slate-800 leading-relaxed">
          {strategyDetails.description}
        </p>

        {/* ── Spillover Alert / Liquid Stash Recommendation ──────────── */}
        {hasMonthlyBudget && (strategyDetails as any).spillover > 0 && (
          <div className="mt-3 bg-amber-950/30 border border-amber-800/60 rounded-xl p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-amber-400 text-xs font-bold">
              <AlertCircle className="w-4 h-4" />
              <span>Capital Rollover: ₹{fmtINR((strategyDetails as any).spillover)} pushes into {fy.nextFyLabel}</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              💡 <span className="font-semibold text-amber-200">Recommended Liquid Stash Strategy:</span> Do not leave this ₹{fmtINR((strategyDetails as any).spillover)} idle in your bank savings account.
              Park it in a low-risk <span className="text-amber-300 font-semibold">Liquid / Arbitrage Fund</span> today. It will earn ~6.8% annualized risk-free return while waiting to be systematically deployed next fiscal year!
            </p>
          </div>
        )}

        {/* ── Deployment Schedule Table ───────────────────────────────── */}
        <div className="mt-4 pt-3 border-t border-slate-800">
          <button
            onClick={() => setShowSchedule((p) => !p)}
            className="flex items-center justify-between w-full text-xs font-semibold text-slate-300 hover:text-white"
          >
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-indigo-400" />
              Detailed Deployment Schedule ({strategyDetails.schedule.length} Tranches)
            </span>
            {showSchedule ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {showSchedule && (
            <div className="mt-2.5 space-y-1.5 max-h-64 overflow-y-auto pr-1">
              {strategyDetails.schedule.map((item, idx) => (
                <div
                  key={idx}
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs ${
                    item.fy === fy.fyLabel
                      ? 'bg-slate-900/80 border-slate-800'
                      : 'bg-amber-950/20 border-amber-900/40'
                  }`}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-200">{item.month}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded ${
                          item.fy === fy.fyLabel
                            ? 'bg-slate-800 text-slate-400'
                            : 'bg-amber-900/60 text-amber-300'
                        }`}
                      >
                        {item.fy}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500 mt-0.5">{item.note}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-slate-100">{fmtINR(item.amount)}</p>
                    <p className="text-[10px] text-indigo-400">{item.equityPct}% Equity</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── STEP 3 RESULT: Long-Term Goal / Glide Path Card ───────────── */}
      {hasGoal && goal && (
        <div className="card border-l-4 border-l-amber-500">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-amber-400" />
            <h3 className="section-title mb-0">
              {goalMode === 'retirement' ? '🌅 Long-Term Retirement Roadmap' : '🎯 Long-Term Goal Roadmap'}
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

          {/* Glide Path (Auto De-risking) */}
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

      {/* ── Market Posture & Timing Indicators ─────────────────────────── */}
      <div className="grid grid-cols-2 gap-3">
        {advice && (
          <div className="card flex flex-col justify-between">
            <p className="text-xs text-slate-400 mb-1">Market Posture</p>
            <span className={`badge text-sm font-bold px-3 py-1 rounded-xl ${postureColor(advice.posture)}`}>
              {advice.posture}
            </span>
            <p className="text-xs text-slate-500 mt-2">
              {(advice.description ?? advice.message ?? '').slice(0, 70)}…
            </p>
          </div>
        )}
        {timing && (
          <div className="card flex flex-col items-center">
            <p className="text-xs text-slate-400 mb-1">Timing Score</p>
            <TimingGauge score={timing.score} signal={timing.signal} />
          </div>
        )}
      </div>

      {/* ── Macro Danger Indicator ────────────────────────────────────── */}
      {macro && <MacroBar macro={macro} />}

      {/* ── Smart SIP Card ────────────────────────────────────────────── */}
      {sipRec && (
        <div className="card border-indigo-700/50">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-4 h-4 text-indigo-400" />
            <p className="section-title mb-0">Smart SIP Intelligence</p>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatBox label="Base Monthly SIP" value={fmtINR(sipRec.base_amount)} />
            <StatBox
              label={`Adjusted (${sipRec.multiplier}×)`}
              value={fmtINR(sipRec.adjusted_amount)}
              color={sipRec.multiplier >= 1 ? 'text-green-400' : 'text-orange-400'}
            />
          </div>

          <div className="bg-indigo-900/20 border border-indigo-800 rounded-xl px-3 py-2 mb-3">
            <p className="text-xs text-indigo-300 font-semibold mb-1">
              📅 Backtested Best SIP Dates
            </p>
            <div className="flex gap-2">
              {(sipRec.best_dates || [1, 7, 15]).map((d) => (
                <span key={d} className="bg-indigo-700 text-white text-xs font-bold px-2.5 py-1 rounded-lg">
                  {ordinal(d)}
                </span>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-1">Next recommended execution: {sipRec.next_sip_date || '—'}</p>
          </div>

          <p className="text-xs text-slate-400">{sipRec.rationale}</p>
        </div>
      )}

      {/* ── Stress Test Simulator ─────────────────────────────────────── */}
      <div className="card">
        <p className="section-title">Historical Stress Test</p>
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
              .stressTest(stressScenario, 500000)
              .then((r) => setStressResult(r.data))
          }
          className="btn-secondary w-full mb-3"
        >
          Run Simulation
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
