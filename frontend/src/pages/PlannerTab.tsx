import { useEffect, useState } from 'react'
import { plannerAPI, analyticsAPI } from '../lib/api'
import { AllocationAdvice, MacroDanger, TimingScore, SIPRecommendation, GoalPlan } from '../types'
import { fmtINR, postureColor, ordinal } from '../lib/utils'
import TimingGauge from '../components/TimingGauge'
import MacroBar from '../components/MacroBar'
import StressTestCard from '../components/StressTestCard'
import { Target, TrendingUp, Calendar, ChevronDown, ChevronUp, Sunset } from 'lucide-react'

const STRESS_SCENARIOS = [
  { key: 'covid_crash', label: 'COVID Crash (2020)' },
  { key: 'gfc_2008', label: 'GFC (2008)' },
  { key: 'crude_spike', label: 'Crude Oil Spike' },
  { key: 'fed_hike_cycle', label: 'Fed Rate Hike Cycle' },
  { key: 'rupee_collapse', label: 'Rupee Collapse' },
  { key: 'india_election', label: 'India Election Shock' },
]

// Retirement: 25× annual spend rule for corpus estimation
const RETIREMENT_AGE = 60
const RETIREMENT_CORPUS_MULTIPLIER = 25 // 25× annual spend (4% safe withdrawal rate)

