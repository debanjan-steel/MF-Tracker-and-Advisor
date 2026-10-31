import sys
sys.path.insert(0, ".")

from src.data.mfapi_client import search_schemes, fetch_full_nav_history
from src.data.amfi_client import _normalise_date
from src.data.storage import init_db, incremental_sync, get_nav_history_df

init_db()

# 1. Search for Parag Parikh Flexi Cap
print("--- Searching for Parag Parikh Flexi Cap ---")
results = search_schemes("parag parikh flexi")
for r in results[:3]:
    print(f"  Code: {r['schemeCode']}  Name: {r['schemeName']}")

# 2. Fetch full NAV history for the first Direct Growth result
code = results[0]["schemeCode"]
print(f"\n--- Fetching full NAV history for scheme {code} ---")
history = fetch_full_nav_history(code)
nav_data = history.get("data", [])
meta = history.get("meta", {})
print(f"  Fund      : {meta.get('scheme_name')}")
print(f"  Category  : {meta.get('scheme_category')}")
print(f"  NAV count : {len(nav_data)}")
print(f"  Latest NAV: {nav_data[0]['nav']} on {nav_data[0]['date']}")
print(f"  Oldest NAV: {nav_data[-1]['nav']} on {nav_data[-1]['date']}")

# 3. Store via incremental sync
print("\n--- Running incremental sync into SQLite ---")

# Ensure the scheme metadata exists in the schemes table first
from src.data.storage import upsert_schemes
upsert_schemes([{
    "scheme_code": code,
    "scheme_name": meta.get("scheme_name", ""),
    "fund_house": meta.get("fund_house", ""),
    "scheme_type": meta.get("scheme_type", ""),
    "scheme_category": meta.get("scheme_category", ""),
}])
print(f"  Scheme metadata upserted for code {code}.")
records = [
    {"date": _normalise_date(d["date"]), "nav": float(d["nav"]), "nav_verified": False}
    for d in nav_data
]
inserted = incremental_sync(code, records)
print(f"  New records inserted: {inserted}")

# 4. Load back as DataFrame
df = get_nav_history_df(code)
print(f"\n--- DataFrame loaded from SQLite ---")
print(f"  Shape: {df.shape}")
print(df.head(3).to_string())
print("\nLive pipeline test PASSED.")
