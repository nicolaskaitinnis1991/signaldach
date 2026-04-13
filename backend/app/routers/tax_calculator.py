"""Crypto Tax Rules & Calculator for DACH countries (DE, CH, AT).

Provides comprehensive, accurate crypto tax reference data and a simple
tax estimation calculator for Germany, Switzerland, and Austria.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/tax", tags=["tax"])


# ---------------------------------------------------------------------------
# Tax rules data — accurate as of 2026-03-30
# ---------------------------------------------------------------------------

_TAX_RULES: dict[str, dict] = {
    "DE": {
        "country": "DE",
        "country_name": "Germany",
        "last_updated": "2026-03-30",
        "summary": (
            "Germany treats crypto as private assets (privates Veräußerungsgeschäft). "
            "Gains are tax-free after 1 year holding period. Short-term gains taxed at "
            "personal income tax rate with a €1,000 Freigrenze. Staking/lending income "
            "taxed as sonstige Einkünfte."
        ),
        "tax_categories": [
            {
                "name": "Trading Gains (Spot)",
                "rules": [
                    {
                        "rule": "Holding period < 1 year: taxed as private sales (§23 EStG)",
                        "tax_rate": "Personal income tax rate (14-45%) + Solidaritätszuschlag (5.5% on tax) + optional Kirchensteuer (8-9%)",
                        "exemption": "€1,000 per year (Freigrenze, not Freibetrag — if exceeded, ALL gains are taxed)",
                        "note": "Changed from €600 to €1,000 in 2024. Freigrenze means if total gains exceed €1,000, the ENTIRE amount is taxed, not just the excess.",
                    },
                    {
                        "rule": "Holding period >= 1 year: completely tax-free",
                        "tax_rate": "0%",
                        "exemption": "Unlimited",
                        "note": "This is Germany's biggest crypto tax advantage. No capital gains tax regardless of amount after 1 year.",
                    },
                ],
            },
            {
                "name": "Staking & Lending Income",
                "rules": [
                    {
                        "rule": "Staking rewards taxed as sonstige Einkünfte (§22 Nr. 3 EStG) at time of receipt",
                        "tax_rate": "Personal income tax rate (14-45%) + Soli",
                        "exemption": "€256 per year Freigrenze for sonstige Einkünfte",
                        "note": "BMF letter from May 2022 clarified: staking does NOT extend the holding period to 10 years. The 1-year rule still applies for the underlying asset.",
                    },
                    {
                        "rule": "Lending interest taxed as sonstige Einkünfte (§22 Nr. 3 EStG)",
                        "tax_rate": "Personal income tax rate (14-45%) + Soli",
                        "exemption": "€256 per year Freigrenze (combined with other sonstige Einkünfte)",
                        "note": "Interest from crypto lending is NOT subject to Abgeltungsteuer (25% flat tax) — it falls under §22 EStG instead.",
                    },
                ],
            },
            {
                "name": "Mining",
                "rules": [
                    {
                        "rule": "Mining income can be classified as gewerbliche Einkünfte (business income) if done professionally",
                        "tax_rate": "Personal income tax rate + Gewerbesteuer (trade tax, ~7-17% depending on municipality)",
                        "exemption": "Gewerbesteuer Freibetrag: €24,500 for individuals",
                        "note": "If mining is occasional/hobby, it may be classified as sonstige Einkünfte. Professional mining requires Gewerbeanmeldung.",
                    },
                    {
                        "rule": "Mined coins: cost basis = fair market value at time of mining",
                        "tax_rate": "Subsequent sale follows normal holding period rules (1-year rule applies)",
                        "exemption": "Standard €1,000 Freigrenze for subsequent sale gains",
                        "note": "Double taxation possible: mining income taxed at receipt + capital gain on later sale.",
                    },
                ],
            },
            {
                "name": "DeFi (Liquidity Providing, Yield Farming)",
                "rules": [
                    {
                        "rule": "Providing liquidity to DEX pools may trigger a taxable disposal event",
                        "tax_rate": "Personal income tax rate if holding < 1 year",
                        "exemption": "€1,000 Freigrenze on disposal gains",
                        "note": "Tax treatment of LP tokens is still debated. Adding tokens to a pool may be treated as a sale of the original tokens. BMF has not issued definitive guidance.",
                    },
                    {
                        "rule": "Yield farming rewards taxed as sonstige Einkünfte at receipt",
                        "tax_rate": "Personal income tax rate (14-45%) + Soli",
                        "exemption": "€256 Freigrenze for sonstige Einkünfte",
                        "note": "Each reward token receipt is a taxable event. Track the EUR value at the exact time of receipt.",
                    },
                ],
            },
            {
                "name": "NFTs",
                "rules": [
                    {
                        "rule": "NFT trading treated same as crypto trading — private sales under §23 EStG",
                        "tax_rate": "Personal income tax rate if sold within 1 year",
                        "exemption": "€1,000 Freigrenze (shared with all private sales)",
                        "note": "Creating and selling NFTs as an artist/creator may be classified as commercial income (Gewerbebetrieb).",
                    },
                ],
            },
            {
                "name": "Airdrops & Forks",
                "rules": [
                    {
                        "rule": "Airdrops: taxed as sonstige Einkünfte at fair market value when received (if received due to active participation)",
                        "tax_rate": "Personal income tax rate (14-45%) + Soli",
                        "exemption": "€256 Freigrenze for sonstige Einkünfte",
                        "note": "Unsolicited airdrops (no action required) may have a cost basis of €0. Claimed airdrops (required action) are taxed at receipt.",
                    },
                    {
                        "rule": "Hard forks: new coins received may have cost basis of €0",
                        "tax_rate": "Taxed on disposal — 1-year holding period applies from fork date",
                        "exemption": "€1,000 Freigrenze on disposal",
                        "note": "The 1-year holding period for forked coins starts at the date of the fork, not the original purchase date.",
                    },
                ],
            },
        ],
        "reporting_requirements": [
            "Must declare in annual tax return (Anlage SO for private sales, Anlage KAP for some income)",
            "Keep detailed records of all transactions (date, amount, price, counterparty)",
            "FIFO method (First In, First Out) is the standard for cost basis calculation",
            "Maintain records for at least 10 years (general tax retention period)",
            "Foreign exchange accounts must be reported (Anlage AUS if applicable)",
        ],
        "deadlines": [
            {
                "date": "2026-07-31",
                "description": "Tax return deadline for 2025 (without Steuerberater)",
            },
            {
                "date": "2027-02-28",
                "description": "Tax return deadline for 2025 (with Steuerberater)",
            },
            {
                "date": "2026-03-10",
                "description": "Quarterly income tax prepayment (Vorauszahlung) Q1 2026",
            },
            {
                "date": "2026-06-10",
                "description": "Quarterly income tax prepayment (Vorauszahlung) Q2 2026",
            },
        ],
        "authorities": {
            "name": "Finanzamt (local tax office)",
            "reporting_to": "BZSt (Bundeszentralamt für Steuern)",
            "guidance_url": "https://www.bundesfinanzministerium.de",
            "key_legislation": [
                "§23 EStG (Private Veräußerungsgeschäfte)",
                "§22 Nr. 3 EStG (Sonstige Einkünfte)",
                "§15 EStG (Gewerbebetrieb — for professional trading/mining)",
                "BMF-Schreiben vom 10.05.2022 (Crypto guidance letter)",
            ],
        },
    },
    "CH": {
        "country": "CH",
        "country_name": "Switzerland",
        "last_updated": "2026-03-30",
        "summary": (
            "Switzerland has no capital gains tax for private investors on crypto. "
            "However, holdings are subject to cantonal wealth tax (Vermögenssteuer). "
            "Professional traders (gewerbsmässiger Handel) are fully taxed on gains. "
            "Staking/mining income is taxed as regular income."
        ),
        "tax_categories": [
            {
                "name": "Trading Gains (Spot)",
                "rules": [
                    {
                        "rule": "Private investors: capital gains on movable assets are TAX-FREE",
                        "tax_rate": "0% (no capital gains tax for private investors)",
                        "exemption": "Unlimited — no cap on tax-free gains",
                        "note": "This is Switzerland's major advantage. No holding period required. However, you must qualify as a 'private investor' not a professional trader.",
                    },
                    {
                        "rule": "Professional traders (gewerbsmässiger Handel): gains taxed as self-employment income",
                        "tax_rate": "Cantonal income tax rates (varies by canton, ~20-40%) + AHV/IV/EO social contributions (~10%)",
                        "exemption": "None for professional traders",
                        "note": "ESTV criteria for professional trading: high trading volume, short holding periods, leveraged positions, trading as main income source, use of specialized knowledge. If 2+ criteria met, risk of classification as professional.",
                    },
                ],
            },
            {
                "name": "Wealth Tax (Vermögenssteuer)",
                "rules": [
                    {
                        "rule": "All crypto holdings must be declared for wealth tax at fair market value on Dec 31",
                        "tax_rate": "Varies by canton: typically 0.1-1.0% of total taxable wealth",
                        "exemption": "Varies by canton (e.g., Zug: ~CHF 200,000 for singles)",
                        "note": "ESTV publishes official crypto exchange rates on Dec 31 each year. Use these rates for your declaration. Unreported crypto is tax evasion.",
                    },
                ],
            },
            {
                "name": "Staking & Lending Income",
                "rules": [
                    {
                        "rule": "Staking rewards taxed as income from movable property (Einkünfte aus beweglichem Vermögen)",
                        "tax_rate": "Cantonal income tax rates (varies by canton)",
                        "exemption": "None specifically for staking income",
                        "note": "Staking rewards are taxed at the fair market value at time of receipt. Must be declared in the annual tax return.",
                    },
                    {
                        "rule": "Lending interest taxed as income",
                        "tax_rate": "Cantonal income tax rates",
                        "exemption": "None",
                        "note": "Interest from crypto lending platforms is treated as regular income and must be declared.",
                    },
                ],
            },
            {
                "name": "Mining",
                "rules": [
                    {
                        "rule": "Mining income is generally taxed as self-employment income (selbständige Erwerbstätigkeit)",
                        "tax_rate": "Cantonal income tax rates + AHV/IV/EO contributions",
                        "exemption": "Business expenses are deductible (electricity, hardware, etc.)",
                        "note": "Hobby mining may be treated as income from movable property. Professional mining requires AHV registration and social contributions.",
                    },
                ],
            },
            {
                "name": "DeFi (Liquidity Providing, Yield Farming)",
                "rules": [
                    {
                        "rule": "DeFi yields generally treated as income for private investors",
                        "tax_rate": "Cantonal income tax rates",
                        "exemption": "None specifically",
                        "note": "Swiss tax authorities are still developing guidance on complex DeFi activities. Conservative approach: declare all DeFi income.",
                    },
                    {
                        "rule": "LP token swaps: may be tax-neutral for private investors (asset swap, no realization event)",
                        "tax_rate": "0% if private investor (no capital gains tax)",
                        "exemption": "N/A for private investors",
                        "note": "This is an advantage of the Swiss system — token swaps in DeFi pools are generally not taxable events for private investors.",
                    },
                ],
            },
            {
                "name": "NFTs",
                "rules": [
                    {
                        "rule": "NFT trading by private investors: capital gains tax-free (same as crypto)",
                        "tax_rate": "0% for private investors",
                        "exemption": "Unlimited",
                        "note": "NFTs must still be declared for wealth tax at fair market value on Dec 31. Valuation can be challenging for unique NFTs.",
                    },
                ],
            },
            {
                "name": "Airdrops & Forks",
                "rules": [
                    {
                        "rule": "Airdrops: taxed as income at fair market value when received",
                        "tax_rate": "Cantonal income tax rates",
                        "exemption": "None",
                        "note": "Even unsolicited airdrops must be declared as income. Fair market value at receipt date is used.",
                    },
                    {
                        "rule": "Hard forks: new coins have cost basis of CHF 0 for wealth tax purposes",
                        "tax_rate": "No capital gains tax on disposal (private investor). Wealth tax applies from Dec 31 valuation.",
                        "exemption": "N/A",
                        "note": "Forked coins must be added to wealth tax declaration at their fair market value.",
                    },
                ],
            },
        ],
        "reporting_requirements": [
            "Declare all crypto holdings in Wertschriftenverzeichnis (securities register) for wealth tax",
            "Use ESTV official exchange rates for Dec 31 valuation",
            "Declare staking/lending/mining income in tax return",
            "Keep transaction records for verification",
            "Professional traders must register for AHV and keep business accounts",
        ],
        "deadlines": [
            {
                "date": "2026-03-31",
                "description": "Tax return deadline 2025 (varies by canton, most cantons March 31)",
            },
            {
                "date": "2026-09-30",
                "description": "Extended deadline with Fristverlängerung (extension request)",
            },
        ],
        "authorities": {
            "name": "Kantonales Steueramt (cantonal tax office)",
            "reporting_to": "ESTV (Eidgenössische Steuerverwaltung)",
            "guidance_url": "https://www.estv.admin.ch",
            "key_legislation": [
                "DBG Art. 16 Abs. 3 (No capital gains tax on private movable assets)",
                "DBG Art. 20 (Income from movable property)",
                "StHG Art. 14 (Cantonal wealth tax)",
                "ESTV Kreisschreiben / Praxishinweise zu Kryptowährungen",
            ],
        },
        "cantonal_notes": {
            "zug": "Crypto Valley — very crypto-friendly administration. Accepts tax payments in BTC/ETH.",
            "zurich": "Strict approach to professional trader classification.",
            "schwyz": "Low wealth tax rates, attractive for large crypto holdings.",
            "bern": "Standard approach, uses ESTV guidelines closely.",
        },
    },
    "AT": {
        "country": "AT",
        "country_name": "Austria",
        "last_updated": "2026-03-30",
        "summary": (
            "Austria introduced a flat 27.5% KESt (Kapitalertragsteuer) on all crypto gains "
            "since March 1, 2022 (ökosozialer Steuerreform). No holding period exemption anymore "
            "for new acquisitions. Altbestand (acquired before Feb 28, 2021) may still be tax-free "
            "after 1 year."
        ),
        "tax_categories": [
            {
                "name": "Trading Gains (Spot)",
                "rules": [
                    {
                        "rule": "Neubestand (acquired after Feb 28, 2021): 27.5% KESt on all gains, no holding period exemption",
                        "tax_rate": "27.5% flat tax (Kapitalertragsteuer / Sondersteuersatz)",
                        "exemption": "None — all gains taxed regardless of holding period",
                        "note": "Major change from 2022: the old 1-year holding period exemption was abolished for Neubestand. Crypto is now treated like stocks/bonds.",
                    },
                    {
                        "rule": "Altbestand (acquired before March 1, 2021): old rules may still apply",
                        "tax_rate": "0% if held for > 1 year (old Spekulationsfrist). If < 1 year: personal income tax rate (up to 55%)",
                        "exemption": "Tax-free after 1 year holding for Altbestand",
                        "note": "Altbestand provisions are transitional. FIFO method determines which coins are Altbestand vs Neubestand. Documentation is critical.",
                    },
                    {
                        "rule": "Option: Regelbesteuerung (standard taxation) instead of 27.5% flat rate",
                        "tax_rate": "Personal income tax rate (0-55%) — beneficial if marginal rate < 27.5%",
                        "exemption": "Standard personal allowances apply",
                        "note": "Low-income taxpayers may benefit from opting into standard taxation if their marginal rate is below 27.5%.",
                    },
                ],
            },
            {
                "name": "Staking & Lending Income",
                "rules": [
                    {
                        "rule": "Staking rewards: taxed at 27.5% KESt at time of receipt (zufluss)",
                        "tax_rate": "27.5% flat tax",
                        "exemption": "None",
                        "note": "Staking rewards are classified as Einkünfte aus Kapitalvermögen (§27 EStG). Taxed at fair market value when received.",
                    },
                    {
                        "rule": "Lending interest: taxed at 27.5% KESt",
                        "tax_rate": "27.5% flat tax",
                        "exemption": "None",
                        "note": "DeFi lending interest is treated the same as centralized lending for tax purposes.",
                    },
                ],
            },
            {
                "name": "Mining",
                "rules": [
                    {
                        "rule": "Mining income: taxed at personal income tax rate (not KESt) as Einkünfte aus Gewerbebetrieb",
                        "tax_rate": "Personal income tax rate (0-55%) + potential Gewerbesteuer",
                        "exemption": "Business expenses deductible (hardware, electricity)",
                        "note": "Mining is NOT covered by the 27.5% flat tax. It is classified as business income (Gewerbebetrieb) and taxed at progressive rates.",
                    },
                ],
            },
            {
                "name": "DeFi (Liquidity Providing, Yield Farming)",
                "rules": [
                    {
                        "rule": "Token swaps into LP tokens: treated as taxable disposal (tauschähnlicher Vorgang)",
                        "tax_rate": "27.5% KESt on realized gains",
                        "exemption": "None",
                        "note": "Entering and exiting liquidity pools triggers taxable events under Austrian law. Track cost basis carefully.",
                    },
                    {
                        "rule": "Yield farming rewards: taxed at 27.5% KESt as Einkünfte aus Kapitalvermögen",
                        "tax_rate": "27.5% flat tax",
                        "exemption": "None",
                        "note": "Each reward receipt is a taxable event. Document the EUR value at the exact time of receipt.",
                    },
                ],
            },
            {
                "name": "NFTs",
                "rules": [
                    {
                        "rule": "NFTs treated as crypto assets under the 2022 reform: 27.5% KESt on gains",
                        "tax_rate": "27.5% flat tax",
                        "exemption": "None",
                        "note": "Both fungible and non-fungible tokens fall under the same tax regime since the 2022 reform.",
                    },
                ],
            },
            {
                "name": "Airdrops & Forks",
                "rules": [
                    {
                        "rule": "Airdrops: taxed at 27.5% KESt at fair market value when received",
                        "tax_rate": "27.5% flat tax",
                        "exemption": "None",
                        "note": "Cost basis of airdropped tokens = fair market value at time of receipt (which was already taxed).",
                    },
                    {
                        "rule": "Hard forks: new coins have cost basis of €0, taxed at 27.5% on disposal",
                        "tax_rate": "27.5% KESt on full disposal amount (cost basis = €0)",
                        "exemption": "None",
                        "note": "Since forked coins have €0 cost basis, the entire sale proceeds are considered taxable gain.",
                    },
                ],
            },
        ],
        "reporting_requirements": [
            "Declare all crypto income in annual tax return (Einkommensteuererklärung)",
            "Formular E1kv for Einkünfte aus Kapitalvermögen",
            "Austrian crypto exchanges may withhold 27.5% KESt automatically",
            "Foreign exchange gains must be self-reported",
            "FIFO method (gleitender Durchschnittspreis also acceptable)",
            "Keep records for minimum 7 years",
        ],
        "deadlines": [
            {
                "date": "2026-04-30",
                "description": "Tax return deadline 2025 (paper submission)",
            },
            {
                "date": "2026-06-30",
                "description": "Tax return deadline 2025 (FinanzOnline electronic submission)",
            },
            {
                "date": "2027-03-31",
                "description": "Extended deadline 2025 (with Steuerberater)",
            },
        ],
        "authorities": {
            "name": "Finanzamt (local tax office)",
            "reporting_to": "BMF (Bundesministerium für Finanzen)",
            "guidance_url": "https://www.bmf.gv.at",
            "key_legislation": [
                "§27 EStG (Einkünfte aus Kapitalvermögen)",
                "§27a EStG (Sondersteuersatz 27.5%)",
                "§27b EStG (Kryptowährungen — introduced 2022)",
                "Ökosoziales Steuerreformgesetz 2022",
                "BMF-Info zur steuerlichen Behandlung von Kryptowährungen (2022)",
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TaxEstimateRequest(BaseModel):
    country: str
    purchase_price: float
    sale_price: float
    holding_days: int
    income_tax_rate: Optional[float] = None
    type: str = "trading"


class TaxEstimateResponse(BaseModel):
    country: str
    country_name: str
    type: str
    purchase_price: float
    sale_price: float
    gain: float
    holding_days: int
    holding_period_met: bool
    tax_rate_applied: float
    estimated_tax: float
    effective_rate: float
    exemption_applied: Optional[str] = None
    notes: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/rules")
async def get_tax_rules(
    country: str = Query(..., pattern="^(DE|CH|AT)$", description="Country code: DE, CH, or AT"),
):
    """Return comprehensive crypto tax rules for the specified country."""
    rules = _TAX_RULES.get(country.upper())
    if not rules:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}. Use DE, CH, or AT.")
    return rules


@router.get("/compare")
async def compare_tax_rules():
    """Return side-by-side comparison of all 3 DACH countries' tax treatment."""
    return {
        "comparison_date": str(date.today()),
        "countries": ["DE", "CH", "AT"],
        "comparison": [
            {
                "category": "Trading Gains (Private Investor)",
                "DE": {
                    "rate": "0-45% + Soli (14-47.5% effective)",
                    "holding_period": "Tax-free after 1 year",
                    "exemption": "€1,000/year Freigrenze (short-term)",
                },
                "CH": {
                    "rate": "0% (no capital gains tax)",
                    "holding_period": "None required",
                    "exemption": "Unlimited — all gains tax-free for private investors",
                },
                "AT": {
                    "rate": "27.5% flat tax (KESt)",
                    "holding_period": "None (abolished in 2022 for Neubestand)",
                    "exemption": "None",
                },
            },
            {
                "category": "Staking Income",
                "DE": {
                    "rate": "Personal income tax rate (14-45%)",
                    "exemption": "€256/year Freigrenze",
                    "note": "Does NOT extend holding period to 10 years (BMF 2022)",
                },
                "CH": {
                    "rate": "Cantonal income tax rate (20-40%)",
                    "exemption": "None specifically",
                    "note": "Taxed as income from movable property",
                },
                "AT": {
                    "rate": "27.5% flat tax (KESt)",
                    "exemption": "None",
                    "note": "Same flat rate as trading gains",
                },
            },
            {
                "category": "Mining",
                "DE": {
                    "rate": "Income tax + Gewerbesteuer if professional",
                    "classification": "Gewerbebetrieb (professional) or sonstige Einkünfte (hobby)",
                },
                "CH": {
                    "rate": "Income tax + AHV contributions",
                    "classification": "Self-employment income",
                },
                "AT": {
                    "rate": "Income tax (0-55%) — NOT the 27.5% flat rate",
                    "classification": "Gewerbebetrieb",
                },
            },
            {
                "category": "Wealth Tax",
                "DE": {
                    "rate": "0% (no wealth tax in Germany)",
                    "note": "Germany abolished wealth tax in 1997",
                },
                "CH": {
                    "rate": "0.1-1.0% depending on canton",
                    "note": "Must declare all crypto holdings at Dec 31 fair market value",
                },
                "AT": {
                    "rate": "0% (no wealth tax in Austria)",
                    "note": "Austria does not have a wealth tax",
                },
            },
            {
                "category": "Loss Deduction",
                "DE": {
                    "rule": "Losses can offset gains from other private sales in the same year or carry forward",
                    "note": "Cannot offset against other income types (salary, etc.)",
                },
                "CH": {
                    "rule": "N/A — no capital gains tax means no loss deduction for private investors",
                    "note": "Professional traders can deduct losses against business income",
                },
                "AT": {
                    "rule": "Crypto losses can offset crypto gains and other capital income (since 2022)",
                    "note": "Loss carryforward is possible within capital income category",
                },
            },
            {
                "category": "Cost Basis Method",
                "DE": "FIFO (First In, First Out) — required",
                "CH": "FIFO recommended, weighted average also accepted",
                "AT": "FIFO or gleitender Durchschnittspreis (moving average cost)",
            },
            {
                "category": "Crypto-Friendliness Rating",
                "DE": {
                    "rating": "8/10",
                    "reason": "1-year holding = tax-free is very attractive for long-term holders",
                },
                "CH": {
                    "rating": "10/10",
                    "reason": "No capital gains tax at all. Best in DACH for traders.",
                },
                "AT": {
                    "rating": "5/10",
                    "reason": "27.5% flat tax on everything, no exemptions. Clear but not favorable.",
                },
            },
        ],
    }


