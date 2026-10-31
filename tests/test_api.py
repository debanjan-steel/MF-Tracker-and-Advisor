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

print("\n" + "=" * 60)
print("✅ ALL FASTAPI BACKEND TESTS PASSED!")
print("=" * 60)

