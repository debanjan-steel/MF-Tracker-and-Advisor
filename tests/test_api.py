"""
tests/test_api.py
━━━━━━━━━━━━━━━━━
Phase 4 FastAPI Backend Smoke Test.
Verifies all routes load, API endpoints respond properly,
and health check passes.
"""

import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from src.api.main import app
from src.data.storage import init_db

init_db()

client = TestClient(app)

print("=" * 60)
print("Phase 4 FastAPI Backend — Route & Endpoint Tests")
print("=" * 60)

# 1. Health check
res = client.get("/health")
assert res.status_code == 200, f"Health check failed: {res.status_code}"
print("✅ GET /health ->", res.json())

# 2. Root check
res = client.get("/")
assert res.status_code == 200, f"Root check failed: {res.status_code}"
print("✅ GET / ->", res.json()["service"])

# 3. List all registered routes
print(f"\nTotal routes registered: {len(app.routes)}")
for route in app.routes:
    methods = getattr(route, "methods", None)
    if methods:
        method_str = ",".join(methods)
        print(f"  [{method_str:<10}] {route.path}")

# 4. Fund search endpoint (public)
res = client.get("/funds/search?q=Parag")
assert res.status_code == 200, f"Search failed: {res.status_code}"
print(f"\n✅ GET /funds/search?q=Parag -> Found {len(res.json().get('results', []))} funds")

# 5. Stress test scenarios endpoint
# Mock user auth bypass for testing endpoints that require current_user
from src.auth.supabase_client import get_current_user
app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user-123", "email": "test@example.com"}

res = client.get("/analytics/stress-test/scenarios")
assert res.status_code == 200, f"Stress scenarios failed: {res.status_code}"
print(f"✅ GET /analytics/stress-test/scenarios -> {len(res.json()['scenarios'])} scenarios available")

# 6. SIP best dates endpoint
res = client.get("/planner/sip-dates")
assert res.status_code == 200, f"SIP dates failed: {res.status_code}"
print(f"✅ GET /planner/sip-dates -> {len(res.json()['best_sip_dates'])} dates returned")

# 7. Optimal SIP recommendation
res = client.get("/planner/sip-recommendation?monthly_amount=10000&scheme_code=122640")
assert res.status_code == 200, f"SIP recommendation failed: {res.status_code}"
print(f"✅ GET /planner/sip-recommendation -> Next date: {res.json()['next_sip_date_formatted']}")

# 8. Alert settings
res = client.get("/alerts/settings")
assert res.status_code == 200, f"Alert settings failed: {res.status_code}"
print(f"✅ GET /alerts/settings -> Settings loaded for user {res.json()['user_id']}")

# 9. Email failsafe & duplicate registration block
res = client.get("/auth/check-email?email=debanjan17052002@gmail.com")
assert res.status_code == 200, f"Check email failed: {res.status_code}"
assert res.json()["exists"] is True, "Existing email was not detected"
assert "Forgot password" in res.json()["message"], "Guidance message does not mention Forgot password"
print(f"✅ GET /auth/check-email -> Detected existing email & advised: {res.json()['message']}")

# 10. Attempt duplicate signup block
res = client.post("/auth/signup", json={"email": "debanjan17052002@gmail.com", "password": "Password123!"})
assert res.status_code == 400, f"Signup should have been blocked: {res.status_code}"
assert "Forgot password" in res.json()["detail"], "Blocked signup message does not direct to Forgot Password"
print(f"✅ POST /auth/signup (duplicate email blocked) -> {res.json()['detail']}")

# 10b. Token Refresh Endpoint
from src.auth.supabase_client import _generate_local_token
local_tok = _generate_local_token("test-user-123", "test@example.com")
res = client.post("/auth/refresh", json={"refresh_token": local_tok})
assert res.status_code == 200, f"Refresh failed: {res.status_code}"
assert "access_token" in res.json(), "Access token missing in refresh response"
print("✅ POST /auth/refresh -> Successfully verified & renewed session token")

