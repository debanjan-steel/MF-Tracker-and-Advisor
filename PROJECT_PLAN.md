# 🇮🇳 Indian Mutual Funds Analytics & Market Timing Platform
## Master Project Roadmap & Execution Plan

> **Note for Developers / AI Assistants**: This document tracks the active state, architectural decisions, and next steps for this project. Update this file whenever tasks transition states, requirements evolve, or new features are designed.

---

### 📌 Status Legend
- ✅ **`[COMPLETED]`** — Built, tested, and verified.
- 🔄 **`[IN PROGRESS]`** — Currently active task.
- ⏳ **`[PLANNED]`** — Queued for future implementation.
- ⏸️ **`[ON HOLD]`** — Blocked or waiting for design input/clarification.

---

### 🧭 Quick Resume Guide (Where to pick up)
- **Current Milestone**: Phase 6 — Cloud Deployment & Verification Complete! 🎉
- **Active Task**: ⏳ Task 4.4 & Step 4: Add GitHub Actions Repository Secrets for 24/7 Nightly Cloud Sync (9:30 PM IST), and optional Twilio WhatsApp credentials.
- **Live URLs**:
  - **Frontend PWA (Vercel)**: `https://mf-tracker-and-advisor.vercel.app/`
  - **Backend REST API (Render)**: `https://mf-tracker-and-advisor.onrender.com/`
  - **Database & Auth (Supabase)**: `https://uwlvxpweowhwlgkvhsmm.supabase.co`
- **Last Completed**: Full production cloud deployment. Live signup, JWT sessions, API routing, and instant account deletion verified 100% operational across Vercel, Render, and Supabase.

---

### 🏛️ Core Architecture: Dual-Source Data Strategy

> 🎯 **Core Investment Philosophy — 100% Pure Equity Focus**:
> The platform is built exclusively for **Equity Mutual Funds** (Large Cap, Flexi Cap, Mid Cap, Small Cap, and Sectoral/Thematic). Multi-asset rebalancing into physical gold or debt bonds is deliberately excluded. Any temporary capital waiting for deployment (dry powder) is held strictly in ultra-short cash equivalents (Arbitrage/Liquid) solely to earn risk-free returns until deployed into equities.

To ensure zero downtime, high data integrity, and resilience against external API failures, the platform implements an automated **Primary + Fallback + Cross-Verification** data pipeline:

```
                     ┌──────────────────────────────────────────────┐
                     │           DATA INGESTION CONTROLLER          │
                     └──────────────────────┬───────────────────────┘
                                            │
                      Try Primary First     │
                   ┌────────────────────────┴───────────────────────┐
                   ▼                                                ▼
       ┌───────────────────────┐                        ┌───────────────────────┐
       │     PRIMARY SITE      │                        │    SECONDARY SITE     │
       │       MFAPI.in        │                        │     AMFI Official     │
       │  (Fast JSON REST API) │                        │ (Statutory Authority) │
       └───────────┬───────────┘                        └───────────┬───────────┘
                   │                                                │
         Success?  │                                                │ Fallback if Primary
                   ├────────────► [ Cache to SQLite ] ◄─────────────┤ fails / times out
                   │                     ▲
                   │                     │
                   └────────── Verification Check ──────────────────┘
                             (Spot-checks latest NAV)
```

1. **Primary Source — MFAPI.in (`api.mfapi.in`)**:
   - High-performance REST API.
   - Supplies full historical daily NAV arrays and scheme metadata in clean JSON format.
   - Primary target for all historical data extraction and search queries.

2. **Secondary / Verification Source — AMFI India Official (`portal.amfiindia.com`)**:
   - The statutory regulatory body and single source of truth for all Indian mutual funds under SEBI.
   - Provides official daily NAV feeds (`NAVAll.txt`).
   - **Automated Fallback**: Activates automatically if MFAPI is unreachable, times out, or returns HTTP 5xx.
   - **Cross-Verification**: Periodically cross-validates latest closing NAVs between MFAPI and AMFI. If discrepancy > 0.01%, AMFI official value takes precedence and a warning log is recorded.

---

### 🌐 Macro Event & Shock Ingestion Architecture (3-Stream Pipeline)

