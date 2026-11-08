import React, { useEffect, useState } from 'react'
import { alertsAPI } from '../lib/api'
import { useAppStore } from '../store/appStore'
import { AlertSettings, InAppAlert } from '../types'
import {
  Bell, RefreshCw, Trash2, TrendingUp, AlertTriangle, Calendar,
  ShieldAlert, Clock, Sparkles, Check, CheckCircle2, SlidersHorizontal,
  ChevronDown, ChevronUp, Briefcase, ArrowRight,
} from 'lucide-react'
import MacroAnalogueCard from '../components/MacroAnalogueCard'

const DEFAULT_SETTINGS: AlertSettings = {
  entry_alert: true,
  macro_alert: true,
  sip_reminder: true,
  dud_alert: true,
  retention_days: 14,
}

type BooleanAlertKey = 'entry_alert' | 'macro_alert' | 'sip_reminder' | 'dud_alert'

const ALERT_CONFIGS: { key: BooleanAlertKey; label: string; desc: string; icon: React.ReactNode }[] = [
  {
    key: 'entry_alert',
    label: '📈 Portfolio Value Entry Signals',
    desc: 'Triggers when a mutual fund in your portfolio tests 200 EMA support or enters deep value',
    icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
  },
  {
    key: 'macro_alert',
    label: '🌍 Macro Danger Alerts',
    desc: 'Triggers when Brent Crude, India VIX, or currency volatility breaches caution levels',
    icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
  },
  {
    key: 'sip_reminder',
    label: '📅 Portfolio Smart SIP Plans',
    desc: 'Calculates the optimal empirical execution date and budget multiplier for your portfolio',
    icon: <Calendar className="w-4 h-4 text-indigo-400" />,
  },
  {
    key: 'dud_alert',
    label: '⚠️ Portfolio Dud Red Flags',
    desc: 'Flags persistent category underperformers or distributor commission drags in your portfolio',
    icon: <ShieldAlert className="w-4 h-4 text-red-400" />,
  },
]

