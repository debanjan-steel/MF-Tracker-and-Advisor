import React, { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { authAPI } from '../lib/api'
import { Eye, EyeOff, TrendingUp, ShieldCheck, Zap, ArrowLeft, Mail, CheckCircle } from 'lucide-react'

type Mode = 'login' | 'signup' | 'forgot'

export default function AuthPage() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotSuccess, setForgotSuccess] = useState<string | null>(null)
  const [forgotError, setForgotError] = useState<string | null>(null)
  const { login, signup, loading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      if (mode === 'login') await login(email, password)
      else if (mode === 'signup') await signup(email, password)
    } catch {
      /* error handled by store */
    }
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setForgotError(null)
    setForgotSuccess(null)
    setForgotLoading(true)
    try {
      const res = await authAPI.forgotPassword(email)
      setForgotSuccess(
        res.data?.message || `Password recovery instructions have been sent to ${email}. Please check your inbox and spam folder.`
      )
    } catch (err: any) {
      setForgotError(err.response?.data?.detail || err.message || 'Failed to send password recovery instructions.')
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12 bg-slate-900">
      {/* Hero */}
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <span className="text-2xl font-bold text-white">MF Analytics</span>
        </div>
        <p className="text-slate-400 text-sm max-w-xs">
          Indian Mutual Funds · Market Timing · Smart SIP Platform
        </p>
        <div className="flex justify-center gap-4 mt-4">
          {[
            { icon: <Zap className="w-4 h-4" />, label: 'AI Timing' },
            { icon: <ShieldCheck className="w-4 h-4" />, label: 'No PAN stored' },
            { icon: <TrendingUp className="w-4 h-4" />, label: 'Pure Equity' },
          ].map((f) => (
            <div key={f.label} className="flex items-center gap-1 text-xs text-slate-500">
              {f.icon} {f.label}
            </div>
          ))}
        </div>
      </div>

      {/* Card */}
      <div className="card w-full max-w-sm">
        {mode === 'forgot' ? (
          <div>
            <button
              type="button"
              onClick={() => { setMode('login'); clearError(); setForgotError(null); setForgotSuccess(null) }}
              className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 mb-4 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Sign In
            </button>

            <div className="mb-5">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Mail className="w-5 h-5 text-indigo-400" /> Forgot Password
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Enter your registered email address. We will send password reset instructions to your inbox.
              </p>
            </div>

            <form onSubmit={handleForgotPassword} className="space-y-4">
              <div>
                <label className="label">Registered Email</label>
                <input
                  type="email"
                  className="input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>

              {forgotError && (
                <p className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                  {forgotError}
                </p>
              )}

              {forgotSuccess && (
                <div className="text-emerald-400 text-xs bg-emerald-900/20 border border-emerald-800 rounded-lg px-3 py-2.5 flex items-start gap-2">
                  <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{forgotSuccess}</span>
                </div>
              )}

              <button type="submit" className="btn-primary w-full" disabled={forgotLoading}>
                {forgotLoading ? 'Sending link…' : 'Send Password Reset Link'}
              </button>
            </form>

            <div className="mt-5 p-3 rounded-xl bg-slate-900/70 border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <p className="font-semibold text-slate-300">Security Notice:</p>
              <p>
                To protect your account, passwords are protected with cryptographic one-way hashing and are never stored in readable plain text. A secure password reset link will be sent to your registered email.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Toggle */}
            <div className="flex bg-slate-900 rounded-xl p-1 mb-6">
              {(['login', 'signup'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); clearError() }}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${
                    mode === m
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {m === 'login' ? 'Sign In' : 'Create Account'}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  className="input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="label mb-0">Password</label>
                  {mode === 'login' && (
                    <button
                      type="button"
                      onClick={() => { setMode('forgot'); clearError(); setForgotError(null); setForgotSuccess(null) }}
                      className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <input
                    type={showPwd ? 'text' : 'password'}
                    className="input pr-12"
                    placeholder={mode === 'signup' ? 'Min 8 characters' : '••••••••'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={mode === 'signup' ? 8 : 1}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowPwd((p) => !p)}
                  >
                    {showPwd ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {error && (
                <p className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button type="submit" className="btn-primary w-full" disabled={loading}>
                {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            </form>

            {mode === 'login' && (
              <p className="text-center text-xs text-slate-500 mt-4">
                Forgot your password? Click{' '}
                <button
                  type="button"
                  onClick={() => { setMode('forgot'); clearError(); setForgotError(null); setForgotSuccess(null) }}
                  className="text-indigo-400 hover:underline"
                >
                  Forgot password
                </button>{' '}
                to reset via email.
              </p>
            )}
            {mode === 'signup' && (
              <p className="text-center text-xs text-slate-500 mt-4">
                Your PAN is never stored. Only email &amp; encrypted password.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

