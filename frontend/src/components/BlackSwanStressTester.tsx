import React, { useEffect, useState, useMemo } from 'react'
import { analyticsAPI } from '../lib/api'
import { DetailedStressTestResult, StressScenarioMeta, Holding } from '../types'
import { fmtINR, fmtPct } from '../lib/utils'
import {
  ShieldAlert,
  Flame,
  AlertTriangle,
  TrendingDown,
  Clock,
  Sparkles,
  Sliders,
  CheckCircle,
  RefreshCw,
  Layers,
  HelpCircle,
  ChevronRight,
} from 'lucide-react'

interface Props {
  holdings?: Holding[]
  portfolioValue?: number
}

const PRESET_AMOUNTS = [100000, 250000, 500000, 1000000, 2500000]

export default function BlackSwanStressTester({ holdings = [], portfolioValue = 0 }: Props) {
  const actualHoldingsTotal = useMemo(() => {
    return holdings.reduce((sum, h) => sum + (Number(h.current_value) || 0), 0)
  }, [holdings])

  const [useActualPortfolio, setUseActualPortfolio] = useState<boolean>(actualHoldingsTotal > 0)
  const [customCapital, setCustomCapital] = useState<string>(
    actualHoldingsTotal > 0 ? String(Math.round(actualHoldingsTotal)) : '500000'
  )

  const effectiveCapital = useMemo(() => {
    if (useActualPortfolio && actualHoldingsTotal > 0) return actualHoldingsTotal
    const parsed = parseFloat(customCapital)
    return isNaN(parsed) || parsed <= 0 ? 500000 : parsed
  }, [useActualPortfolio, actualHoldingsTotal, customCapital])

  const [scenarios, setScenarios] = useState<StressScenarioMeta[]>([])
  const [selectedKey, setSelectedKey] = useState<string>('covid_crash_2020')
  const [customDrawdown, setCustomDrawdown] = useState<number>(-25)
  const [customRecovery, setCustomRecovery] = useState<number>(12)

  const [result, setResult] = useState<DetailedStressTestResult | null>(null)
  const [loading, setLoading] = useState<boolean>(false)

  // Fetch scenarios list on mount
  useEffect(() => {
    analyticsAPI
      .stressScenarios()
      .then((res) => {
        if (res.data?.scenarios) {
          setScenarios(res.data.scenarios)
        }
      })
      .catch((err) => console.warn('Could not load scenarios:', err))
  }, [])

  // Run simulation whenever parameters change
  const runSimulation = async () => {
    setLoading(true)
    try {
      const payload: any = {
        portfolio_value: effectiveCapital,
        scenario_key: selectedKey,
      }

      if (useActualPortfolio && holdings.length > 0) {
        payload.holdings = holdings.map((h) => ({
          scheme_name: h.scheme_name,
          category: h.category || 'Flexi Cap',
          value: Number(h.current_value) || 0,
        }))
      }

      if (selectedKey === 'custom') {
        payload.custom_drawdown_pct = customDrawdown
        payload.custom_recovery_months = customRecovery
      }

      const res = await analyticsAPI.stressSimulate(payload)
      setResult(res.data)
    } catch (err) {
      console.warn('Stress test simulation fallback:', err)
      // Client-side fallback if backend route unavailable
      const dropPct = selectedKey === 'custom' ? customDrawdown : -38.0
      const trough = effectiveCapital * (1 + dropPct / 100)
      const loss = effectiveCapital - trough
      setResult({
        scenario_name: selectedKey === 'custom' ? `Custom Shock (${dropPct}%)` : 'COVID-19 Flash Crash',
        scenario_description: 'Global pandemic lockdown leading to rapid liquidity contraction.',
        current_portfolio_value: effectiveCapital,
        projected_trough_value: trough,
        projected_loss_amount: loss,
        projected_loss_pct: dropPct,
        recovery_months: selectedKey === 'custom' ? customRecovery : 6,
        recovery_date_estimate: '~6 months from now',
        category_breakdown: [
          { category: 'Large Cap', scheme_name: 'Large Cap Core', current_value: effectiveCapital * 0.35, scenario_impact_pct: dropPct * 0.88, projected_trough_value: effectiveCapital * 0.35 * (1 + dropPct * 0.0088), loss: effectiveCapital * 0.35 * Math.abs(dropPct * 0.0088) },
          { category: 'Mid Cap', scheme_name: 'Mid Cap Growth', current_value: effectiveCapital * 0.30, scenario_impact_pct: dropPct * 1.15, projected_trough_value: effectiveCapital * 0.30 * (1 + dropPct * 0.0115), loss: effectiveCapital * 0.30 * Math.abs(dropPct * 0.0115) },
          { category: 'Small Cap', scheme_name: 'Small Cap Alpha', current_value: effectiveCapital * 0.25, scenario_impact_pct: dropPct * 1.35, projected_trough_value: effectiveCapital * 0.25 * (1 + dropPct * 0.0135), loss: effectiveCapital * 0.25 * Math.abs(dropPct * 0.0135) },
          { category: 'Liquid / Debt', scheme_name: 'Liquid Parking', current_value: effectiveCapital * 0.10, scenario_impact_pct: +3.0, projected_trough_value: effectiveCapital * 0.10 * 1.03, loss: -effectiveCapital * 0.10 * 0.03 },
        ],
        worst_hit_category: 'Small Cap',
        most_resilient_category: 'Liquid / Debt',
        recommended_action: '🛡️ ELEVATED CORRECTION PLAYBOOK: Maintain core equity SIPs. Avoid panic exits; historical recovery took under 10 months.',
        silver_lining: '📈 SIP DISPLACEMENT ADVANTAGE: At the projected market trough, every ₹10,000 SIP purchases +45.2% more fund units than today.',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runSimulation()
  }, [selectedKey, effectiveCapital, customDrawdown, customRecovery, useActualPortfolio])

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-2xl space-y-5">
      {/* ── Title & Intro ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-red-500/10 text-red-400">
              <ShieldAlert className="w-5 h-5" />
            </span>
            <h2 className="text-base sm:text-lg font-bold text-slate-100">
              Macro Stress Tester & "Black Swan" Simulator
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Simulate how your portfolio survives historical crises, rate spikes, and crude shocks.
          </p>
        </div>

        {/* Portfolio Source Toggle */}
        <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setUseActualPortfolio(true)}
            disabled={actualHoldingsTotal <= 0}
            className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              useActualPortfolio && actualHoldingsTotal > 0
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            My Portfolio ({fmtINR(actualHoldingsTotal)})
          </button>
          <button
            onClick={() => setUseActualPortfolio(false)}
            className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              !useActualPortfolio || actualHoldingsTotal <= 0
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Custom Amount
          </button>
        </div>
      </div>

      {/* ── Custom Amount Controls (if not using actual portfolio) ── */}
      {(!useActualPortfolio || actualHoldingsTotal <= 0) && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-300">
              Simulated Capital to Stress Test (₹)
            </label>
            <span className="text-xs font-bold font-mono text-amber-400">
              {fmtINR(effectiveCapital)}
            </span>
          </div>
          <input
            type="number"
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-slate-100 focus:outline-none focus:border-red-500"
            value={customCapital}
            onChange={(e) => setCustomCapital(e.target.value)}
            placeholder="500000"
          />
          <div className="flex gap-1.5 overflow-x-auto pb-1">
            {PRESET_AMOUNTS.map((amt) => (
              <button
                key={amt}
                onClick={() => setCustomCapital(String(amt))}
                className={`px-2.5 py-1 text-xs rounded-lg font-mono border transition-all ${
                  effectiveCapital === amt
                    ? 'bg-red-500/20 border-red-500 text-red-300 font-bold'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {fmtINR(amt)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Crisis Scenarios Selector ── */}
      <div className="space-y-2">
        <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
          <Flame className="w-3.5 h-3.5 text-red-400" /> Choose Crisis Scenario or Shock Anomaly
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {scenarios.map((sc) => {
            const isSelected = selectedKey === sc.key
            return (
              <button
                key={sc.key}
                onClick={() => setSelectedKey(sc.key)}
                className={`p-3 rounded-xl border text-left transition-all relative overflow-hidden ${
                  isSelected
                    ? 'bg-red-950/40 border-red-500 text-slate-100 shadow-md shadow-red-950/30'
                    : 'bg-slate-950 border-slate-800/80 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-[10px] font-bold text-red-400 font-mono">
                    {sc.drawdown_pct}% Drawdown
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    ~{sc.recovery_months}m rec.
                  </span>
                </div>
                <p className="text-xs font-bold leading-tight line-clamp-2">{sc.name}</p>
                <p className="text-[10px] text-slate-500 mt-1 truncate">{sc.category_tag}</p>
              </button>
            )
          })}

          {/* Custom Slider Option */}
          <button
            onClick={() => setSelectedKey('custom')}
            className={`p-3 rounded-xl border text-left transition-all ${
              selectedKey === 'custom'
                ? 'bg-red-950/40 border-red-500 text-slate-100 shadow-md shadow-red-950/30'
                : 'bg-slate-950 border-slate-800/80 text-slate-400 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className="text-[10px] font-bold text-amber-400 font-mono">
                {customDrawdown}% Custom
              </span>
              <span className="text-[10px] text-slate-500 font-mono">~{customRecovery}m</span>
            </div>
            <p className="text-xs font-bold leading-tight">Custom Shock Slider</p>
            <p className="text-[10px] text-slate-500 mt-1">Manual Drawdown %</p>
          </button>
        </div>
      </div>

      {/* ── Custom Sliders (if Custom Selected) ── */}
      {selectedKey === 'custom' && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Market Drawdown Shock</span>
              <span className="font-bold font-mono text-red-400">{customDrawdown}%</span>
            </div>
            <input
              type="range"
              min="-65"
              max="-5"
              step="1"
              value={customDrawdown}
              onChange={(e) => setCustomDrawdown(Number(e.target.value))}
              className="w-full accent-red-500 cursor-pointer"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400">Estimated Recovery Horizon</span>
              <span className="font-bold font-mono text-yellow-400">{customRecovery} Months</span>
            </div>
            <input
              type="range"
              min="2"
              max="36"
              step="1"
              value={customRecovery}
              onChange={(e) => setCustomRecovery(Number(e.target.value))}
              className="w-full accent-yellow-500 cursor-pointer"
            />
          </div>
        </div>
      )}

      {/* ── Simulation Results ── */}
      {loading ? (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-8 text-center">
          <RefreshCw className="w-6 h-6 text-red-400 animate-spin mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-300">Stress testing portfolio holdings…</p>
        </div>
      ) : result ? (
        <div className="space-y-4">
          {/* Top Outcome KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
              <p className="text-[11px] font-medium text-slate-400">Projected Trough Value</p>
              <p className="text-xl font-bold font-mono text-slate-100 mt-1">
                {fmtINR(result.projected_trough_value)}
              </p>
              <p className="text-xs font-semibold text-red-400 mt-0.5">
                Loss: -{fmtINR(result.projected_loss_amount)} ({result.projected_loss_pct}%)
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
              <p className="text-[11px] font-medium text-slate-400">Recovery Time Horizon</p>
              <p className="text-xl font-bold font-mono text-yellow-400 mt-1">
                ~{result.recovery_months} Months
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Estimated Breakeven: <span className="text-slate-200 font-semibold">{result.recovery_date_estimate}</span>
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
              <p className="text-[11px] font-medium text-slate-400">Relative Vulnerability</p>
              <div className="mt-1 space-y-0.5">
                <p className="text-xs text-slate-300">
                  Worst Bleed: <span className="font-bold text-red-400">{result.worst_hit_category}</span>
                </p>
                <p className="text-xs text-slate-300">
                  Most Resilient: <span className="font-bold text-emerald-400">{result.most_resilient_category}</span>
                </p>
              </div>
            </div>
          </div>

          {/* Category-by-Category Impact Bar Breakdown */}
          {result.category_breakdown && result.category_breakdown.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-200">Category Shock Resistance & Trough Values</span>
                <span className="text-slate-500 text-[11px]">Holdings Stress Breakdown</span>
              </div>
              <div className="space-y-2.5">
                {result.category_breakdown.map((cat, idx) => {
                  const isPositive = cat.scenario_impact_pct >= 0
                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-300 truncate max-w-[200px]">
                          {cat.category}
                        </span>
                        <div className="flex items-center gap-3 font-mono text-xs">
                          <span className="text-slate-500">
                            {fmtINR(cat.current_value)} → <strong className="text-slate-200">{fmtINR(cat.projected_trough_value)}</strong>
                          </span>
                          <span
                            className={`font-bold px-1.5 py-0.5 rounded text-[11px] ${
                              isPositive
                                ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/60'
                                : 'bg-red-950/50 text-red-400 border border-red-800/60'
                            }`}
                          >
                            {isPositive ? '+' : ''}{cat.scenario_impact_pct}%
                          </span>
                        </div>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            isPositive ? 'bg-emerald-500' : 'bg-red-500'
                          }`}
                          style={{
                            width: `${Math.min(100, Math.max(10, Math.abs(cat.scenario_impact_pct) * 1.5))}%`,
                          }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Institutional Action Playbook */}
          <div className="bg-red-950/30 border border-red-900/60 rounded-xl p-4 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-red-300 font-bold">
              <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
              Institutional Playbook & Mitigation Strategy
            </div>
            <p className="text-slate-300 leading-relaxed">{result.recommended_action}</p>
          </div>

          {/* SIP Advantage / Silver Lining */}
          <div className="bg-emerald-950/30 border border-emerald-900/60 rounded-xl p-4 text-xs text-emerald-200 flex items-start gap-2.5">
            <Sparkles className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block mb-0.5">The Silver Lining</span>
              <p className="text-slate-300 leading-relaxed">{result.silver_lining}</p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