# 11. Initial Add Holding
h_payload1 = {
    "scheme_code": 122640,
    "scheme_name": "Parag Parikh Flexi Cap Fund - Regular Plan",
    "invested_amount": 10000.0,
    "units": 100.0,
    "avg_nav": 100.0,
    "current_value": 10000.0,
    "investment_type": "LUMPSUM"
}
res = client.post("/portfolio/holdings", json=h_payload1)
assert res.status_code == 200, f"Add holding failed: {res.status_code}"
assert res.json()["action"] in ("created", "accumulated"), "Holding action not reported"
print(f"✅ POST /portfolio/holdings (add) -> {res.json()['action']} successfully")

# 12. Accumulate Holding (fund that already exists - adds auto calculated NAV amount)
h_payload2 = {
    "scheme_code": 122640,
    "scheme_name": "Parag Parikh Flexi Cap Fund - Regular Plan",
    "invested_amount": 5000.0,
    "units": 50.0,
    "avg_nav": 100.0,
    "current_value": 5000.0,
    "investment_type": "LUMPSUM"
}
res = client.post("/portfolio/holdings", json=h_payload2)
assert res.status_code == 200, f"Accumulate holding failed: {res.status_code}"
assert res.json()["action"] == "accumulated", f"Expected action 'accumulated', got: {res.json().get('action')}"
assert res.json()["holding"]["units"] >= 150.0, f"Expected total units >= 150, got: {res.json()['holding']['units']}"
assert "added_value" in res.json()["holding"], "added_value missing from holding payload"
print(f"✅ POST /portfolio/holdings (accumulate existing) -> {res.json()['message']}")

# 13. 1-Click ITR Tax Pack (Auto-generate from user's holdings)
tax_payload = {
    "lots": [],
    "redemptions": [],
    "financial_year": "2026-27"
}
res = client.post("/planner/tax-pack", json=tax_payload)
assert res.status_code == 200, f"POST /planner/tax-pack failed: {res.status_code} {res.text}"
data = res.json()
assert "ltcg_total" in data, "ltcg_total missing from tax pack response"
assert "stcg_total" in data, "stcg_total missing from tax pack response"
assert "ltcg_exempt" in data, "ltcg_exempt missing from tax pack response"
assert "tax_due" in data, "tax_due missing from tax pack response"
assert "lines" in data, "lines missing from tax pack response"
assert "csv_download" in data, "csv_download missing from tax pack response"
assert len(data["lines"]) >= 1, "Expected at least 1 tax line from portfolio holdings"
print(f"✅ POST /planner/tax-pack -> Generated successfully: {len(data['lines'])} lines, Tax Due: ₹{data['tax_due']}")

# 14. 1-Click ITR Tax Pack CSV export
res = client.get("/planner/tax-pack?format=csv")
assert res.status_code == 200, f"GET /planner/tax-pack?format=csv failed: {res.status_code}"
assert "text/csv" in res.headers.get("content-type", ""), f"Expected CSV content-type, got: {res.headers.get('content-type')}"
assert "Financial Year" in res.text, "CSV header missing 'Financial Year'"
assert "attachment" in res.headers.get("content-disposition", ""), "Missing Content-Disposition attachment header"
print(f"✅ GET /planner/tax-pack?format=csv -> Downloadable CSV received ({len(res.text)} bytes)")

# 15. Portfolio Alerts Feed Ranking & Auto-Update
res = client.get("/alerts/feed")
assert res.status_code == 200, f"GET /alerts/feed failed: {res.status_code}"
alerts_list = res.json()
assert len(alerts_list) > 0, "Alerts feed is empty"
# Ensure portfolio_empty notice is NOT present because user has holdings
assert not any(a["alert_type"] == "portfolio_empty" for a in alerts_list), "Stale portfolio_empty alert was returned"
# Ensure portfolio alerts exist
portfolio_types = [a["alert_type"] for a in alerts_list if a["alert_type"] in ("dud", "entry", "sip") or a.get("scheme_code")]
assert len(portfolio_types) > 0, "No portfolio-specific alerts generated for user's held funds"
# Ensure portfolio alerts appear at the top before general macro alerts
macro_indices = [i for i, a in enumerate(alerts_list) if a["alert_type"] == "macro"]
portfolio_indices = [i for i, a in enumerate(alerts_list) if a["alert_type"] in ("dud", "entry", "sip")]
if macro_indices and portfolio_indices:
    assert min(portfolio_indices) < min(macro_indices), "Portfolio alerts are not prioritized at the top of the feed"
