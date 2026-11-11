// Shared type definitions for the MF Analytics platform

export interface SchemeInfo {
  scheme_code: number
  scheme_name: string
  fund_house?: string
  scheme_type?: string
  scheme_category?: string
  schemeCode?: number
  schemeName?: string
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

export interface Tranche {
  label: string
  amount: number
  pct: number
}

export interface HeroDeploymentPlan {
  total_capital: number
  equity_amount: number
  liquid_amount: number
  tranches: Tranche[]
  category_split?: Record<string, number>
  note?: string
}

export interface AllocationAdvice {
  posture: 'AGGRESSIVE' | 'GROWTH' | 'BALANCED' | 'DEFENSIVE' | 'CAPITAL_SAFE'
  equity_pct: number
  liquid_pct: number
  sip_multiplier?: number
  lumpsum_allowed?: boolean
  opportunity_score?: number
  action_items?: string[]
  category_weights?: Record<string, number>
  hero_deployment_plan?: HeroDeploymentPlan | null
  emoji?: string
  description?: string
  monthly_sip?: number
  lumpsum_now?: number
  stagger_months?: number
  message?: string
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
  category?: string
  units: number
  avg_nav: number
  current_nav: number
  invested: number
  current_value: number
  gain_loss: number
  xirr: number
  dud_severity: string
}

export interface GlidePathStep {
  year: number
  equity_pct: number
  debt_pct?: number
  liquid_pct?: number
}

export interface GoalPlan {
  target_amount?: number
  target_corpus?: number
  years?: number
  years_remaining?: number
  required_monthly_sip?: number
  monthly_sip_required?: number
  projected_corpus?: number
  goal_name?: string
  equity_pct?: number
  glide_path?: GlidePathStep[]
  glide_path_schedule?: GlidePathStep[]
  de_risk_action?: string
  milestone_alerts?: string[]
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
  entry_alert: boolean
  macro_alert: boolean
  sip_reminder: boolean
  dud_alert: boolean
  retention_days?: number
}

export interface InAppAlert {
  id: string
  alert_type: 'entry' | 'macro' | 'sip' | 'dud' | 'portfolio_empty' | 'plan_update'
  title: string
  message: string
  severity: 'SUCCESS' | 'WARNING' | 'INFO' | 'DANGER'
  scheme_code?: number | null
  scheme_name?: string | null
  action_text?: string | null
  created_at: string
  expires_at: string
  days_remaining: number
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
  financial_year?: string
  transaction_count?: number
  ltcg_total: number
  stcg_total: number
  ltcg_exempt: number
  ltcg_taxable: number
  tax_due: number
  lines: TaxLine[]
  warnings?: string[]
  csv_download?: string
}

// ── Tactical Investment Plan Types ──────────────────────────────────────────
export interface CategoryAllocation {
  category: string
  allocation_pct: number
  allocation_amount: number
  temperature_score: number
  temperature_label: string
  temperature_emoji: string
  valuation_status: string
  rationale: string
  color: string
}

export interface RecommendedFund {
  category: string
  fund_name: string
  scheme_code: number
  cagr_3y: number
  cagr_5y: number
  sharpe: number
  max_drawdown: number
  allocation_pct: number
  allocation_amount: number
  action_timing: string
  timing_rationale: string
  is_dip_trigger?: boolean
  predicted_dip_pct?: number
  predicted_dip_window?: string
}

export interface MacroCatalyst {
  event: string
  date: string
  impact: string
  action: string
}

export interface ExecutionRoadmapPhase {
  month: string
  action: string
  deployed_equity: number
  parked_liquid: number
  status: string
}

export interface TacticalPlan {
  capital: number
  posture: string
  timing_score: number
  danger_score: number
  forecast_summary: string
  category_allocations: CategoryAllocation[]
  fund_recommendations: RecommendedFund[]
  macro_catalysts: MacroCatalyst[]
  execution_roadmap: ExecutionRoadmapPhase[]
}

export interface SavedInvestmentPlanPayload {
  capital: number
  hasMonthlyBudget: boolean
  monthlyLimit: string
  hasGoal: boolean
  goalMode: 'target' | 'retirement'
  goalTarget: string
  goalYears: string
  currentAge: string
  strategyMode: 'tactical' | 'strict_equity'
  tacticalPlan: TacticalPlan
  timing?: TimingScore | null
  goal?: GoalPlan | null
  savedAt: string
}

export interface SavedGoalPlan {
  id: string
  goal_name: string
  target_corpus: number
  years: number
  required_monthly_sip: number
  projected_corpus: number
  equity_pct: number
  liquid_pct: number
  glide_path: GlidePathStep[]
  milestone_alerts?: string[]
  created_at?: string
  updated_at?: string
}

// ── Probabilistic Monte Carlo Types ─────────────────────────
export interface MonteCarloPoint {
  day: number
  date: string
  p10: number
  p25: number
  p50: number
  p75: number
  p90: number
}

export interface MonteCarloResponse {
  scheme_code?: number
  scheme_name: string
  current_nav?: number
  current_portfolio_value?: number
  horizon_days: number
  num_simulations: number
  annualized_drift: number
  annualized_volatility: number
  vix_scale_factor: number
  var_95_pct: number
  cvar_95_pct: number
  prob_loss_pct: number
  cone_spread_pct: number
  volatility_regime: string
  summary_insight: string
  fan_series: MonteCarloPoint[]
}

// ── Black Swan Stress Testing Types ──────────────────────────
export interface CategoryStressImpact {
  category: string
  scheme_name: string
  current_value: number
  scenario_impact_pct: number
  projected_trough_value: number
  loss: number
}

export interface DetailedStressTestResult {
  scenario_name: string
  scenario_description: string
  current_portfolio_value: number
  projected_trough_value: number
  projected_loss_amount: number
  projected_loss_pct: number
  recovery_months: number
  recovery_date_estimate: string
  category_breakdown: CategoryStressImpact[]
  worst_hit_category: string
  most_resilient_category: string
  recommended_action: string
  silver_lining: string
}

export interface StressScenarioMeta {
  key: string
  name: string
  event_year?: number
  drawdown_pct: number
  recovery_months: number
  category_tag: string
  description: string
  category_impacts: Record<string, number>
  is_live_monitored?: boolean
  status?: string
}

// ── Historical Macro Analogue & Hedging Types ────────────────
export interface HistoricalAnalogue {
  id: string
  name: string
  period: string
  similarity_score: number
  description: string
  drawdowns: {
    nifty_50: number
    midcap: number
    smallcap: number
    liquid_debt: number
  }
  duration_months: number
  recovery_months: number
  best_performer: string
  institutional_lesson: string
}

export interface DynamicHedgingPlan {
  macro_danger_score: number
  recommended_hedge_pct: number
  hedge_category: string
  preservation_posture: string
  hedging_rationale: string
  unhedge_exit_trigger: string
  safe_haven_funds: {
    category: string
    scheme_name: string
    yield_est: string
  }[]
}

export interface MacroAnalogueResponse {
  current_snapshot: {
    vix: number
    crude: number
    us10y: number
    usdinr: number
    dxy: number
  }
  macro_danger_score: number
  top_analogue: HistoricalAnalogue
  runner_up: HistoricalAnalogue
  hedging_plan: DynamicHedgingPlan
  ranked_analogues: {
    id: string
    name: string
    period: string
    similarity_score: number
    drawdowns: Record<string, number>
    recovery_months: number
  }[]
}

