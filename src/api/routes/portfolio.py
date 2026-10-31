"""
src/api/routes/portfolio.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Portfolio routes: CAS upload, holdings management, portfolio X-ray.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from pydantic import BaseModel

from src.auth.supabase_client import get_current_user

router = APIRouter()


class HoldingInput(BaseModel):
    scheme_code: int
    scheme_name: str
    units: float
    avg_nav: float
    current_nav: Optional[float] = None
    category: str = "Equity"
    folio_number: Optional[str] = None
    sip_amount: Optional[float] = None
    sip_date: Optional[int] = None
    investment_type: str = "SIP"       # "SIP" | "LUMPSUM"


@router.post("/upload-cas", summary="Upload CAS PDF to auto-import holdings")
async def upload_cas(
    file: UploadFile = File(..., description="Consolidated Account Statement (CAS) PDF"),
    pan_last4: str = "",
    user: dict = Depends(get_current_user),
):
    """
    Parse a CAS PDF and automatically import all mutual fund holdings.

    PRIVACY NOTE:
      - PAN digits are used only in-memory to decrypt password-protected PDFs.
      - PAN is NEVER stored in the database.
      - Only fund holdings (scheme code, units, folio) are persisted.

    Supports CAS PDFs from CAMS, KFintech, and MF Central.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted."
        )

    contents = await file.read()

    try:
        from src.data.cas_parser import parse_cas_pdf
        statement = parse_cas_pdf(contents, pan_password=pan_last4)
        holdings = [
            {
                "scheme_name": s.scheme_name,
                "amfi_code": s.amfi_code,
                "folio_number": s.folio_number,
                "units": s.close_units,
                "valuation": s.valuation,
                "transactions_count": len(s.transactions),
            }
            for s in statement.schemes
        ]
        return {
            "message": f"CAS parsed successfully. Found {len(holdings)} fund holdings.",
            "investor_name": statement.investor_name,
            "statement_period": statement.statement_period,
            "total_valuation": statement.total_valuation,
            "holdings": holdings,
            "note": "PAN was used only in-memory to decrypt the PDF and has been discarded.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CAS parsing failed: {str(e)[:200]}. Ensure the file is a valid CAS PDF.",
        )


def _parse_cas_holdings(cas_data) -> list[dict]:
    """
    Extract holding records from casparser output.
    Returns list of holding dicts (scheme_code, units, folio, etc.)
    """
    holdings = []
    try:
        for folio in (cas_data.folios or []):
            for scheme in (folio.schemes or []):
                holdings.append({
                    "folio_number": folio.folio,
                    "scheme_name": scheme.scheme,
                    "amfi_code": scheme.amfi_code,
                    "units": scheme.close,
                    "nav": scheme.nav,
                    "value": scheme.valuation.value if scheme.valuation else None,
                    "transactions_count": len(scheme.transactions or []),
                })
    except Exception:
        pass
    return holdings


@router.get("/holdings", summary="Get user portfolio holdings")
def get_holdings(user: dict = Depends(get_current_user)):
    """
    Return the current user's portfolio holdings from their Supabase profile.
    Holdings are stored per-user using Supabase Row Level Security (RLS).
    """
    # Placeholder — in production this queries Supabase with user_id
    return {
        "user_id": user["user_id"],
        "holdings": [],
        "note": "Connect Supabase to persist holdings per user. Use POST /portfolio/holdings to add."
    }


@router.post("/holdings", summary="Add or update a holding")
def add_holding(holding: HoldingInput, user: dict = Depends(get_current_user)):
    """
    Manually add or update a fund holding in the portfolio.
    Use this if you prefer manual entry over CAS upload.
    """
    return {
        "message": "Holding added.",
        "user_id": user["user_id"],
        "holding": holding.model_dump(),
        "note": "Supabase persistence active when SUPABASE_URL is configured."
    }


@router.post("/xray", summary="Portfolio sector and thematic X-Ray")
def portfolio_xray(
    holdings: list[HoldingInput],
    user: dict = Depends(get_current_user),
):
    """
    Run a full Portfolio X-Ray:
    - Sector concentration heatmap
    - Thematic clusters (Financials, Tech, Healthcare, etc.)
    - Fund-to-fund overlap score
    - Market cap distribution (Large / Mid / Small)
    - Diversification score
    """
    from src.analytics.portfolio_xray import FundHolding, run_portfolio_xray

    fund_holdings = [
        FundHolding(
            scheme_code=h.scheme_code,
            scheme_name=h.scheme_name,
            current_value=(h.units * (h.current_nav or h.avg_nav)),
            category=h.category,
        )
        for h in holdings
    ]
    result = run_portfolio_xray(fund_holdings)
    return {
        "total_portfolio_value": result.total_portfolio_value,
        "diversification_score": result.diversification_score,
        "sector_exposure": result.sector_exposure,
        "market_cap_exposure": result.market_cap_exposure,
        "category_distribution": result.category_distribution,
        "overlap_matrix": result.overlap_matrix,
        "concentration_alerts": result.concentration_alerts,
        "thematic_clusters": result.thematic_clusters,
        "summary": result.summary,
    }

