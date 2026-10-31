import React, { useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { Eye, EyeOff, TrendingUp, ShieldCheck, Zap } from 'lucide-react'

type Mode = 'login' | 'signup'

export default function AuthPage() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const { login, signup, loading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      if (mode === 'login') await login(email, password)
      else await signup(email, password)
    } catch {
      /* error handled by store */
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
        {/* Toggle */}
        <div className="flex bg-slate-900 rounded-xl p-1 mb-6">
          {(['login', 'signup'] as Mode[]).map((m) => (
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
            <label className="label">Password</label>
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
            Forgot password? Reset via email link from your Supabase dashboard.
          </p>
        )}
        {mode === 'signup' && (
          <p className="text-center text-xs text-slate-500 mt-4">
            Your PAN is never stored. Only email &amp; encrypted password.
          </p>
        )}
      </div>
    </div>
  )
}

