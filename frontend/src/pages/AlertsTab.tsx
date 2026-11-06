import React, { useEffect, useState } from 'react'
import { alertsAPI } from '../lib/api'
import { AlertSettings } from '../types'
import { Bell, MessageCircle, Send, CheckCircle, XCircle, Info, ExternalLink, ShieldCheck, Zap } from 'lucide-react'

const DEFAULT_SETTINGS: AlertSettings = {
  whatsapp_number: '',
  callmebot_apikey: '',
  telegram_chat_id: '',
  telegram_bot_token: '',
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
  const [provider, setProvider] = useState<'callmebot' | 'telegram' | 'twilio'>('callmebot')
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testSent, setTestSent] = useState<'idle' | 'ok' | 'err'>('idle')
  const [history, setHistory] = useState<any[]>([])

  useEffect(() => {
    alertsAPI.getSettings()
      .then((r) => {
        setSettings({ ...DEFAULT_SETTINGS, ...r.data })
        if (r.data?.callmebot_apikey) setProvider('callmebot')
        else if (r.data?.telegram_chat_id) setProvider('telegram')
        else if (r.data?.is_twilio_configured) setProvider('twilio')
      })
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
      if (provider === 'telegram') {
        await alertsAPI.sendTest({
          channel: 'telegram',
          telegramChatId: settings.telegram_chat_id,
          alertType: 'entry',
        })
      } else {
        await alertsAPI.sendTest({
          phoneNumber: settings.whatsapp_number,
          alertType: 'entry',
          channel: 'whatsapp',
          callmebotApikey: settings.callmebot_apikey,
        })
      }
      setTestSent('ok')
    } catch {
      setTestSent('err')
    }
    setTimeout(() => setTestSent('idle'), 4000)
  }

  const toggle = (key: BooleanAlertKey) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="space-y-4 pb-6">
      {/* ── Alert Channel & Provider Selector ────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2 mb-1">
          <MessageCircle className="w-4 h-4 text-emerald-400" /> Real-time Alert Channels
        </p>
        <p className="text-xs text-slate-400 mb-3">
          Choose how you wish to receive signals. Both <strong>CallMeBot WhatsApp</strong> and <strong>Telegram</strong> are 100% free forever with no credit cards, no monthly fee, and no 30-day trial expiry.
        </p>

        {/* Channel Switcher */}
        <div className="grid grid-cols-3 gap-2 p-1 bg-slate-900 rounded-xl mb-4 border border-slate-800">
          <button
            type="button"
            onClick={() => setProvider('callmebot')}
            className={`py-2 px-2 rounded-lg text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
              provider === 'callmebot'
                ? 'bg-emerald-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="flex items-center gap-1 text-[11px]">
              <Zap className="w-3.5 h-3.5 text-amber-300" /> WhatsApp (Free)
            </span>
            <span className="text-[9px] opacity-80 font-normal">CallMeBot (No Trial)</span>
          </button>

          <button
            type="button"
            onClick={() => setProvider('telegram')}
            className={`py-2 px-2 rounded-lg text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
              provider === 'telegram'
                ? 'bg-sky-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="flex items-center gap-1 text-[11px]">
              <Send className="w-3.5 h-3.5 text-sky-200" /> Telegram (Free)
            </span>
            <span className="text-[9px] opacity-80 font-normal">Instant Bot Alerts</span>
          </button>

          <button
            type="button"
            onClick={() => setProvider('twilio')}
            className={`py-2 px-2 rounded-lg text-xs font-semibold flex flex-col items-center gap-1 transition-all ${
              provider === 'twilio'
                ? 'bg-indigo-600 text-white shadow-lg'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="flex items-center gap-1 text-[11px]">
              <MessageCircle className="w-3.5 h-3.5" /> Twilio WhatsApp
            </span>
            <span className="text-[9px] opacity-80 font-normal">Sandbox Mode</span>
          </button>
        </div>

        {/* ── CallMeBot WhatsApp (100% Free Forever) ── */}
        {provider === 'callmebot' && (
          <div className="space-y-3 mb-4">
            <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-xl p-3 text-xs text-emerald-200">
              <div className="flex items-center gap-1.5 font-bold mb-1 text-emerald-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400" /> 100% Free Forever — 30-Second Setup:
              </div>
              <ol className="list-decimal list-inside space-y-1 text-[11px] text-emerald-200/90 ml-1">
                <li>Save <strong className="text-white">+34 644 67 85 86</strong> (or +34 644 44 49 53) in your phone contacts as <em>CallMeBot</em>.</li>
                <li>Send a WhatsApp message saying: <code className="bg-emerald-900/80 px-1.5 py-0.5 rounded text-white font-mono">I allow callmebot to send me messages</code></li>
                <li>CallMeBot will reply immediately with your private <strong>API Key</strong>.</li>
                <li>Enter your phone number &amp; API Key below and tap <strong>Test</strong>!</li>
              </ol>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label">Your WhatsApp Number</label>
                <input
                  className="input"
                  type="tel"
                  placeholder="+919876543210"
                  value={settings.whatsapp_number}
                  onChange={(e) => setSettings((p) => ({ ...p, whatsapp_number: e.target.value }))}
                />
              </div>
              <div>
                <label className="label">CallMeBot API Key</label>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. 982143"
                  value={settings.callmebot_apikey || ''}
                  onChange={(e) => setSettings((p) => ({ ...p, callmebot_apikey: e.target.value }))}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── Telegram Bot (100% Free Forever) ── */}
        {provider === 'telegram' && (
          <div className="space-y-3 mb-4">
            <div className="bg-sky-950/40 border border-sky-800/60 rounded-xl p-3 text-xs text-sky-200">
              <div className="flex items-center gap-1.5 font-bold mb-1 text-sky-300">
                <Send className="w-4 h-4 text-sky-400" /> Telegram Setup (Unlimited Free Alerts):
              </div>
              <ol className="list-decimal list-inside space-y-1 text-[11px] text-sky-200/90 ml-1">
                <li>Open Telegram and message <strong>@BotFather</strong> to create your bot (<code className="bg-sky-900/80 px-1 py-0.5 rounded text-white">/newbot</code>) or use our default bot.</li>
                <li>Get your numeric Telegram Chat ID by messaging <strong>@userinfobot</strong> on Telegram.</li>
                <li>Enter your Chat ID below and tap <strong>Test</strong>!</li>
              </ol>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="label">Telegram Chat ID</label>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. 123456789"
                  value={settings.telegram_chat_id || ''}
                  onChange={(e) => setSettings((p) => ({ ...p, telegram_chat_id: e.target.value }))}
                />
              </div>
              <div>
                <label className="label">Custom Bot Token (Optional)</label>
                <input
                  className="input"
                  type="password"
                  placeholder="Optional (Uses default system bot if blank)"
                  value={settings.telegram_bot_token || ''}
                  onChange={(e) => setSettings((p) => ({ ...p, telegram_bot_token: e.target.value }))}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── Twilio WhatsApp Sandbox ── */}
        {provider === 'twilio' && (
          <div className="space-y-3 mb-4">
            <p className="text-xs text-slate-400">
              Uses Twilio WhatsApp Sandbox (<code className="text-slate-200">+1 415 523 8886</code>). Free trial accounts have credit limits.
            </p>
            <label className="label">WhatsApp Number</label>
            <input
              className="input"
              type="tel"
              placeholder="+919876543210"
              value={settings.whatsapp_number}
              onChange={(e) => setSettings((p) => ({ ...p, whatsapp_number: e.target.value }))}
            />
          </div>
        )}

        {/* Alert toggles */}
        <div className="space-y-2 mb-4">
          {ALERT_CONFIGS.map((a) => (
            <div key={a.key} className="flex items-center justify-between bg-slate-900 rounded-xl px-3 py-3 border border-slate-800">
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
          <button onClick={sendTest} className="btn-secondary flex items-center gap-2 px-5">
            <Send className="w-4 h-4" />
            Send Test Alert
          </button>
        </div>

        {testSent === 'ok' && (
          <div className="flex items-center gap-2 mt-3 p-2 rounded-lg bg-emerald-950/50 border border-emerald-800/60 text-emerald-300 text-sm">
            <CheckCircle className="w-4 h-4 text-emerald-400" /> Test alert dispatched successfully! Check your phone.
          </div>
        )}
        {testSent === 'err' && (
          <div className="flex items-center gap-2 mt-3 p-2 rounded-lg bg-red-950/50 border border-red-800/60 text-red-300 text-sm">
            <XCircle className="w-4 h-4 text-red-400" /> Alert delivery failed — check your phone number / API key.
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
              needs to be kept on.
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


