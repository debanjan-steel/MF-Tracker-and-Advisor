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

print("\n" + "=" * 60)
print("✅ ALL FASTAPI BACKEND TESTS PASSED!")
print("=" * 60)

