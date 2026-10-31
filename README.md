# 🇮🇳 Indian Mutual Funds Analytics & Market Timing Platform (MF Tracker & Advisor)

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.0-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8.svg?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An autonomous, full-stack, quantitative analytics and market-timing platform specifically built for Indian Equity Mutual Funds. Features dynamic capital deployment, empirical SIP date optimization, automated CAS PDF parsing, and a 24/7 self-improving ML feedback loop running entirely on free-tier cloud resources (\$0 operating cost).

---

## 🎯 Core Investment Philosophy

- **100% Pure Equity Focus**: Engineered exclusively for equity mutual funds (Large Cap, Flexi Cap, Mid Cap, Small Cap, and Thematic). Multi-asset rebalancing into physical gold or debt bonds is deliberately excluded.
- **Yield Reserve (Dry Powder)**: Any unallocated capital waiting for deployment is held strictly in ultra-short cash equivalents (Arbitrage / Liquid funds) to earn risk-free yields while waiting for valuation dips.
- **Strict Privacy & Zero-PAN Storage**: Your PAN number is used strictly in-memory to decrypt password-protected CAS statements and is discarded immediately after parsing. It is **never** written to database or logs.
- **Instant One-Tap Account Deletion**: One-click hard delete in Settings permanently wipes all portfolios, holdings, transaction logs, goals, and credentials with zero cooldown period or confirmation emails.

---

## ✨ Key Features

### 1. 📊 Hero Investment Planner & Capital Deployment
- **Real-Time Capital Allocator**: Input total available capital (e.g., ₹50k, ₹5L, ₹10L) to get an actionable deployment plan:
  - **Lump Sum** (Deep Value Zone)
  - **Regular SIP** (Fair Value Zone)
  - **2–3 Month Staggered Tranches** (Elevated Valuation / Volatility Zone)
- **Market Posture Verdict**: Live classification (`AGGRESSIVE`, `GROWTH`, `BALANCED`, `DEFENSIVE`, `CAPITAL_SAFE`).
- **📅 Embedded Optimal SIP Execution Dates**: Displays empirically backtested best days of the month (**1st, 7th, 15th**) directly in the plan card—no separate screen needed.
- **Smart SIP Multiplier**: Dynamically scales monthly contributions (0.7× when overheated, 1.0× when fair, 1.2×–1.5× during major market dips).

### 2. 🧠 Quantitative Market Timing & Macro Danger Engine
- **Timing Score (0–100)**: Combines 200-day Exponential Moving Average (EMA) distance, Relative Strength Index (RSI), and 52-week High/Low percentiles.
- **3-Stream Macro Vulnerability Engine**: Aggregates live macro proxies:
  - **Brent Crude Oil** (`BZ=F`)
  - **India VIX** (`^INDIAVIX`)
  - **US 10-Year Treasury Yield** (`^TNX`)
  - **US Dollar Index** (`DX-Y.NYB`)
  - **USD/INR** (`USDINR=X`)
  - **Gold** (`GC=F`)
- **Self-Improving ML Feedback Loop**: Logs all model calls into a SQLite/PostgreSQL `prediction_ledger`. When target dates arrive, an automated walk-forward retrainer calculates directional accuracy and Mean Absolute Error (MAE), dynamically tuning momentum vs. mean-reversion feature weights.

### 3. 💼 Automated CAS Portfolio Ingestion & Dud Fund Scanner
- **Zero-Manual Entry CAS Parser**: Ingests official Consolidated Account Statement (CAS) PDFs from CAMS, KFintech, and MF Central via `casparser`.
- **Dud Fund Red-Flag Alerter**: Flags funds that underperform their category benchmark (e.g., Nifty 500 TRI) for 4 consecutive quarters and recommends top-performing alternatives in the same category.
- **Portfolio X-Ray**: Sector concentration bar charts with immediate risk alerts whenever any single sector exceeds 25%, plus market-cap breakdown (Large / Mid / Small).

