import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
})

// Inject auth token on every request
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('access_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// ── Auth ────────────────────────────────────────────────────────────
export const authAPI = {
  signup: (email: string, password: string) =>
    api.post('/auth/signup', { email, password }),
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  logout: () => api.post('/auth/logout'),
  deleteAccount: () => api.delete('/auth/delete-account/confirm', { data: { confirm: true } }),
}

// ── Funds ────────────────────────────────────────────────────────────
export const fundsAPI = {
  search: (q: string) => api.get('/funds/search', { params: { q } }),
  scheme: (code: number) => api.get(`/funds/${code}`),
  navHistory: (code: number, years = 1.0) =>
    api.get(`/funds/${code}/nav`, { params: { years } }),
  latestNav: (code: number) => api.get(`/funds/${code}/latest-nav`),
}

// ── Analytics ────────────────────────────────────────────────────────
export const analyticsAPI = {
  timingScore: (code: number) => api.get(`/analytics/timing/${code}`),
  macroDanger: () => api.get('/analytics/macro-danger/live'),
  scorecard: (code: number) => api.get(`/analytics/scorecard/${code}`),
  backtest: (code: number, monthly: number, years: number) =>
    api.get(`/analytics/backtest/${code}`, { params: { monthly_amount: monthly, years } }),
  stressScenarios: () => api.get('/analytics/stress-test/scenarios'),
  stressTest: (scenario: string, portfolioValue = 500000) =>
    api.get(`/analytics/stress-test/${scenario}`, { params: { portfolio_value: portfolioValue } }),
  thermometer: (code = 122640, category = 'Equity') =>
    api.get(`/analytics/thermometer/${code}`, { params: { category } }),
  dudScan: (code = 122640) => api.get(`/analytics/dud-scan/${code}`),
}

// ── Planner ──────────────────────────────────────────────────────────
export const plannerAPI = {
  sipDates: () => api.get('/planner/sip-dates'),
  allocationAdvice: (capital: number, timingScore = 60, dangerScore = 20) =>
    api.post('/planner/allocation-advice', {
      timing_score: timingScore,
      danger_score: dangerScore,
      hero_capital: capital,
    }),
  goalPlanner: (target: number, years: number, currentMonthly = 0) => {
    const targetDate = new Date()
    targetDate.setFullYear(targetDate.getFullYear() + years)
    return api.post('/planner/goal', {
      name: 'Investment Goal',
      target_corpus: target,
      target_date: targetDate.toISOString().split('T')[0],
      current_corpus: currentMonthly * 12,
    })
  },
  sipRecommendation: (monthly: number, code = 122640) =>
    api.get('/planner/sip-recommendation', { params: { monthly_amount: monthly, scheme_code: code } }),
  taxPack: (lots: any[] = [], redemptions: any[] = []) =>
    api.post('/planner/tax-pack', {
      lots,
      redemptions,
      financial_year: '2026-27',
    }),
  valueAveraging: (code: number, targetGrowth: number, currentVal: number, baseSip: number) =>
    api.get(`/planner/value-averaging/${code}`, {
      params: {
        monthly_target_growth: targetGrowth,
        current_portfolio_value: currentVal,
        base_monthly_sip: baseSip,
      },
    }),
}

// ── Portfolio ────────────────────────────────────────────────────────
export const portfolioAPI = {
  uploadCAS: (file: File, panLast4 = '') => {
    const fd = new FormData()
    fd.append('file', file)
    if (panLast4) fd.append('pan_last4', panLast4)
    return api.post('/portfolio/upload-cas', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  holdings: () => api.get('/portfolio/holdings'),
  addHolding: (holding: any) => api.post('/portfolio/holdings', holding),
  xray: (holdings: any[]) => api.post('/portfolio/xray', holdings),
}

// ── Alerts ───────────────────────────────────────────────────────────
export const alertsAPI = {
  getSettings: () => api.get('/alerts/settings'),
  saveSettings: (data: object) => api.post('/alerts/settings', data),
  sendTest: () => api.post('/alerts/test'),
  history: () => api.get('/alerts/history'),
}
