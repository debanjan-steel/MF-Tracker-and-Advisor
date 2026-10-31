import React from 'react'
import { MacroDanger } from '../types'
import { AlertTriangle, TrendingDown } from 'lucide-react'

interface Props { macro: MacroDanger }

export default function MacroBar({ macro }: Props) {
  const danger = macro.danger_score
  const barColor =
    danger >= 70 ? 'bg-red-500' : danger >= 50 ? 'bg-orange-500' : danger >= 30 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="card border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-slate-400 flex items-center gap-1">
          <TrendingDown className="w-3.5 h-3.5" /> Macro Danger Score
        </p>
        <span className={`text-xs font-bold ${
          danger >= 70 ? 'text-red-400' : danger >= 50 ? 'text-orange-400' : 'text-green-400'
        }`}>
          {danger.toFixed(0)}/100
        </span>
      </div>
      {/* Bar */}
      <div className="h-2 bg-slate-700 rounded-full mb-2">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${danger}%` }} />
      </div>
      {/* Posture */}
      <p className="text-xs text-slate-400 mb-1">Posture: <span className="text-slate-200 font-medium">{macro.posture}</span></p>
      {/* Flags */}
      {macro.flags?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {macro.flags.map((f) => (
            <span key={f} className="flex items-center gap-1 text-xs bg-red-900/30 text-red-400 border border-red-800 px-2 py-0.5 rounded-full">
              <AlertTriangle className="w-2.5 h-2.5" /> {f}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

