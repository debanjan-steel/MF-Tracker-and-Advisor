// Utility helpers
export function fmt(n: number, dec = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—'
  return n.toFixed(dec)
}

export function fmtINR(n: number): string {
  if (!n && n !== 0) return '—'
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

export function fmtPct(n: number, dec = 2): string {
  if (n === null || n === undefined || isNaN(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toFixed(dec)}%`
}

export function colorForValue(
  v: number,
  good = 'text-green-400',
  bad = 'text-red-400',
  neutral = 'text-slate-400'
): string {
  if (v > 0) return good
  if (v < 0) return bad
  return neutral
}

export function postureColor(posture: string): string {
  const map: Record<string, string> = {
    AGGRESSIVE: 'bg-green-600 text-white',
    GROWTH: 'bg-emerald-600 text-white',
    BALANCED: 'bg-yellow-600 text-white',
    DEFENSIVE: 'bg-orange-600 text-white',
    CAPITAL_SAFE: 'bg-red-700 text-white',
  }
  return map[posture] ?? 'bg-slate-600 text-white'
}

export function signalColor(signal: string): string {
  const map: Record<string, string> = {
    STRONG_BUY: 'text-green-400',
    BUY: 'text-emerald-400',
    NEUTRAL: 'text-yellow-400',
    CAUTION: 'text-orange-400',
    AVOID: 'text-red-400',
  }
  return map[signal] ?? 'text-slate-400'
}

export function thermometerColor(status: string): string {
  const map: Record<string, string> = {
    COLD: 'text-blue-400 bg-blue-900/30',
    WARM: 'text-green-400 bg-green-900/30',
    HOT: 'text-orange-400 bg-orange-900/30',
    OVERHEATED: 'text-red-400 bg-red-900/30',
  }
  return map[status] ?? 'text-slate-400 bg-slate-800'
}

export function dudColor(severity: string): string {
  const map: Record<string, string> = {
    CLEAN: 'bg-green-900/40 text-green-400 border-green-700',
    MILD: 'bg-yellow-900/40 text-yellow-400 border-yellow-700',
    MODERATE: 'bg-orange-900/40 text-orange-400 border-orange-700',
    SEVERE: 'bg-red-900/40 text-red-400 border-red-700',
  }
  return map[severity] ?? 'bg-slate-800 text-slate-400 border-slate-700'
}

export function stressColor(severity: string): string {
  const map: Record<string, string> = {
    LOW: 'text-green-400',
    MEDIUM: 'text-yellow-400',
    HIGH: 'text-orange-400',
    SEVERE: 'text-red-400',
  }
  return map[severity] ?? 'text-slate-400'
}

/** Format ordinal (1 → 1st, 7 → 7th) */
export function ordinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

