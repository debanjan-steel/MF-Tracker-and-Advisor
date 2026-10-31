"""
src/analytics/tax_pack.py
━━━━━━━━━━━━━━━━━━━━━━━━━
1-Click ITR Capital Gains Tax Pack for Indian Mutual Funds.

Generates a tax-ready capital gains summary for the financial year,
ready to paste into ITR-2 / ITR-3 or share with a CA:

STCG (Short Term Capital Gains) — held < 1 year:
  Equity MFs : Taxed at 20% flat (post Budget 2024)

LTCG (Long Term Capital Gains) — held ≥ 1 year:
  Equity MFs : 12.5% on gains > ₹1,25,000 per year (post Budget 2024)
  Grandfathering: Cost of equity MFs bought before 31 Jan 2018 → use
                  higher of actual cost or NAV on 31 Jan 2018

SIP redemptions: Each SIP instalment is a separate purchase lot (FIFO).

Output:
  - Transaction-level STCG / LTCG breakdown
  - Aggregated STCG / LTCG totals
  - Tax liability estimate (with LTCG exemption applied)
  - Download-ready CSV for CA / ITR filing
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Tax Constants (as per Indian Budget 2024)
# ─────────────────────────────────────────────────────────────────────────────

LTCG_THRESHOLD_DAYS = 365          # ≥ 365 days = LTCG for equity
LTCG_EXEMPTION_LIMIT = 125_000.0   # ₹1,25,000 LTCG exempt per year
LTCG_TAX_RATE = 0.125              # 12.5% LTCG on equity MF
STCG_TAX_RATE = 0.20               # 20% STCG on equity MF
GRANDFATHERING_DATE = date(2018, 1, 31)

SURCHARGE_THRESHOLDS = [
    (5_000_000, 0.10),    # >50L → 10% surcharge
    (10_000_000, 0.15),   # >1Cr → 15% surcharge
    (20_000_000, 0.25),   # >2Cr → 25% surcharge
    (50_000_000, 0.37),   # >5Cr → 37% surcharge (not applicable post-2023 for LTCG)
]
HEALTH_EDUCATION_CESS = 0.04       # 4% cess on tax


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PurchaseLot:
    """A single purchase (SIP instalment or lump sum buy)."""
    scheme_code: int
    scheme_name: str
    purchase_date: date
    units: float
    purchase_nav: float             # NAV per unit on purchase date
    purchase_amount: float          # Total cost (units × NAV)
    nav_on_31jan2018: Optional[float] = None  # For grandfathering (pre-2018 lots)


@dataclass
class RedemptionTransaction:
    """A single redemption transaction."""
    scheme_code: int
    scheme_name: str
    redemption_date: date
    units_redeemed: float
    redemption_nav: float
    redemption_amount: float        # Total proceeds


@dataclass
class CapitalGainRecord:
    """Computed capital gain for a matched lot."""
    scheme_name: str
    purchase_date: date
    redemption_date: date
    units: float
    cost_basis: float               # Adjusted cost (including grandfathering)
    proceeds: float
    gain: float                     # proceeds - cost_basis
    holding_days: int
    gain_type: str                  # "STCG" or "LTCG"
    grandfathered: bool             # Was cost grandfathered to Jan 2018 NAV?
    tax_rate: float
    estimated_tax: float


@dataclass
class TaxPackSummary:
    """Full tax pack output."""
    financial_year: str             # e.g., "2025-26"
    records: list[CapitalGainRecord] = field(default_factory=list)

    total_stcg: float = 0.0
    total_ltcg: float = 0.0
    ltcg_after_exemption: float = 0.0
    estimated_stcg_tax: float = 0.0
    estimated_ltcg_tax: float = 0.0
    estimated_total_tax: float = 0.0  # Before cess
    estimated_tax_with_cess: float = 0.0

    warnings: list[str] = field(default_factory=list)
    csv_data: str = ""              # Ready-to-download CSV string


# ─────────────────────────────────────────────────────────────────────────────
# FIFO Lot Matching Engine
# ─────────────────────────────────────────────────────────────────────────────

def compute_capital_gains(
    purchase_lots: list[PurchaseLot],
    redemptions: list[RedemptionTransaction],
    financial_year_end: date | None = None,
) -> TaxPackSummary:
    """
    Match redemptions to purchase lots using FIFO and compute capital gains.

    Indian MF tax rules (post Budget 2024):
      - FIFO: oldest purchase lots matched first against each redemption.
      - Equity MF held ≥ 365 days → LTCG at 12.5% (exempt up to ₹1.25L/year)
      - Equity MF held < 365 days → STCG at 20%
      - Grandfathering: For lots purchased before 31 Jan 2018,
        cost = MAX(actual purchase cost, NAV on 31 Jan 2018 × units)

    Parameters
    ----------
    purchase_lots     : All purchase lots (SIP + lump sum), sorted by date.
    redemptions       : All redemption transactions for the financial year.
    financial_year_end: FY end date (default: 31-Mar of current/past FY).

    Returns
    -------
    TaxPackSummary
    """
    # Determine FY
    today = date.today()
    if financial_year_end is None:
        if today.month >= 4:
            fy_end = date(today.year + 1, 3, 31)
            fy_label = f"{today.year}-{str(today.year + 1)[-2:]}"
        else:
            fy_end = date(today.year, 3, 31)
            fy_label = f"{today.year - 1}-{str(today.year)[-2:]}"
    else:
        fy_end = financial_year_end
        fy_yr = fy_end.year
        fy_label = f"{fy_yr - 1}-{str(fy_yr)[-2:]}"

    summary = TaxPackSummary(financial_year=fy_label)

    # Group lots by scheme, sorted FIFO
    lots_by_scheme: dict[int, list[PurchaseLot]] = {}
    for lot in sorted(purchase_lots, key=lambda l: l.purchase_date):
        lots_by_scheme.setdefault(lot.scheme_code, []).append(lot)

    # Working copies (mutable units remaining per lot)
    remaining: dict[int, list[list]] = {}  # scheme_code → [[lot, remaining_units]]
    for code, lots in lots_by_scheme.items():
        remaining[code] = [[lot, lot.units] for lot in lots]

    records: list[CapitalGainRecord] = []
    warnings: list[str] = []

    for redemption in sorted(redemptions, key=lambda r: r.redemption_date):
        code = redemption.scheme_code
        units_to_match = redemption.units_redeemed
        lot_queue = remaining.get(code, [])

        if not lot_queue:
            warnings.append(
                f"⚠️ No purchase lots found for {redemption.scheme_name} "
                f"(code {code}) redeemed on {redemption.redemption_date}. "
                "Capital gain skipped — check your CAS data."
            )
            continue

        while units_to_match > 0.0001 and lot_queue:
            lot, lot_remaining = lot_queue[0]
            matched_units = min(units_to_match, lot_remaining)

            # Adjust cost basis for grandfathering
            actual_cost_per_unit = lot.purchase_amount / lot.units if lot.units > 0 else lot.purchase_nav
            grandfathered = False
            if lot.purchase_date <= GRANDFATHERING_DATE and lot.nav_on_31jan2018 is not None:
                grandfather_cost = lot.nav_on_31jan2018
                if grandfather_cost > actual_cost_per_unit:
                    actual_cost_per_unit = grandfather_cost
                    grandfathered = True

            cost_basis = actual_cost_per_unit * matched_units
            proceeds = (redemption.redemption_amount / redemption.units_redeemed) * matched_units

            holding_days = (redemption.redemption_date - lot.purchase_date).days
            gain = proceeds - cost_basis

            if holding_days >= LTCG_THRESHOLD_DAYS:
                gain_type = "LTCG"
                tax_rate = LTCG_TAX_RATE
            else:
                gain_type = "STCG"
                tax_rate = STCG_TAX_RATE

            # Tax is estimated at lot level (LTCG exemption applied at summary level)
            estimated_tax = max(0, gain) * tax_rate if gain > 0 else 0.0

            records.append(CapitalGainRecord(
                scheme_name=redemption.scheme_name,
                purchase_date=lot.purchase_date,
                redemption_date=redemption.redemption_date,
                units=matched_units,
                cost_basis=round(cost_basis, 4),
                proceeds=round(proceeds, 4),
                gain=round(gain, 4),
                holding_days=holding_days,
                gain_type=gain_type,
                grandfathered=grandfathered,
                tax_rate=tax_rate,
                estimated_tax=round(estimated_tax, 2),
            ))

            lot_queue[0][1] -= matched_units
            units_to_match -= matched_units

            if lot_queue[0][1] < 0.0001:
                lot_queue.pop(0)

        if units_to_match > 0.001:
            warnings.append(
                f"⚠️ Could not fully match {units_to_match:.4f} units of "
                f"{redemption.scheme_name} (insufficient purchase lots)."
            )

    # Aggregate totals
    total_stcg = sum(r.gain for r in records if r.gain_type == "STCG" and r.gain > 0)
    total_ltcg = sum(r.gain for r in records if r.gain_type == "LTCG" and r.gain > 0)
    total_stcg_loss = sum(r.gain for r in records if r.gain_type == "STCG" and r.gain < 0)
    total_ltcg_loss = sum(r.gain for r in records if r.gain_type == "LTCG" and r.gain < 0)

    # Net STCG (set-off losses)
    net_stcg = total_stcg + total_stcg_loss  # losses are negative
    net_ltcg = total_ltcg + total_ltcg_loss
    ltcg_after_exemption = max(0, net_ltcg - LTCG_EXEMPTION_LIMIT)

    stcg_tax = max(0, net_stcg) * STCG_TAX_RATE
    ltcg_tax = ltcg_after_exemption * LTCG_TAX_RATE
    total_tax = stcg_tax + ltcg_tax
    tax_with_cess = total_tax * (1 + HEALTH_EDUCATION_CESS)

    if net_ltcg > 0 and net_ltcg <= LTCG_EXEMPTION_LIMIT:
        warnings.append(
            f"✅ LTCG of ₹{net_ltcg:,.0f} is within the ₹1,25,000 annual exemption. No LTCG tax payable."
        )

    summary.records = records
    summary.total_stcg = round(net_stcg, 2)
    summary.total_ltcg = round(net_ltcg, 2)
    summary.ltcg_after_exemption = round(ltcg_after_exemption, 2)
    summary.estimated_stcg_tax = round(stcg_tax, 2)
    summary.estimated_ltcg_tax = round(ltcg_tax, 2)
    summary.estimated_total_tax = round(total_tax, 2)
    summary.estimated_tax_with_cess = round(tax_with_cess, 2)
    summary.warnings = warnings
    summary.csv_data = _generate_csv(records, fy_label)

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────────────────────

def _generate_csv(records: list[CapitalGainRecord], fy: str) -> str:
    """Generate a CA-ready CSV string from capital gain records."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Financial Year", "Fund Name", "Purchase Date", "Redemption Date",
        "Holding Days", "Gain Type", "Units", "Cost Basis (₹)", "Proceeds (₹)",
        "Capital Gain (₹)", "Tax Rate (%)", "Estimated Tax (₹)", "Grandfathered",
    ])
    for r in records:
        writer.writerow([
            fy,
            r.scheme_name,
            r.purchase_date.isoformat(),
            r.redemption_date.isoformat(),
            r.holding_days,
            r.gain_type,
            f"{r.units:.4f}",
            f"{r.cost_basis:.2f}",
            f"{r.proceeds:.2f}",
            f"{r.gain:.2f}",
            f"{r.tax_rate * 100:.1f}",
            f"{r.estimated_tax:.2f}",
            "Yes" if r.grandfathered else "No",
        ])
    return output.getvalue()