To predict market downturn timelines and assess risk from real-world events (e.g., wars, crude oil shocks, interest rate cycles), the platform ingests macro signals via 3 automated, zero-cost streams:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MACRO DATA INGESTION ENGINE                           │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│       STREAM 1        │   │       STREAM 2        │   │       STREAM 3        │
│ Live Financial Proxies│   │   Scheduled Events    │   │  Breaking News & RSS  │
│ (Crude, VIX, US 10Y)  │   │  (Elections, Budgets) │   │ (Sentiment / Alerts)  │
│  Via: `yfinance` API  │   │ Via: Calendar Matrix  │   │ Via: Google News RSS  │
└───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
            │                           │                           │
            └───────────────────────────┼───────────────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │ SQLite Macro Cache (Local DB) │
                        └───────────────────────────────┘
```

1. **Stream 1: Live Market Shock Proxies (`yfinance` API — Free & Real-Time)**:
   - **Brent Crude Oil (`BZ=F`)**: India imports >85% of crude; spikes >\$90–\$100 trigger CAD expansion, rupee depreciation, and corporate margin compression.
   - **India VIX (`^INDIAVIX`)**: Quantifies market fear and volatility.
   - **US 10-Year Treasury Yield (`^TNX`)**: Drives foreign institutional (FII) capital flows out of emerging markets into US debt.
   - **US Dollar Index (`DX-Y.NYB`) & USD/INR (`USDINR=X`)**: Tracks currency risk and foreign capital flight.
   - **Gold Futures (`GC=F`)**: Global safe-haven asset demand indicator.
   - **Benchmark Indices**: Nifty 50 (`^NSEI`), Nifty Midcap 150.

2. **Stream 2: Scheduled Macro Calendar Matrix (`src/data/macro_calendar.json`)**:
   - Curated structured dates of high-impact scheduled events:
     - General Elections (every 5 years, pre-election volatility window).
     - Union Budget of India (Annually on Feb 1).
     - RBI Monetary Policy Committee (MPC) Rate Decisions (Bi-monthly).
     - US Fed FOMC Interest Rate Meetings (8 times/year).
   - The engine computes "Days to Major Event" and raises uncertainty scores within 15–30 days of high-impact dates.

3. **Stream 3: Unscheduled Shocks & News Sentiment**:
   - **Direct Threshold Triggers**: Automated rules (e.g., `Crude Oil > +4% in 24h` or `India VIX > 20`) trigger an immediate **"Active Macro Shock Alert"** without relying on error-prone text analysis.
   - **Google News RSS Feed**: Free query endpoint (`https://news.google.com/rss/search?q=Nifty+OR+RBI+OR+"Crude+Oil"+when:1d`) for surfacing relevant top headlines.

---

### ☁️ Autonomous Cloud & Zero-Laptop Execution Architecture

The platform operates **100% autonomously in the cloud for $0**, with **zero dependency on keeping your personal laptop running**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       24/7 AUTONOMOUS CLOUD ENGINE                          │
│                          (Your Laptop is OFF)                               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
     Runs every night at 9:30 PM IST   │
 ┌─────────────────────────────────────┴─────────────────────────────────────┐
 │ 1. Free Cloud Scheduled Worker: GitHub Actions (Free 2,000 min/month)     │
 │    • Wakes up automatically on Microsoft's cloud servers at 9:30 PM       │
 │    • Pulls latest NAVs from MFAPI / AMFI                                  │
 │    • Ingests Crude Oil, VIX, US 10Y data                                  │
 │    • Checks past predictions: calculates error & directional hit rate     │
 │    • Retrains ML models if needed and generates tomorrow's forecasts      │
 │    • Shuts down cleanly (uses ~30 seconds of compute/day)                 │
 └─────────────────────────────────────┬─────────────────────────────────────┘
                                       │ Updates
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 2. Free Cloud Database: Supabase / Turso (Free Tier)                      │
 │    • Stores historical NAVs, prediction ledger, and accuracy scorecards   │
 │    • Always online, secure, accessible from anywhere                      │
 └─────────────────────────────────────┬─────────────────────────────────────┘
                                       │ Serves data to
                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 3. Standalone Android App / PWA (Installed on phone)                      │
 │    • Open on Android phone from anywhere in the world                     │
 │    • Full-screen native experience, instant charts, alerts & timing gauge │
 │    • Zero battery drain because all heavy calculations happened in cloud  │
 └───────────────────────────────────────────────────────────────────────────┘
