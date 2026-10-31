import React from 'react'
import { stressColor } from '../lib/utils'
import { Shield } from 'lucide-react'

interface Props { result: any }

export default function StressTestCard({ result }: Props) {
  if (!result) return null
  return (
    <div className={`bg-slate-900 rounded-xl px-4 py-3 border ${
      result.severity === 'SEVERE' ? 'border-red-800' :
      result.severity === 'HIGH' ? 'border-orange-800' :
      result.severity === 'MEDIUM' ? 'border-yellow-800' : 'border-green-800'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <Shield className={`w-4 h-4 ${stressColor(result.severity)}`} />
        <span className="text-sm font-semibold text-slate-200">{result.scenario}</span>
        <span className={`ml-auto text-xs font-bold ${stressColor(result.severity)}`}>
          {result.severity}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-800 rounded-lg px-2 py-1.5">
          <p className="text-xs text-slate-500">Estimated Loss</p>
          <p className="text-sm font-bold text-red-400">{result.estimated_loss_pct?.toFixed(1)}%</p>
        </div>
        <div className="bg-slate-800 rounded-lg px-2 py-1.5">
          <p className="text-xs text-slate-500">Recovery Est.</p>
          <p className="text-sm font-bold text-yellow-400">{result.recovery_months_est} months</p>
        </div>
      </div>
    </div>
  )
}

