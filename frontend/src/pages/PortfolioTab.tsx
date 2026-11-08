import React, { useEffect, useState, useRef, useCallback } from 'react'
import { portfolioAPI, analyticsAPI, plannerAPI, fundsAPI } from '../lib/api'
import { Holding, DudFund, TaxSummary } from '../types'
import { fmtINR, fmtPct, dudColor, colorForValue } from '../lib/utils'
import {
  Upload, FileText, Lock, ChevronDown, ChevronUp, Download, AlertTriangle,
  Plus, X, Search, CheckCircle, Trash2, Calendar, TrendingUp, RefreshCw,
  Clock, Info, Sparkles
} from 'lucide-react'
import BlackSwanStressTester from '../components/BlackSwanStressTester'
import MonteCarloFanChart from '../components/MonteCarloFanChart'

// ── Manual Add Fund types ──────────────────────────────────────────────
interface FundSearchResult { scheme_code: number; scheme_name: string; category?: string }

type EntryMode = 'date' | 'current_value' | 'units'

interface ManualForm {
  fundQuery: string
  selectedFund: FundSearchResult | null
  investedAmount: string
  investmentDate: string
  investmentType: 'SIP' | 'LUMPSUM'
  entryMode: EntryMode
  currentValue: string
  units: string
}

interface PreviewCalc {
  histNav: number
  latestNav: number
  histDate: string
  units: number
  currentValue: number
  gainLoss: number
  gainPct: number
  cagr: number | null
  loading: boolean
}

const emptyForm = (): ManualForm => ({
  fundQuery: '',
  selectedFund: null,
  investedAmount: '',
  investmentDate: new Date().toISOString().split('T')[0],
  investmentType: 'LUMPSUM',
  entryMode: 'date',
  currentValue: '',
  units: '',
})