@router.post("/estimate", response_model=TaxEstimateResponse)
async def estimate_tax(req: TaxEstimateRequest):
    """Calculate estimated tax owed based on the country's rules."""
    country = req.country.upper()
    if country not in _TAX_RULES:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}. Use DE, CH, or AT.")

    gain = req.sale_price - req.purchase_price
    notes: list[str] = []
    tax_rate = 0.0
    estimated_tax = 0.0
    exemption_applied: Optional[str] = None
    holding_period_met = False

    if country == "DE":
        income_rate = req.income_tax_rate if req.income_tax_rate is not None else 42.0
        soli_rate = income_rate * 0.055  # 5.5% Solidaritätszuschlag on the tax
        effective_rate = income_rate + soli_rate

        if req.type == "trading":
            if req.holding_days >= 365:
                holding_period_met = True
                tax_rate = 0.0
                estimated_tax = 0.0
                exemption_applied = "1-year holding period (§23 EStG) — completely tax-free"
                notes.append("Held for >= 1 year: gains are completely tax-free in Germany.")
            else:
                holding_period_met = False
                if gain <= 0:
                    tax_rate = 0.0
                    estimated_tax = 0.0
                    notes.append("No gain — no tax owed. Loss can be carried forward for offset against future private sale gains.")
                elif gain <= 1000:
                    tax_rate = 0.0
                    estimated_tax = 0.0
                    exemption_applied = "€1,000 Freigrenze (total short-term gains below threshold)"
                    notes.append("Gain below €1,000 Freigrenze — tax-free. WARNING: This is a Freigrenze, not Freibetrag. If your TOTAL private sale gains in 2025 exceed €1,000, ALL gains become taxable.")
                else:
                    tax_rate = round(effective_rate, 2)
                    estimated_tax = round(gain * effective_rate / 100, 2)
                    notes.append(f"Short-term gain above €1,000: taxed at {income_rate}% + {round(soli_rate, 2)}% Soli = {round(effective_rate, 2)}% effective rate.")
                    notes.append("Freigrenze exceeded: the ENTIRE gain is taxed, not just the amount above €1,000.")
        elif req.type == "staking":
            tax_rate = round(effective_rate, 2)
            if gain <= 256:
                estimated_tax = 0.0
                exemption_applied = "€256 Freigrenze for sonstige Einkünfte"
                notes.append("Staking income below €256 Freigrenze — tax-free.")
            else:
                estimated_tax = round(gain * effective_rate / 100, 2)
                notes.append(f"Staking income taxed as sonstige Einkünfte at {round(effective_rate, 2)}%.")
        else:
            tax_rate = round(effective_rate, 2)
            estimated_tax = max(0, round(gain * effective_rate / 100, 2))
            notes.append(f"Taxed at personal income tax rate: {round(effective_rate, 2)}%.")

    elif country == "CH":
        if req.type == "trading":
            holding_period_met = True  # No holding period in CH
            tax_rate = 0.0
            estimated_tax = 0.0
            exemption_applied = "No capital gains tax for private investors (DBG Art. 16 Abs. 3)"
            notes.append("Switzerland has NO capital gains tax for private investors.")
            notes.append("WARNING: If you qualify as a professional trader (gewerbsmässiger Handel), gains would be taxed as self-employment income at cantonal rates (20-40%+).")
            notes.append("ESTV criteria for professional trader: high volume, short holding periods, leverage, trading as main income, specialized knowledge.")
        elif req.type == "staking":
            cantonal_rate = req.income_tax_rate if req.income_tax_rate is not None else 30.0
            tax_rate = cantonal_rate
            estimated_tax = round(gain * cantonal_rate / 100, 2)
            notes.append(f"Staking income taxed as income from movable property at estimated cantonal rate of {cantonal_rate}%.")
            notes.append("Actual rate depends on your canton and total income. Rates vary significantly (Zug ~22%, Zurich ~35%).")
        else:
            cantonal_rate = req.income_tax_rate if req.income_tax_rate is not None else 30.0
            tax_rate = cantonal_rate
            estimated_tax = max(0, round(gain * cantonal_rate / 100, 2))
            notes.append(f"Taxed at estimated cantonal rate of {cantonal_rate}%.")
        # Always note wealth tax
        notes.append("Remember: ALL crypto holdings are subject to cantonal wealth tax (0.1-1.0%) based on Dec 31 valuation.")

    elif country == "AT":
        if req.type == "trading":
            holding_period_met = False  # No holding period exemption for Neubestand
            if gain <= 0:
                tax_rate = 0.0
                estimated_tax = 0.0
                notes.append("No gain — no tax owed. Losses can offset other capital income (Verlustausgleich).")
            else:
                tax_rate = 27.5
                estimated_tax = round(gain * 0.275, 2)
                notes.append("27.5% KESt flat tax on all crypto gains (Neubestand since March 2022).")
                notes.append("No holding period exemption for Neubestand. The old 1-year Spekulationsfrist was abolished.")
                if req.holding_days >= 365:
                    notes.append("NOTE: Altbestand (acquired before March 1, 2021) would be tax-free after 1 year. Use FIFO to determine if your coins are Altbestand.")
        elif req.type == "staking":
            tax_rate = 27.5
            estimated_tax = round(max(0, gain) * 0.275, 2)
            notes.append("Staking income taxed at 27.5% KESt flat rate.")
        elif req.type == "mining":
            mining_rate = req.income_tax_rate if req.income_tax_rate is not None else 42.0
            tax_rate = mining_rate
            estimated_tax = round(max(0, gain) * mining_rate / 100, 2)
            notes.append(f"Mining income taxed at personal income tax rate ({mining_rate}%), NOT the 27.5% flat rate.")
            notes.append("Mining is classified as Gewerbebetrieb. Business expenses (hardware, electricity) are deductible.")
        else:
            tax_rate = 27.5
            estimated_tax = round(max(0, gain) * 0.275, 2)
            notes.append("Taxed at 27.5% KESt flat rate.")

    effective_rate_pct = round((estimated_tax / gain * 100) if gain > 0 else 0.0, 2)

    return TaxEstimateResponse(
        country=country,
        country_name=_TAX_RULES[country]["country_name"],
        type=req.type,
        purchase_price=req.purchase_price,
        sale_price=req.sale_price,
        gain=round(gain, 2),
        holding_days=req.holding_days,
        holding_period_met=holding_period_met,
        tax_rate_applied=tax_rate,
        estimated_tax=max(0, estimated_tax),
        effective_rate=effective_rate_pct,
        exemption_applied=exemption_applied,
        notes=notes,
    )
