import React from 'react'
import { TrendingUp, RefreshCw } from 'lucide-react'

interface Props {
  title?: string
}

export default function Header({ title = 'MF Analytics' }: Props) {
  return (
    <header className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800">
      <div className="max-w-lg mx-auto flex items-center justify-between px-4 h-14">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
            <TrendingUp className="w-4 h-4 text-white" />
          </div>
          <span className="text-base font-bold text-slate-100">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-600">Live · NSE</span>
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        </div>
      </div>
    </header>
  )
}