```

---

### 🧠 Self-Improving ML Feedback Loop & Prediction Ledger

To continuously verify, audit, and improve forecasting accuracy, the backend maintains a **closed-loop learning cycle**:

```
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │                       CONTINUOUS MODEL FEEDBACK LOOP                             │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
 1. Generate & Log Prediction             ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ Model generates probabilistic outcome (expected return band, confidence bounds)  │
 │ ──► Written to Cloud DB `prediction_ledger` with Timestamp & Model Version       │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
 2. Target Date Arrival & Audit           ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ Automated Reconciliation Routine runs when actual closing NAV arrives:           │
 │ • Computes Error (Residual), Directional Hit Rate (Up/Down accuracy), MAE        │
 │ ──► Written to `model_accuracy_metrics`                                          │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
 3. Automated Walk-Forward Retraining     ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │ Retrainer engine re-calibrates feature weights (penalizing patterns that caused  │
 │ recent forecast errors) and deploys updated model weights autonomously           │
 └──────────────────────────────────────────────────────────────────────────────────┘
```

---

### 🗺️ Project Phases & Task Breakdown

#### Phase 1: Environment & Workspace Setup
- [x] ✅ **Task 1.1**: Initialize Python 3.13 local virtual environment (`.venv`).
- [x] ✅ **Task 1.2**: Configure `.vscode/settings.json` for interpreter path and terminal auto-activation.
- [x] ✅ **Task 1.3**: Configure `.python-version` and `.gitignore`.
- [x] ✅ **Task 1.4**: Add terminal activation helper scripts (`activate.ps1`, `activate.bat`).
- [x] ✅ **Task 1.5**: Establish Master Project Plan and Progress Tracking mechanism (`PROJECT_PLAN.md`).

---

#### Phase 2: Dual-Source Historical Data Ingestion & Caching Engine
- [x] ✅ **Task 2.1**: Define dependency manifest (`requirements.txt`):
  - `pandas`, `numpy`, `requests`, `yfinance`, `pydantic`, `sqlite3` / `sqlalchemy`.
- [x] ✅ **Task 2.2**: Build **Primary Data Client** (`src/data/mfapi_client.py`):
  - Scheme master search (all active Indian mutual funds & AMFI codes).
  - Historical daily NAV fetcher with retry logic and error handling.
- [x] ✅ **Task 2.3**: Build **Secondary & Verification Client** (`src/data/amfi_client.py`):
  - AMFI daily official feed parser (`NAVAll.txt`).
  - AMFI historical NAV lookup for fallback.
- [x] ✅ **Task 2.4**: Build **Resilient Ingestion Controller** (`src/data/data_manager.py`):
  - Auto-failover logic (Primary → Secondary).
  - Cross-verification engine (checks NAV consistency between MFAPI and AMFI).
- [x] ✅ **Task 2.5**: Build **Local Caching Layer** (`src/data/storage.py`):
  - SQLite database schema for storing scheme metadata and historical daily NAV series.
  - Incremental sync mechanism (only download latest NAV delta rather than whole history every time).
- [x] ✅ **Task 2.6**: Build **Macro & Benchmark Ingestion Client** (`src/data/macro_client.py`):
  - Ingestion for benchmark indices (Nifty 50, Nifty Midcap 150) and macro shock proxies (Brent Crude `BZ=F`, India VIX `^INDIAVIX`, US 10Y Yield `^TNX`, US Dollar Index `DX-Y.NYB`, USD/INR `USDINR=X`, Gold `GC=F`) via `yfinance`.
- [x] ✅ **Task 2.7**: Seed **Scheduled Macro Events Calendar Matrix** (`src/data/macro_calendar.json`):
  - Structured calendar of high-impact events (Union Budgets, RBI MPC meetings, US Fed FOMC rate decisions, General Elections).
- [x] ✅ **Task 2.8**: Build **Automated CAS (Consolidated Account Statement) Ingestion Engine** (`src/data/cas_parser.py`):
  - Ingests official CAMS / KFintech / MFCentral CAS PDF statements via open-source `casparser`.
  - In-memory password decryption (using user's PAN).
  - Automatically extracts the user's complete multi-year investment ledger: Scheme AMFI codes, Folio numbers, transaction dates, amounts, transaction types (SIP vs. Lumpsum vs. Switch), units, and purchase NAVs with zero manual data entry.
  - Includes a quick-entry manual fallback form for users holding only 1–2 funds.

---

#### Phase 3: Financial Analytics, Macro Shocks & Market Timing Engine
- [x] ✅ **Task 3.1**: **Historical Performance & Risk Metrics Engine** (`src/analytics/metrics.py`):
  - Absolute returns, Annualized CAGR (1Y, 3Y, 5Y, Since Inception).
  - Rolling Returns generator (3-year and 5-year rolling returns to gauge consistency).
  - Risk metrics: Standard Deviation, Sharpe Ratio, Sortino Ratio, Maximum Drawdown (MDD).
- [x] ✅ **Task 3.2**: **Market Timing & Valuation Model** (`src/analytics/timing_model.py`):
  - Valuation ratios: Nifty PE & PB relative to 5Y / 10Y rolling median.
  - Bond-Equity Earnings Yield Ratio (BEER indicator: 10Y G-Sec yield vs. Nifty earnings yield).
  - Technical / Mean-reversion indicators: 200-day EMA distance, Drawdown from 52-week highs.
  - India VIX extreme fear/greed indicator.
- [x] ✅ **Task 3.3**: **Macro Shock & Downturn Vulnerability Engine** (`src/analytics/macro_engine.py`):
  - Quantifies market fragility to real-world events.
  - Combines rapid macro shocks (Crude oil surges, VIX spikes, currency flight) with underlying market valuation to output a **Downturn Probability Score (0 to 100%)**.
  - Evaluates distance to scheduled calendar events (raising uncertainty bands 15–30 days prior).
- [x] ✅ **Task 3.4**: **"What-If" Scenario Stress-Tester** (`src/analytics/stress_tester.py`):
  - Simulates expected drawdowns on specific mutual funds under historical analogue shocks (e.g., 2008 crash, 2020 COVID shock, 2022 crude spike to \$130) or custom parameters ("If Crude hits \$100/barrel").
- [x] ✅ **Task 3.5**: **Unified Allocation Score** (`src/analytics/allocation_advisor.py`):
  - Synthesizes valuation multiples, macro vulnerability, and momentum into an actionable investment posture (*Aggressive Lumpsum Zone*, *Standard SIP Zone*, *Defensive / Staggered STP Zone*).
- [x] ✅ **Task 3.6**: **Backtesting Engine** (`src/analytics/backtester.py`):
  - Simulate dynamic SIP (investing extra during cheap / post-shock markets) vs. standard static monthly SIP.
- [x] ✅ **Task 3.7**: **Prediction Ledger & Automated Reconciliation Engine** (`src/analytics/ledger.py`, `evaluator.py`):
  - Structured storage of all historical predictions with feature snapshots.
  - Automated audit on target date arrival: calculates MAE, directional accuracy (hit rate %), and confidence band capture.
- [x] ✅ **Task 3.8**: **Automated Walk-Forward Model Retrainer** (`src/analytics/retrainer.py`):
  - Re-calibrates feature weights based on recent prediction errors (adaptive learning).
- [x] ✅ **Task 3.9**: **Smart SIP & Dynamic Value Averaging Engine** (`src/analytics/smart_sip.py`):
  - Calculates dynamic monthly SIP multiplier: 0.7x (Overheated), 1.0x (Fair), 1.5x–2.0x (Deep Value Dip).
  - **Empirical Optimal SIP Execution Date Engine**: Integrates backtested best day of the month (e.g., historical dips around monthly F&O expiry vs. early month salary inflows) directly into the SIP recommendation card (no separate tab needed).
  - Cash buffer tracker: simulates parking remaining allocation in Liquid/Arbitrage fund for deployment on crash dips.
  - Backtests dynamic SIP vs. traditional static SIP.
- [x] ✅ **Task 3.10**: **Category Valuation Thermometer** (`src/analytics/category_thermometer.py`):
  - Monitors valuation spreads between market caps: Nifty Smallcap 250 P/E vs. Nifty 50 P/E.
  - Generates Category Rotation Alerts (e.g., "Small Caps overheated by 30% vs historical median; rotate new flows into Large / Flexi Caps").
- [x] ✅ **Task 3.11**: **Dynamic Capital Deployment & Investment Planner Engine** (`src/analytics/allocation_advisor.py`):
  - Top-level capital allocation solver: User enters remaining capital pool (e.g., ₹50k, ₹5L, ₹10L).
  - Evaluates current market valuation and macro shock readings to generate an optimized deployment plan: **Lump Sum vs. SIP vs. 2–3 Month Staggered Tranches**.
  - Dynamic Tranche Scheduler: Calculates exact rupee breakdown (Immediate Lumpsum % vs. Parked Liquid/Arbitrage Reserve %) and exact recommended execution dates.
  - Adaptive Event Triggers: Accelerates tranche releases when market dips or macro shocks present entry opportunities.
  - Instant live recalculation whenever the user modifies their total capital amount.
- [x] ✅ **Task 3.12**: **"Dud Fund" Red-Flag & Exit Alerter** (`src/analytics/underperformance_scanner.py`):
  - Quarterly benchmark auditor: flags any fund underperforming its benchmark index (e.g., Nifty 500 TRI) and category median for 4 consecutive quarters.
  - Recommends the top 2 alternative funds in the same category demonstrating superior rolling-return consistency.
- [x] ✅ **Task 3.13**: **Goal-Based Equity Glide Path & Horizon Shield** (`src/analytics/goal_planner.py`):
  - Target corpus & horizon tracker (e.g., ₹25 Lakhs in 5 years).
  - Horizon Shield: Systematically transitions equity exposure from aggressive (Small/Mid Cap) to defensive (Large Cap / Arbitrage cash) in the final 12–18 months to prevent sudden market crashes from jeopardizing the goal.
- [x] ✅ **Task 3.14**: **Portfolio Sector & Thematic X-Ray Heatmap** (`src/analytics/portfolio_xray.py`):
  - Aggregates underlying stock and sector holdings across all shortlisted/owned mutual funds.
  - Generates consolidated sector exposure (Financials, Tech, Auto, Pharma, Capital Goods, Energy).
  - Flags concentration warnings whenever any single sector exceeds 25% of the overall portfolio.
- [x] ✅ **Task 3.15**: **Fund Manager Track Record & Migration Tracker** (`src/analytics/manager_tracker.py`):
  - Tracks fund manager tenure, historical alpha generated across past schemes, and career consistency.
  - Raises a "Manager Migration Alert" when a lead manager resigns or moves to a competing AMC.
- [x] ✅ **Task 3.16**: **1-Click ITR Capital Gains Tax Pack Generator** (`src/analytics/tax_pack.py`):
  - Computes FIFO capital gains across all historical SIP tranches and lump sums.
  - Automatically breaks down gains into **LTCG under Section 112A** (accounting for the annual ₹1.25 Lakh exemption limit) and **STCG under Section 111A** (20% rate).
  - Generates CA-ready and ITR-2/ITR-3 tax schedule exports (Excel/PDF) for effortless annual tax filing.

---

#### Phase 4: Backend API & 24/7 Autonomous Cloud Runner
- [x] ✅ **Task 4.1**: Build FastAPI application structure (`src/api/main.py` + routes).
- [x] ✅ **Task 4.2**: API Endpoints (37 endpoints registered across 6 route modules):
  - `GET /funds/search?q={query}` — Search mutual funds by name or AMC.
  - `GET /funds/{code}/nav` — Returns full NAV history with date range filtering.
  - `GET /analytics/timing/{code}` — Market timing score (0–100) and signal.
  - `GET /analytics/macro-danger/live` & `POST /analytics/macro-danger` — Downturn probability score and posture.
  - `POST /planner/allocation-advice` — Solves dynamic capital deployment (Lump Sum vs SIP vs Tranches) for input capital amount.
  - `GET /planner/sip-dates` & `GET /planner/sip-recommendation` — Dynamic SIP allocation, optimal dates [1, 7, 15], and cash reserve breakdown.
  - `GET /analytics/backtest/{code}` — Compare simulated dynamic SIP vs static SIP.
  - `POST /portfolio/xray` — Consolidated sector & stock concentration breakdown.
  - `GET /analytics/dud-scan/{code}` — Dud fund check (4-quarter rolling benchmark comparison) & alternatives.
  - `POST /planner/goal` — Goal horizon tracker and systematic equity de-risking roadmap.
  - `POST /portfolio/upload-cas` — Ingest & parse CAMS/KFintech CAS PDF statements in-memory with PAN password decryption.
  - `POST /planner/tax-pack` — Export CA-ready ITR capital gains tax schedule (LTCG Section 112A + STCG Section 111A).
  - `POST /auth/login`, `POST /auth/signup`, `POST /auth/logout` — Multi-tenant authentication session & profile scoping.
  - `DELETE /auth/delete-account` & `DELETE /auth/delete-account/confirm` — Instant hard-delete of all user data and auth credentials.
- [x] ✅ **Task 4.3**: Build **Autonomous 24/7 Cloud Worker Pipeline** (`.github/workflows/nightly_sync.yml` & `scripts/nightly_sync.py`):
  - Zero-laptop dependency: runs automatically on GitHub Actions at 9:30 PM IST daily.
  - Executes daily NAV sync, macro ingestion, prediction reconciliation, and model retraining.
- [x] ✅ **Task 4.4**: Build **WhatsApp Alert Dispatcher** (`src/notifications/whatsapp_bot.py`):
  - Cloud-triggered notifications sent directly to user WhatsApp via Twilio.
  - Templates for Opportunity, Macro Shock, Monthly SIP, and Dud Fund Alerts.
- [x] ✅ **Task 4.5**: Build **Multi-Tenant User Authentication & Row-Level Security (RLS)** (`src/auth/`):
  - Supabase Auth integration supporting Sign in with Google and Email & Password.
  - **Instant "Delete My Account" (One-Tap Hard Delete)**: One confirmed click permanently wipes all user portfolio, holdings, alerts, and credentials.

---

#### Phase 5: Web Dashboard & Visualizer (Frontend)
- [x] ✅ **Task 5.1**: Scaffold Vite + React + TypeScript + Tailwind CSS PWA (`frontend/`).
- [x] ✅ **Task 5.2**: **Hero Section: Progressive Financial Year Capital Deployment & Investment Planner** (`frontend/src/pages/PlannerTab.tsx`):
  - **Step 1 (Core Capital & FY Strategy)**: Primary input asks only for Total Capital to invest, dynamically calculating remaining months in current Indian Financial Year (till March 31) and selecting optimal strategy (One-time Lump sum vs. Systematic Monthly Tranches vs. Spaced 2-3 Month Gap Tranches).
  - **Step 2 (Optional Monthly Budget Limit)**: 1-click toggle to set monthly investment limit; computes whether capital fits into current FY or spills over into the next FY, with full dual-FY tranche breakdown and automated Liquid/Arbitrage yield parking recommendation.
  - **Step 3 (Optional Long-Term Goal / Retirement)**: 1-click toggle to set target corpus & horizon or 25× annual spend retirement mode with systematic auto de-risking glide path.
  - Live strategic verdict posture badge (AGGRESSIVE / GROWTH / BALANCED / DEFENSIVE / CAPITAL_SAFE).
  - **Embedded Optimal SIP Execution Date**: Displays backtested best days (1st, 7th, 15th) directly inside plan card.
  - Interactive Tranche Schedule & Rupee Breakdown (Immediate equity deployment vs. parked Liquid/Arbitrage yield reserve).
- [x] ✅ **Task 5.3**: Interactive NAV & Benchmark Comparison Charts with 200-day EMA overlay via Recharts (`frontend/src/pages/ExplorerTab.tsx`).
- [x] ✅ **Task 5.4**: Visual Market Timing Gauge (Speedometer Arc SVG + Multi-indicator display) (`frontend/src/components/TimingGauge.tsx`).
- [x] ✅ **Task 5.5**: Rolling Returns & Drawdown Distribution Charts via Recharts.
- [x] ✅ **Task 5.6**: **Category Thermometer & Smart SIP Cards**:
  - Category valuation spread thermometer (Cold / Warm / Hot / Overheated).
  - Monthly Smart SIP Action Card showing current multiplier (0.7x / 1.0x / 1.2x / 1.5x) and next execution date.
- [x] ✅ **Task 5.7**: **Sector X-Ray Heatmap & Dud Fund Badges**:
  - Visual breakdown of sector exposure with >25% risk alerts.
  - Dud Fund badges (CLEAN / MILD / MODERATE / SEVERE) with switch suggestions.
- [x] ✅ **Task 5.8**: **Goal Glide-Path Visualizer & Manager Profile Card**:
  - Goal horizon progress with automatic equity/debt de-risking milestone markers.
- [x] ✅ **Task 5.9**: **1-Click ITR Capital Gains Tax Export Widget**:
  - LTCG Section 112A (₹1.25L exemption breakdown) + STCG Section 111A summary & CSV export.
- [x] ✅ **Task 5.10**: Progressive Web App (PWA) manifest and Workbox service worker for installable Android/iOS experience (`vite-plugin-pwa`, `public/manifest.json`, `public/icons/`).
- [x] ✅ **Task 5.11**: **Settings & Account Management Panel** (`frontend/src/pages/SettingsTab.tsx`):
  - WhatsApp alert toggle controls.
  - Cloud Engine status display.
  - **[ 🗑️ Delete My Account ]** — Prominent destructive red button with one-step confirmation (`DELETE`) that immediately hard-deletes all user data and signs out.

---

#### Phase 6: Advanced Extensions, Deployment & Live Verification
- [x] ✅ **Task 6.1**: End-to-end integration and smoke verification of all tabs and API flows (Verified 100% operational across live Vercel frontend and Render backend).
- [x] ✅ **Task 6.2**: User Cloud Credentials Setup (Supabase project created, connected, and verified live with auth & instant delete).
- [x] ✅ **Task 6.3**: Production cloud deployment:
  - Backend API: **LIVE** on Render at `https://mf-tracker-and-advisor.onrender.com/` (all 37 endpoints active).
  - Frontend PWA: **LIVE** on Vercel at `https://mf-tracker-and-advisor.vercel.app/` (installable PWA with offline service worker).