export default function AlertsTab() {
  const { setTab } = useAppStore()
  const [settings, setSettings] = useState<AlertSettings>(DEFAULT_SETTINGS)
  const [alerts, setAlerts] = useState<InAppAlert[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [showConfig, setShowConfig] = useState(false)
  const [savedToast, setSavedToast] = useState(false)

  // Load active alerts & user preferences on mount
  useEffect(() => {
    setLoading(true)
    Promise.all([
      alertsAPI.getSettings().then((r) => setSettings({ ...DEFAULT_SETTINGS, ...r.data })).catch(() => {}),
      alertsAPI.getFeed().then((r) => setAlerts(r.data || [])).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  // Toggle alert preference and save immediately
  const toggle = async (key: BooleanAlertKey) => {
    const updated = { ...settings, [key]: !settings[key] }
    setSettings(updated)
    try {
      await alertsAPI.saveSettings(updated)
      setSavedToast(true)
      setTimeout(() => setSavedToast(false), 2000)
    } catch {}
  }

  // Refresh live alerts by evaluating signals
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const res = await alertsAPI.refreshAlerts()
      if (res.data?.alerts) {
        setAlerts(res.data.alerts)
      } else {
        const feed = await alertsAPI.getFeed()
        setAlerts(feed.data || [])
      }
    } catch {
    } finally {
      setRefreshing(false)
    }
  }

  // Delete / Dismiss a single alert
  const handleDeleteAlert = async (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
    try {
      await alertsAPI.deleteAlert(id)
    } catch {}
  }

  // Clear all active alerts
  const handleClearAll = async () => {
    if (!window.confirm('Are you sure you want to dismiss all active alerts?')) return
    setAlerts([])
    try {
      await alertsAPI.clearAll()
    } catch {}
  }

  const getSeverityBadge = (severity: string, type: string) => {
    if (type === 'plan_update') {
      return {
        badge: 'bg-purple-950/80 border-purple-700/60 text-purple-300',
        border: 'border-purple-600/50 bg-slate-900/90 hover:border-purple-500/80',
        icon: <Sparkles className="w-4 h-4 text-purple-400" />,
        label: 'PLAN CHANGELOG (14-DAY RETENTION)',
      }
    }
    if (type === 'dud') {
      return {
        badge: 'bg-red-950/80 border-red-700/60 text-red-300',
        border: 'border-red-600/50 bg-slate-900/90 hover:border-red-500/80',
        icon: <ShieldAlert className="w-4 h-4 text-red-400" />,
        label: 'DUD / TAKE MONEY OUT',
      }
    }

    switch (severity) {
      case 'SUCCESS':
        return {
          badge: 'bg-emerald-950/80 border-emerald-700/60 text-emerald-300',
          border: 'border-emerald-600/50 bg-slate-900/90 hover:border-emerald-500/80',
          icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
          label: 'PORTFOLIO BUY / DIP ENTRY',
        }
      case 'WARNING':
        return {
          badge: 'bg-amber-950/80 border-amber-700/60 text-amber-300',
          border: 'border-amber-600/50 bg-slate-900/90 hover:border-amber-500/80',
          icon: <AlertTriangle className="w-4 h-4 text-amber-400" />,
          label: 'MACRO CAUTION / REBALANCE',
        }
      case 'DANGER':
        return {
          badge: 'bg-red-950/80 border-red-700/60 text-red-300',
          border: 'border-red-600/50 bg-slate-900/90 hover:border-red-500/80',
          icon: <ShieldAlert className="w-4 h-4 text-red-400" />,
          label: 'HOLDING RED FLAG / DUD',
        }
      default:
        return {
          badge: 'bg-indigo-950/80 border-indigo-700/60 text-indigo-300',
          border: 'border-indigo-600/50 bg-slate-900/90 hover:border-indigo-500/80',
          icon: <Calendar className="w-4 h-4 text-indigo-400" />,
          label: 'SMART SIP EXECUTION',
        }
    }
  }

  return (
    <div className="space-y-4 pb-8">
      {/* ── Top Header Card ────────────────────────── */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Bell className="w-5 h-5 text-indigo-400" />
              Portfolio Intelligence &amp; Alerts
              {alerts.length > 0 && (
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-600/40 border border-indigo-500/60 text-indigo-300">
                  {alerts.length} Active
                </span>
              )}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live intelligence evaluated strictly for the mutual funds in your portfolio.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="btn-primary text-xs font-semibold px-3.5 py-2 flex items-center gap-1.5 transition-all shadow-md shadow-indigo-950"
              title="Re-evaluate live signals for your portfolio"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              {refreshing ? 'Evaluating…' : 'Refresh Alerts'}
            </button>

            {/* Toggle Config drawer */}
            <button
              onClick={() => setShowConfig(!showConfig)}
              className={`text-xs font-medium px-3 py-2 rounded-xl border flex items-center gap-1.5 transition-all ${
                showConfig
                  ? 'bg-slate-700 border-slate-600 text-white'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white hover:bg-slate-700'
              }`}
              title="Customize alert preferences"
            >
              <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
              <span>Filters</span>
              {showConfig ? <ChevronUp className="w-3 h-3 ml-0.5" /> : <ChevronDown className="w-3 h-3 ml-0.5" />}
            </button>

            {/* Clear all if alerts exist */}
            {alerts.length > 0 && (
              <button
                onClick={handleClearAll}
                className="text-xs font-medium px-2.5 py-2 rounded-xl border border-slate-700 bg-slate-800/80 text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors"
                title="Clear all active alerts"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* ── Expandable Preferences / Filter Settings ── */}
        {showConfig && (
          <div className="mt-4 pt-4 border-t border-slate-700/70 space-y-2.5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold text-slate-200">Portfolio Alert Categories</span>
              {savedToast && (
                <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Saved!
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {ALERT_CONFIGS.map((cfg) => (
                <div
                  key={cfg.key}
                  className="flex items-center justify-between bg-slate-900/90 rounded-xl px-3 py-2.5 border border-slate-800"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-xs font-semibold text-slate-200 leading-tight">{cfg.label}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{cfg.desc}</p>
                  </div>
                  <button
                    onClick={() => toggle(cfg.key)}
                    className={`w-10 h-5 rounded-full transition-colors relative shrink-0 focus:outline-none ${
                      settings[cfg.key] ? 'bg-indigo-600' : 'bg-slate-700'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
                        settings[cfg.key] ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>

            <p className="text-[11px] text-slate-500 pt-1">
              Active alerts automatically remain visible for <strong>14 days</strong> unless manually deleted.
            </p>
          </div>
        )}
      </div>

      {/* ── Macro Analogue & Dynamic Hedging Engine ──── */}
      <MacroAnalogueCard />

      {/* ── Alerts Feed ────────────────────────────── */}
      {loading ? (
        <div className="card text-center py-14">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-300">Evaluating Portfolio Signals…</p>
          <p className="text-xs text-slate-500 mt-1">Cross-checking NAV 200 EMAs and category drawdowns for your held funds.</p>
        </div>
      ) : alerts.length === 0 ? (
        <div className="card text-center py-12 border-dashed border-slate-700/80">
          <CheckCircle2 className="w-10 h-10 text-emerald-400/80 mx-auto mb-2" />
          <h3 className="text-base font-bold text-slate-200">All Clear — No Active Alerts</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Your portfolio mutual funds are within steady volatility thresholds. Click <strong>Refresh Alerts</strong> at any time to re-scan live signals for your holdings.
          </p>
          <div className="flex justify-center gap-2 mt-4">
            <button
              onClick={handleRefresh}
              className="btn-primary text-xs font-semibold px-4 py-2 inline-flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Re-scan Portfolio Signals
            </button>
            <button
              onClick={() => setTab('portfolio')}
              className="btn-secondary text-xs font-semibold px-4 py-2 inline-flex items-center gap-1.5"
            >
              <Briefcase className="w-3.5 h-3.5 text-indigo-400" /> Go to Portfolio
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const style = getSeverityBadge(alert.severity, alert.alert_type)
            const isPortfolioEmptyNotice = alert.alert_type === 'portfolio_empty'

            return (
              <div
                key={alert.id}
                className={`card p-4 border transition-all duration-200 shadow-md ${style.border}`}
              >
                {/* Header Row */}
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border tracking-wider uppercase ${style.badge}`}>
                      {style.icon} {isPortfolioEmptyNotice ? 'PORTFOLIO SETUP' : style.label}
                    </span>
                    <span className="text-[11px] text-slate-500 flex items-center gap-1 font-medium">
                      <Clock className="w-3 h-3 text-slate-500" />
                      Retained for {alert.days_remaining} more day{alert.days_remaining !== 1 ? 's' : ''}
                    </span>
                  </div>

                  {/* Delete / Dismiss button */}
                  <button
                    onClick={() => handleDeleteAlert(alert.id)}
                    title="Dismiss / Delete this alert"
                    className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/40 rounded-lg transition-colors shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Title */}
                <h3 className="text-sm font-bold text-slate-100 leading-snug mb-1.5">
                  {alert.title}
                </h3>

                {/* Message Body */}
                <p className="text-xs text-slate-300 leading-relaxed mb-3">
                  {alert.message}
                </p>

                {/* Actionable Recommendation Box */}
                {alert.action_text && (
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-slate-950/70 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-indigo-200 font-medium">
                    <div className="flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                      <span>{alert.action_text}</span>
                    </div>

                    {isPortfolioEmptyNotice && (
                      <button
                        onClick={() => setTab('portfolio')}
                        className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-1 shrink-0 transition-colors"
                      >
                        Add Holdings <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                )}

                {/* Footer metadata */}
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2.5 pt-2 border-t border-slate-800/80">
                  <span>Detected: {alert.created_at ? alert.created_at.slice(0, 16) : 'Live'}</span>
                  <span>Expires in {alert.days_remaining}d (Auto-purged after 14d)</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Informational Note ────────────────────── */}
      <div className="card bg-slate-900/50 border-slate-800">
        <div className="flex gap-2.5 text-xs text-slate-400">
          <Briefcase className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-slate-300">Exclusively for Your Portfolio</p>
            <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">
              Every alert is generated exclusively for the mutual funds you hold in your portfolio. Watchlist funds are not alerted here. Alerts remain stored in your feed for <strong>14 days</strong> so you can review them whenever you log in, or until you tap the <strong>Delete (trash)</strong> button.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