### 4. 🧾 1-Click ITR Capital Gains Tax Pack
- **FIFO Capital Gains Calculator**: Automatically classifies transactions into **LTCG under Section 112A** (applying the ₹1.25 Lakh annual exemption limit) and **STCG under Section 111A** (20% rate).
- **CA-Ready CSV Export**: Instant one-click download for seamless ITR-2 / ITR-3 income tax filing.

### 5. 🤖 Autonomous 24/7 Cloud Worker
- **Zero-Laptop Dependency**: Runs on a scheduled **GitHub Actions** cron job every night at **9:30 PM IST (16:00 UTC)**.
- Automatically syncs NAV deltas, ingests closing macro data, reconciles past predictions, retrains feature weights, and dispatches WhatsApp alerts via Twilio.

### 6. 📱 Installable Progressive Web App (PWA)
- Fully responsive dark-themed UI built with React 19, Tailwind CSS v4, Lucide icons, and Recharts.
- Native Android/iOS installable experience with Workbox service worker and offline capability.

---

## 🏛️ System Architecture

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    DATA INGESTION                      │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                        ┌──────────────────────────────────┴──────────────────────────────────┐
                        ▼                                                                     ▼
             ┌─────────────────────┐                                               ┌─────────────────────┐
             │  Primary: MFAPI.in  │                                               │ Secondary: AMFI.gov │
             │  (Fast JSON REST)   │                                               │ (Official NAV feed) │
             └──────────┬──────────┘                                               └──────────┬──────────┘
                        │                                                                     │
                        └─────────────────────────┬───────────────────────────────────────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │   DataManager Layer   │ (Auto-failover + cross-verification)
                                      └───────────┬───────────┘
                                                  │
             ┌────────────────────────────────────┼────────────────────────────────────┐
             ▼                                    ▼                                    ▼
┌─────────────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
│ Macro & Shock Proxies   │          │  Financial Analytics    │          │ Automated CAS Ingestion │
│ (yfinance 6 proxies +   │          │  (Metrics, Timing Model,│          │ (In-memory PAN decrypt, │
│ Scheduled Event Matrix) │          │  Smart SIP, Stress Test)│          │  Zero disk persistence) │
└────────────┬────────────┘          └────────────┬────────────┘          └────────────┬────────────┘
             │                                    │                                    │
             └────────────────────────────────────┼────────────────────────────────────┘
                                                  ▼
                                      ┌───────────────────────┐
                                      │    FastAPI Backend    │ (37 REST routes, JWT Auth, RLS)
                                      └───────────┬───────────┘
                                                  │
                        ┌─────────────────────────┴─────────────────────────┐
                        ▼                                                   ▼
            ┌───────────────────────┐                           ┌───────────────────────┐
            │   Vite + React PWA    │                           │  24/7 GitHub Actions  │
            │  (Mobile Web / App)   │                           │  (Nightly 9:30 PM IST)│
            └───────────────────────┘                           └───────────────────────┘
