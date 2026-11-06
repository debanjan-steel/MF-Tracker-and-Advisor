import React, { useState, useCallback, useRef } from 'react'
import { fundsAPI, analyticsAPI } from '../lib/api'
import { SchemeInfo, Scorecard, Thermometer } from '../types'
import { fmtPct, fmt, thermometerColor, signalColor } from '../lib/utils'
import { Search, TrendingUp, Thermometer as ThermIcon, BarChart2 } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

export default function ExplorerTab() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SchemeInfo[]>([])
  const [selected, setSelected] = useState<SchemeInfo | null>(null)
  const [scorecard, setScorecard] = useState<Scorecard | null>(null)
  const [navData, setNavData] = useState<any[]>([])
  const [thermometer, setThermometer] = useState<Thermometer | null>(null)
  const [backtestData, setBacktestData] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const [loadingFund, setLoadingFund] = useState(false)
  const [activeSection, setActiveSection] = useState<'search' | 'thermo' | 'backtest'>('search')

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim() || q.length < 2) return
    setSearching(true)
    try {
      const { data } = await fundsAPI.search(q)
      setResults(data?.results || data || [])
    } finally {
      setSearching(false)
    }
  }, [])

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleQueryChange = (val: string) => {
    setQuery(val)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (val.length >= 2) {
      searchTimer.current = setTimeout(() => doSearch(val), 300)
    } else {
      setResults([])
    }
  }

  const selectFund = async (scheme: SchemeInfo) => {
    setSelected(scheme)
    setResults([])
    setQuery(scheme.scheme_name)
    setLoadingFund(true)
    try {
      const [sc, nav, bt] = await Promise.allSettled([
        analyticsAPI.scorecard(scheme.scheme_code),
        fundsAPI.navHistory(scheme.scheme_code, 1.0),
        analyticsAPI.backtest(scheme.scheme_code, 5000, 5),
      ])
      if (sc.status === 'fulfilled') setScorecard(sc.value.data)
      if (nav.status === 'fulfilled') {
        const raw = nav.value.data?.nav_history || nav.value.data?.nav_records || []
        // Build chart data with 200-day EMA
        let ema = 0
        const k = 2 / (200 + 1)
        const chart = raw.map((r: any, i: number) => {
          ema = i === 0 ? r.nav : r.nav * k + ema * (1 - k)
          return { date: (r.date || '').slice(0, 7), nav: r.nav, ema200: +ema.toFixed(2) }
        })
        setNavData(chart)
      }
      if (bt.status === 'fulfilled') setBacktestData(bt.value.data)
    } finally {
      setLoadingFund(false)
    }
  }

  const loadThermometer = async () => {
    const { data } = await analyticsAPI.thermometer()
    setThermometer(data)
    setActiveSection('thermo')
  }

  return (
    <div className="space-y-4 pb-6">
      {/* ── Tab Bar ───────────────────────────────── */}
      <div className="flex bg-slate-800 rounded-xl p-1 gap-1">
        {[
          { key: 'search', icon: <Search className="w-4 h-4" />, label: 'Fund Search' },
          { key: 'thermo', icon: <ThermIcon className="w-4 h-4" />, label: 'Thermometer' },
          { key: 'backtest', icon: <BarChart2 className="w-4 h-4" />, label: 'Backtest' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setActiveSection(t.key as any)
              if (t.key === 'thermo' && !thermometer) loadThermometer()
            }}
            className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-xs font-medium transition-colors ${
              activeSection === t.key
                ? 'bg-indigo-600 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── Fund Search ───────────────────────────── */}
      {activeSection === 'search' && (
        <>
          <div className="relative">
            <input
              className="input pl-10"
              placeholder="Search fund name or AMC…"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doSearch(query)}
            />
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            {searching && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 animate-pulse">searching…</span>
            )}
          </div>

          {results.length > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden max-h-64 overflow-y-auto shadow-xl">
              {searching && (
                <p className="text-xs text-slate-500 text-center py-2 animate-pulse">Searching…</p>
              )}
              {results.slice(0, 20).map((r) => (
                <button
                  key={r.scheme_code}
                  onClick={() => selectFund(r)}
                  className="w-full text-left px-4 py-3 hover:bg-slate-700 border-b border-slate-700/50 last:border-0 transition-colors"
                >
                  <p className="text-sm font-medium text-slate-100 leading-tight">{r.scheme_name}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{r.fund_house} · {r.scheme_category}</p>
                </button>
              ))}
            </div>
          )}

          {/* Scorecard */}
          {scorecard && (
            <div className="card">
              <p className="section-title">{scorecard.scheme_name?.slice(0, 40)}…</p>
              <div className="grid grid-cols-3 gap-2 mb-3">
                <MetricBox label="CAGR 1Y" value={fmtPct(scorecard.cagr_1y)} color={scorecard.cagr_1y > 0 ? 'text-green-400' : 'text-red-400'} />
                <MetricBox label="CAGR 3Y" value={fmtPct(scorecard.cagr_3y)} color={scorecard.cagr_3y > 0 ? 'text-green-400' : 'text-red-400'} />
                <MetricBox label="CAGR 5Y" value={fmtPct(scorecard.cagr_5y)} color={scorecard.cagr_5y > 0 ? 'text-green-400' : 'text-red-400'} />
                <MetricBox label="Sharpe" value={fmt(scorecard.sharpe)} />
                <MetricBox label="Max DD" value={fmtPct(scorecard.max_drawdown)} color="text-red-400" />
                <MetricBox label="Alpha" value={fmtPct(scorecard.alpha)} color={scorecard.alpha > 0 ? 'text-green-400' : 'text-red-400'} />
                <MetricBox label="Beta" value={fmt(scorecard.beta)} />
                <MetricBox label="Up Cap" value={fmtPct(scorecard.up_capture)} color="text-green-400" />
                <MetricBox label="Dn Cap" value={fmtPct(scorecard.down_capture)} color="text-red-400" />
              </div>
              <div className="flex items-center justify-between bg-slate-900 rounded-xl px-4 py-3">
                <span className="text-slate-400 text-sm">Overall Grade</span>
                <span className={`text-2xl font-black ${scorecard.overall_score > 65 ? 'text-green-400' : scorecard.overall_score > 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {scorecard.grade}
                </span>
              </div>
            </div>
          )}

          {/* NAV Chart */}
          {navData.length > 0 && (
            <div className="card">
              <p className="section-title flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-indigo-400" /> NAV + 200-Day EMA
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={navData.slice(-60)}>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} width={40} />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8 }}
                    labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                    itemStyle={{ fontSize: 12 }}
                  />
                  <Line type="monotone" dataKey="nav" stroke="#6366f1" dot={false} strokeWidth={2} name="NAV" />
                  <Line type="monotone" dataKey="ema200" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="4 2" name="200 EMA" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* ── Category Thermometer ──────────────────── */}
      {activeSection === 'thermo' && (
        <div className="card">
          <p className="section-title">Category Valuation Thermometer</p>
          {thermometer ? (
            <div className="space-y-2">
              {Object.entries(thermometer).map(([cat, info]) => (
                <div
                  key={cat}
                  className={`flex items-center justify-between rounded-xl px-3 py-2.5 ${thermometerColor(info.status)}`}
                >
                  <div>
                    <p className="text-sm font-semibold">{cat}</p>
                    <p className="text-xs opacity-70">{info.recommendation}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-bold">{info.status}</p>
                    <p className="text-xs opacity-60">Score: {info.score}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm text-center py-6">Loading thermometer…</p>
          )}
        </div>
      )}

      {/* ── Backtest ──────────────────────────────── */}
      {activeSection === 'backtest' && (
        <div className="card">
          <p className="section-title">SIP Backtest (₹5,000/mo · 5 Yrs)</p>
          {backtestData ? (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <MetricBox label="Static SIP XIRR" value={fmtPct(backtestData.static_xirr)} color="text-indigo-400" />
                <MetricBox label="Dynamic SIP XIRR" value={fmtPct(backtestData.dynamic_xirr)} color="text-green-400" />
                <MetricBox label="Static Final" value={backtestData.static_final_value?.toLocaleString('en-IN', { maximumFractionDigits: 0 })} />
                <MetricBox label="Dynamic Final" value={backtestData.dynamic_final_value?.toLocaleString('en-IN', { maximumFractionDigits: 0 })} />
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Select a fund in the Search tab first, then switch here to see its backtest.
              </p>
            </div>
          ) : (
            <p className="text-slate-500 text-sm text-center py-6">
              Search &amp; select a fund first.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function MetricBox({
  label, value, color = 'text-slate-200',
}: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-slate-900 rounded-xl px-2 py-2 text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  )
}