export default function PortfolioTab() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [duds, setDuds] = useState<DudFund[]>([])
  const [taxData, setTaxData] = useState<TaxSummary | null>(null)
  const [xray, setXray] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [casLoading, setCasLoading] = useState(false)
  const [pan, setPan] = useState('')
  const [showPanInput, setShowPanInput] = useState(false)
  const [expandedFund, setExpandedFund] = useState<number | null>(null)
  const [casError, setCasError] = useState<string | null>(null)
  const [showTax, setShowTax] = useState(false)
  const [refreshingNavs, setRefreshingNavs] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // ── Delete Confirmation state ───────────────────────────────────────
  const [fundToDelete, setFundToDelete] = useState<Holding | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  // ── Manual Add Fund state ──────────────────────────────────────────
  const [showManual, setShowManual] = useState(false)
  const [manualForm, setManualForm] = useState<ManualForm>(emptyForm())
  const [fundSuggestions, setFundSuggestions] = useState<FundSearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [manualLoading, setManualLoading] = useState(false)
  const [manualError, setManualError] = useState<string | null>(null)
  const [manualSuccess, setManualSuccess] = useState<string | null>(null)
  const [previewCalc, setPreviewCalc] = useState<PreviewCalc | null>(null)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const calcTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadHoldings = async () => {
    setLoading(true)
    try {
      const [h, d, x] = await Promise.allSettled([
        portfolioAPI.holdings(),
        analyticsAPI.dudScan(),
        portfolioAPI.xray([]),
      ])
      if (h.status === 'fulfilled') setHoldings(h.value.data?.holdings || h.value.data || [])
      if (d.status === 'fulfilled') setDuds(Array.isArray(d.value.data) ? d.value.data : [d.value.data])
      if (x.status === 'fulfilled') setXray(x.value.data)
    } finally {
      setLoading(false)
    }
  }

  const handleRefreshNavs = async () => {
    setRefreshingNavs(true)
    try {
      await loadHoldings()
    } finally {
      setRefreshingNavs(false)
    }
  }

  const loadTax = async () => {
    try {
      const { data } = await plannerAPI.taxPack()
      setTaxData(data)
      setShowTax(true)
    } catch { /* ignore */ }
  }

  useEffect(() => { loadHoldings() }, [])

  // ── Calculate CAGR Helper ──────────────────────────────────────────
  const calcCAGR = (invested: number, currentVal: number, dateStr: string): number | null => {
    if (!dateStr || invested <= 0 || currentVal <= 0) return null
    const diffYears = (Date.now() - new Date(dateStr).getTime()) / (365.25 * 24 * 3600 * 1000)
    if (diffYears < 0.25) return null
    return (Math.pow(currentVal / invested, 1 / diffYears) - 1) * 100
  }

  // ── Real-time Growth & Units Preview Calculator ─────────────────────
  const updatePreview = useCallback(async (form: ManualForm) => {
    if (!form.selectedFund) {
      setPreviewCalc(null)
      return
    }

    const invested = parseFloat(form.investedAmount)
    if (!invested || invested <= 0) {
      setPreviewCalc(null)
      return
    }

    const schemeCode = form.selectedFund.scheme_code

    try {
      if (form.entryMode === 'date') {
        const { data } = await fundsAPI.navOnDate(schemeCode, form.investmentDate)
        const histNav = Number(data.nav) || 10
        const latestNav = Number(data.latest_nav) || histNav
        const units = invested / histNav
        const currentVal = units * latestNav
        const gainLoss = currentVal - invested
        const gainPct = (gainLoss / invested) * 100
        const cagr = calcCAGR(invested, currentVal, form.investmentDate)

        setPreviewCalc({
          histNav,
          latestNav,
          histDate: data.matched_date || form.investmentDate,
          units,
          currentValue: currentVal,
          gainLoss,
          gainPct,
          cagr,
          loading: false,
        })
      } else if (form.entryMode === 'current_value') {
        const { data: latestData } = await fundsAPI.latestNav(schemeCode)
        const latestNav = Number(latestData?.nav || latestData?.latest_nav) || 10
        const currentVal = parseFloat(form.currentValue) || invested
        const units = currentVal / latestNav
        const histNav = invested / units
        const gainLoss = currentVal - invested
        const gainPct = (gainLoss / invested) * 100
        const cagr = calcCAGR(invested, currentVal, form.investmentDate)

        setPreviewCalc({
          histNav,
          latestNav,
          histDate: form.investmentDate,
          units,
          currentValue: currentVal,
          gainLoss,
          gainPct,
          cagr,
          loading: false,
        })
      } else if (form.entryMode === 'units') {
        const { data: latestData } = await fundsAPI.latestNav(schemeCode)
        const latestNav = Number(latestData?.nav || latestData?.latest_nav) || 10
        const units = parseFloat(form.units) || 1
        const currentVal = units * latestNav
        const histNav = invested / units
        const gainLoss = currentVal - invested
        const gainPct = (gainLoss / invested) * 100
        const cagr = calcCAGR(invested, currentVal, form.investmentDate)

        setPreviewCalc({
          histNav,
          latestNav,
          histDate: form.investmentDate,
          units,
          currentValue: currentVal,
          gainLoss,
          gainPct,
          cagr,
          loading: false,
        })
      }
    } catch {
      setPreviewCalc(null)
    }
  }, [])

  // Debounce preview calculations on input change
  useEffect(() => {
    if (calcTimer.current) clearTimeout(calcTimer.current)
    if (manualForm.selectedFund && manualForm.investedAmount) {
      calcTimer.current = setTimeout(() => {
        updatePreview(manualForm)
      }, 350)
    } else {
      setPreviewCalc(null)
    }
  }, [manualForm, updatePreview])

  // ── Fund search with debounce ──────────────────────────────────────
  const searchFunds = useCallback((q: string) => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!q || q.length < 2) { setFundSuggestions([]); return }
    searchTimer.current = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const { data } = await fundsAPI.search(q)
        const raw = data?.results || (Array.isArray(data) ? data : [])
        const normalized: FundSearchResult[] = raw.map((item: any) => ({
          scheme_code: Number(item.scheme_code || item.schemeCode),
          scheme_name: item.scheme_name || item.schemeName,
          category: item.category || item.scheme_category || 'Equity'
        }))
        setFundSuggestions(normalized.slice(0, 8))
      } catch { setFundSuggestions([]) }
      finally { setSearchLoading(false) }
    }, 300)
  }, [])

  const handleFundQueryChange = (q: string) => {
    setManualForm((f) => ({ ...f, fundQuery: q, selectedFund: null }))
    searchFunds(q)
  }

  const selectFund = (fund: FundSearchResult) => {
    setManualForm((f) => ({ ...f, selectedFund: fund, fundQuery: fund.scheme_name }))
    setFundSuggestions([])
  }

  const setDatePreset = (yearsAgo: number) => {
    const d = new Date()
    if (yearsAgo === 0) {
      setManualForm((f) => ({ ...f, investmentDate: d.toISOString().split('T')[0] }))
      return
    }
    d.setFullYear(d.getFullYear() - yearsAgo)
    setManualForm((f) => ({ ...f, investmentDate: d.toISOString().split('T')[0] }))
  }

  // ── Existing fund accumulation check ──────────────────────────────
  const existingHolding = holdings.find(
    (h) => h.scheme_code === manualForm.selectedFund?.scheme_code
  )

  const handleManualSubmit = async () => {
    setManualError(null)
    if (!manualForm.selectedFund) return setManualError('Please search and select a mutual fund.')
    const amount = parseFloat(manualForm.investedAmount)
    if (!amount || amount <= 0) return setManualError('Enter a valid invested amount.')

    setManualLoading(true)
    try {
      const payload: any = {
        scheme_code: manualForm.selectedFund.scheme_code,
        scheme_name: manualForm.selectedFund.scheme_name,
        invested_amount: amount,
        investment_date: manualForm.investmentDate,
        investment_type: manualForm.investmentType,
        category: manualForm.selectedFund.category || 'Equity',
      }

      if (previewCalc && previewCalc.units > 0) {
        payload.units = previewCalc.units
        payload.avg_nav = previewCalc.histNav
        payload.current_value = previewCalc.currentValue
      } else {
        const { data: navData } = await fundsAPI.latestNav(manualForm.selectedFund.scheme_code)
        const nav = navData?.nav || navData?.latest_nav || 10
        payload.units = amount / nav
        payload.avg_nav = nav
        payload.current_value = amount
      }

      const res = await portfolioAPI.addHolding(payload)
      const actionMsg = res.data?.action === 'accumulated'
        ? `Investment merged! Updated total value: ${fmtINR(res.data?.holding?.current_value || 0)}`
        : 'Fund added to portfolio successfully!'

      setManualSuccess(actionMsg)
      setTimeout(() => {
        setManualSuccess(null)
        setShowManual(false)
        setManualForm(emptyForm())
        setFundSuggestions([])
        setPreviewCalc(null)
        loadHoldings()
      }, 1500)
    } catch (err: any) {
      setManualError(err.response?.data?.detail || 'Failed to add fund. Please try again.')
    } finally {
      setManualLoading(false)
    }
  }

  // ── Delete Holding ─────────────────────────────────────────────────
  const handleConfirmDelete = async () => {
    if (!fundToDelete) return
    setDeleteLoading(true)
    try {
      await portfolioAPI.deleteHolding(fundToDelete.scheme_code)
      setFundToDelete(null)
      await loadHoldings()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to remove fund.')
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setCasLoading(true)
    setCasError(null)
    try {
      await portfolioAPI.uploadCAS(file, pan || undefined)
      await loadHoldings()
      setPan('')
    } catch (err: any) {
      setCasError(err.response?.data?.detail || 'Upload failed. Check your PDF/PAN.')
    } finally {
      setCasLoading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const totalInvested = holdings.reduce((s, h) => s + (h.invested || 0), 0)
  const totalValue = holdings.reduce((s, h) => s + (h.current_value || 0), 0)
  const totalGain = totalValue - totalInvested

  return (
    <div className="space-y-4 pb-6">
      {/* ── CAS Upload ───────────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <FileText className="w-4 h-4 text-indigo-400" /> Import Portfolio via CAS
        </p>
        <p className="text-xs text-slate-500 mb-3">
          Upload your CAMS/KFintech CAS PDF statement. All holdings and past transactions are automatically imported.
        </p>

        <button
          onClick={() => setShowPanInput((p) => !p)}
          className="flex items-center gap-1 text-xs text-yellow-400 mb-2 hover:text-yellow-300"
        >
          <Lock className="w-3 h-3" />
          {showPanInput ? 'Hide PAN field' : 'PDF is PAN-encrypted? Enter PAN'}
        </button>

        {showPanInput && (
          <div className="mb-3">
            <input
              className="input"
              placeholder="Enter PAN (e.g. ABCDE1234F) — used only in memory"
              value={pan}
              onChange={(e) => setPan(e.target.value.toUpperCase())}
              maxLength={10}
            />
            <p className="text-xs text-slate-600 mt-1 flex items-center gap-1">
              <Lock className="w-3 h-3" /> Zero-retention: PAN is discarded immediately after parsing.
            </p>
          </div>
        )}

        <button
          onClick={() => fileRef.current?.click()}
          className="btn-secondary w-full flex items-center justify-center gap-2"
          disabled={casLoading}
        >
          <Upload className="w-4 h-4" />
          {casLoading ? 'Parsing PDF…' : 'Upload CAS PDF'}
        </button>
        <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
        {casError && (
          <p className="text-red-400 text-xs mt-2 bg-red-900/20 rounded-lg px-3 py-2">{casError}</p>
        )}
      </div>

      {/* ── Add Fund Manually (Enhanced) ─────────── */}
      <div className="card">
        <button
          onClick={() => { setShowManual((p) => !p); setManualError(null); setManualSuccess(null) }}
          className="flex items-center justify-between w-full"
        >
          <span className="section-title mb-0 flex items-center gap-2">
            <Plus className="w-4 h-4 text-indigo-400" /> Add Fund Manually
          </span>
          {showManual
            ? <X className="w-4 h-4 text-slate-400" />
            : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>

        {showManual && (
          <div className="mt-4 space-y-3.5">
            <p className="text-xs text-slate-400 leading-relaxed">
              Add any mutual fund investment. If you bought it years ago, select your investment date or today's value and the app will automatically calculate your total units, profit, and percentage growth.
            </p>

            {/* 1. Fund Search */}
            <div className="relative">
              <label className="text-xs text-slate-400 mb-1 block font-medium">1. Select Mutual Fund</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  className="input pl-9"
                  placeholder="Search fund (e.g. Nippon India Small Cap, Motilal Oswal Midcap)…"
                  value={manualForm.fundQuery}
                  onChange={(e) => handleFundQueryChange(e.target.value)}
                />
                {searchLoading && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 animate-pulse">
                    searching…
                  </span>
                )}
              </div>
              {/* Dropdown */}
              {fundSuggestions.length > 0 && (
                <div className="absolute z-20 left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-700 rounded-xl overflow-hidden shadow-2xl max-h-56 overflow-y-auto">
                  {fundSuggestions.map((f) => (
                    <button
                      key={f.scheme_code}
                      onMouseDown={() => selectFund(f)}
                      className="w-full text-left px-3 py-2.5 hover:bg-slate-700 transition-colors border-b border-slate-700/50 last:border-0"
                    >
                      <p className="text-sm text-slate-100 font-medium leading-tight">{f.scheme_name}</p>
                      {f.category && <p className="text-xs text-indigo-400 mt-0.5">{f.category}</p>}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selected fund badge */}
            {manualForm.selectedFund && (
              <div className="flex items-center gap-2 bg-indigo-950/60 border border-indigo-700/60 rounded-xl px-3 py-2.5">
                <CheckCircle className="w-4 h-4 text-indigo-400 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-indigo-300 font-semibold truncate">{manualForm.selectedFund.scheme_name}</p>
                  <p className="text-[11px] text-slate-400">AMFI Code: {manualForm.selectedFund.scheme_code}</p>
                </div>
              </div>
            )}

            {/* Existing Fund Auto-Accumulation Alert */}
            {existingHolding && (
              <div className="bg-indigo-900/30 border border-indigo-600/50 rounded-xl p-3 text-xs space-y-1.5">
                <div className="flex items-center gap-1.5 font-semibold text-indigo-300">
                  <Sparkles className="w-4 h-4 text-yellow-400" />
                  Auto-Accumulate into Existing Balance
                </div>
                <p className="text-slate-300 leading-normal">
                  You already have this fund in your portfolio! Entering this new amount will automatically add to your existing holding.
                </p>
                <div className="flex items-center justify-between pt-1 border-t border-indigo-800/40 text-[11px]">
                  <span className="text-slate-400">Current Value: <strong className="text-white">{fmtINR(existingHolding.current_value)}</strong></span>
                  <span className="text-emerald-400 font-semibold">
                    New Value: {fmtINR(existingHolding.current_value + (previewCalc?.currentValue || parseFloat(manualForm.investedAmount) || 0))}
                  </span>
                </div>
              </div>
            )}

            {/* 2. Invested Amount */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block font-medium">2. Invested Amount (₹)</label>
              <input
                className="input"
                type="number"
                placeholder="e.g. 25000"
                value={manualForm.investedAmount}
                onChange={(e) => setManualForm((f) => ({ ...f, investedAmount: e.target.value }))}
                min={1}
              />
            </div>

            {/* 3. When did you invest? */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-slate-400 font-medium flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-indigo-400" /> 3. When did you invest?
                </label>
                <span className="text-[11px] text-slate-500">Pick date or quick preset</span>
              </div>

              {/* Quick Presets */}
              <div className="flex gap-1.5 mb-2 overflow-x-auto pb-0.5">
                {[
                  { label: 'Today', years: 0 },
                  { label: '1Y Ago', years: 1 },
                  { label: '3Y Ago', years: 3 },
                  { label: '5Y Ago', years: 5 },
                  { label: '10Y Ago', years: 10 },
                ].map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => setDatePreset(preset.years)}
                    className="px-2.5 py-1 text-xs rounded-lg bg-slate-800 text-slate-300 hover:bg-indigo-600 hover:text-white border border-slate-700 transition-colors whitespace-nowrap"
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              <input
                type="date"
                className="input text-sm"
                value={manualForm.investmentDate}
                max={new Date().toISOString().split('T')[0]}
                onChange={(e) => setManualForm((f) => ({ ...f, investmentDate: e.target.value }))}
              />
            </div>

            {/* 4. Entry Mode Selector */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block font-medium">
                4. Units & Valuation Mode
              </label>
              <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-900 rounded-xl">
                {[
                  { id: 'date', label: 'Auto (Date NAV)' },
                  { id: 'current_value', label: "Today's Value" },
                  { id: 'units', label: 'Exact Units' },
                ].map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    onClick={() => setManualForm((f) => ({ ...f, entryMode: mode.id as EntryMode }))}
                    className={`py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                      manualForm.entryMode === mode.id
                        ? 'bg-indigo-600 text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Optional Current Value input */}
            {manualForm.entryMode === 'current_value' && (
              <div>
                <label className="text-xs text-slate-400 mb-1 block">What is its value today? (₹)</label>
                <input
                  type="number"
                  className="input"
                  placeholder="e.g. 100000"
                  value={manualForm.currentValue}
                  onChange={(e) => setManualForm((f) => ({ ...f, currentValue: e.target.value }))}
                  min={1}
                />
              </div>
            )}

            {/* Optional Units input */}
            {manualForm.entryMode === 'units' && (
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Exact Units Owned</label>
                <input
                  type="number"
                  step="any"
                  className="input"
                  placeholder="e.g. 450.250"
                  value={manualForm.units}
                  onChange={(e) => setManualForm((f) => ({ ...f, units: e.target.value }))}
                  min={0.001}
                />
              </div>
            )}

            {/* Investment Type */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block font-medium">5. Investment Type</label>
              <div className="flex gap-2">
                {(['LUMPSUM', 'SIP'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setManualForm((f) => ({ ...f, investmentType: t }))}
                    className={`flex-1 py-2 rounded-xl text-xs font-semibold border transition-all ${
                      manualForm.investmentType === t
                        ? 'bg-indigo-600 border-indigo-500 text-white'
                        : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    {t === 'SIP' ? '📅 SIP' : '💰 One-time Lumpsum'}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Live Growth & Return Summary Card ──────── */}
            {previewCalc && (
              <div className="bg-slate-900 border border-slate-700/80 rounded-2xl p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-emerald-400" /> Calculated Growth & Valuation
                  </span>
                  <span className="text-[11px] text-slate-400">Live AMFI/MFAPI</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-slate-800/80 rounded-xl p-2.5">
                    <span className="text-[11px] text-slate-400">Invested Amount</span>
                    <p className="text-sm font-bold text-slate-100">{fmtINR(parseFloat(manualForm.investedAmount) || 0)}</p>
                    <span className="text-[10px] text-slate-500">Buy NAV: ₹{previewCalc.histNav.toFixed(2)}</span>
                  </div>

                  <div className="bg-slate-800/80 rounded-xl p-2.5">
                    <span className="text-[11px] text-slate-400">Current Value Today</span>
                    <p className="text-sm font-bold text-emerald-400">{fmtINR(previewCalc.currentValue)}</p>
                    <span className="text-[10px] text-slate-500">Live NAV: ₹{previewCalc.latestNav.toFixed(2)}</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t border-slate-800">
                  <div className="bg-slate-800/50 rounded-lg py-1.5 px-1">
                    <span className="text-[10px] text-slate-400 block">Total Profit</span>
                    <span className={`text-xs font-bold ${previewCalc.gainLoss >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {previewCalc.gainLoss >= 0 ? '+' : ''}{fmtINR(previewCalc.gainLoss)}
                    </span>
                  </div>

                  <div className="bg-slate-800/50 rounded-lg py-1.5 px-1">
                    <span className="text-[10px] text-slate-400 block">Total Return</span>
                    <span className={`text-xs font-bold ${previewCalc.gainPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {previewCalc.gainPct >= 0 ? '+' : ''}{previewCalc.gainPct.toFixed(1)}%
                    </span>
                  </div>

                  <div className="bg-slate-800/50 rounded-lg py-1.5 px-1">
                    <span className="text-[10px] text-slate-400 block">CAGR (p.a.)</span>
                    <span className="text-xs font-bold text-indigo-300">
                      {previewCalc.cagr !== null ? `${previewCalc.cagr.toFixed(1)}%` : '—'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-800">
                  <span>Units: <strong className="text-slate-300">{previewCalc.units.toFixed(3)}</strong></span>
                  <span>Date: {previewCalc.histDate}</span>
                </div>
              </div>
            )}

            {/* Error / Success messages */}
            {manualError && (
              <p className="text-red-400 text-xs bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">{manualError}</p>
            )}
            {manualSuccess && (
              <p className="text-green-400 text-xs bg-green-900/20 border border-green-800 rounded-lg px-3 py-2 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4 shrink-0" /> {manualSuccess}
              </p>
            )}

            {/* Submit */}
            <button
              onClick={handleManualSubmit}
              disabled={manualLoading || !!manualSuccess}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {manualLoading
                ? 'Processing…'
                : manualSuccess
                ? '✓ Success!'
                : existingHolding
                ? <><Sparkles className="w-4 h-4 text-yellow-400" /> Accumulate into Existing Fund</>
                : <><Plus className="w-4 h-4" /> Add to Portfolio</>
              }
            </button>
          </div>
        )}
      </div>

      {/* ── Portfolio Summary ─────────────────────── */}
      {holdings.length > 0 && (
        <>
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Portfolio Valuation (Auto-updates with market)
              </span>
              <button
                onClick={handleRefreshNavs}
                disabled={refreshingNavs}
                className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                title="Refresh latest market NAV"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshingNavs ? 'animate-spin' : ''}`} />
                {refreshingNavs ? 'Updating…' : 'Refresh NAVs'}
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <SummaryBox label="Invested" value={fmtINR(totalInvested)} />
              <SummaryBox label="Current Value" value={fmtINR(totalValue)} color="text-green-400" />
              <SummaryBox
                label="Gain/Loss"
                value={fmtINR(totalGain)}
                color={totalGain >= 0 ? 'text-green-400' : 'text-red-400'}
              />
            </div>
          </div>

          {/* ── Holdings List (Locked & Auto-Updating) ────────────────── */}
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <p className="section-title mb-0">Holdings ({holdings.length})</p>
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Lock className="w-3 h-3 text-slate-500" /> Market Linked
              </span>
            </div>
            <div className="space-y-2">
              {holdings.map((h) => {
                const dud = duds.find((d) => d.scheme_code === h.scheme_code)
                const isExpanded = expandedFund === h.scheme_code
                const gainPct = h.invested > 0 ? (h.gain_loss / h.invested) * 100 : 0
                return (
                  <div
                    key={h.scheme_code}
                    className={`border rounded-xl overflow-hidden transition-all ${
                      dud ? dudColor(dud.severity) : 'border-slate-700 bg-slate-900'
                    }`}
                  >
                    <button
                      className="w-full text-left px-3 py-2.5"
                      onClick={() => setExpandedFund(isExpanded ? null : h.scheme_code)}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-slate-100 truncate">
                            {h.scheme_name}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5">
                            {dud && dud.severity !== 'CLEAN' && (
                              <span className="badge bg-red-900 text-red-400 border border-red-700">
                                <AlertTriangle className="w-3 h-3" /> {dud.severity}
                              </span>
                            )}
                            <span className={`text-xs font-semibold ${colorForValue(h.gain_loss)}`}>
                              {gainPct >= 0 ? '+' : ''}{gainPct.toFixed(1)}%
                            </span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-bold text-slate-100">{fmtINR(h.current_value)}</p>
                          <p className="text-xs text-slate-500">{fmtINR(h.invested)} invested</p>
                        </div>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-slate-500 shrink-0 mt-1" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-500 shrink-0 mt-1" />
                        )}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="px-3 pb-3 border-t border-slate-700/50">
                        <div className="grid grid-cols-3 gap-2 mt-2">
                          <MiniStat label="Units" value={h.units?.toFixed(3)} />
                          <MiniStat label="Avg Buy NAV" value={`₹${h.avg_nav?.toFixed(2)}`} />
                          <MiniStat label="Live NAV" value={`₹${h.current_nav?.toFixed(2)}`} color="text-indigo-300" />
                        </div>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          <MiniStat label="Total Gain / Profit" value={`${h.gain_loss >= 0 ? '+' : ''}${fmtINR(h.gain_loss)}`} color={colorForValue(h.gain_loss)} />
                          <MiniStat label="Overall Return" value={`${gainPct >= 0 ? '+' : ''}${gainPct.toFixed(2)}%`} color={colorForValue(gainPct)} />
                        </div>

                        {dud && dud.severity !== 'CLEAN' && (
                          <div className="mt-2 bg-red-900/20 rounded-lg px-2 py-1.5">
                            <p className="text-xs text-red-300 font-semibold mb-1">⚠️ Dud Fund Flags</p>
                            {dud.flags.map((f) => (
                              <p key={f} className="text-xs text-red-400">• {f}</p>
                            ))}
                            <p className="text-xs text-slate-400 mt-1">💡 {dud.suggestion}</p>
                          </div>
                        )}

                        {/* Holding Action: Remove from Portfolio */}
                        <div className="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between">
                          <span className="text-[11px] text-slate-500 flex items-center gap-1">
                            <Lock className="w-3 h-3 text-slate-500" /> Values auto-update with market
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setFundToDelete(h)
                            }}
                            className="inline-flex items-center gap-1 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/40 px-2.5 py-1.5 rounded-lg border border-red-900/50 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" /> Remove from Portfolio
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── Portfolio X-Ray ───────────────────── */}
          {xray && (
            <div className="card">
              <p className="section-title">Portfolio X-Ray</p>
              {xray.sector_concentration && (
                <div className="mb-3">
                  <p className="text-xs text-slate-400 mb-2">Sector Concentration</p>
                  {Object.entries(xray.sector_concentration as Record<string, number>)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 6)
                    .map(([s, pct]) => (
                      <div key={s} className="mb-1.5">
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-slate-400 truncate max-w-[60%]">{s}</span>
                          <span className={pct > 25 ? 'text-red-400 font-bold' : 'text-slate-300'}>
                            {pct.toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-1.5 bg-slate-700 rounded-full">
                          <div
                            className={`h-full rounded-full ${pct > 25 ? 'bg-red-500' : 'bg-indigo-500'}`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                </div>
              )}

              {xray.market_cap_distribution && (
                <div>
                  <p className="text-xs text-slate-400 mb-2">Market Cap Mix</p>
                  <div className="flex gap-2">
                    {Object.entries(xray.market_cap_distribution as Record<string, number>).map(
                      ([cap, pct]) => (
                        <div key={cap} className="flex-1 bg-slate-900 rounded-xl px-2 py-2 text-center">
                          <p className="text-xs text-slate-500">{cap}</p>
                          <p className="text-sm font-bold text-slate-200">{pct.toFixed(0)}%</p>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Tax Pack ──────────────────────────── */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <p className="section-title mb-0">1-Click ITR Tax Pack</p>
              <button onClick={loadTax} className="btn-secondary text-sm py-2 px-4">
                Generate
              </button>
            </div>
            {showTax && taxData && (
              <div className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <SummaryBox label="LTCG Total" value={fmtINR(taxData.ltcg_total)} />
                  <SummaryBox label="STCG Total" value={fmtINR(taxData.stcg_total)} />
                  <SummaryBox label="LTCG Exempt (₹1.25L)" value={fmtINR(taxData.ltcg_exempt)} color="text-green-400" />
                  <SummaryBox label="Tax Due" value={fmtINR(taxData.tax_due)} color={taxData.tax_due > 0 ? 'text-red-400' : 'text-green-400'} />
                </div>
                <a
                  href={`${import.meta.env.VITE_API_URL || '/api'}/planner/tax-pack?format=csv`}
                  download="tax_pack.csv"
                  className="flex items-center justify-center gap-2 btn-secondary w-full mt-2"
                >
                  <Download className="w-4 h-4" /> Download CSV
                </a>
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Probabilistic Monte Carlo Forecast for Portfolio ── */}
      <MonteCarloFanChart
        isPortfolio={true}
        portfolioValue={totalValue > 0 ? totalValue : 500000}
        holdings={holdings}
        schemeName="Portfolio Growth & Uncertainty Distribution"
      />

      {/* ── Macro Stress Tester & Black Swan Simulator ── */}
      <BlackSwanStressTester
        holdings={holdings}
        portfolioValue={totalValue}
      />

      {holdings.length === 0 && !loading && (
        <div className="text-center py-10 text-slate-500">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm mb-1 font-semibold text-slate-400">No holdings in your portfolio</p>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">
            Upload your CAS statement PDF above, or click <strong className="text-indigo-400">Add Fund Manually</strong> to record past investments and track their live gains.
          </p>
        </div>
      )}

      {/* ── Delete Confirmation Modal ─────────────── */}
      {fundToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-sm w-full p-5 shadow-2xl">
            <div className="w-10 h-10 rounded-xl bg-red-900/30 border border-red-800 flex items-center justify-center text-red-400 mb-3">
              <Trash2 className="w-5 h-5" />
            </div>
            <h4 className="text-base font-bold text-white mb-1">Remove Fund from Portfolio?</h4>
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              Are you sure you want to remove <span className="text-slate-100 font-semibold">{fundToDelete.scheme_name}</span>? This will remove all its units ({fundToDelete.units?.toFixed(3)}) and valuation ({fmtINR(fundToDelete.current_value)}) from your portfolio.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setFundToDelete(null)}
                className="btn-secondary flex-1 text-sm py-2"
                disabled={deleteLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="btn-danger flex-1 text-sm py-2 flex items-center justify-center gap-1.5"
                disabled={deleteLoading}
              >
                {deleteLoading ? 'Removing…' : 'Yes, Remove'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryBox({
  label, value, color = 'text-slate-200',
}: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-slate-900 rounded-xl px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  )
}

function MiniStat({
  label, value, color = 'text-slate-300',
}: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-slate-800 rounded-lg px-2 py-1.5 text-center">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xs font-bold mt-0.5 ${color}`}>{value}</p>
    </div>
  )
}