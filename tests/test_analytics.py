"""
tests/test_analytics.py
━━━━━━━━━━━━━━━━━━━━━━━
Phase 3 Analytics Engine — Import & Smoke Test.

Verifies all analytics modules load correctly and core functions
return sensible values on real NAV data.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import date

print("=" * 60)
print("Phase 3 Analytics Engine — Import Test")
print("=" * 60)

# ── 1. Load real NAV data from SQLite ──
from src.data.storage import get_nav_history_df, init_db
init_db()
nav_df = get_nav_history_df(122640)  # Parag Parikh Flexi Cap

if nav_df.empty:
    print("❌ NAV data not found in SQLite. Run test_pipeline.py first.")
    sys.exit(1)

nav_series = nav_df["nav"]
print(f"\n✅ Loaded NAV series: {len(nav_series)} records for scheme 122640")
print(f"   Date range: {nav_series.index[0].date()} → {nav_series.index[-1].date()}")

# ── 2. Metrics ──
print("\n--- metrics.py ---")
from src.analytics.metrics import (
    calculate_cagr, calculate_max_drawdown,
    calculate_sharpe_ratio, calculate_sortino_ratio,
    calculate_volatility, full_scorecard
)
cagr_3y = calculate_cagr(nav_series, years=3)
cagr_all = calculate_cagr(nav_series)
mdd = calculate_max_drawdown(nav_series)
sharpe = calculate_sharpe_ratio(nav_series)
sortino = calculate_sortino_ratio(nav_series)
vol = calculate_volatility(nav_series)
print(f"  3Y CAGR      : {cagr_3y*100:.2f}%")
print(f"  All-time CAGR: {cagr_all*100:.2f}%")
print(f"  Max Drawdown : {mdd*100:.2f}%")
print(f"  Sharpe       : {sharpe:.3f}")
print(f"  Sortino      : {sortino:.3f}")
print(f"  Volatility   : {vol*100:.2f}%")
assert not np.isnan(cagr_3y), "CAGR should not be NaN"
assert mdd < 0, "MDD should be negative"
print("  ✅ metrics.py OK")

# ── 3. Timing Model ──
print("\n--- timing_model.py ---")
from src.analytics.timing_model import compute_timing_score, ema_distance_score, rsi_score
ema_sc = ema_distance_score(nav_series)
rsi_sc = rsi_score(nav_series)
timing = compute_timing_score(nav_series)
print(f"  EMA Distance Score : {ema_sc:.1f}/100")
print(f"  RSI Score          : {rsi_sc:.1f}/100")
print(f"  Total Timing Score : {timing['total_score']}/100")
print(f"  Interpretation     : {timing['interpretation']}")
assert 0 <= timing["total_score"] <= 100, "Score out of range"
print("  ✅ timing_model.py OK")

# ── 4. Macro Engine ──
print("\n--- macro_engine.py ---")
from src.analytics.macro_engine import compute_downturn_probability
sample_macro = {
    "vix": 18.5,
    "crude": 78.0,
    "crude_change_pct": 1.2,
    "usdinr": 84.2,
    "usdinr_change_pct": 0.3,
    "us10y": 4.3,
    "dxy": 103.5,
    "dxy_change_pct": 0.2,
    "gold": 2650.0,
    "gold_change_pct": 0.5,
}
danger = compute_downturn_probability(sample_macro)
print(f"  Danger Score : {danger['danger_score']}/100")
print(f"  Risk Level   : {danger['risk_level']}")
print(f"  Dry Powder % : {danger['dry_powder_pct']}%")
assert 0 <= danger["danger_score"] <= 100
print("  ✅ macro_engine.py OK")

# ── 5. Smart SIP ──
print("\n--- smart_sip.py ---")
from src.analytics.smart_sip import get_optimal_sip_dates, format_sip_recommendation, compute_value_averaging_schedule
best_dates = get_optimal_sip_dates()
sip_card = format_sip_recommendation(monthly_amount=10000, timing_score=timing["total_score"])
va_schedule = compute_value_averaging_schedule(
    nav_history=nav_series,
    monthly_target_growth=5000,
    current_portfolio_value=500000,
    base_monthly_sip=10000,
    months_ahead=6,
)
print(f"  Best SIP Dates : {[d['day'] for d in best_dates]}")
print(f"  Adjusted SIP   : ₹{sip_card['adjusted_monthly_amount']:,.0f}")
print(f"  VA Schedule    : {len(va_schedule)} months")
for m in va_schedule[:3]:
    print(f"    {m.month}: ₹{m.suggested_investment:,.0f} ({m.action})")
print("  ✅ smart_sip.py OK")

# ── 6. Allocation Advisor ──
print("\n--- allocation_advisor.py ---")
from src.analytics.allocation_advisor import compute_allocation_advice
advice = compute_allocation_advice(
    timing_score=timing["total_score"],
    danger_score=danger["danger_score"],
    hero_capital=100000,
)
print(f"  Posture         : {advice.emoji} {advice.posture}")
print(f"  Equity / Liquid : {advice.equity_pct:.0f}% / {advice.liquid_pct:.0f}%")
print(f"  SIP Multiplier  : {advice.sip_multiplier}×")
if advice.hero_deployment_plan:
    hp = advice.hero_deployment_plan
    print(f"  Hero Tranches   : {len(hp['tranches'])}")
assert advice.equity_pct + advice.liquid_pct == 100
print("  ✅ allocation_advisor.py OK")

# ── 7. Stress Tester ──
print("\n--- stress_tester.py ---")
from src.analytics.stress_tester import run_stress_test, BUILT_IN_SCENARIOS
result = run_stress_test(current_portfolio_value=500000, scenario_key="covid_crash_2020")
print(f"  Scenario        : {result.scenario_name}")
print(f"  Current Value   : ₹{result.current_portfolio_value:,.0f}")
print(f"  Projected Trough: ₹{result.projected_trough_value:,.0f}")
print(f"  Loss            : {result.projected_loss_pct}%")
print(f"  Recovery        : ~{result.recovery_months} months ({result.recovery_date_estimate})")
assert result.projected_trough_value < result.current_portfolio_value
print("  ✅ stress_tester.py OK")

# ── 8. Backtester ──
print("\n--- backtester.py ---")
from src.analytics.backtester import simulate_static_sip, simulate_dynamic_sip, compare_strategies
# Use last 5Y of data for speed
nav_5y = nav_series[nav_series.index >= nav_series.index[-1] - pd.DateOffset(years=5)]
static = simulate_static_sip(nav_5y, monthly_amount=10000)
dynamic = simulate_dynamic_sip(nav_5y, monthly_budget=10000)
comp = compare_strategies(static, dynamic)
print(f"  Static CAGR  : {static.cagr*100:.2f}%  (Corpus: ₹{static.final_corpus:,.0f})")
print(f"  Dynamic CAGR : {dynamic.cagr*100:.2f}%  (Corpus: ₹{dynamic.final_corpus:,.0f})")
print(f"  Verdict      : {comp['verdict']}")
print("  ✅ backtester.py OK")

# ── 9. Category Thermometer ──
print("\n--- category_thermometer.py ---")
from src.analytics.category_thermometer import compute_category_temperature
temp = compute_category_temperature("Flexi Cap", nav_series)
print(f"  Category     : {temp.category}")
print(f"  Temperature  : {temp.emoji} {temp.label} ({temp.temperature}/100)")
print(f"  SIP Rec      : {temp.sip_recommendation}")
assert 0 <= temp.temperature <= 100
print("  ✅ category_thermometer.py OK")

# ── 10. Goal Planner ──
print("\n--- goal_planner.py ---")
from src.analytics.goal_planner import FinancialGoal, generate_glide_path_recommendation
from datetime import date
goal = FinancialGoal(
    name="Retirement",
    target_corpus=10_000_000,
    target_date=date(2040, 1, 1),
    current_corpus=500_000,
)
rec = generate_glide_path_recommendation(goal)
print(f"  Goal            : {rec.goal_name}")
print(f"  Years Remaining : {rec.years_remaining}")
print(f"  Allocation      : {rec.equity_pct:.0f}% Equity / {rec.liquid_pct:.0f}% Liquid")
print(f"  Monthly SIP     : ₹{rec.monthly_sip_required:,.0f}")
print(f"  Projected Corpus: ₹{rec.projected_corpus:,.0f}")
print("  ✅ goal_planner.py OK")

# ── 11. Tax Pack ──
print("\n--- tax_pack.py ---")
from src.analytics.tax_pack import PurchaseLot, RedemptionTransaction, compute_capital_gains
lots = [
    PurchaseLot(122640, "Parag Parikh Flexi Cap", date(2020, 1, 15), 100.0, 35.0, 3500.0),
    PurchaseLot(122640, "Parag Parikh Flexi Cap", date(2022, 3, 10), 50.0, 55.0, 2750.0),
]
redemptions = [
    RedemptionTransaction(122640, "Parag Parikh Flexi Cap", date(2024, 6, 20), 80.0, 70.0, 5600.0),
]
tax_summary = compute_capital_gains(lots, redemptions)
print(f"  FY             : {tax_summary.financial_year}")
print(f"  Transactions   : {len(tax_summary.records)}")
print(f"  Total LTCG     : ₹{tax_summary.total_ltcg:,.2f}")
print(f"  Total STCG     : ₹{tax_summary.total_stcg:,.2f}")
print(f"  Est. Total Tax : ₹{tax_summary.estimated_tax_with_cess:,.2f}")
print("  ✅ tax_pack.py OK")

# ── 12. Underperformance Scanner ──
print("\n--- underperformance_scanner.py ---")
from src.analytics.underperformance_scanner import FundProfile, scan_fund_for_dud
fund = FundProfile(
    scheme_code=122640,
    scheme_name="Parag Parikh Flexi Cap — Regular Growth",
    nav_history=nav_series,
    category="Flexi Cap",
    is_direct_plan=False,
    expense_ratio=0.015,
)
dud_result = scan_fund_for_dud(fund, category_avg_cagr_3y=cagr_3y * 0.9)
print(f"  Fund     : {dud_result.scheme_name}")
print(f"  Is Dud   : {dud_result.is_dud}")
print(f"  Severity : {dud_result.severity}")
print(f"  Score    : {dud_result.score}/100")
print("  ✅ underperformance_scanner.py OK")

# ── 13. Ledger ──
print("\n--- ledger.py ---")
from src.analytics.ledger import log_prediction, get_model_accuracy_stats
log_prediction(
    scheme_code=122640,
    prediction_date=date.today(),
    prediction="BUY",
    timing_score=timing["total_score"],
    danger_score=danger["danger_score"],
    nav_at_prediction=float(nav_series.iloc[-1]),
)
stats = get_model_accuracy_stats()
print(f"  Total predictions logged : {stats.get('total_predictions', 0)}")
print("  ✅ ledger.py OK")

print("\n" + "=" * 60)
print("✅ ALL PHASE 3 ANALYTICS MODULES PASSED!")
print("=" * 60)

