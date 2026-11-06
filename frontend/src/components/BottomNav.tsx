import React from 'react'
import { useAppStore } from '../store/appStore'
import {
  Calculator, Briefcase, Compass, Bell, Settings,
} from 'lucide-react'

const TABS = [
  { key: 'planner',   icon: Calculator,  label: 'Planner' },
  { key: 'portfolio', icon: Briefcase,   label: 'Portfolio' },
  { key: 'explorer',  icon: Compass,     label: 'Explorer' },
  { key: 'alerts',    icon: Bell,        label: 'Alerts' },
  { key: 'settings',  icon: Settings,    label: 'Settings' },
] as const

export default function BottomNav() {
  const { activeTab, setTab } = useAppStore()

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-slate-900/95 backdrop-blur-sm border-t border-slate-800 flex max-w-lg mx-auto safe-bottom">
      {TABS.map(({ key, icon: Icon, label }) => (
        <button
          key={key}
          onClick={() => setTab(key)}
          className={`relative tab-btn ${activeTab === key ? 'text-indigo-400 font-semibold' : 'text-slate-500 hover:text-slate-300'}`}
        >
          <Icon className="w-5 h-5" />
          <span className="text-[10px]">{label}</span>
          {activeTab === key && (
            <span className="absolute -top-px left-1/2 -translate-x-1/2 w-8 h-0.5 bg-indigo-500 rounded-full shadow-sm shadow-indigo-500/50" />
          )}
        </button>
      ))}
    </nav>
  )
}

