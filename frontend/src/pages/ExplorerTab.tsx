import React, { useState, useCallback, useRef } from 'react'
import { fundsAPI, analyticsAPI } from '../lib/api'
import { SchemeInfo, Scorecard, Thermometer } from '../types'
import { fmtPct, fmt, thermometerColor, signalColor } from '../lib/utils'
import { Search, TrendingUp, Thermometer as ThermIcon, BarChart2, Star, Trash2 } from 'lucide-react'
import { useAppStore } from '../store/appStore'
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
  const { watchlist, addToWatchlist, removeFromWatchlist } = useAppStore()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SchemeInfo[]>([])
  const [selected, setSelected] = useState<SchemeInfo | null>(null)
  const [scorecard, setScorecard] = useState<Scorecard | null>(null)
  const [navData, setNavData] = useState<any[]>([])
  const [thermometer, setThermometer] = useState<Thermometer | null>(null)
  const [backtestData, setBacktestData] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const [loadingFund, setLoadingFund] = useState(false)
  const [activeSection, setActiveSection] = useState<'search' | 'watchlist' | 'thermo' | 'backtest'>('search')

  const isWatched = (code: number) => watchlist.some((w) => w.scheme_code === code)

  const toggleWatchlist = (scheme: any) => {
    const code = Number(scheme.scheme_code || scheme.schemeCode)
    const name = scheme.scheme_name || scheme.schemeName || `Scheme ${code}`
    if (isWatched(code)) {
      removeFromWatchlist(code)
    } else {
      addToWatchlist({
        scheme_code: code,
        scheme_name: name,
        fund_house: scheme.fund_house || '',
        scheme_category: scheme.scheme_category || '',
        added_at: new Date().toISOString(),
      })
    }
  }

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

  const selectFund = async (scheme: any) => {
    const code = Number(scheme.scheme_code || scheme.schemeCode)
    const name = scheme.scheme_name || scheme.schemeName || `Scheme ${code}`
    const normalized: SchemeInfo = {
      ...scheme,
      scheme_code: code,
      scheme_name: name,
    }
    setSelected(normalized)
    setResults([])
    setQuery(name)
    setScorecard(null)
    setNavData([])
    setBacktestData(null)
    setLoadingFund(true)
    try {
      const [sc, nav, bt] = await Promise.allSettled([
        analyticsAPI.scorecard(code),
        fundsAPI.navHistory(code, 1.0),
        analyticsAPI.backtest(code, 5000, 5),
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
          {
            key: 'watchlist',
            icon: <Star className={`w-4 h-4 ${watchlist.length > 0 ? 'text-amber-400 fill-amber-400' : ''}`} />,
            label: `Watchlist${watchlist.length > 0 ? ` (${watchlist.length})` : ''}`,
          },
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
              {results.slice(0, 20).map((r: any) => {
                const code = r.scheme_code || r.schemeCode
                const name = r.scheme_name || r.schemeName || `Scheme ${code}`
                const subtitle = [r.fund_house, r.scheme_category].filter(Boolean).join(' · ')
                const watched = isWatched(code)
                return (
                  <div
                    key={code}
                    className="flex items-center justify-between px-4 py-2.5 hover:bg-slate-700/80 border-b border-slate-700/50 last:border-0 transition-colors"
                  >
                    <button
                      onClick={() => selectFund(r)}
                      className="flex-1 text-left min-w-0 pr-3"
                    >
                      <p className="text-sm font-medium text-slate-100 leading-tight">{name}</p>
                      {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleWatchlist(r)
                      }}
                      title={watched ? 'Remove from Watchlist' : 'Add to Watchlist'}
                      className="p-2 rounded-lg hover:bg-slate-600/50 text-slate-400 hover:text-amber-400 transition-colors shrink-0"
                    >
                      <Star className={`w-4 h-4 ${watched ? 'text-amber-400 fill-amber-400' : 'text-slate-500 hover:text-slate-300'}`} />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          {/* Loading Fund Details */}
          {loadingFund && (
            <div className="card text-center py-8">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-300 font-medium">Fetching Fund NAV History & Analytics…</p>
              <p className="text-xs text-slate-500 mt-1">Downloading historical records from MFAPI & computing scorecard</p>
            </div>
          )}

          {/* Scorecard */}
          {scorecard && (
            <div className="card">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1 min-w-0">
                  <p className="text-base font-bold text-slate-100 leading-tight">
                    {selected?.scheme_name || scorecard.scheme_name || 'Fund Performance'}
                  </p>
                  {(selected?.fund_house || selected?.scheme_category) && (
                    <p className="text-xs text-slate-400 mt-1">
                      {[selected?.fund_house, selected?.scheme_category].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
                {selected && (
                  <button
                    onClick={() => toggleWatchlist(selected)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 border transition-all ${
                      isWatched(selected.scheme_code)
                        ? 'bg-amber-500/15 border-amber-500/40 text-amber-400 hover:bg-amber-500/25'
                        : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white'
                    }`}
                  >
                    <Star className={`w-3.5 h-3.5 ${isWatched(selected.scheme_code) ? 'fill-amber-400 text-amber-400' : 'text-slate-400'}`} />
                    {isWatched(selected.scheme_code) ? 'In Watchlist' : 'Add to Watchlist'}
                  </button>
                )}
              </div>
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
                <span className={`text-2xl font-black ${(scorecard.overall_score ?? 60) > 65 ? 'text-green-400' : (scorecard.overall_score ?? 60) > 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {scorecard.grade || 'A'}
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

      {/* ── Watchlist ────────────────────────────── */}
      {activeSection === 'watchlist' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="section-title mb-0 flex items-center gap-2">
                <Star className="w-4 h-4 text-amber-400 fill-amber-400" /> Watchlist
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                {watchlist.length} {watchlist.length === 1 ? 'fund' : 'funds'} saved
              </p>
            </div>
          </div>

          {watchlist.length === 0 ? (
            <div className="card text-center py-12">
              <Star className="w-12 h-12 text-slate-600 mx-auto mb-3 opacity-40" />
              <p className="text-base font-semibold text-slate-200">Your Watchlist is Empty</p>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Search for any mutual fund in the <strong>Fund Search</strong> tab and tap <strong>&quot;Add to Watchlist&quot;</strong> to track it here.
              </p>
              <button
                onClick={() => setActiveSection('search')}
                className="btn-primary mt-4 text-xs py-2 px-4 inline-flex items-center gap-1.5"
              >
                <Search className="w-3.5 h-3.5" /> Go to Fund Search
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {watchlist.map((w) => {
                const isCurrent = selected?.scheme_code === w.scheme_code
                return (
                  <div
                    key={w.scheme_code}
                    className={`card p-3 transition-all border ${
                      isCurrent ? 'border-indigo-500 bg-slate-800' : 'border-slate-700/60 bg-slate-800 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div
                        onClick={() => selectFund(w)}
                        className="flex-1 cursor-pointer min-w-0"
                      >
                        <p className="text-sm font-semibold text-slate-100 leading-snug hover:text-indigo-300 transition-colors">
                          {w.scheme_name}
                        </p>
                        {(w.fund_house || w.scheme_category) && (
                          <p className="text-xs text-slate-400 mt-0.5 truncate">
                            {[w.fund_house, w.scheme_category].filter(Boolean).join(' · ')}
                          </p>
                        )}
                        <p className="text-[11px] text-indigo-400 mt-1 font-medium flex items-center gap-1">
                          Tap to view Scorecard &amp; 200 EMA
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => selectFund(w)}
                          title="View analytics"
                          className="rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600 hover:text-white border border-indigo-500/30 transition-all text-xs font-medium px-2.5 py-1.5 flex items-center gap-1"
                        >
                          View
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            removeFromWatchlist(w.scheme_code)
                            if (selected?.scheme_code === w.scheme_code) {
                              setScorecard(null)
                              setSelected(null)
                              setNavData([])
                            }
                          }}
                          title="Remove from watchlist"
                          className="p-2 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Loading Fund Details in Watchlist */}
          {loadingFund && (
            <div className="card text-center py-8">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-300 font-medium">Fetching Fund NAV History &amp; Analytics…</p>
              <p className="text-xs text-slate-500 mt-1">Downloading historical records from MFAPI &amp; computing scorecard</p>
            </div>
          )}

          {/* Render selected fund's Scorecard & NAV Chart right inside Watchlist tab */}
          {scorecard && selected && (
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                  Fund Analytics &amp; Scorecard
                </span>
                <button
                  onClick={() => { setScorecard(null); setSelected(null); setNavData([]) }}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Close Analytics ✕
                </button>
              </div>

              {/* Scorecard */}
              <div className="card">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-base font-bold text-slate-100 leading-tight">
                      {selected.scheme_name || scorecard.scheme_name}
                    </p>
                    {(selected.fund_house || selected.scheme_category) && (
                      <p className="text-xs text-slate-400 mt-1">
                        {[selected.fund_house, selected.scheme_category].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => toggleWatchlist(selected)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 border bg-amber-500/15 border-amber-500/40 text-amber-400 hover:bg-red-500/20 hover:border-red-500/40 hover:text-red-400 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>

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
                  <span className={`text-2xl font-black ${(scorecard.overall_score ?? 60) > 65 ? 'text-green-400' : (scorecard.overall_score ?? 60) > 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {scorecard.grade || 'A'}
                  </span>
                </div>
              </div>

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
            </div>
          )}
        </div>
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

