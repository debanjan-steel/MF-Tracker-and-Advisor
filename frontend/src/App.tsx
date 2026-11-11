import React from 'react'
import './index.css'
import { useAuthStore } from './store/authStore'
import { useAppStore } from './store/appStore'
import AuthPage from './pages/AuthPage'
import PlannerTab from './pages/PlannerTab'
import PortfolioTab from './pages/PortfolioTab'
import ExplorerTab from './pages/ExplorerTab'
import AlertsTab from './pages/AlertsTab'
import SettingsTab from './pages/SettingsTab'
import BottomNav from './components/BottomNav'
import Header from './components/Header'

const TAB_TITLES: Record<string, string> = {
  planner: 'Investment Planner',
  portfolio: 'My Portfolio',
  explorer: 'Fund Explorer',
  alerts: 'Alerts',
  settings: 'Settings',
}

function App() {
  const { user } = useAuthStore()
  const { activeTab, syncWithCloud } = useAppStore()

  React.useEffect(() => {
    if (user) {
      syncWithCloud()
    }
  }, [user?.id])

  if (!user) {
    return <AuthPage />
  }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <Header title={TAB_TITLES[activeTab] ?? 'MF Analytics'} />

      {/* Main content — scrollable, padded above bottom nav */}
      <main className="flex-1 overflow-y-auto pb-24 pt-2">
        <div className="max-w-lg mx-auto px-4">
          {activeTab === 'planner' && <PlannerTab />}
          {activeTab === 'portfolio' && <PortfolioTab />}
          {activeTab === 'explorer' && <ExplorerTab />}
          {activeTab === 'alerts' && <AlertsTab />}
          {activeTab === 'settings' && <SettingsTab />}
        </div>
      </main>

      <BottomNav />
    </div>
  )
}

export default App