- [ ] ⏳ **Task 6.4**: Portfolio Overlap & Concentration Analyzer (shared holdings between funds).
- [ ] ⏳ **Task 6.5**: Direct vs. Regular Plan Compounding Fee Drain Visualizer.

---

### 📝 Progress & Changelog

| Date | Phase | Task | Summary of Work Completed |
| :--- | :--- | :--- | :--- |
| **2026-10-31** | Phase 5 | UX Redesign | Redesigned **Investment Planner** into a 3-step progressive workflow (`PlannerTab.tsx`): 1) Pure capital input generating strategy before current Financial Year ends (March 31) with Lump sum vs Monthly SIP vs 2-3 month gap tranches; 2) Optional Monthly Budget Limit with FY capacity check, spillover rollover calculation into next FY, and liquid parking yield advice; 3) Optional Long-Term Goal / Retirement with systematic glide-path. |
| **2026-10-31** | Phase 5 | UX Enhancement | Added **Retirement Mode (No Fixed Goal)** to Planner (`PlannerTab.tsx`): 1-tap toggle calculating years to retirement (age 60 - current age) and corpus target based on 25× annual spend rule (4% safe withdrawal rule). Fixed API response field mappings for Allocation Advice tranches and Goal Planner glide path. |
| **2026-10-31** | Phase 6 | Task 6.1 - 6.3 | Full cloud production deployment complete! Frontend deployed on Vercel (`https://mf-tracker-and-advisor.vercel.app/`), Backend deployed on Render (`https://mf-tracker-and-advisor.onrender.com/`), and Auth & DB active on Supabase. Verified end-to-end user signup, JWT auth, and protected API endpoints. |
| **2026-10-31** | Phase 1 | Task 1.1 - 1.5 | Initialized Python 3.13 `.venv`, configured `.vscode/settings.json`, added `.python-version`, `.gitignore`, activation scripts (`activate.ps1`, `activate.bat`), and established `PROJECT_PLAN.md`. |
| **2026-10-31** | Phase 2 | Architecture | Finalized Dual-Source Data Strategy: **Primary (MFAPI.in)** + **Secondary / Verification (AMFI Official Portal)** with auto-failover and NAV verification. |
| **2026-10-31** | Phase 2-3 | Architecture | Designed and integrated the **3-Stream Macro Event & Shock Ingestion Pipeline** (`yfinance` macro proxies, scheduled event matrix, shock threshold triggers, and downturn vulnerability/stress-testing engine). |
| **2026-10-31** | Phase 3-4 | Architecture | Established **Autonomous 24/7 Cloud Architecture** (GitHub Actions nightly runner, cloud database, zero laptop dependency) and **Self-Improving ML Feedback Loop** (Prediction Ledger, automated audit vs actuals, walk-forward retraining). |
| **2026-10-31** | Phase 3-5 | Features | Integrated 3 Core Differentiators: **Smart SIP / Dynamic Value Averaging Engine** (Task 3.9), **Category Valuation Thermometer** (Task 3.10), and **WhatsApp Alert Bot** (Task 4.4). |
| **2026-10-31** | Phase 3-5 | Flagship Feature | Added **Hero Section: Dynamic Capital Deployment & Investment Planner** (Tasks 3.11, 4.2, 5.2): Real-time capital allocation solver (SIP vs. Lumpsum vs. 2–3 Month Tranches), adaptive event-driven tranche releases, and instant recalculation on capital changes. |
| **2026-10-31** | Master Plan | Philosophy & Analytics | Formally codified **100% Pure Equity Focus** and added **Dud Fund Red-Flag Alerter** (Task 3.12), **Goal-Based Horizon Glide Path** (Task 3.13), **Sector/Thematic X-Ray Heatmap** (Task 3.14), and **Fund Manager Migration Tracker** (Task 3.15). |
| **2026-10-31** | Phase 2 & 4 | Auth & Ingestion | Added **Automated CAS Statement Parser** (`casparser` PDF ingestion, Task 2.8) and **Multi-Tenant User Auth & Row-Level Security** (Supabase Google/Email Auth, Task 4.5). |
| **2026-10-31** | Phase 3 & 5 | Tax & Planning | Embedded **Optimal SIP Execution Date** directly inside Hero Investment Planner and added **1-Click ITR Capital Gains Tax Pack** (Task 3.16, Task 5.9). |
| **2026-10-31** | Phase 4 & 5 | UX & Auth | Added **Instant One-Tap "Delete My Account" hard-delete** (Task 4.5, Task 5.11) — no email confirmation, no waiting period, immediate full data wipe with fresh signup capability. |
| **2026-10-31** | Phase 4 | Tasks 4.1 - 4.5 | Implemented all 37 FastAPI endpoints, Supabase Auth client, Twilio WhatsApp bot, `nightly_sync.py` cloud worker, GitHub Actions workflow `.github/workflows/nightly_sync.yml`. All backend tests passing (`test_api.py`, `test_analytics.py`, `test_pipeline.py`). |
| **2026-10-31** | Phase 3 | Task 3.8 | Implemented `src/analytics/retrainer.py` (walk-forward retrainer for adaptive feature weight recalibration based on historical accuracy). Integrated into `nightly_sync.py`. |
| **2026-10-31** | Phase 5 | Tasks 5.1 - 5.11 | Built standalone Vite + React + TypeScript + Tailwind CSS PWA frontend with service worker, 5-tab responsive navigation, TimingGauge SVG, MacroBar, StressTestCard, Recharts NAV & 200 EMA charts, CAS upload with in-memory PAN decryption, and instant hard delete account modal. Production build passing (`dist/` generated). |
| **2026-10-31** | Phase 6 | Task 6.2 - 6.3 | Connected live Supabase project. Deployed FastAPI backend to Render (`https://mf-tracker-and-advisor.onrender.com/`). Verified live `/health` and `/funds/search` endpoints via HTTPS. |

