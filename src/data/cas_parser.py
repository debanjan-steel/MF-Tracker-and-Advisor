"""
src/data/cas_parser.py
━━━━━━━━━━━━━━━━━━━━━━
Automated Consolidated Account Statement (CAS) Parser.

Parses official CAMS, KFintech, and MF Central CAS PDF statements:
  - Decrypts password-protected PDFs using user's PAN in-memory
  - CRITICAL PRIVACY RULE: PAN is NEVER stored in database or disk
  - Extracts full portfolio history:
      • Scheme name & AMFI code (matched via mfapi)
      • Folio numbers
      • Current unit balance & current valuation
      • Historical transaction ledger (purchase date, purchase NAV, units, amount)
      • Automatic classification: SIP vs Lumpsum vs Dividend Reinvestment vs Switch

Uses open-source `casparser` library.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CASTransaction:
    """Individual mutual fund transaction from CAS."""
    date: date
    description: str
    amount: float
    units: float
    nav: float
    balance: float
    type: str  # "SIP", "PURCHASE", "REDEMPTION", "DIVIDEND", "SWITCH_IN", "SWITCH_OUT", "OTHER"


@dataclass
class CASScheme:
    """Individual fund holding with transaction ledger."""
    scheme_name: str
    amfi_code: Optional[int]
    folio_number: str
    advisor: str
    open_units: float
    close_units: float
    valuation: Optional[float]
    valuation_date: Optional[date]
    transactions: list[CASTransaction] = field(default_factory=list)


@dataclass
class CASStatementSummary:
    """Consolidated CAS Statement object."""
    investor_name: str
    investor_email: str
    statement_period: str
    schemes: list[CASScheme] = field(default_factory=list)
    total_valuation: float = 0.0


def _classify_transaction(description: str) -> str:
    """Classify transaction string into standardized type."""
    desc = description.upper()
    if "SYSTEMATIC" in desc or "SIP" in desc:
        return "SIP"
    elif "PURCHASE" in desc or "SUBSCRIPTION" in desc:
        return "PURCHASE"
    elif "REDEMPTION" in desc or "SWITCH OUT" in desc:
        return "REDEMPTION"
    elif "SWITCH IN" in desc:
        return "SWITCH_IN"
    elif "DIVIDEND" in desc or "IDCW" in desc:
        return "DIVIDEND"
    return "OTHER"


def parse_cas_pdf(pdf_bytes: bytes, pan_password: str = "") -> CASStatementSummary:
    """
    Parse a CAS PDF file in-memory.

    Parameters
    ----------
    pdf_bytes    : Raw bytes of the uploaded PDF file.
    pan_password : Password to decrypt the PDF (usually user's PAN).
                   Used transiently in-memory and discarded immediately.

    Returns
    -------
    CASStatementSummary
    """
    try:
        import casparser
    except ImportError:
        raise RuntimeError("casparser library not installed. Run: pip install casparser")

    # casparser.read accepts a file path or file-like object
    buffer = io.BytesIO(pdf_bytes)
    try:
        data = casparser.read(buffer, password=pan_password)
    except Exception as e:
        logger.error("Failed to parse CAS statement: %s", e)
        raise ValueError(f"Could not parse CAS statement. Verify file format and password: {e}")

    summary = CASStatementSummary(
        investor_name=getattr(data.investor_info, "name", "Investor"),
        investor_email=getattr(data.investor_info, "email", ""),
        statement_period=f"{data.statement_period.from_} to {data.statement_period.to}",
    )

    total_val = 0.0
    for folio in data.folios:
        for scheme in folio.schemes:
            txns: list[CASTransaction] = []
            for t in getattr(scheme, "transactions", []) or []:
                tx_date = t.date if hasattr(t.date, "year") else date.fromisoformat(str(t.date))
                txns.append(
                    CASTransaction(
                        date=tx_date,
                        description=t.description,
                        amount=float(t.amount or 0.0),
                        units=float(t.units or 0.0),
                        nav=float(t.nav or 0.0),
                        balance=float(t.balance or 0.0),
                        type=_classify_transaction(t.description),
                    )
                )

            val = float(scheme.valuation.value) if scheme.valuation and scheme.valuation.value else 0.0
            total_val += val

            amfi_code = None
            if hasattr(scheme, "amfi") and scheme.amfi:
                try:
                    amfi_code = int(scheme.amfi)
                except (ValueError, TypeError):
                    pass

            summary.schemes.append(
                CASScheme(
                    scheme_name=scheme.scheme,
                    amfi_code=amfi_code,
                    folio_number=folio.folio,
                    advisor=getattr(scheme, "advisor", ""),
                    open_units=float(getattr(scheme, "open", 0.0) or 0.0),
                    close_units=float(getattr(scheme, "close", 0.0) or 0.0),
                    valuation=val,
                    valuation_date=getattr(scheme.valuation, "date", None) if scheme.valuation else None,
                    transactions=txns,
                )
            )

    summary.total_valuation = total_val
    return summary

