import React, { useEffect, useState, useRef } from 'react'
import { portfolioAPI, analyticsAPI, plannerAPI } from '../lib/api'
import { Holding, DudFund, TaxSummary } from '../types'
import { fmtINR, fmtPct, dudColor, colorForValue } from '../lib/utils'
import { Upload, FileText, Lock, ChevronDown, ChevronUp, Download, AlertTriangle } from 'lucide-react'

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
  const fileRef = useRef<HTMLInputElement>(null)

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

  const loadTax = async () => {
    try {
      const { data } = await plannerAPI.taxPack()
      setTaxData(data)
      setShowTax(true)
    } catch { /* ignore */ }
  }

  useEffect(() => { loadHoldings() }, [])

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
          Upload your CAMS/KFintech CAS PDF statement. Your PAN is used only in memory to decrypt
          the PDF and is never stored.
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
              placeholder="Enter PAN (e.g. ABCDE1234F) — not stored"
              value={pan}
              onChange={(e) => setPan(e.target.value.toUpperCase())}
              maxLength={10}
            />
            <p className="text-xs text-slate-600 mt-1 flex items-center gap-1">
              <Lock className="w-3 h-3" /> Used in-memory only. Cleared after parsing.
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

      {/* ── Portfolio Summary ─────────────────────── */}
      {holdings.length > 0 && (
        <>
          <div className="card">
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

          {/* ── Holdings List ─────────────────────── */}
          <div className="card">
            <p className="section-title">Holdings ({holdings.length})</p>
            <div className="space-y-2">
              {holdings.map((h) => {
                const dud = duds.find((d) => d.scheme_code === h.scheme_code)
                const isExpanded = expandedFund === h.scheme_code
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
                            <span className={`text-xs font-medium ${colorForValue(h.gain_loss)}`}>
                              {fmtPct((h.gain_loss / h.invested) * 100)}
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
                          <MiniStat label="Avg NAV" value={`₹${h.avg_nav?.toFixed(2)}`} />
                          <MiniStat label="XIRR" value={fmtPct(h.xirr)} color={colorForValue(h.xirr)} />
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

      {holdings.length === 0 && !loading && (
        <div className="text-center py-12 text-slate-500">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Upload your CAS PDF to see your holdings</p>
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

