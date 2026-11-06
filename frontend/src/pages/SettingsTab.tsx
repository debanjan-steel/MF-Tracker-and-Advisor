import React, { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { useAppStore } from '../store/appStore'
import { authAPI } from '../lib/api'
import {
  User, Moon, Sun, Shield, Clock, Database, AlertTriangle, LogOut, Trash2,
  ChevronRight, Bell, Lock, Key, Eye, EyeOff, CheckCircle, X,
} from 'lucide-react'

export default function SettingsTab() {
  const { user, logout, deleteAccount, loading } = useAuthStore()
  const { darkMode, toggleDark } = useAppStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  // Change Password state
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showOldPwd, setShowOldPwd] = useState(false)
  const [showNewPwd, setShowNewPwd] = useState(false)
  const [showConfirmPwd, setShowConfirmPwd] = useState(false)
  const [pwdLoading, setPwdLoading] = useState(false)
  const [pwdError, setPwdError] = useState<string | null>(null)
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null)

  const openPasswordModal = () => {
    setOldPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setPwdError(null)
    setPwdSuccess(null)
    setShowPasswordModal(true)
  }

  const closePasswordModal = () => {
    setShowPasswordModal(false)
    setPwdError(null)
    setPwdSuccess(null)
  }

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    setPwdError(null)
    setPwdSuccess(null)

    if (newPassword.length < 6) {
      setPwdError('New password must be at least 6 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPwdError('New password and confirm new password do not match.')
      return
    }
    if (oldPassword === newPassword) {
      setPwdError('New password must be different from your old password.')
      return
    }

    setPwdLoading(true)
    try {
      await authAPI.changePassword(oldPassword, newPassword)
      setPwdSuccess('Your password has been updated successfully!')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => {
        closePasswordModal()
      }, 1600)
    } catch (err: any) {
      setPwdError(
        err.response?.data?.detail || err.message || 'Failed to change password. Please verify your old password.'
      )
    } finally {
      setPwdLoading(false)
    }
  }

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
        <div className="flex items-center justify-between mb-3">
          <p className="section-title flex items-center gap-2 mb-0">
            <User className="w-4 h-4 text-indigo-400" /> Account
          </p>
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
            <Lock className="w-3 h-3 text-slate-400" /> Permanent Identifier
          </span>
        </div>
        <div className="bg-slate-900 rounded-xl px-4 py-3 mb-3">
          <p className="text-xs text-slate-500">Registered Email Address</p>
          <div className="flex items-center justify-between mt-0.5">
            <p className="text-sm font-semibold text-slate-100 font-mono">{user?.email || '—'}</p>
            <span className="text-[11px] text-slate-500 font-medium">Non-editable</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-2 border-t border-slate-800/80 pt-1.5">
            Email cannot be changed because it is the primary unique identifier for your account and all associated portfolios.
          </p>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full btn-secondary justify-center"
        >
          <LogOut className="w-4 h-4" /> Sign Out
        </button>
      </div>

      {/* ── Change Password Option ─────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Key className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-100 leading-tight">Password &amp; Security</p>
              <p className="text-xs text-slate-400 mt-0.5">Click to change your account password</p>
            </div>
          </div>
          <button
            onClick={openPasswordModal}
            className="btn-primary text-xs font-semibold px-4 py-2 flex items-center gap-1.5 shrink-0"
          >
            Change Password <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── Password Modal Popup ──────────────────── */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl relative">
            <button
              onClick={closePasswordModal}
              className="absolute top-4 right-4 p-1.5 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition-colors"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 mb-1">
              <div className="p-2 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                <Key className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">Change Password</h3>
                <p className="text-xs text-slate-400">Enter your old password and choose a new one</p>
              </div>
            </div>

            <form onSubmit={handlePasswordChange} className="space-y-3.5 mt-5">
              {/* Old Password */}
              <div>
                <label className="label text-xs">Type Old Password</label>
                <div className="relative">
                  <input
                    type={showOldPwd ? 'text' : 'password'}
                    className="input pr-10 text-sm"
                    placeholder="Enter current password"
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowOldPwd(!showOldPwd)}
                  >
                    {showOldPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div>
                <label className="label text-xs">Type New Password</label>
                <div className="relative">
                  <input
                    type={showNewPwd ? 'text' : 'password'}
                    className="input pr-10 text-sm"
                    placeholder="Minimum 6 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={6}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowNewPwd(!showNewPwd)}
                  >
                    {showNewPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Confirm / Retype New Password */}
              <div>
                <label className="label text-xs">Re-type New Password</label>
                <div className="relative">
                  <input
                    type={showConfirmPwd ? 'text' : 'password'}
                    className="input pr-10 text-sm"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={6}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowConfirmPwd(!showConfirmPwd)}
                  >
                    {showConfirmPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Feedback messages */}
              {pwdError && (
                <div className="text-red-400 text-xs bg-red-900/30 border border-red-800 rounded-xl px-3 py-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                  <span>{pwdError}</span>
                </div>
              )}

              {pwdSuccess && (
                <div className="text-emerald-400 text-xs bg-emerald-900/30 border border-emerald-800 rounded-xl px-3 py-2 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>{pwdSuccess}</span>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={closePasswordModal}
                  className="btn-secondary flex-1"
                  disabled={pwdLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary flex-1"
                  disabled={pwdLoading}
                >
                  {pwdLoading ? 'Updating…' : 'Update Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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