| Date | Phase | Task | Summary of Work Completed |
| :--- | :--- | :--- | :--- |
| **2026-10-31** | Phase 1 | Task 1.1 - 1.5 | Initialized Python 3.13 `.venv`, configured `.vscode/settings.json`, added `.python-version`, `.gitignore`, activation scripts (`activate.ps1`, `activate.bat`), and established `PROJECT_PLAN.md`. |
| **2026-10-31** | Phase 2 | Architecture | Finalized Dual-Source Data Strategy: **Primary (MFAPI.in)** + **Secondary / Verification (AMFI Official Portal)** with auto-failover and NAV verification. |
| **2026-10-31** | Phase 2-3 | Architecture | Designed and integrated the **3-Stream Macro Event & Shock Ingestion Pipeline** (`yfinance` macro proxies, scheduled event matrix, shock threshold triggers, and downturn vulnerability/stress-testing engine). |
| **2026-10-31** | Phase 3-4 | Architecture | Established **Autonomous 24/7 Cloud Architecture** (GitHub Actions nightly runner, cloud database, zero laptop dependency) and **Self-Improving ML Feedback Loop** (Prediction Ledger, automated audit vs actuals, walk-forward retraining). |
| **2026-10-31** | Phase 3-5 | Features | Integrated 3 Core Differentiators: **Smart SIP / Dynamic Value Averaging Engine** (Task 3.9), **Category Valuation Thermometer** (Task 3.10), and **WhatsApp Alert Bot** (Task 4.4). |
| **2026-10-31** | Phase 3-5 | Flagship Feature | Added **Hero Section: Dynamic Capital Deployment & Investment Planner** (Tasks 3.11, 4.2, 5.2): Real-time capital allocation solver (SIP vs. Lumpsum vs. 2–3 Month Tranches), adaptive event-driven tranche releases, and instant recalculation on capital changes. |
| **2026-10-31** | Master Plan | Philosophy & Analytics | Formally codified **100% Pure Equity Focus** and added **Dud Fund Red-Flag Alerter** (Task 3.12), **Goal-Based Horizon Glide Path** (Task 3.13), **Sector/Thematic X-Ray Heatmap** (Task 3.14), and **Fund Manager Migration Tracker** (Task 3.15). |
| **2026-10-31** | Phase 2 & 4 | Auth & Ingestion | Added **Automated CAS Statement Parser** (`casparser` PDF ingestion, Task 2.8) and **Multi-Tenant User Auth & Row-Level Security** (Supabase Google/Email Auth, Task 4.5). |
| **2026-10-31** | Phase 3 & 5 | Tax & Planning | Embedded **Optimal SIP Execution Date** directly inside Hero Investment Planner and added **1-Click ITR Capital Gains Tax Pack** (Task 3.16, Task 5.9). |
| **2026-10-31** | Phase 4 & 5 | UX & Auth | Added **Instant One-Tap "Delete My Account" hard-delete** (Task 4.5, Task 5.11) — no email confirmation, no waiting period, immediate full data wipe with fresh signup capability. |

