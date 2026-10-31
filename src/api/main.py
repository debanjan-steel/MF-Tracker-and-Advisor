"""
src/api/main.py
━━━━━━━━━━━━━━━
FastAPI application entrypoint.

Mounts all route modules:
  /auth       — login, signup, logout, delete account
  /funds      — search, NAV history, scheme metadata
  /portfolio  — portfolio CRUD, CAS upload
  /analytics  — timing score, macro danger, metrics, scorecard
  /planner    — SIP planner, goal planner, allocation advice
  /alerts     — WhatsApp alert configuration
  /admin      — nightly sync trigger (internal use)

Middleware:
  - CORS (allows the React PWA frontend)
  - Request timing header
  - Global exception handler (never leak stack traces to client)

Run locally:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import time
import warnings
warnings.filterwarnings("ignore")

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.data.storage import init_db

# Import all route modules
from src.api.routes import auth, funds, analytics, planner, portfolio, alerts


# ─────────────────────────────────────────────────────────────────────────────
# App Instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Indian MF Analytics Platform",
    description=(
        "100% Equity-focused mutual fund analytics, market timing, "
        "and intelligent SIP planning for Indian investors."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # In production: restrict to your Vercel/Netlify domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed:.1f}"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler — never expose stack traces to API consumers."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error.", "detail": str(exc)[:200]},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Initialise SQLite database on server start."""
    init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(auth.router,      prefix="/auth",      tags=["Authentication"])
app.include_router(funds.router,     prefix="/funds",     tags=["Fund Data"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(planner.router,   prefix="/planner",   tags=["Planner"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(alerts.router,    prefix="/alerts",    tags=["Alerts"])


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "Indian MF Analytics Platform",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}

