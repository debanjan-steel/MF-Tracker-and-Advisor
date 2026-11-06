import React, { useEffect, useState } from 'react'
import { alertsAPI } from '../lib/api'
import { AlertSettings } from '../types'
import { Bell, MessageCircle, Send, CheckCircle, XCircle, Info } from 'lucide-react'

const DEFAULT_SETTINGS: AlertSettings = {
  whatsapp_number: '',
  entry_alert: true,
  macro_alert: true,
  sip_reminder: true,
  dud_alert: true,
}

type BooleanAlertKey = 'entry_alert' | 'macro_alert' | 'sip_reminder' | 'dud_alert'

const ALERT_CONFIGS: { key: BooleanAlertKey; label: string; desc: string }[] = [
  { key: 'entry_alert', label: '📈 Entry Signal Alert', desc: 'When timing score crosses buy threshold' },
  { key: 'macro_alert', label: '🌍 Macro Danger Alert', desc: 'When macro danger score spikes' },
  { key: 'sip_reminder', label: '📅 SIP Execution Reminder', desc: 'Monthly reminder on your best SIP date' },
  { key: 'dud_alert', label: '⚠️ Dud Fund Alert', desc: 'When a held fund turns MODERATE/SEVERE' },
]

export default function AlertsTab() {
  const [settings, setSettings] = useState<AlertSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testSent, setTestSent] = useState<'idle' | 'ok' | 'err'>('idle')
  const [history, setHistory] = useState<any[]>([])

  useEffect(() => {
    alertsAPI.getSettings()
      .then((r) => setSettings({ ...DEFAULT_SETTINGS, ...r.data }))
      .catch(() => {})
    alertsAPI.history()
      .then((r) => setHistory(r.data || []))
      .catch(() => {})
  }, [])

  const save = async () => {
    setLoading(true)
    try {
      await alertsAPI.saveSettings(settings)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } finally {
      setLoading(false)
    }
  }

  const sendTest = async () => {
    setTestSent('idle')
    try {
      await alertsAPI.sendTest(settings.whatsapp_number, 'entry')
      setTestSent('ok')
    } catch {
      setTestSent('err')
    }
    setTimeout(() => setTestSent('idle'), 3000)
  }

  const toggle = (key: BooleanAlertKey) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="space-y-4 pb-6">
      {/* ── WhatsApp Setup ────────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <MessageCircle className="w-4 h-4 text-green-400" /> WhatsApp Alerts
        </p>
        <p className="text-xs text-slate-500 mb-3">
          Alerts are sent via Twilio WhatsApp. Enter your number in international format.
        </p>
        <label className="label">WhatsApp Number</label>
        <input
          className="input mb-3"
          type="tel"
          placeholder="+919876543210"
          value={settings.whatsapp_number}
          onChange={(e) => setSettings((p) => ({ ...p, whatsapp_number: e.target.value }))}
        />

        {/* Alert toggles */}
        <div className="space-y-2 mb-4">
          {ALERT_CONFIGS.map((a) => (
            <div key={a.key} className="flex items-center justify-between bg-slate-900 rounded-xl px-3 py-3">
              <div>
                <p className="text-sm font-medium text-slate-200">{a.label}</p>
                <p className="text-xs text-slate-500">{a.desc}</p>
              </div>
              <button
                onClick={() => toggle(a.key)}
                className={`w-12 h-6 rounded-full transition-colors relative shrink-0 focus:outline-none ${
                  settings[a.key] ? 'bg-indigo-600' : 'bg-slate-700'
                }`}
              >
                <span
                  className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
                    settings[a.key] ? 'translate-x-6' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button onClick={save} className="btn-primary flex-1" disabled={loading}>
            {saved ? '✓ Saved!' : loading ? 'Saving…' : 'Save Settings'}
          </button>
          <button onClick={sendTest} className="btn-secondary flex items-center gap-2 px-4">
            <Send className="w-4 h-4" />
            Test
          </button>
        </div>

        {testSent === 'ok' && (
          <div className="flex items-center gap-2 mt-2 text-green-400 text-sm">
            <CheckCircle className="w-4 h-4" /> Test alert sent!
          </div>
        )}
        {testSent === 'err' && (
          <div className="flex items-center gap-2 mt-2 text-red-400 text-sm">
            <XCircle className="w-4 h-4" /> Failed — check Twilio credentials in .env
          </div>
        )}
      </div>

      {/* ── Info ─────────────────────────────────── */}
      <div className="card border-blue-800 bg-blue-900/10">
        <div className="flex gap-2">
          <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-blue-300">How alerts work</p>
            <p className="text-xs text-slate-400 mt-1">
              The nightly GitHub Actions runner (9:30 PM IST) evaluates all signals and sends alerts
              automatically. You can also trigger manual checks from the Planner tab. No laptop or phone
              needs to be on.
            </p>
          </div>
        </div>
      </div>

      {/* ── Alert History ─────────────────────────── */}
      {history.length > 0 && (
        <div className="card">
          <p className="section-title">Recent Alerts</p>
          <div className="space-y-2">
            {history.slice(0, 10).map((h, i) => (
              <div key={i} className="flex items-start gap-2 bg-slate-900 rounded-xl px-3 py-2">
                <Bell className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-slate-300">{h.message}</p>
                  <p className="text-xs text-slate-600">{h.sent_at}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

