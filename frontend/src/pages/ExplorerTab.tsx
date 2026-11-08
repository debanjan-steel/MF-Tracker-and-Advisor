import React, { useState, useCallback, useRef, useEffect } from 'react'
import { fundsAPI, analyticsAPI } from '../lib/api'
import { SchemeInfo, Scorecard, Thermometer } from '../types'
import { fmtPct, fmt, fmtINR, thermometerColor, signalColor } from '../lib/utils'
import {
  Search, TrendingUp, Thermometer as ThermIcon, BarChart2, Star, Trash2,
  ChevronDown, ChevronUp, RefreshCw, AlertTriangle, Sparkles
} from 'lucide-react'
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
import MonteCarloFanChart from '../components/MonteCarloFanChart'

interface FundThermometer {
  scheme_code: number
  scheme_name: string
  category: string
  temperature: number
  label: string
  emoji: string
  cagr_3y: number
  cagr_3y_percentile: number
  max_drawdown: number
  in_recovery: boolean
  recovery_pct: number
  sip_recommendation: string
  lumpsum_recommendation: string
  rationale: string
}

export default function ExplorerTab() {
  const {
    watchlist,
    addToWatchlist,
    removeFromWatchlist,
    explorerSection,
    setExplorerSection,
  } = useAppStore()

  const activeSection = explorerSection
  const setActiveSection = setExplorerSection

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SchemeInfo[]>([])
  const [selected, setSelected] = useState<SchemeInfo | null>(null)
  const [scorecard, setScorecard] = useState<Scorecard | null>(null)
  const [navData, setNavData] = useState<any[]>([])
  const [watchlistThermos, setWatchlistThermos] = useState<FundThermometer[]>([])
  const [thermoLoading, setThermoLoading] = useState(false)
  const [backtestData, setBacktestData] = useState<any>(null)
  const [btMonthly, setBtMonthly] = useState<number>(5000)
  const [btYears, setBtYears] = useState<number>(5)
  const [btLoading, setBtLoading] = useState<boolean>(false)
  const [btSelectedFund, setBtSelectedFund] = useState<{ scheme_code: number; scheme_name: string; category?: string } | null>(null)
  const [btSearchQuery, setBtSearchQuery] = useState('')
  const [btSuggestions, setBtSuggestions] = useState<SchemeInfo[]>([])
  const [btSearching, setBtSearching] = useState(false)
  const btSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [searching, setSearching] = useState(false)
  const [loadingFund, setLoadingFund] = useState(false)

  // ── Watchlist tab direct search state ──────────────────────────────
  const [wlQuery, setWlQuery] = useState('')
  const [wlSuggestions, setWlSuggestions] = useState<SchemeInfo[]>([])
  const [wlSearching, setWlSearching] = useState(false)
  const wlTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  const handleWlQueryChange = (val: string) => {
    setWlQuery(val)
    if (wlTimer.current) clearTimeout(wlTimer.current)
    if (val.length >= 2) {
      wlTimer.current = setTimeout(async () => {
        setWlSearching(true)
        try {
          const { data } = await fundsAPI.search(val)
          setWlSuggestions(data?.results || data || [])
        } finally {
          setWlSearching(false)
        }
      }, 300)
    } else {
      setWlSuggestions([])
    }
  }

  // ── Watchlist inline expansion state ──────────────────────────────
  const [expandedWlCode, setExpandedWlCode] = useState<number | null>(null)
  const [wlScorecard, setWlScorecard] = useState<Scorecard | null>(null)
  const [wlNavData, setWlNavData] = useState<any[]>([])
  const [wlLoadingFund, setWlLoadingFund] = useState(false)

  const toggleExpandWatchlist = async (w: any) => {
    const code = Number(w.scheme_code || w.schemeCode)
    if (expandedWlCode === code) {
      setExpandedWlCode(null)
      setWlScorecard(null)
      setWlNavData([])
      return
    }

    setExpandedWlCode(code)
    setWlScorecard(null)
    setWlNavData([])
    setWlLoadingFund(true)
    try {
      const [sc, nav] = await Promise.allSettled([
        analyticsAPI.scorecard(code),
        fundsAPI.navHistory(code, 1.0),
      ])
      if (sc.status === 'fulfilled') setWlScorecard(sc.value.data)
      if (nav.status === 'fulfilled') {
        const raw = nav.value.data?.nav_history || nav.value.data?.nav_records || []
        let ema = 0
        const k = 2 / (200 + 1)
        const chart = raw.map((r: any, i: number) => {
          ema = i === 0 ? r.nav : r.nav * k + ema * (1 - k)
          return { date: (r.date || '').slice(0, 7), nav: r.nav, ema200: +ema.toFixed(2) }
        })
        setWlNavData(chart)
      }
    } finally {
      setWlLoadingFund(false)
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
    setThermoLoading(true)
    try {
      const fundsToQuery: { scheme_code: number; scheme_name?: string; category?: string }[] = []

      // 1. Watchlist mutual funds (primary focus)
      if (watchlist && watchlist.length > 0) {
        watchlist.forEach((w) => {
          fundsToQuery.push({
            scheme_code: w.scheme_code,
            scheme_name: w.scheme_name,
            category: w.scheme_category || 'Equity',
          })
        })
      }

      // 2. Also include currently selected fund if not already in list
      if (selected && !fundsToQuery.some((f) => f.scheme_code === selected.scheme_code)) {
        fundsToQuery.push({
          scheme_code: selected.scheme_code,
          scheme_name: selected.scheme_name,
          category: selected.scheme_category || 'Equity',
        })
      }

      // 3. Fallback benchmark funds if watchlist is empty
      if (fundsToQuery.length === 0) {
        fundsToQuery.push(
          { scheme_code: 120716, scheme_name: 'Nippon India Large Cap Fund', category: 'Large Cap' },
          { scheme_code: 127042, scheme_name: 'Motilal Oswal Midcap Fund', category: 'Mid Cap' },
          { scheme_code: 118989, scheme_name: 'Nippon India Small Cap Fund', category: 'Small Cap' },
        )
      }

      const res = await analyticsAPI.thermometerBatch(fundsToQuery)
      setWatchlistThermos(res.data?.results || [])
    } catch (e) {
      console.error('Thermometer load failed:', e)
    } finally {
      setThermoLoading(false)
    }
  }

  useEffect(() => {
    if (activeSection === 'thermo') {
      loadThermometer()
    }
  }, [activeSection, watchlist])

  const runBacktest = useCallback(async (code: number, monthly: number, years: number) => {
    setBtLoading(true)
    try {
      const { data } = await analyticsAPI.backtest(code, monthly, years)
      setBacktestData(data)
    } catch (e) {
      console.error('Backtest error:', e)
    } finally {
      setBtLoading(false)
    }
  }, [])

  const handleBtSearchChange = (val: string) => {
    setBtSearchQuery(val)
    if (btSearchTimer.current) clearTimeout(btSearchTimer.current)
    if (val.length >= 2) {
      btSearchTimer.current = setTimeout(async () => {
        setBtSearching(true)
        try {
          const { data } = await fundsAPI.search(val)
          const raw = data?.results || (Array.isArray(data) ? data : [])
          setBtSuggestions(raw.slice(0, 8))
        } catch {
          setBtSuggestions([])
        } finally {
          setBtSearching(false)
        }
      }, 300)
    } else {
      setBtSuggestions([])
    }
  }

  const selectBtFund = (fund: any) => {
    const code = Number(fund.scheme_code || fund.schemeCode)
    const name = fund.scheme_name || fund.schemeName || `Scheme ${code}`
    const cat = fund.scheme_category || fund.category || 'Equity'
    const chosen = { scheme_code: code, scheme_name: name, category: cat }
    setBtSelectedFund(chosen)
    setBtSearchQuery('')
    setBtSuggestions([])
    runBacktest(code, btMonthly, btYears)
  }

  useEffect(() => {
    if (activeSection === 'backtest') {
      let targetCode: number | null = null
      let targetFund: any = null

      if (btSelectedFund) {
        targetCode = btSelectedFund.scheme_code
        targetFund = btSelectedFund
      } else if (watchlist.length > 0) {
        targetCode = watchlist[0].scheme_code
        targetFund = watchlist[0]
      } else if (selected) {
        targetCode = selected.scheme_code
        targetFund = selected
      } else {
        targetCode = 118989
        targetFund = { scheme_code: 118989, scheme_name: 'Nippon India Small Cap Fund', scheme_category: 'Small Cap' }
      }

      if (targetCode) {
        setBtSelectedFund({
          scheme_code: targetCode,
          scheme_name: targetFund.scheme_name,
          category: targetFund.scheme_category || targetFund.category || 'Equity',
        })
        runBacktest(targetCode, btMonthly, btYears)
      }
    }
  }, [activeSection, btMonthly, btYears, watchlist.length])

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
                      className={`text-xs font-semibold px-2.5 py-1.5 rounded-lg border flex items-center gap-1.5 shrink-0 transition-all ${
                        watched
                          ? 'bg-amber-500/20 border-amber-500/60 text-amber-300'
                          : 'bg-indigo-600/30 border-indigo-500/50 text-indigo-200 hover:bg-indigo-600 hover:text-white'
                      }`}
                    >
                      <Star className={`w-3.5 h-3.5 ${watched ? 'fill-amber-400 text-amber-400' : ''}`} />
                      {watched ? 'Saved' : '+ Watch'}
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          {/* Loading Fund Details indicator when no selected card yet */}
          {loadingFund && !selected && (
            <div className="card text-center py-8">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-sm text-slate-300 font-medium">Fetching Fund NAV History & Analytics…</p>
              <p className="text-xs text-slate-500 mt-1">Downloading historical records from MFAPI & computing scorecard</p>
            </div>
          )}

          {/* Fund Details & Scorecard */}
          {selected && (
            <div className="card">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1 min-w-0">
                  <p className="text-base font-bold text-slate-100 leading-tight">
                    {selected.scheme_name || scorecard?.scheme_name || 'Fund Performance'}
                  </p>
                  {(selected.fund_house || selected.scheme_category) && (
                    <p className="text-xs text-slate-400 mt-1">
                      {[selected.fund_house, selected.scheme_category].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => toggleWatchlist(selected)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold shrink-0 border transition-all ${
                    isWatched(selected.scheme_code)
                      ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 hover:bg-amber-500/30'
                      : 'bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500 shadow-md shadow-indigo-600/30'
                  }`}
                >
                  <Star className={`w-3.5 h-3.5 ${isWatched(selected.scheme_code) ? 'fill-amber-400 text-amber-400' : 'text-white'}`} />
                  {isWatched(selected.scheme_code) ? 'In Watchlist' : '+ Add to Watchlist'}
                </button>
              </div>

              {loadingFund && (
                <div className="text-center py-6 border-t border-slate-800 mt-2">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs text-slate-400">Loading Scorecard &amp; 200-Day EMA…</p>
                </div>
              )}

              {scorecard && !loadingFund && (
                <>
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
                </>
              )}
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

          {/* Probabilistic Monte Carlo Forecast */}
          {selected && (
            <MonteCarloFanChart
              schemeCode={selected.scheme_code}
              schemeName={selected.scheme_name}
            />
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

          {/* Direct Search & Add to Watchlist */}
          <div className="relative">
            <input
              className="input pl-10"
              placeholder="Search fund to add to watchlist…"
              value={wlQuery}
              onChange={(e) => handleWlQueryChange(e.target.value)}
            />
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            {wlSearching && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 animate-pulse">searching…</span>
            )}

            {/* Quick Suggestions Dropdown */}
            {wlSuggestions.length > 0 && (
              <div className="absolute z-30 left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden max-h-56 overflow-y-auto shadow-2xl">
                {wlSuggestions.slice(0, 10).map((r: any) => {
                  const code = r.scheme_code || r.schemeCode
                  const name = r.scheme_name || r.schemeName || `Scheme ${code}`
                  const watched = isWatched(code)
                  return (
                    <div
                      key={code}
                      className="flex items-center justify-between px-3 py-2.5 hover:bg-slate-700/80 border-b border-slate-700/50 last:border-0"
                    >
                      <p className="text-xs font-medium text-slate-200 truncate flex-1 pr-2">{name}</p>
                      <button
                        onClick={() => {
                          toggleWatchlist(r)
                          setWlSuggestions([])
                          setWlQuery('')
                        }}
                        className={`text-xs px-2.5 py-1 rounded-lg border font-semibold flex items-center gap-1 shrink-0 ${
                          watched
                            ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                            : 'bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500'
                        }`}
                      >
                        <Star className={`w-3 h-3 ${watched ? 'fill-amber-400 text-amber-400' : ''}`} />
                        {watched ? 'Saved' : '+ Add'}
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {watchlist.length === 0 ? (
            <div className="card text-center py-10">
              <Star className="w-10 h-10 text-slate-600 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-semibold text-slate-200">Your Watchlist is Empty</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                Type any mutual fund name in the search box above to add it to your watchlist.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {watchlist.map((w) => {
                const isExpanded = expandedWlCode === w.scheme_code
                return (
                  <div
                    key={w.scheme_code}
                    className={`card p-3.5 transition-all border ${
                      isExpanded
                        ? 'border-indigo-500 bg-slate-800 ring-1 ring-indigo-500/30'
                        : 'border-slate-700/60 bg-slate-800 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div
                        onClick={() => toggleExpandWatchlist(w)}
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
                          {isExpanded ? '▲ Tap to collapse' : '▼ Tap to view Scorecard & 200 EMA'}
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => toggleExpandWatchlist(w)}
                          title={isExpanded ? 'Hide details' : 'View scorecard & chart'}
                          className={`rounded-lg border text-xs font-semibold px-2.5 py-1.5 flex items-center gap-1 transition-all ${
                            isExpanded
                              ? 'bg-indigo-600 border-indigo-500 text-white'
                              : 'bg-indigo-600/20 border-indigo-500/30 text-indigo-300 hover:bg-indigo-600 hover:text-white'
                          }`}
                        >
                          {isExpanded ? (
                            <>Hide <ChevronUp className="w-3.5 h-3.5" /></>
                          ) : (
                            <>View <ChevronDown className="w-3.5 h-3.5" /></>
                          )}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            removeFromWatchlist(w.scheme_code)
                            if (expandedWlCode === w.scheme_code) {
                              setExpandedWlCode(null)
                              setWlScorecard(null)
                              setWlNavData([])
                            }
                          }}
                          title="Remove from watchlist"
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {/* Inline Expandable Scorecard & NAV Chart just under THIS exact fund */}
                    {isExpanded && (
                      <div className="mt-3.5 pt-3.5 border-t border-slate-700/80 space-y-3">
                        {wlLoadingFund && (
                          <div className="text-center py-6">
                            <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                            <p className="text-xs text-slate-400">Loading Scorecard &amp; 200-Day EMA…</p>
                          </div>
                        )}

                        {wlScorecard && !wlLoadingFund && (
                          <div className="space-y-3">
                            <div className="grid grid-cols-3 gap-2">
                              <MetricBox label="CAGR 1Y" value={fmtPct(wlScorecard.cagr_1y)} color={wlScorecard.cagr_1y > 0 ? 'text-green-400' : 'text-red-400'} />
                              <MetricBox label="CAGR 3Y" value={fmtPct(wlScorecard.cagr_3y)} color={wlScorecard.cagr_3y > 0 ? 'text-green-400' : 'text-red-400'} />
                              <MetricBox label="CAGR 5Y" value={fmtPct(wlScorecard.cagr_5y)} color={wlScorecard.cagr_5y > 0 ? 'text-green-400' : 'text-red-400'} />
                              <MetricBox label="Sharpe" value={fmt(wlScorecard.sharpe)} />
                              <MetricBox label="Max DD" value={fmtPct(wlScorecard.max_drawdown)} color="text-red-400" />
                              <MetricBox label="Alpha" value={fmtPct(wlScorecard.alpha)} color={wlScorecard.alpha > 0 ? 'text-green-400' : 'text-red-400'} />
                              <MetricBox label="Beta" value={fmt(wlScorecard.beta)} />
                              <MetricBox label="Up Cap" value={fmtPct(wlScorecard.up_capture)} color="text-green-400" />
                              <MetricBox label="Dn Cap" value={fmtPct(wlScorecard.down_capture)} color="text-red-400" />
                            </div>
                            <div className="flex items-center justify-between bg-slate-900 rounded-xl px-4 py-2.5">
                              <span className="text-slate-400 text-xs">Overall Grade</span>
                              <span className={`text-xl font-black ${(wlScorecard.overall_score ?? 60) > 65 ? 'text-green-400' : (wlScorecard.overall_score ?? 60) > 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                                {wlScorecard.grade || 'A'}
                              </span>
                            </div>
                          </div>
                        )}

                        {wlNavData.length > 0 && !wlLoadingFund && (
                          <div className="bg-slate-900/90 rounded-xl p-3 border border-slate-700/60">
                            <p className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-2">
                              <TrendingUp className="w-3.5 h-3.5 text-indigo-400" /> NAV + 200-Day EMA
                            </p>
                            <ResponsiveContainer width="100%" height={180}>
                              <LineChart data={wlNavData.slice(-60)}>
                                <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#64748b' }} tickLine={false} />
                                <YAxis tick={{ fontSize: 9, fill: '#64748b' }} tickLine={false} axisLine={false} width={35} />
                                <Tooltip
                                  contentStyle={{ background: '#1e293b', border: '1px solid #475569', borderRadius: 8, fontSize: 11 }}
                                  labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                                  itemStyle={{ fontSize: 11 }}
                                />
                                <Line type="monotone" dataKey="nav" stroke="#6366f1" dot={false} strokeWidth={2} name="NAV" />
                                <Line type="monotone" dataKey="ema200" stroke="#f59e0b" dot={false} strokeWidth={1.5} strokeDasharray="4 2" name="200 EMA" />
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        )}

                        {/* Probabilistic Monte Carlo Forecast */}
                        <MonteCarloFanChart
                          schemeCode={Number(w.scheme_code)}
                          schemeName={w.scheme_name}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Category Thermometer ──────────────────── */}
      {activeSection === 'thermo' && (
        <div className="space-y-3">
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="section-title mb-0 flex items-center gap-2">
                  <ThermIcon className="w-4 h-4 text-indigo-400" />
                  {watchlist.length > 0
                    ? `Watchlist Valuation Thermometer (${watchlist.length} Fund${watchlist.length > 1 ? 's' : ''})`
                    : 'Category Valuation Thermometer'}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Live heat-map indicating whether your mutual funds are historically cheap (Bargain) or expensive (Bubble risk).
                </p>
              </div>
              <button
                onClick={loadThermometer}
                disabled={thermoLoading}
                className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 py-1.5 px-3 rounded-lg bg-slate-800 border border-slate-700 transition-colors"
                title="Refresh temperatures"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${thermoLoading ? 'animate-spin' : ''}`} />
                {thermoLoading ? 'Updating…' : 'Refresh'}
              </button>
            </div>

            {watchlist.length === 0 && (
              <div className="bg-amber-950/30 border border-amber-800/40 rounded-xl p-3 my-2 text-xs text-amber-300 flex items-center justify-between">
                <span>⭐ You have 0 funds in your Watchlist. Showing benchmark funds below. Click <strong>+ Watch</strong> in Fund Search to add your favorite funds!</span>
                <button
                  onClick={() => setActiveSection('search')}
                  className="px-2.5 py-1 rounded-lg bg-amber-600 text-white font-semibold text-[11px] shrink-0 ml-2"
                >
                  Search Funds
                </button>
              </div>
            )}
          </div>

          {thermoLoading && watchlistThermos.length === 0 ? (
            <div className="card text-center py-12">
              <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-slate-300">Evaluating valuation temperatures…</p>
              <p className="text-xs text-slate-500 mt-1">Analyzing 3-year rolling returns and 10-year percentile valuation rank.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {watchlistThermos.map((t) => {
                const isOverheated = t.temperature >= 80
                const isHot = t.temperature >= 60 && t.temperature < 80
                const isWarm = t.temperature >= 40 && t.temperature < 60

                const badgeBg = isOverheated
                  ? 'bg-red-950/60 border-red-800 text-red-300'
                  : isHot
                  ? 'bg-amber-950/60 border-amber-800 text-amber-300'
                  : isWarm
                  ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                  : 'bg-cyan-950/60 border-cyan-800 text-cyan-300'

                const barColor = isOverheated
                  ? 'bg-gradient-to-r from-amber-500 to-red-500'
                  : isHot
                  ? 'bg-gradient-to-r from-yellow-500 to-amber-500'
                  : isWarm
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  : 'bg-gradient-to-r from-blue-500 to-cyan-400'

                return (
                  <div key={t.scheme_code} className="card border-slate-700/80 bg-slate-900/90 shadow-lg">
                    {/* Header */}
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-indigo-300 border border-slate-700">
                            {t.category}
                          </span>
                          {watchlist.some((w) => w.scheme_code === t.scheme_code) && (
                            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-950/50 text-amber-400 border border-amber-800 flex items-center gap-1">
                              <Star className="w-2.5 h-2.5 fill-amber-400" /> Watchlist
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-slate-100 leading-snug truncate">
                          {t.scheme_name}
                        </h4>
                      </div>

                      {/* Temperature Badge */}
                      <div className={`px-3 py-1.5 rounded-xl border text-right shrink-0 ${badgeBg}`}>
                        <div className="flex items-center gap-1.5 justify-end">
                          <span className="text-base">{t.emoji}</span>
                          <span className="text-sm font-extrabold font-mono">{t.temperature.toFixed(0)}°</span>
                        </div>
                        <p className="text-[10px] font-bold tracking-wider uppercase mt-0.5">{t.label}</p>
                      </div>
                    </div>

                    {/* Progress Bar / Temperature Gauge */}
                    <div className="my-3">
                      <div className="h-2.5 w-full bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                          style={{ width: `${Math.max(6, Math.min(100, t.temperature))}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-[10px] text-slate-500 font-medium mt-1">
                        <span>0° Freezing (Bargain)</span>
                        <span>40° WARM</span>
                        <span>70° HOT</span>
                        <span>100° OVERHEATED (Peak)</span>
                      </div>
                    </div>

                    {/* Metrics row */}
                    <div className="grid grid-cols-3 gap-2 my-2 text-center">
                      <div className="bg-slate-800/60 rounded-xl py-2 px-1 border border-slate-800">
                        <span className="text-[10px] text-slate-400 block">3Y CAGR</span>
                        <span className="text-xs font-bold text-slate-200">
                          {isNaN(t.cagr_3y) ? '—' : fmtPct(t.cagr_3y * 100)}
                        </span>
                      </div>
                      <div className="bg-slate-800/60 rounded-xl py-2 px-1 border border-slate-800">
                        <span className="text-[10px] text-slate-400 block">Valuation Percentile</span>
                        <span className="text-xs font-bold text-indigo-300">
                          {t.cagr_3y_percentile ? `${t.cagr_3y_percentile.toFixed(0)}th pct` : '50th pct'}
                        </span>
                      </div>
                      <div className="bg-slate-800/60 rounded-xl py-2 px-1 border border-slate-800">
                        <span className="text-[10px] text-slate-400 block">Drawdown Recovery</span>
                        <span className="text-xs font-bold text-slate-200">
                          {t.in_recovery ? `${t.recovery_pct.toFixed(0)}% recovered` : 'At All-Time High'}
                        </span>
                      </div>
                    </div>

                    {/* Recommendations */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
                      <div className="bg-slate-800/50 rounded-xl p-2.5 border border-slate-700/60">
                        <p className="text-[11px] font-semibold text-slate-400 mb-0.5 flex items-center gap-1">
                          📅 Monthly SIP Recommendation
                        </p>
                        <p className="text-xs font-medium text-slate-200 leading-relaxed">{t.sip_recommendation}</p>
                      </div>

                      <div className="bg-slate-800/50 rounded-xl p-2.5 border border-slate-700/60">
                        <p className="text-[11px] font-semibold text-slate-400 mb-0.5 flex items-center gap-1">
                          💰 Lump Sum Recommendation
                        </p>
                        <p className="text-xs font-medium text-slate-200 leading-relaxed">{t.lumpsum_recommendation}</p>
                      </div>
                    </div>

                    {/* Rationale */}
                    <div className="mt-2.5 bg-slate-950/60 rounded-xl p-2.5 border border-slate-800/80 text-xs text-slate-400 leading-relaxed">
                      💡 <strong className="text-slate-300">Why this score:</strong> {t.rationale}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Backtest ──────────────────────────────── */}
      {activeSection === 'backtest' && (
        <div className="space-y-3">
          {/* Controls Card */}
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="section-title mb-0 flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-indigo-400" />
                  SIP Strategy Backtester
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Historical simulation: Traditional Static SIP vs Antigravity Dynamic AI Timing SIP.
                </p>
              </div>
              {btSelectedFund && (
                <button
                  type="button"
                  onClick={() => runBacktest(btSelectedFund.scheme_code, btMonthly, btYears)}
                  disabled={btLoading}
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 py-1.5 px-3 rounded-lg bg-slate-800 border border-slate-700 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${btLoading ? 'animate-spin' : ''}`} />
                  {btLoading ? 'Simulating…' : 'Re-run'}
                </button>
              )}
            </div>

            {/* Quick Watchlist Fund Selector */}
            <div className="mt-3">
              <label className="text-xs text-slate-400 font-medium block mb-1.5 flex items-center gap-1">
                <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" /> Select Fund to Backtest:
              </label>

              {watchlist.length > 0 && (
                <div className="flex gap-1.5 overflow-x-auto pb-1 mb-2.5">
                  {watchlist.map((w) => {
                    const isSelected = btSelectedFund?.scheme_code === w.scheme_code
                    return (
                      <button
                        key={w.scheme_code}
                        type="button"
                        onClick={() => selectBtFund(w)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shrink-0 flex items-center gap-1.5 ${
                          isSelected
                            ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30'
                            : 'bg-slate-800 text-slate-300 border-slate-700 hover:border-slate-600'
                        }`}
                      >
                        <Star className={`w-3 h-3 ${isSelected ? 'fill-white text-white' : 'fill-amber-400 text-amber-400'}`} />
                        <span className="truncate max-w-[180px]">{w.scheme_name}</span>
                      </button>
                    )
                  })}
                </div>
              )}

              {/* In-tab Search input */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  className="input pl-9 text-xs"
                  placeholder="Or search any other mutual fund to backtest…"
                  value={btSearchQuery}
                  onChange={(e) => handleBtSearchChange(e.target.value)}
                />
                {btSearching && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 animate-pulse">
                    searching…
                  </span>
                )}
                {/* Search Dropdown */}
                {btSuggestions.length > 0 && (
                  <div className="absolute z-20 left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden shadow-2xl max-h-52 overflow-y-auto">
                    {btSuggestions.map((f: any) => {
                      const code = Number(f.scheme_code || f.schemeCode)
                      const name = f.scheme_name || f.schemeName
                      return (
                        <button
                          key={code}
                          type="button"
                          onClick={() => selectBtFund(f)}
                          className="w-full text-left px-3 py-2 hover:bg-slate-700 border-b border-slate-700/50 last:border-0"
                        >
                          <p className="text-xs font-medium text-slate-200 truncate">{name}</p>
                          <p className="text-[10px] text-slate-400">{f.scheme_category || f.fund_house || 'Equity'}</p>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Simulation Parameters */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 pt-3 border-t border-slate-800">
              {/* Monthly Amount */}
              <div>
                <label className="text-xs text-slate-400 font-medium block mb-1">
                  Monthly SIP Amount (₹)
                </label>
                <div className="flex gap-1.5">
                  {[2500, 5000, 10000, 25000].map((amt) => (
                    <button
                      key={amt}
                      type="button"
                      onClick={() => {
                        setBtMonthly(amt)
                        if (btSelectedFund) runBacktest(btSelectedFund.scheme_code, amt, btYears)
                      }}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                        btMonthly === amt
                          ? 'bg-indigo-600 text-white border-indigo-500'
                          : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
                      }`}
                    >
                      ₹{(amt / 1000).toFixed(0)}k
                    </button>
                  ))}
                </div>
              </div>

              {/* Time Horizon */}
              <div>
                <label className="text-xs text-slate-400 font-medium block mb-1">
                  Backtest Duration
                </label>
                <div className="flex gap-1.5">
                  {[1, 3, 5, 10].map((yr) => (
                    <button
                      key={yr}
                      type="button"
                      onClick={() => {
                        setBtYears(yr)
                        if (btSelectedFund) runBacktest(btSelectedFund.scheme_code, btMonthly, yr)
                      }}
                      className={`flex-1 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                        btYears === yr
                          ? 'bg-indigo-600 text-white border-indigo-500'
                          : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
                      }`}
                    >
                      {yr} Year{yr > 1 ? 's' : ''}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Results Display */}
          {btLoading ? (
            <div className="card text-center py-12">
              <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold text-slate-300">Simulating SIP strategies…</p>
              <p className="text-xs text-slate-500 mt-1">
                Testing {btYears} years of monthly cash flows against 200-day EMA market signals.
              </p>
            </div>
          ) : backtestData ? (
            <div className="space-y-3">
              {/* Fund Title & Overall Invested */}
              <div className="card bg-slate-900 border-slate-800">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-indigo-300 border border-slate-700">
                      {backtestData.category || btSelectedFund?.category || 'Equity'}
                    </span>
                    <h3 className="text-base font-bold text-white mt-1">
                      {backtestData.scheme_name || btSelectedFund?.scheme_name}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Backtested over <strong>{backtestData.years_backtested || btYears} Years</strong> at <strong>₹{(backtestData.monthly_amount || btMonthly).toLocaleString('en-IN')}/month</strong>
                    </p>
                  </div>
                  <div className="text-right shrink-0 bg-slate-800/80 px-3 py-2 rounded-xl border border-slate-700">
                    <span className="text-[11px] text-slate-400 block">Total Invested</span>
                    <span className="text-sm font-bold text-white font-mono">
                      {fmtINR(backtestData.total_invested || (backtestData.static_sip?.total_invested) || ((backtestData.monthly_amount || btMonthly) * 12 * btYears))}
                    </span>
                  </div>
                </div>
              </div>

              {/* Side-by-Side Strategy Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Static Regular SIP */}
                <div className="card bg-slate-900/90 border-slate-800">
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-800">
                    <span className="text-xs font-bold text-slate-300">1. Traditional Static SIP</span>
                    <span className="text-[10px] text-slate-400 px-2 py-0.5 rounded bg-slate-800">Fixed 1st of month</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Final Corpus:</span>
                      <span className="text-base font-bold text-slate-100 font-mono">
                        {fmtINR(backtestData.static_final_value || backtestData.static_sip?.final_corpus || 0)}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Annualized XIRR:</span>
                      <span className="text-sm font-bold text-indigo-400 font-mono">
                        {fmtPct((backtestData.static_xirr || backtestData.static_sip?.xirr || 0) * 100)}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Total Profit:</span>
                      <span className="text-sm font-bold text-emerald-400 font-mono">
                        +{fmtINR((backtestData.static_final_value || backtestData.static_sip?.final_corpus || 0) - (backtestData.total_invested || backtestData.static_sip?.total_invested || 0))}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Dynamic Smart SIP */}
                <div className="card bg-indigo-950/30 border-indigo-700/50 relative overflow-hidden">
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-indigo-800/50">
                    <span className="text-xs font-bold text-indigo-300 flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 text-yellow-400" /> 2. Dynamic Timing SIP
                    </span>
                    <span className="text-[10px] text-indigo-300 px-2 py-0.5 rounded bg-indigo-900/60 font-semibold">
                      Antigravity AI Timing
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Final Corpus:</span>
                      <span className="text-base font-bold text-emerald-400 font-mono">
                        {fmtINR(backtestData.dynamic_final_value || backtestData.dynamic_sip?.final_corpus || 0)}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Annualized XIRR:</span>
                      <span className="text-sm font-bold text-emerald-400 font-mono">
                        {fmtPct((backtestData.dynamic_xirr || backtestData.dynamic_sip?.xirr || 0) * 100)}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline">
                      <span className="text-xs text-slate-400">Total Profit:</span>
                      <span className="text-sm font-bold text-emerald-400 font-mono">
                        +{fmtINR((backtestData.dynamic_final_value || backtestData.dynamic_sip?.final_corpus || 0) - (backtestData.total_invested || backtestData.dynamic_sip?.total_invested || 0))}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Verdict Card */}
              <div className="card bg-slate-900 border-slate-700 p-4">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-emerald-400" /> Strategy Verdict & Analysis
                </h4>
                <p className="text-sm text-slate-200 leading-relaxed font-medium">
                  {backtestData.verdict || backtestData.comparison?.verdict || 'Simulation complete.'}
                </p>

                {/* Extra Return Highlight */}
                {backtestData.extra_gain !== undefined && (
                  <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Net Wealth Difference:</span>
                    <span className={`font-bold font-mono text-sm ${backtestData.extra_gain >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {backtestData.extra_gain >= 0 ? `+${fmtINR(backtestData.extra_gain)} Extra Corpus` : `${fmtINR(backtestData.extra_gain)} Difference`}
                    </span>
                  </div>
                )}
              </div>

              {/* Educational How it Works */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 text-xs text-slate-400 space-y-1">
                <p className="font-semibold text-slate-300">How Dynamic SIP Timing Works:</p>
                <p>• <strong>Deep Dips (&lt; -15% of 200 EMA):</strong> Deploys 2.0× SIP to buy aggressively at deep market discounts.</p>
                <p>• <strong>Normal Range (±5% of 200 EMA):</strong> Deploys normal 1.0× monthly budget.</p>
                <p>• <strong>Overheated (&gt; +15% of 200 EMA):</strong> Deploys 0.5× and preserves dry powder cash for the next market dip.</p>
              </div>

              {/* Forward-Looking Probabilistic Monte Carlo Forecast */}
              {btSelectedFund && (
                <MonteCarloFanChart
                  schemeCode={btSelectedFund.scheme_code}
                  schemeName={btSelectedFund.scheme_name}
                />
              )}
            </div>
          ) : (
            <div className="card text-center py-10 text-slate-500">
              <BarChart2 className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p className="text-sm font-semibold text-slate-400">Select a mutual fund above to run the backtest</p>
            </div>
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

