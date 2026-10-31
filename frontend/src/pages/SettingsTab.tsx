import React, { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { useAppStore } from '../store/appStore'
import {
  User, Moon, Sun, Shield, Clock, Database, AlertTriangle, LogOut, Trash2,
  ChevronRight, Bell,
} from 'lucide-react'

export default function SettingsTab() {
  const { user, logout, deleteAccount, loading } = useAuthStore()
  const { darkMode, toggleDark } = useAppStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  const handleDelete = async () => {
    if (confirmText !== 'DELETE') return
    setDeleteLoading(true)
    try {
      await deleteAccount()
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <div className="space-y-4 pb-6">
      {/* ── Account ───────────────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <User className="w-4 h-4 text-indigo-400" /> Account
        </p>
        <div className="bg-slate-900 rounded-xl px-4 py-3 mb-3">
          <p className="text-xs text-slate-500">Signed in as</p>
          <p className="text-sm font-semibold text-slate-100 mt-0.5">{user?.email || '—'}</p>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full btn-secondary justify-center"
        >
          <LogOut className="w-4 h-4" /> Sign Out
        </button>
      </div>

      {/* ── Preferences ───────────────────────────── */}
      <div className="card">
        <p className="section-title">Preferences</p>
        <div className="flex items-center justify-between bg-slate-900 rounded-xl px-4 py-3">
          <div className="flex items-center gap-2">
            {darkMode ? <Moon className="w-4 h-4 text-indigo-400" /> : <Sun className="w-4 h-4 text-yellow-400" />}
            <span className="text-sm text-slate-200">Dark Mode</span>
          </div>
          <button
            onClick={toggleDark}
            className={`w-12 h-6 rounded-full relative transition-colors shrink-0 focus:outline-none ${darkMode ? 'bg-indigo-600' : 'bg-slate-600'}`}
          >
            <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${darkMode ? 'translate-x-6' : 'translate-x-0'}`} />
          </button>
        </div>
      </div>

      {/* ── Privacy & Security ────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <Shield className="w-4 h-4 text-green-400" /> Privacy & Security
        </p>
        <div className="space-y-2 text-xs text-slate-400">
          {[
            '🔒 PAN number is never stored — only used in-memory to decrypt CAS PDFs',
            '🛡️ All data stored in Supabase with Row-Level Security',
            '📡 WhatsApp alerts via Twilio — only your number is stored',
            '🌐 This app never sells your data or shares it with third parties',
          ].map((item) => (
            <p key={item} className="flex items-start gap-2 bg-slate-900 rounded-xl px-3 py-2">
              {item}
            </p>
          ))}
        </div>
      </div>

      {/* ── Cloud Engine Status ───────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <Clock className="w-4 h-4 text-yellow-400" /> Cloud Engine Status
        </p>
        <div className="space-y-2">
          {[
            { label: 'Nightly Sync', value: '9:30 PM IST via GitHub Actions', ok: true },
            { label: 'Data Source', value: 'MFAPI.in (primary) + AMFI (fallback)', ok: true },
            { label: 'Macro Data', value: 'Yahoo Finance — 6 indicators', ok: true },
            { label: 'Database', value: 'Supabase PostgreSQL (free tier)', ok: true },
          ].map((s) => (
            <div key={s.label} className="flex items-center justify-between bg-slate-900 rounded-xl px-3 py-2.5">
              <div>
                <p className="text-xs text-slate-400">{s.label}</p>
                <p className="text-xs text-slate-300">{s.value}</p>
              </div>
              <span className={`text-xs font-bold ${s.ok ? 'text-green-400' : 'text-red-400'}`}>
                {s.ok ? '● Live' : '● Error'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── About ─────────────────────────────────── */}
      <div className="card">
        <p className="section-title flex items-center gap-2">
          <Database className="w-4 h-4 text-slate-400" /> About
        </p>
        <div className="text-xs text-slate-500 space-y-1">
          <p>MF Analytics Platform v1.0</p>
          <p>Indian Mutual Funds · Market Timing · Smart SIP</p>
          <p className="text-slate-600">
            For personal/educational use only. Not SEBI registered investment advice.
          </p>
        </div>
      </div>

      {/* ── DANGER: Delete Account ────────────────── */}
      <div className="card border-red-900/50">
        <p className="section-title flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-4 h-4" /> Danger Zone
        </p>
        <p className="text-xs text-slate-400 mb-3">
          Permanently delete your account. All portfolio data, goals, holdings, CAS history,
          alerts, and your login will be instantly and irreversibly erased.
        </p>

        {!showDeleteConfirm ? (
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center justify-center gap-2 w-full border-2 border-red-700 text-red-400 
                       hover:bg-red-900/30 font-semibold py-3 px-5 rounded-xl transition-all duration-200"
          >
            <Trash2 className="w-4 h-4" /> Delete My Account
          </button>
        ) : (
          <div className="space-y-3 bg-red-900/20 border border-red-800 rounded-xl p-4">
            <p className="text-sm font-bold text-red-300">⚠️ This cannot be undone</p>
            <p className="text-xs text-red-400">
              Type <span className="font-mono font-bold bg-red-900/40 px-1 rounded">DELETE</span> to confirm
            </p>
            <input
              className="input border-red-700 focus:ring-red-500"
              placeholder="Type DELETE"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={() => { setShowDeleteConfirm(false); setConfirmText('') }}
                className="btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="btn-danger flex-1"
                disabled={confirmText !== 'DELETE' || deleteLoading}
              >
                {deleteLoading ? 'Deleting…' : '🗑 Delete Everything'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