print(f"✅ GET /alerts/feed -> {len(alerts_list)} alerts loaded. Portfolio alerts strictly prioritized at the top!")

# 16. Portfolio & Mutual Fund Multi-Horizon Future Forecaster
forecast_payload = {
    "holdings": [
        {
            "scheme_code": 122640,
            "scheme_name": "Parag Parikh Flexi Cap Fund",
            "units": 50.0,
            "invested": 3000.0,
            "current_value": 4277.07,
            "current_nav": 85.54,
            "category": "Equity",
        }
    ]
}
res = client.post("/analytics/portfolio-forecast", json=forecast_payload)
assert res.status_code == 200, f"POST /analytics/portfolio-forecast failed: {res.status_code} {res.text}"
f_data = res.json()
assert "total_portfolio" in f_data, "total_portfolio missing from forecast response"
assert "funds" in f_data, "funds list missing from forecast response"
assert "calibration" in f_data, "calibration missing from forecast response"
assert len(f_data["total_portfolio"]["milestones"]) == 6, f"Expected 6 milestones, got {len(f_data['total_portfolio']['milestones'])}"
assert f_data["calibration"]["normal_market_accuracy"] > 70.0, "Expected normal market accuracy > 70%"
print(f"✅ POST /analytics/portfolio-forecast -> Generated {len(f_data['total_portfolio']['milestones'])} milestones. Normal market match rate: {f_data['calibration']['normal_market_accuracy']}%")

# 16b. Empty Portfolio Forecast Initial Zero State
empty_forecast_res = client.post("/analytics/portfolio-forecast", json={"holdings": []})
assert empty_forecast_res.status_code == 200, f"POST /analytics/portfolio-forecast (empty) failed: {empty_forecast_res.status_code}"
empty_data = empty_forecast_res.json()
assert empty_data.get("empty") is True or len(empty_data.get("funds", [])) == 0, "Empty portfolio forecast should have 0 funds"
assert empty_data["total_portfolio"]["current_value"] == 0.0, "Empty portfolio current_value should be 0.0"
assert "Add mutual fund" in empty_data.get("message", ""), "Empty forecast should advise adding mutual funds"
print(f"✅ POST /analytics/portfolio-forecast (0 holdings) -> Correctly reset to 0 initial value with empty portfolio guidance")

# 17. Forecast Recalibrate Engine Loop
res = client.post("/analytics/forecast-recalibrate", json=forecast_payload)
assert res.status_code == 200, f"POST /analytics/forecast-recalibrate failed: {res.status_code} {res.text}"
recalib_data = res.json()
assert recalib_data.get("success") is True, "Recalibration did not return success"
print(f"✅ POST /analytics/forecast-recalibrate -> Engine recalibrated against normal market trends with outlier shock filtering")

# 18. Dynamic Black Swan Simulator & Rolling Macro Event Deck
res = client.get("/analytics/stress-test/scenarios")
assert res.status_code == 200, f"GET /analytics/stress-test/scenarios failed: {res.status_code}"
sc_deck = res.json()
assert "scenarios" in sc_deck, "scenarios key missing from stress test response"
assert "retired_oldest_event" in sc_deck, "retired_oldest_event metadata missing"
assert len(sc_deck["scenarios"]) <= 7, f"Active scenarios exceed max threshold of 7: {len(sc_deck['scenarios'])}"
# Verify modern event is active
has_modern_event = any(s.get("event_year", 0) >= 2025 for s in sc_deck["scenarios"])
assert has_modern_event, "No modern 2025-2026 macro events found in active deck"
print(f"✅ GET /analytics/stress-test/scenarios -> {len(sc_deck['scenarios'])} modern tracked events active. Oldest retired: {sc_deck['retired_oldest_event']}")