export default function PlannerTab() {
  const [capital, setCapital] = useState<string>('1000000')
  const [monthlyTarget, setMonthlyTarget] = useState<string>('25000')
  const [goalTarget, setGoalTarget] = useState<string>('10000000')
  const [goalYears, setGoalYears] = useState<string>('10')
  const [schemeCode, setSchemeCode] = useState<string>('122640')
  const [stressScenario, setStressScenario] = useState('covid_crash')

  // Retirement mode state
  const [retirementMode, setRetirementMode] = useState(false)
  const [currentAge, setCurrentAge] = useState<string>('30')

  const [advice, setAdvice] = useState<AllocationAdvice | null>(null)
  const [macro, setMacro] = useState<MacroDanger | null>(null)
  const [timing, setTiming] = useState<TimingScore | null>(null)
  const [sipRec, setSipRec] = useState<SIPRecommendation | null>(null)
  const [goal, setGoal] = useState<GoalPlan | null>(null)
  const [stressResult, setStressResult] = useState<any>(null)

  const [loadingAdvice, setLoadingAdvice] = useState(false)
  const [showGlidePath, setShowGlidePath] = useState(false)
  const [showTranches, setShowTranches] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Computed retirement values
  const retirementYears = Math.max(1, RETIREMENT_AGE - Number(currentAge))
  const retirementCorpus = Number(monthlyTarget) * 12 * RETIREMENT_CORPUS_MULTIPLIER

  // Effective goal values — use retirement auto-computed when in retirement mode
  const effectiveGoalTarget = retirementMode ? String(retirementCorpus) : goalTarget
  const effectiveGoalYears = retirementMode ? String(retirementYears) : goalYears

  // Load macro + timing on mount
  useEffect(() => {
    analyticsAPI.macroDanger().then((r) => setMacro(r.data)).catch(() => {})
    analyticsAPI.timingScore(Number(schemeCode)).then((r) => setTiming(r.data)).catch(() => {})
  }, [schemeCode])

  const loadPlan = async () => {
    setLoadingAdvice(true)
    setError(null)
    try {
      const [adv, sip, gol, str] = await Promise.allSettled([
        plannerAPI.allocationAdvice(Number(capital)),
        plannerAPI.sipRecommendation(Number(monthlyTarget), Number(schemeCode)),
        plannerAPI.goalPlanner(Number(effectiveGoalTarget), Number(effectiveGoalYears), Number(monthlyTarget)),
        analyticsAPI.stressTest(stressScenario, 500000),
      ])
      if (adv.status === 'fulfilled') setAdvice(adv.value.data)
      if (sip.status === 'fulfilled') setSipRec(sip.value.data)
      if (gol.status === 'fulfilled') {
        const d = gol.value.data
        setGoal({
          ...d,
          // Normalise field names from backend snake_case variants
          target_amount: d.target_amount ?? Number(effectiveGoalTarget),
          projected_corpus: d.projected_corpus ?? 0,
          required_monthly_sip: d.required_monthly_sip ?? d.monthly_sip_required ?? 0,
          years: d.years ?? d.years_remaining ?? Number(effectiveGoalYears),
          glide_path: d.glide_path ?? d.glide_path_schedule ?? [],
        })
      }
      if (str.status === 'fulfilled') setStressResult(str.value.data)
    } catch {
      setError('Could not load plan. Is the backend running?')
    } finally {
      setLoadingAdvice(false)
    }
  }

  useEffect(() => { loadPlan() }, [])

  return (
    <div className="space-y-4 pb-6">
      {/* ── Capital Input ─────────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-indigo-400" /> Investment Planner
        </p>

        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="label">Available Capital (₹)</label>
            <input
              className="input"
              type="number"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
              placeholder="10,00,000"
            />
          </div>
          <div>
            <label className="label">Monthly SIP Budget (₹)</label>
            <input
              className="input"
              type="number"
              value={monthlyTarget}
              onChange={(e) => setMonthlyTarget(e.target.value)}
              placeholder="25,000"
            />
          </div>
        </div>

        {/* ── Retirement Mode Toggle ─────────────── */}
        <div className="flex items-center gap-3 mb-4 p-3 rounded-xl bg-slate-900 border border-slate-700">
          <button
            onClick={() => setRetirementMode((p) => !p)}
            className={`relative w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
              retirementMode ? 'bg-amber-500' : 'bg-slate-600'
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
                retirementMode ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
          <div>
            <p className="text-sm font-medium text-slate-200 flex items-center gap-1">
              🌅 Investing for Retirement
            </p>
            <p className="text-xs text-slate-500">
              {retirementMode
                ? `Retiring at ${RETIREMENT_AGE} · ${retirementYears}Y horizon · ${RETIREMENT_CORPUS_MULTIPLIER}× annual spend rule`
                : 'No fixed goal — auto-compute corpus & timeline'}
            </p>
          </div>
        </div>

        {/* ── Goal Inputs (conditional) ──────────── */}
        {retirementMode ? (
          <div className="mb-4">
            <div className="mb-3">
              <label className="label">Your Current Age</label>
              <input
                className="input"
                type="number"
                min={18}
                max={59}
                value={currentAge}
                onChange={(e) => setCurrentAge(e.target.value)}
                placeholder="30"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-3 py-2">
                <p className="text-xs text-amber-400 mb-0.5">Estimated Retirement Corpus</p>
                <p className="text-sm font-bold text-amber-300">{fmtINR(retirementCorpus)}</p>
                <p className="text-xs text-slate-500 mt-0.5">{RETIREMENT_CORPUS_MULTIPLIER}× annual SIP spend</p>
              </div>
              <div className="bg-amber-900/20 border border-amber-800 rounded-xl px-3 py-2">
                <p className="text-xs text-amber-400 mb-0.5">Years to Retirement</p>
                <p className="text-sm font-bold text-amber-300">{retirementYears} years</p>
                <p className="text-xs text-slate-500 mt-0.5">Retire at age {RETIREMENT_AGE}</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
              <span>ℹ️</span>
              Corpus = {RETIREMENT_CORPUS_MULTIPLIER}× annual spend (4% safe withdrawal rule). Adjust SIP budget to change target.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="label">Goal Corpus (₹)</label>
              <input
                className="input"
                type="number"
                value={goalTarget}
                onChange={(e) => setGoalTarget(e.target.value)}
              />
            </div>
            <div>
              <label className="label">Time Horizon (yrs)</label>
              <input
                className="input"
                type="number"
                value={goalYears}
                onChange={(e) => setGoalYears(e.target.value)}
              />
            </div>
          </div>
        )}

        <button onClick={loadPlan} className="btn-primary w-full" disabled={loadingAdvice}>
          {loadingAdvice ? 'Computing…' : '⚡ Generate Plan'}
        </button>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      </div>

      {/* ── Posture + Timing ──────────────────────── */}
      <div className="grid grid-cols-2 gap-3">
        {advice && (
          <div className="card flex flex-col justify-between">
            <p className="text-xs text-slate-400 mb-1">Market Posture</p>
            <span className={`badge text-sm font-bold px-3 py-1 rounded-xl ${postureColor(advice.posture)}`}>
              {advice.posture}
            </span>
            <p className="text-xs text-slate-500 mt-2">
              {(advice.description ?? advice.message ?? '').slice(0, 60)}…
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

      {/* ── Macro Danger ──────────────────────────── */}
      {macro && <MacroBar macro={macro} />}

      {/* ── Allocation Card ───────────────────────── */}
      {advice && (() => {
        const heroPlan = advice.hero_deployment_plan
        const tranches = heroPlan?.tranches ?? []
        const deployNow = tranches.length > 0
          ? tranches[0].amount
          : (advice.lumpsum_now ?? (Number(capital) * (advice.equity_pct / 100)))
        const staggerCount = tranches.length > 0 ? tranches.length : (advice.stagger_months ?? 0)

        return (
          <div className="card">
            <p className="section-title">Capital Deployment</p>
            <div className="grid grid-cols-3 gap-2 mb-3">
              <StatBox label="Deploy Now" value={fmtINR(deployNow)} color="text-green-400" />
              <StatBox label="Equity %" value={`${advice.equity_pct}%`} color="text-indigo-400" />
              <StatBox label="Liquid Reserve" value={`${advice.liquid_pct}%`} color="text-yellow-400" />
            </div>

            {/* Tranche toggle */}
            <button
              onClick={() => setShowTranches((p) => !p)}
              className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 mb-2"
            >
              {showTranches ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {staggerCount > 1 ? `Stagger over ${staggerCount} tranches` : 'Lump sum recommended'}
            </button>

            {showTranches && (
              <div className="space-y-2 mb-2">
                {tranches.length > 0 ? (
                  tranches.map((t, i) => (
                    <div key={i} className="flex justify-between text-xs bg-slate-900 rounded-lg px-3 py-2">
                      <span className="text-slate-400">{t.label} ({t.pct}%)</span>
                      <span className="text-slate-200 font-medium">{fmtINR(t.amount)}</span>
                    </div>
                  ))
                ) : advice.stagger_months && advice.stagger_months > 0 ? (
                  Array.from({ length: advice.stagger_months }, (_, i) => {
                    const amt = (advice.lumpsum_now ?? Number(capital)) / advice.stagger_months!
                    return (
                      <div key={i} className="flex justify-between text-xs bg-slate-900 rounded-lg px-3 py-2">
                        <span className="text-slate-400">Tranche {i + 1} (Month {i + 1})</span>
                        <span className="text-slate-200 font-medium">{fmtINR(amt)}</span>
                      </div>
                    )
                  })
                ) : null}
              </div>
            )}
            {heroPlan?.note && (
              <p className="text-xs text-slate-400 mt-2">{heroPlan.note}</p>
            )}
          </div>
        )
      })()}

      {/* ── Smart SIP Card ────────────────────────── */}
      {sipRec && (
        <div className="card border-indigo-700">
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-4 h-4 text-indigo-400" />
            <p className="section-title mb-0">Smart SIP Plan</p>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatBox label="Base SIP" value={fmtINR(sipRec.base_amount)} />
            <StatBox
              label={`Adjusted (${sipRec.multiplier}×)`}
              value={fmtINR(sipRec.adjusted_amount)}
              color={sipRec.multiplier >= 1 ? 'text-green-400' : 'text-orange-400'}
            />
          </div>

          {/* Empirical best SIP dates — embedded directly */}
          <div className="bg-indigo-900/20 border border-indigo-800 rounded-xl px-3 py-2 mb-3">
            <p className="text-xs text-indigo-300 font-semibold mb-1">
              📅 Backtested Best SIP Dates
            </p>
            <div className="flex gap-2">
              {(sipRec.best_dates || [1, 7, 15]).map((d) => (
                <span key={d} className="bg-indigo-700 text-white text-xs font-bold px-2 py-1 rounded-lg">
                  {ordinal(d)}
                </span>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-1">Next execution: {sipRec.next_sip_date || '—'}</p>
          </div>

          <p className="text-xs text-slate-400">{sipRec.rationale}</p>
        </div>
      )}

      {/* ── Goal / Retirement Planner ─────────────── */}
      {goal && (
        <div className={`card ${retirementMode ? 'border-amber-700' : ''}`}>
          <div className="flex items-center gap-2 mb-3">
            {retirementMode
              ? <span className="text-lg">🌅</span>
              : <Target className="w-4 h-4 text-yellow-400" />
            }
            <p className="section-title mb-0">
              {retirementMode ? 'Retirement Projection' : 'Goal Planner'}
            </p>
          </div>

          {retirementMode && (
            <div className="bg-amber-900/10 border border-amber-800/50 rounded-xl px-3 py-2 mb-3 text-xs text-amber-400/80">
              Based on retiring at age {RETIREMENT_AGE} with {RETIREMENT_CORPUS_MULTIPLIER}× annual spend corpus
              (4% safe withdrawal rate). Adjust your monthly SIP budget above to recalculate.
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatBox
              label={retirementMode ? 'Retirement Corpus' : 'Target Corpus'}
              value={fmtINR(goal.target_amount ?? 0)}
            />
            <StatBox
              label="Projected Corpus"
              value={fmtINR(goal.projected_corpus ?? 0)}
              color="text-green-400"
            />
            <StatBox label="Required SIP/mo" value={fmtINR(goal.required_monthly_sip ?? 0)} />
            <StatBox
              label={retirementMode ? 'Years to Retirement' : 'Time Horizon'}
              value={`${goal.years ?? 0}Y`}
            />
          </div>

          <button
            onClick={() => setShowGlidePath((p) => !p)}
            className="flex items-center gap-1 text-xs text-yellow-400 hover:text-yellow-300"
          >
            {showGlidePath ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            Glide Path (Auto De-risking)
          </button>

          {showGlidePath && goal.glide_path && (
            <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
              {goal.glide_path.map((g) => (
                <div key={g.year} className="flex items-center gap-2 text-xs bg-slate-900 rounded-lg px-3 py-1.5">
                  <span className="text-slate-500 w-10">Yr {g.year}</span>
                  <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 rounded-full"
                      style={{ width: `${g.equity_pct}%` }}
                    />
                  </div>
                  <span className="text-indigo-400 w-12 text-right">{g.equity_pct}% Eq</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Stress Test ───────────────────────────── */}
      <div className="card">
        <p className="section-title">Stress Test</p>
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