def format_tax_pack_report(summary: TaxPackSummary) -> str:
    """Format tax pack as a human-readable summary."""
    lines = [
        f"# 📋 Capital Gains Tax Pack — FY {summary.financial_year}",
        f"*(Indian Equity Mutual Funds — post Budget 2024 tax rules)*\n",
        f"## Summary",
        f"| | Amount |",
        f"|---|---|",
        f"| Net STCG (Short Term < 1 Year) | ₹{summary.total_stcg:,.2f} |",
        f"| Net LTCG (Long Term ≥ 1 Year) | ₹{summary.total_ltcg:,.2f} |",
        f"| LTCG Exemption Used | ₹{min(summary.total_ltcg, 125000):,.2f} |",
        f"| Taxable LTCG | ₹{summary.ltcg_after_exemption:,.2f} |",
        f"| STCG Tax @20% | ₹{summary.estimated_stcg_tax:,.2f} |",
        f"| LTCG Tax @12.5% | ₹{summary.estimated_ltcg_tax:,.2f} |",
        f"| Total Tax (before cess) | ₹{summary.estimated_total_tax:,.2f} |",
        f"| **Total Tax + 4% Cess** | **₹{summary.estimated_tax_with_cess:,.2f}** |",
        f"\n## Transaction Details ({len(summary.records)} transactions)",
    ]

    for r in summary.records[:20]:  # Show first 20 in report
        lines.append(
            f"  - {r.scheme_name[:35]} | {r.gain_type} | "
            f"₹{r.gain:,.2f} | {r.holding_days}d | "
            f"Tax: ₹{r.estimated_tax:,.2f}"
            + (" [GF]" if r.grandfathered else "")
        )

    if len(summary.records) > 20:
        lines.append(f"  *(+ {len(summary.records) - 20} more — download CSV for full details)*")

    if summary.warnings:
        lines.append("\n## ⚠️ Warnings / Notes")
        for w in summary.warnings:
            lines.append(f"  - {w}")

    lines.append(
        "\n> **Disclaimer**: This is an educational estimate only. "
        "Consult a qualified CA before filing ITR. Tax laws may change."
    )

    return "\n".join(lines)