```

---

## 📂 Project Structure

```
.
├── .github/
│   └── workflows/
│       └── nightly_sync.yml        # 24/7 autonomous GitHub Actions runner
├── data/                           # SQLite database & static macro calendars
│   └── macro_calendar.json         # Union Budget, RBI MPC, FOMC & F&O expiry dates
├── frontend/                       # Vite + React 19 + TypeScript + Tailwind CSS PWA
│   ├── public/                     # PWA icons, manifest, and favicon
│   └── src/
│       ├── components/             # BottomNav, Header, TimingGauge, MacroBar, StressCard
│       ├── lib/                    # Axios API client, formatting utils
│       ├── pages/                  # PlannerTab, PortfolioTab, ExplorerTab, AlertsTab, SettingsTab
│       ├── store/                  # Zustand stores (authStore, appStore)
│       └── types/                  # TypeScript interface definitions
├── scripts/
│   └── nightly_sync.py             # Autonomous 24/7 cloud sync worker script
├── src/
│   ├── analytics/                  # 13 quantitative analytics modules + retrainer
│   │   ├── allocation_advisor.py   # Hero capital allocation & posture solver
│   │   ├── backtester.py           # Dynamic vs static SIP simulator
│   │   ├── category_thermometer.py # Valuation spread & rotation analyzer
│   │   ├── goal_planner.py         # Horizon glide path & auto de-risking
│   │   ├── ledger.py               # Prediction ledger & performance auditor
│   │   ├── macro_engine.py         # Macro downturn probability score (0-100%)
│   │   ├── manager_tracker.py      # Star manager tenure & alpha tracker
│   │   ├── metrics.py              # CAGR, Sharpe, Sortino, Calmar, MDD
│   │   ├── portfolio_xray.py       # Sector concentration & overlap matrix
│   │   ├── retrainer.py            # Walk-forward ML feature weight optimizer
│   │   ├── smart_sip.py            # Empirical optimal dates [1, 7, 15] & multiplier
│   │   ├── stress_tester.py        # 6 historical crash simulation models
│   │   ├── tax_pack.py             # Section 112A LTCG / Section 111A STCG FIFO
│   │   └── underperformance_scanner.py # Dud fund auditor
│   ├── api/                        # FastAPI REST API
│   │   ├── main.py                 # Application entrypoint & CORS middleware
│   │   └── routes/                 # auth, funds, analytics, planner, portfolio, alerts
│   ├── auth/                       # Supabase Auth client & token verification
│   ├── data/                       # MFAPI, AMFI, Macro, and CAS ingestion clients
│   └── notifications/              # Twilio WhatsApp alert templates & dispatcher
├── tests/                          # Automated test suites
├── requirements.txt                # Python dependencies
└── PROJECT_PLAN.md                 # Complete roadmap and milestone ledger
```

---

## 🛠️ Quick Start Guide

### Prerequisites
- Python 3.13+
- Node.js 20+ and npm

### 1. Backend Setup
```bash
# Clone the repository
git clone https://github.com/debanjan-steel/MF-Tracker-and-Advisor.git
cd MF-Tracker-and-Advisor

# Create and activate Python 3.13 virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run database migration & initial test
python tests/test_api.py

# Start FastAPI development server
uvicorn src.api.main:app --reload --port 8000
```
Interactive API documentation will be live at `http://localhost:8000/docs`.

### 2. Frontend PWA Setup
```bash
# In a separate terminal
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
The application will be accessible at `http://localhost:5173`.

---

## ⚙️ Environment Variables (`.env`)

```ini
# Database
DATABASE_URL=data/mf_platform.db

# Authentication (Supabase - Free Tier)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# WhatsApp Notifications (Twilio - Free Sandbox)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_WHATSAPP_FROM=+14155238886
DEFAULT_WHATSAPP_TO=+91XXXXXXXXXX
```

---

## ☁️ Autonomous Cloud Deployment ($0 Cost)

1. **GitHub Secrets**:
   In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and add:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_WHATSAPP_FROM`
   - `DEFAULT_WHATSAPP_TO`
2. **24/7 Nightly Cloud Runner**:
   The workflow in `.github/workflows/nightly_sync.yml` triggers automatically every evening at **9:30 PM IST (16:00 UTC)**. You can also trigger it manually from the **Actions** tab in GitHub.
3. **Frontend Hosting**:
   Deploy the `frontend/` directory to **Vercel**, **Netlify**, or **Cloudflare Pages** for free. Set `VITE_API_URL` to your production backend URL.

---

## 🔒 Security & Privacy Disclaimer

- **Zero-Storage for Sensitive Identifiers**: User PAN numbers are never stored in the database, cookies, or persistent storage. They are held in transient memory only for the millisecond duration needed to unlock password-encrypted CAS statements.
- **Educational / Analytical Purpose**: This tool provides quantitative, algorithmic, and educational market analysis. It is **not** SEBI-registered investment advice. Mutual fund investments are subject to market risks; read all scheme-related documents carefully before investing.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