# 19. Dynamic Event Self-Update & Oldest Retirement
sync_res = client.post("/analytics/stress-test/sync-events")
assert sync_res.status_code == 200, f"POST /analytics/stress-test/sync-events failed: {sync_res.status_code}"
sync_data = sync_res.json()
assert sync_data.get("success") is True, "Sync events did not return success"
print(f"✅ POST /analytics/stress-test/sync-events -> Macro engine successfully synchronized live modern crisis deck")

# 20. Universal State Persistence & Automatic Schema Migration
# Test syncing legacy data format (old field names, strings, bare integer watchlists)
legacy_state = {
    "holdings": [
        {
            "scheme_code": "122640",
            "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Plan",
            "invested": "50000",
            "units": "800.5",
            "investment_type": "SIP",
        }
    ],
    "watchlist": [122640, "118989"],
    "saved_goals": [
        {
            "goal_name": "Retirement Corpus",
            "target": "25000000",
            "years": "15",
            "required_monthly_sip": "42000",
        }
    ],
    "saved_investment_plan": {
        "capital": "250000",
        "plan_data": {"tacticalPlan": {"capital": 250000, "posture": "GROWTH"}},
    },
    "alert_preferences": {
        "entry_alert": 1,
        "macro_alert": "true",
    },
}

sync_state_res = client.post("/user/sync", json=legacy_state)
assert sync_state_res.status_code == 200, f"POST /user/sync failed: {sync_state_res.status_code} {sync_state_res.text}"
sync_res_body = sync_state_res.json()
assert sync_res_body.get("success") is True, "Sync did not return success"
print(f"✅ POST /user/sync (Legacy schema migration) -> Upgraded & synced: {sync_res_body.get('details')}")

# Verify GET /user/state returns fully normalized types and values
state_res = client.get("/user/state")
assert state_res.status_code == 200, f"GET /user/state failed: {state_res.status_code} {state_res.text}"
migrated_state = state_res.json()
assert migrated_state["schema_version"] == 3, f"Expected schema_version 3, got {migrated_state.get('schema_version')}"

# Verify holding migration: 'invested' migrated to 'invested_amount' as float, units as float
migrated_holding = next((h for h in migrated_state["holdings"] if str(h["scheme_code"]) == "122640"), None)
assert migrated_holding is not None, "Holding 122640 not found in migrated state"
assert isinstance(migrated_holding["invested_amount"], float) and migrated_holding["invested_amount"] == 50000.0, "invested_amount not migrated properly"
assert isinstance(migrated_holding["units"], float) and migrated_holding["units"] == 800.5, "units not migrated to float"
assert migrated_holding["avg_nav"] > 0, "avg_nav not calculated"

# Verify watchlist migration: integers migrated to objects
assert len(migrated_state["watchlist"]) >= 2, "Watchlist items missing"
assert all(isinstance(w["scheme_code"], int) and isinstance(w["scheme_name"], str) for w in migrated_state["watchlist"]), "Watchlist not normalized"

# Verify goal migration: 'target' migrated to 'target_corpus' as float, years as int
migrated_goal = migrated_state["saved_goals"][0]
assert migrated_goal["target_corpus"] == 25000000.0, f"Expected 25000000.0 target_corpus, got {migrated_goal['target_corpus']}"
assert migrated_goal["years"] == 15, f"Expected 15 years, got {migrated_goal['years']}"

print(f"✅ GET /user/state -> Universal state verified across holdings, watchlist, goals, plans (Schema v{migrated_state['schema_version']})")

# 21. Watchlist dedicated endpoint
wl_post = client.post("/user/watchlist", json={"watchlist": [122640, {"scheme_code": 118989, "scheme_name": "Mirae Asset Large Cap"}]})
assert wl_post.status_code == 200, f"POST /user/watchlist failed: {wl_post.text}"
wl_get = client.get("/user/watchlist")
assert wl_get.status_code == 200, f"GET /user/watchlist failed: {wl_get.text}"
assert len(wl_get.json()["watchlist"]) == 2, "Watchlist length mismatch"
print(f"✅ POST & GET /user/watchlist -> Dedicated watchlist sync verified ({len(wl_get.json()['watchlist'])} funds)")

print("\n" + "=" * 60)
print("✅ ALL FASTAPI BACKEND TESTS PASSED!")
print("=" * 60)

