// Shared type definitions for the MF Analytics platform

export interface SchemeInfo {
  scheme_code: number
  scheme_name: string
  fund_house: string
  scheme_type: string
  scheme_category: string
}

export interface NAVRecord {
  date: string
  nav: number
}

export interface TimingScore {
  score: number          // 0-100
  signal: 'STRONG_BUY' | 'BUY' | 'NEUTRAL' | 'CAUTION' | 'AVOID'
  label: string
  components: Record<string, number>
}

export interface MacroDanger {
  danger_score: number   // 0-100
  posture: string
  flags: string[]
}

export interface AllocationAdvice {
  posture: 'AGGRESSIVE' | 'GROWTH' | 'BALANCED' | 'DEFENSIVE' | 'CAPITAL_SAFE'
  equity_pct: number
  liquid_pct: number
  monthly_sip: number
  lumpsum_now: number
  stagger_months: number
  message: string
}

export interface Scorecard {
  scheme_code: number
  scheme_name: string
  cagr_1y: number
  cagr_3y: number
  cagr_5y: number
  sharpe: number
  sortino: number
  max_drawdown: number
  alpha: number
  beta: number
  up_capture: number
  down_capture: number
  overall_score: number
  grade: string
}

export interface StressResult {
  scenario: string
  estimated_loss_pct: number
  recovery_months_est: number
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'SEVERE'
}

export interface Thermometer {
  [category: string]: {
    status: 'COLD' | 'WARM' | 'HOT' | 'OVERHEATED'
    score: number
    recommendation: string
  }
}

export interface DudFund {
  scheme_code: number
  scheme_name: string
  severity: 'CLEAN' | 'MILD' | 'MODERATE' | 'SEVERE'
  flags: string[]
  suggestion: string
}

export interface Holding {
  scheme_code: number
  scheme_name: string
  units: number
  avg_nav: number
  current_nav: number
  invested: number
  current_value: number
  gain_loss: number
  xirr: number
  dud_severity: string
}

export interface GoalPlan {
  target_amount: number
  years: number
  required_monthly_sip: number
  projected_corpus: number
  glide_path: Array<{ year: number; equity_pct: number; debt_pct: number }>
}

export interface SIPRecommendation {
  base_amount: number
  adjusted_amount: number
  multiplier: number
  best_dates: number[]
  next_sip_date: string
  rationale: string
}

export interface AlertSettings {
  whatsapp_number: string
  entry_alert: boolean
  macro_alert: boolean
  sip_reminder: boolean
  dud_alert: boolean
}

export interface TaxLine {
  scheme_name: string
  units_sold: number
  buy_date: string
  sell_date: string
  buy_nav: number
  sell_nav: number
  gain_type: 'LTCG' | 'STCG'
  gain_amount: number
}

export interface TaxSummary {
  ltcg_total: number
  stcg_total: number
  ltcg_exempt: number
  ltcg_taxable: number
  tax_due: number
  lines: TaxLine[]
}

