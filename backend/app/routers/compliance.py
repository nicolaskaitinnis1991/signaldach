"""MiCA Compliance Checker — comprehensive regulatory checklist for DACH crypto businesses."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.auth import require_role

router = APIRouter(prefix="/compliance", tags=["compliance"], dependencies=[Depends(require_role("admin", "analyst"))])

# ---------------------------------------------------------------------------
# Shared data
# ---------------------------------------------------------------------------

def _today() -> str:
    """Return current date as ISO string. Evaluated at call time, not module import."""
    return date.today().isoformat()

# ---------------------------------------------------------------------------
# Per-business-type checklist definitions
# ---------------------------------------------------------------------------

_CASP_ITEMS: list[dict] = [
    # -- Licensing --
    {
        "id": "casp-lic-001",
        "category": "Licensing",
        "requirement": "CASP License under MiCA Art. 59",
        "description": "All crypto-asset service providers must obtain authorization from their national competent authority before providing services in the EU.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Apply for CASP license with BaFin (DE) or utilize passporting from another EU member state.",
    },
    {
        "id": "casp-lic-002",
        "category": "Licensing",
        "requirement": "FINMA FinTech License or Banking License (CH)",
        "description": "Swiss CASPs must hold a FinTech license (accepting public deposits up to CHF 100M) or a full banking license from FINMA.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/authorisation/fintech/",
        "action": "Apply to FINMA for FinTech license under the Banking Act (BankA) Art. 1b.",
    },
    {
        "id": "casp-lic-003",
        "category": "Licensing",
        "requirement": "Transitional period registration (MiCA Art. 143)",
        "description": "Existing licensed CASPs may continue operating under national law during the 18-month transition period ending July 2026.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Verify your existing BaFin license qualifies for the transition period and file for full MiCA authorization before deadline.",
    },
    {
        "id": "casp-lic-004",
        "category": "Licensing",
        "requirement": "EU Passporting notification",
        "description": "Once MiCA-authorized, CASPs can passport services across EU by notifying home NCA at least 3 months before.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Prepare passporting notification for each target EU jurisdiction.",
    },
    {
        "id": "casp-lic-005",
        "category": "Licensing",
        "requirement": "BaFin Crypto Custody License (KWG Section 1 Abs. 1a)",
        "description": "German entities providing crypto custody must hold a separate license under KWG if not already covered by CASP authorization.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE"],
        "severity": "high",
        "reference_url": "https://www.bafin.de/EN/Aufsicht/FinTech/Kryptoverwahrgeschaeft/kryptoverwahrgeschaeft_node_en.html",
        "action": "Confirm whether your MiCA CASP license covers custody or if a separate KWG license is needed.",
    },
    # -- AML/KYC --
    {
        "id": "casp-aml-001",
        "category": "AML/KYC",
        "requirement": "Customer Due Diligence (CDD) under MiCA Art. 68",
        "description": "CASPs must perform CDD including identity verification for all customers before establishing a business relationship.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement KYC onboarding flow with identity verification, PEP screening, and sanctions checks.",
    },
    {
        "id": "casp-aml-002",
        "category": "AML/KYC",
        "requirement": "Travel Rule compliance (TFR Regulation)",
        "description": "Transfer of Funds Regulation requires CASPs to collect and transmit originator and beneficiary data for all crypto transfers.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1113",
        "action": "Integrate Travel Rule protocol (e.g., TRISA, OpenVASP, Sygna) for all outgoing crypto transfers.",
    },
    {
        "id": "casp-aml-003",
        "category": "AML/KYC",
        "requirement": "Swiss AMLA compliance (GwG)",
        "description": "Swiss CASPs are financial intermediaries under the Anti-Money Laundering Act and must register with a self-regulatory organization (SRO).",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/supervision/anti-money-laundering/",
        "action": "Register with an SRO (e.g., VQF, PolyReg) and implement AMLA-compliant procedures.",
    },
    {
        "id": "casp-aml-004",
        "category": "AML/KYC",
        "requirement": "Suspicious Activity Reporting (SAR)",
        "description": "CASPs must file SARs with the FIU (BKA in DE, MROS in CH) for any suspicious transactions.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Establish internal SAR procedures and designate a Money Laundering Reporting Officer (MLRO).",
    },
    {
        "id": "casp-aml-005",
        "category": "AML/KYC",
        "requirement": "Enhanced Due Diligence for high-risk customers",
        "description": "CASPs must apply EDD for PEPs, high-risk third countries, and transactions above EUR 1,000 threshold.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Implement tiered risk assessment framework and EDD procedures for flagged accounts.",
    },
    # -- Capital Requirements --
    {
        "id": "casp-cap-001",
        "category": "Capital Requirements",
        "requirement": "Minimum capital EUR 125,000 (MiCA Art. 67)",
        "description": "CASPs providing exchange, portfolio management, or transfer services must maintain minimum own funds of EUR 125,000.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Ensure EUR 125,000 in permanent own funds or professional indemnity insurance.",
    },
    {
        "id": "casp-cap-002",
        "category": "Capital Requirements",
        "requirement": "Minimum capital EUR 150,000 for custody/admin",
        "description": "CASPs providing custody and administration of crypto-assets must maintain at least EUR 150,000.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Maintain EUR 150,000 in own funds if providing custody services.",
    },
    {
        "id": "casp-cap-003",
        "category": "Capital Requirements",
        "requirement": "Quarter of fixed overheads requirement",
        "description": "Own funds must be at least one quarter of the prior year's fixed overheads, whichever is higher.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Calculate fixed overheads and ensure capital exceeds 25% of prior-year fixed costs.",
    },
    {
        "id": "casp-cap-004",
        "category": "Capital Requirements",
        "requirement": "Swiss capital requirements (FinTech license)",
        "description": "FINMA FinTech license holders must maintain minimum capital of CHF 300,000.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/authorisation/fintech/",
        "action": "Maintain minimum CHF 300,000 in equity capital.",
    },
    # -- Governance --
    {
        "id": "casp-gov-001",
        "category": "Governance",
        "requirement": "Management body fitness and propriety (MiCA Art. 63)",
        "description": "Directors and qualifying shareholders must demonstrate good repute, knowledge, and experience.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Prepare fit-and-proper documentation for all board members and significant shareholders.",
    },
    {
        "id": "casp-gov-002",
        "category": "Governance",
        "requirement": "Conflict of interest policy (MiCA Art. 72)",
        "description": "CASPs must establish, implement, and maintain an effective conflict of interest policy.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Draft and implement conflict of interest policy covering all service areas.",
    },
    {
        "id": "casp-gov-003",
        "category": "Governance",
        "requirement": "Business continuity and disaster recovery plan",
        "description": "CASPs must maintain ICT risk management and business continuity frameworks aligned with DORA.",
        "status": "required",
        "deadline": "2025-01-17",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        "action": "Develop BCP/DRP aligned with DORA (Digital Operational Resilience Act) requirements.",
    },
    {
        "id": "casp-gov-004",
        "category": "Governance",
        "requirement": "Internal control mechanisms",
        "description": "CASPs must establish adequate internal control mechanisms including compliance function, risk management, and internal audit.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish three lines of defense: operational management, compliance/risk, and internal audit.",
    },
    {
        "id": "casp-gov-005",
        "category": "Governance",
        "requirement": "Outsourcing arrangements documentation",
        "description": "CASPs outsourcing critical functions must notify NCA and ensure the outsourcing does not impair quality of internal controls.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Document all outsourcing arrangements and assess whether NCA notification is required.",
    },
    # -- Reporting --
    {
        "id": "casp-rep-001",
        "category": "Reporting",
        "requirement": "Annual reporting to NCA (MiCA Art. 65)",
        "description": "CASPs must submit annual reports to their NCA including financial statements and activity reports.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Prepare template for annual NCA reporting covering all required disclosures.",
    },
    {
        "id": "casp-rep-002",
        "category": "Reporting",
        "requirement": "Transaction reporting and record-keeping",
        "description": "CASPs must maintain records of all transactions for at least 5 years and make them available to authorities.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement 5-year transaction logging with searchable records and audit trail.",
    },
    {
        "id": "casp-rep-003",
        "category": "Reporting",
        "requirement": "DORA ICT incident reporting",
        "description": "Major ICT-related incidents must be reported to competent authorities within defined timeframes under DORA.",
        "status": "required",
        "deadline": "2025-01-17",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        "action": "Establish ICT incident classification and reporting procedures per DORA timelines.",
    },
    {
        "id": "casp-rep-004",
        "category": "Reporting",
        "requirement": "DAC8 tax reporting (crypto transactions)",
        "description": "CASPs must report crypto transaction data to tax authorities under the EU DAC8 directive starting 2026.",
        "status": "required",
        "deadline": "2026-01-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023L2226",
        "action": "Implement DAC8-compliant tax reporting system for all customer transactions.",
    },
    # -- Consumer Protection --
    {
        "id": "casp-con-001",
        "category": "Consumer Protection",
        "requirement": "Pre-contractual disclosure (MiCA Art. 66)",
        "description": "CASPs must provide clear, fair, and not misleading information to clients before providing services.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Prepare pre-contractual disclosure documents including fee schedules, risk warnings, and service descriptions.",
    },
    {
        "id": "casp-con-002",
        "category": "Consumer Protection",
        "requirement": "Complaints handling procedure (MiCA Art. 71)",
        "description": "CASPs must establish and maintain an effective and transparent complaints handling procedure.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement complaints procedure with defined timelines and escalation paths.",
    },
    {
        "id": "casp-con-003",
        "category": "Consumer Protection",
        "requirement": "Asset segregation (MiCA Art. 70)",
        "description": "CASPs holding client crypto-assets must keep them segregated from own assets and clearly identifiable.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Ensure complete segregation of client crypto-assets from proprietary holdings with independent audit.",
    },
    {
        "id": "casp-con-004",
        "category": "Consumer Protection",
        "requirement": "Risk warnings for crypto-assets",
        "description": "Marketing communications must include clear risk warnings that crypto-assets can lose their entire value.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Add standardized risk warnings to all marketing materials and client-facing communications.",
    },
    {
        "id": "casp-con-005",
        "category": "Consumer Protection",
        "requirement": "Suitability and appropriateness assessment",
        "description": "CASPs providing advice or portfolio management must assess client suitability; others must assess appropriateness.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement client profiling questionnaire for suitability/appropriateness assessment.",
    },
]

_ISSUER_ITEMS: list[dict] = [
    # -- Licensing --
    {
        "id": "iss-lic-001",
        "category": "Licensing",
        "requirement": "White Paper notification (MiCA Art. 8)",
        "description": "Issuers of crypto-assets (other than ARTs/EMTs) must publish a crypto-asset white paper and notify the competent authority.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Draft compliant white paper per MiCA Annex I and notify BaFin at least 20 working days before publication.",
    },
    {
        "id": "iss-lic-002",
        "category": "Licensing",
        "requirement": "ART authorization (MiCA Art. 16)",
        "description": "Issuers of Asset-Referenced Tokens must be authorized by NCA and comply with specific reserve and governance requirements.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Apply for ART authorization including reserve asset documentation and redemption procedures.",
    },
    {
        "id": "iss-lic-003",
        "category": "Licensing",
        "requirement": "EMT authorization as credit/e-money institution (MiCA Art. 48)",
        "description": "E-Money Token issuers must be authorized as a credit institution or e-money institution.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Obtain e-money institution license or credit institution license before issuing EMTs.",
    },
    {
        "id": "iss-lic-004",
        "category": "Licensing",
        "requirement": "FINMA Securities classification (CH)",
        "description": "FINMA classifies tokens as payment, utility, or asset tokens — each with different regulatory requirements.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/documentation/finma-guidance/guidelines/guidelines-relating-to-initial-coin-offerings/",
        "action": "Submit token classification request to FINMA to determine applicable regulatory framework.",
    },
    # -- AML/KYC --
    {
        "id": "iss-aml-001",
        "category": "AML/KYC",
        "requirement": "KYC for token holders",
        "description": "Issuers must implement KYC procedures for all token purchasers in primary distribution.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement KYC for primary token distribution with identity verification.",
    },
    {
        "id": "iss-aml-002",
        "category": "AML/KYC",
        "requirement": "ART/EMT holder identification",
        "description": "ART/EMT issuers must maintain records of all holders and ensure traceability of transfers.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement holder registry with ongoing monitoring of transfer patterns.",
    },
    {
        "id": "iss-aml-003",
        "category": "AML/KYC",
        "requirement": "Sanctions screening for all purchasers",
        "description": "All token purchasers must be screened against EU, OFAC, and Swiss SECO sanctions lists.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0269",
        "action": "Integrate real-time sanctions screening into token purchase flow.",
    },
    # -- Capital Requirements --
    {
        "id": "iss-cap-001",
        "category": "Capital Requirements",
        "requirement": "ART reserve of assets (MiCA Art. 36)",
        "description": "ART issuers must maintain a reserve of assets backing the token at all times, with composition rules.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish compliant reserve with custodian, composition rules, and regular independent audits.",
    },
    {
        "id": "iss-cap-002",
        "category": "Capital Requirements",
        "requirement": "EMT funds safeguarding (MiCA Art. 54)",
        "description": "EMT issuers must safeguard funds received in exchange for tokens in segregated accounts or invested in secure assets.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Open segregated safeguarding accounts with approved credit institutions.",
    },
    {
        "id": "iss-cap-003",
        "category": "Capital Requirements",
        "requirement": "Own funds requirement for ART (MiCA Art. 35)",
        "description": "ART issuers must maintain own funds of at least EUR 350,000 or 2% of average reserve assets, whichever is higher.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Calculate own funds requirement based on reserve size and maintain adequate capital.",
    },
    # -- Governance --
    {
        "id": "iss-gov-001",
        "category": "Governance",
        "requirement": "White paper accuracy and liability (MiCA Art. 15)",
        "description": "Issuers are liable for damages to holders resulting from misleading, inaccurate, or unclear information in the white paper.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Have legal counsel review white paper for accuracy and completeness before publication.",
    },
    {
        "id": "iss-gov-002",
        "category": "Governance",
        "requirement": "ART governance arrangements (MiCA Art. 34)",
        "description": "ART issuers need robust governance including management body accountability, internal controls, and risk management.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish governance framework with clear accountability for reserve management.",
    },
    {
        "id": "iss-gov-003",
        "category": "Governance",
        "requirement": "Redemption rights and mechanisms (MiCA Art. 39)",
        "description": "ART holders must have the right to redeem at any time at market value of referenced assets.",
        "status": "required",
        "deadline": "2025-06-30",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement clear redemption mechanism with documented procedures and timelines.",
    },
    # -- Reporting --
    {
        "id": "iss-rep-001",
        "category": "Reporting",
        "requirement": "White paper update obligations",
        "description": "Issuers must update the white paper whenever there is a significant change affecting the assessment of crypto-assets.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish white paper maintenance process with triggers for material updates.",
    },
    {
        "id": "iss-rep-002",
        "category": "Reporting",
        "requirement": "ART quarterly reserve report (MiCA Art. 36)",
        "description": "ART issuers must publish quarterly independent audit reports on the composition of reserve assets.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Engage independent auditor for quarterly reserve attestation and public reporting.",
    },
    {
        "id": "iss-rep-003",
        "category": "Reporting",
        "requirement": "Significant ART/EMT designation reporting",
        "description": "If token reaches significance thresholds (e.g., > EUR 5B market cap), additional EBA reporting applies.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Monitor significance indicators and prepare for enhanced EBA reporting if thresholds are approached.",
    },
    # -- Consumer Protection --
    {
        "id": "iss-con-001",
        "category": "Consumer Protection",
        "requirement": "Right of withdrawal (MiCA Art. 13)",
        "description": "Retail holders have a 14-day right of withdrawal from purchase of crypto-assets offered to the public.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement 14-day cooling-off mechanism for retail purchasers with refund capability.",
    },
    {
        "id": "iss-con-002",
        "category": "Consumer Protection",
        "requirement": "Marketing communications standards (MiCA Art. 7)",
        "description": "Marketing must be clearly identifiable, fair, clear, and not misleading, with risk warnings.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Review all marketing materials for compliance with MiCA marketing standards.",
    },
    {
        "id": "iss-con-003",
        "category": "Consumer Protection",
        "requirement": "Fair treatment of token holders",
        "description": "Issuers must act honestly, fairly, and professionally in the best interests of token holders.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Develop and implement fair treatment policy covering pricing, information disclosure, and governance.",
    },
]

_FUND_ITEMS: list[dict] = [
    # -- Licensing --
    {
        "id": "fund-lic-001",
        "category": "Licensing",
        "requirement": "AIFM registration/authorization (AIFMD)",
        "description": "Crypto funds structured as AIFs need an AIFM license. Sub-threshold managers may use registration regime.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Apply for AIFM authorization with BaFin or determine if sub-threshold registration applies.",
    },
    {
        "id": "fund-lic-002",
        "category": "Licensing",
        "requirement": "KWG Section 32 License (Finanzportfolioverwaltung)",
        "description": "German crypto fund managers providing portfolio management need a KWG license from BaFin.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE"],
        "severity": "critical",
        "reference_url": "https://www.bafin.de/EN/Aufsicht/BankenFinanzdienstleister/Zulassungspflicht/zulassungspflicht_node_en.html",
        "action": "Apply for Finanzportfolioverwaltung license with BaFin.",
    },
    {
        "id": "fund-lic-003",
        "category": "Licensing",
        "requirement": "FINMA CISA authorization (CH)",
        "description": "Swiss crypto funds must comply with the Collective Investment Schemes Act and obtain FINMA authorization.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/authorisation/collective-investment-schemes/",
        "action": "Apply for FINMA authorization under CISA for the fund and its management company.",
    },
    {
        "id": "fund-lic-004",
        "category": "Licensing",
        "requirement": "MiCA CASP license for fund-related services",
        "description": "If the fund directly provides crypto services (exchange, custody), additional CASP authorization is required.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Assess whether fund activities trigger CASP licensing requirements under MiCA.",
    },
    {
        "id": "fund-lic-005",
        "category": "Licensing",
        "requirement": "AIFMD II updates compliance",
        "description": "AIFMD II introduces new rules for loan origination, liquidity management, and delegation effective April 2026.",
        "status": "required",
        "deadline": "2026-04-16",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024L0927",
        "action": "Review fund structures and processes against AIFMD II requirements.",
    },
    # -- AML/KYC --
    {
        "id": "fund-aml-001",
        "category": "AML/KYC",
        "requirement": "Investor onboarding KYC/AML",
        "description": "Fund managers must perform full KYC/AML on all investors including UBO identification.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Implement comprehensive investor onboarding with KYC, AML, UBO identification, and source of funds checks.",
    },
    {
        "id": "fund-aml-002",
        "category": "AML/KYC",
        "requirement": "Ongoing transaction monitoring",
        "description": "Fund managers must monitor fund transactions for suspicious patterns and report to FIU.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Deploy transaction monitoring system covering all fund flows and crypto transactions.",
    },
    {
        "id": "fund-aml-003",
        "category": "AML/KYC",
        "requirement": "Travel Rule for fund crypto transfers",
        "description": "Fund crypto transfers must comply with Travel Rule requirements for originator/beneficiary data.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1113",
        "action": "Ensure fund's crypto transfers comply with Travel Rule via integrated protocol.",
    },
    # -- Capital Requirements --
    {
        "id": "fund-cap-001",
        "category": "Capital Requirements",
        "requirement": "AIFM initial capital EUR 125,000 (internally managed)",
        "description": "Internally managed AIFs require minimum initial capital of EUR 125,000; external AIFMs need EUR 300,000.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Maintain required initial capital (EUR 125K internal / EUR 300K external AIFM).",
    },
    {
        "id": "fund-cap-002",
        "category": "Capital Requirements",
        "requirement": "Additional own funds (0.02% of AUM above EUR 250M)",
        "description": "AIFMs must hold additional own funds of 0.02% of AUM exceeding EUR 250M, capped at EUR 10M total.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Calculate and maintain additional capital based on fund AUM.",
    },
    {
        "id": "fund-cap-003",
        "category": "Capital Requirements",
        "requirement": "Professional indemnity insurance",
        "description": "AIFMs must hold professional liability insurance or additional own funds to cover negligence risks.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Obtain PII coverage or maintain additional own funds as per AIFMD delegated regulation.",
    },
    # -- Governance --
    {
        "id": "fund-gov-001",
        "category": "Governance",
        "requirement": "Depositary appointment (AIFMD Art. 21)",
        "description": "AIFs must appoint an independent depositary for safekeeping of assets and oversight of fund operations.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Appoint qualified depositary with crypto-asset custody capabilities.",
    },
    {
        "id": "fund-gov-002",
        "category": "Governance",
        "requirement": "Valuation policy for crypto-assets",
        "description": "Fund managers must establish a fair value assessment policy for crypto-assets with independent valuation.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Develop crypto-asset valuation policy using reliable price sources and methodology.",
    },
    {
        "id": "fund-gov-003",
        "category": "Governance",
        "requirement": "Risk management framework",
        "description": "Fund managers must implement risk management covering market, liquidity, counterparty, and operational risks.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Establish comprehensive risk management with crypto-specific risk factors (smart contract, protocol, custody).",
    },
    {
        "id": "fund-gov-004",
        "category": "Governance",
        "requirement": "Liquidity management tools (AIFMD II)",
        "description": "AIFMD II requires open-ended AIFs to have at least two liquidity management tools available.",
        "status": "required",
        "deadline": "2026-04-16",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024L0927",
        "action": "Select and implement at least two LMTs (gates, swing pricing, side pockets, etc.) per AIFMD II.",
    },
    # -- Reporting --
    {
        "id": "fund-rep-001",
        "category": "Reporting",
        "requirement": "AIFMD Annex IV reporting to NCA",
        "description": "AIFMs must submit regular reports to NCA including leverage, risk, and liquidity data.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Prepare quarterly/semi-annual Annex IV reports including crypto-specific data points.",
    },
    {
        "id": "fund-rep-002",
        "category": "Reporting",
        "requirement": "Annual report to investors (AIFMD Art. 22)",
        "description": "Annual report must include audited financial statements, activity report, and remuneration disclosures.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Produce annual fund report within 6 months of fiscal year end with all AIFMD-required content.",
    },
    {
        "id": "fund-rep-003",
        "category": "Reporting",
        "requirement": "PRIIPs KID for retail-facing funds",
        "description": "If available to retail investors, fund must produce a Key Information Document under PRIIPs regulation.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R1286",
        "action": "Prepare and maintain PRIIPs KID if fund is marketed to retail investors.",
    },
    # -- Consumer Protection --
    {
        "id": "fund-con-001",
        "category": "Consumer Protection",
        "requirement": "Professional investor classification",
        "description": "Crypto funds must verify investor qualification (professional/semi-professional/retail) and restrict access accordingly.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Implement investor classification process and restrict access based on fund structure.",
    },
    {
        "id": "fund-con-002",
        "category": "Consumer Protection",
        "requirement": "Fee and cost transparency",
        "description": "All fees, costs, and charges must be clearly disclosed including management, performance, and transaction fees.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0061",
        "action": "Provide clear fee schedule in offering documents with total expense ratio calculation.",
    },
    {
        "id": "fund-con-003",
        "category": "Consumer Protection",
        "requirement": "SFDR sustainability disclosures",
        "description": "Fund managers must classify funds under SFDR (Art. 6/8/9) and provide sustainability-related disclosures.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019R2088",
        "action": "Classify fund under SFDR and prepare required sustainability disclosures for prospectus and website.",
    },
]

_CUSTODY_ITEMS: list[dict] = [
    # -- Licensing --
    {
        "id": "cust-lic-001",
        "category": "Licensing",
        "requirement": "Crypto custody license under KWG (Germany)",
        "description": "Kryptoverwahrgeschaeft requires a dedicated BaFin license under KWG Section 1 Abs. 1a Satz 2 Nr. 6.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE"],
        "severity": "critical",
        "reference_url": "https://www.bafin.de/EN/Aufsicht/FinTech/Kryptoverwahrgeschaeft/kryptoverwahrgeschaeft_node_en.html",
        "action": "Apply for Kryptoverwahrgeschaeft license with BaFin.",
    },
    {
        "id": "cust-lic-002",
        "category": "Licensing",
        "requirement": "MiCA CASP authorization for custody (Art. 75)",
        "description": "Custody and administration of crypto-assets is a regulated CASP service requiring MiCA authorization.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Obtain MiCA CASP authorization for custody services with BaFin or home NCA.",
    },
    {
        "id": "cust-lic-003",
        "category": "Licensing",
        "requirement": "FINMA authorization for custody services (CH)",
        "description": "Swiss custody providers need FINMA authorization; DLT trading facility license may apply for institutional custody.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["CH"],
        "severity": "critical",
        "reference_url": "https://www.finma.ch/en/authorisation/fintech/",
        "action": "Apply for appropriate FINMA license for crypto custody operations.",
    },
    {
        "id": "cust-lic-004",
        "category": "Licensing",
        "requirement": "DLT Pilot Regime participation (optional)",
        "description": "EU DLT Pilot Regime allows sandbox testing of DLT-based settlement and custody infrastructure.",
        "status": "not_applicable",
        "deadline": None,
        "jurisdictions": ["EU"],
        "severity": "low",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R0858",
        "action": "Evaluate if DLT Pilot Regime sandbox would benefit custody infrastructure development.",
    },
    # -- AML/KYC --
    {
        "id": "cust-aml-001",
        "category": "AML/KYC",
        "requirement": "Full KYC for all custody clients",
        "description": "Custody providers must perform comprehensive KYC/CDD for all clients including institutional clients.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Implement institutional KYC covering UBO, source of funds, and ongoing monitoring.",
    },
    {
        "id": "cust-aml-002",
        "category": "AML/KYC",
        "requirement": "Travel Rule for custody transfers",
        "description": "Custody providers facilitating transfers must comply with Travel Rule for originator/beneficiary information.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1113",
        "action": "Integrate Travel Rule compliance for all outbound crypto transfers from custody.",
    },
    {
        "id": "cust-aml-003",
        "category": "AML/KYC",
        "requirement": "Wallet screening and chain analysis",
        "description": "Custody providers should implement blockchain analytics to screen incoming/outgoing transactions for illicit activity.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0849",
        "action": "Deploy blockchain analytics tool (Chainalysis, Elliptic, etc.) for transaction screening.",
    },
    # -- Capital Requirements --
    {
        "id": "cust-cap-001",
        "category": "Capital Requirements",
        "requirement": "Minimum own funds EUR 150,000 (MiCA Art. 67)",
        "description": "CASP custody providers must maintain own funds of at least EUR 150,000.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Maintain minimum EUR 150,000 in permanent own funds.",
    },
    {
        "id": "cust-cap-002",
        "category": "Capital Requirements",
        "requirement": "Insurance or guarantee for client assets",
        "description": "Custody providers should maintain insurance or equivalent guarantee covering loss of client crypto-assets.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Obtain custody insurance covering theft, hack, and operational loss of client assets.",
    },
    # -- Governance --
    {
        "id": "cust-gov-001",
        "category": "Governance",
        "requirement": "Custody agreement requirements (MiCA Art. 75)",
        "description": "Written custody agreements must specify terms, rights, obligations, and liability arrangements.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Draft MiCA-compliant custody agreements covering all required terms and conditions.",
    },
    {
        "id": "cust-gov-002",
        "category": "Governance",
        "requirement": "Segregation of client assets (MiCA Art. 70/75)",
        "description": "Client crypto-assets must be held separately from custodian's own assets and clearly identifiable.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement technical and legal asset segregation with regular proof-of-reserves.",
    },
    {
        "id": "cust-gov-003",
        "category": "Governance",
        "requirement": "Key management and security policy",
        "description": "Custody providers must maintain robust private key management policies including HSM usage and multi-sig.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Document key management policy covering HSM, multi-sig, key ceremony, and disaster recovery.",
    },
    {
        "id": "cust-gov-004",
        "category": "Governance",
        "requirement": "DORA ICT risk management and resilience",
        "description": "Custody providers as financial entities must comply with DORA for digital operational resilience.",
        "status": "required",
        "deadline": "2025-01-17",
        "jurisdictions": ["DE", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2554",
        "action": "Implement DORA-compliant ICT risk management, incident reporting, and resilience testing.",
    },
    {
        "id": "cust-gov-005",
        "category": "Governance",
        "requirement": "Sub-custodian due diligence",
        "description": "If delegating custody to sub-custodians, the primary custodian must perform due diligence and maintain oversight.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish sub-custodian selection criteria, due diligence process, and ongoing monitoring.",
    },
    # -- Reporting --
    {
        "id": "cust-rep-001",
        "category": "Reporting",
        "requirement": "Client asset reporting and statements",
        "description": "Custody providers must provide regular statements to clients detailing all assets held.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Implement automated client reporting with real-time portfolio visibility and periodic statements.",
    },
    {
        "id": "cust-rep-002",
        "category": "Reporting",
        "requirement": "Proof of reserves / audit",
        "description": "Custody providers should perform regular proof-of-reserves attestations to verify client asset holdings.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "high",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Engage independent auditor for periodic proof-of-reserves using on-chain verification.",
    },
    {
        "id": "cust-rep-003",
        "category": "Reporting",
        "requirement": "Incident reporting to NCA",
        "description": "Security incidents involving client assets must be reported to competent authority without undue delay.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Establish incident response and NCA reporting procedures for security breaches.",
    },
    # -- Consumer Protection --
    {
        "id": "cust-con-001",
        "category": "Consumer Protection",
        "requirement": "Liability for loss of client crypto-assets (MiCA Art. 75)",
        "description": "Custodians are liable for loss of crypto-assets unless they can prove the loss was caused by external events beyond control.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Review liability framework and ensure insurance coverage aligns with MiCA liability regime.",
    },
    {
        "id": "cust-con-002",
        "category": "Consumer Protection",
        "requirement": "Insolvency protection for client assets",
        "description": "Client crypto-assets must be protected in the event of custodian insolvency and not form part of the estate.",
        "status": "required",
        "deadline": "2026-07-01",
        "jurisdictions": ["DE", "EU"],
        "severity": "critical",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Ensure legal structure provides insolvency remoteness for client crypto-assets.",
    },
    {
        "id": "cust-con-003",
        "category": "Consumer Protection",
        "requirement": "Transparent fee structure",
        "description": "All custody fees must be clearly disclosed upfront including storage, transaction, and withdrawal fees.",
        "status": "required",
        "deadline": None,
        "jurisdictions": ["DE", "CH", "EU"],
        "severity": "medium",
        "reference_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1114",
        "action": "Publish clear fee schedule covering all custody-related charges.",
    },
]

_TYPE_MAP = {
    "casp": _CASP_ITEMS,
    "issuer": _ISSUER_ITEMS,
    "fund": _FUND_ITEMS,
    "custody": _CUSTODY_ITEMS,
}

_FRAMEWORK_MAP = {
    "casp": "MiCA + KWG + GwG + FINIG",
    "issuer": "MiCA + WpPG + BankA + FINIG",
    "fund": "MiCA + AIFMD + KWG + CISA + FINIG",
    "custody": "MiCA + KWG + DORA + FINIG",
}

_COST_MAP = {
    "casp": {
        "licensing": "EUR 50,000 - 200,000",
        "legal_counsel": "EUR 15,000 - 50,000",
        "ongoing_compliance": "EUR 50,000 - 150,000/year",
        "capital_requirements": "EUR 125,000 - 150,000",
    },
    "issuer": {
        "licensing": "EUR 30,000 - 150,000",
        "legal_counsel": "EUR 20,000 - 80,000",
        "ongoing_compliance": "EUR 40,000 - 120,000/year",
        "capital_requirements": "EUR 350,000+ (ART) or varies",
    },
    "fund": {
        "licensing": "EUR 80,000 - 300,000",
        "legal_counsel": "EUR 30,000 - 100,000",
        "ongoing_compliance": "EUR 100,000 - 250,000/year",
        "capital_requirements": "EUR 125,000 - 10,000,000",
    },
    "custody": {
        "licensing": "EUR 50,000 - 250,000",
        "legal_counsel": "EUR 20,000 - 60,000",
        "ongoing_compliance": "EUR 60,000 - 200,000/year",
        "capital_requirements": "EUR 150,000+",
    },
}

_RECENT_CHANGES = [
    {
        "date": "2026-01-01",
        "title": "MiCA full enforcement begins for CASPs",
        "impact": "All crypto-asset service providers must be licensed or in transition period. Unlicensed operators must cease services.",
        "severity": "critical",
    },
    {
        "date": "2025-06-30",
        "title": "MiCA Title III/IV in force for ARTs and EMTs",
        "impact": "ART and EMT issuers must be fully authorized. Stablecoins without authorization must be delisted.",
        "severity": "critical",
    },
    {
        "date": "2025-01-17",
        "title": "DORA entered into force",
        "impact": "All financial entities must comply with digital operational resilience requirements including ICT risk management.",
        "severity": "high",
    },
    {
        "date": "2026-07-01",
        "title": "MiCA transition period ends",
        "impact": "No more grandfathering of existing national licenses. Full MiCA compliance required.",
        "severity": "critical",
    },
    {
        "date": "2026-04-16",
        "title": "AIFMD II transposition deadline",
        "impact": "Fund managers must comply with updated AIFMD II rules on delegation, liquidity management, and loan origination.",
        "severity": "high",
    },
    {
        "date": "2026-01-01",
        "title": "DAC8 crypto tax reporting begins",
        "impact": "CASPs must begin collecting and reporting transaction data to tax authorities under DAC8.",
        "severity": "high",
    },
    {
        "date": "2025-12-30",
        "title": "EU AML Package negotiations progressing",
        "impact": "New EU AML Authority (AMLA) will have direct supervisory powers over high-risk CASPs.",
        "severity": "medium",
    },
]


def _group_by_category(items: list[dict]) -> list[dict]:
    """Group flat checklist items into categorized sections."""
    categories: dict[str, list[dict]] = {}
    for item in items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        entry = {k: v for k, v in item.items() if k != "category"}
        categories[cat].append(entry)
    return [{"name": name, "items": cat_items} for name, cat_items in categories.items()]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/check")
async def compliance_check(
    business_type: str = Query(
        default="casp",
        pattern="^(casp|issuer|fund|custody)$",
        description="Business type to check compliance for",
    ),
):
    """Return a comprehensive MiCA compliance checklist for the given business type."""
    items = _TYPE_MAP.get(business_type, _CASP_ITEMS)
    return {
        "business_type": business_type,
        "jurisdiction": "dach",
        "framework": _FRAMEWORK_MAP.get(business_type, "MiCA"),
        "last_updated": _today(),
        "overall_status": "action_required",
        "categories": _group_by_category(items),
        "recent_changes": _RECENT_CHANGES,
        "costs_estimate": _COST_MAP.get(business_type, _COST_MAP["casp"]),
    }


@router.get("/timeline")
async def compliance_timeline():
    """Return a timeline of upcoming regulatory deadlines for DACH crypto businesses."""
    # Collect all deadlines from all business types
    deadlines: list[dict] = []
    seen_ids: set[str] = set()

    for btype, items in _TYPE_MAP.items():
        for item in items:
            if item["deadline"] and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                deadlines.append({
                    "date": item["deadline"],
                    "business_type": btype,
                    "requirement_id": item["id"],
                    "requirement": item["requirement"],
                    "description": item["description"],
                    "severity": item["severity"],
                    "jurisdictions": item["jurisdictions"],
                    "action": item["action"],
                })

    # Add major regulatory milestones
    for change in _RECENT_CHANGES:
        deadlines.append({
            "date": change["date"],
            "business_type": "all",
            "requirement_id": None,
            "requirement": change["title"],
            "description": change["impact"],
            "severity": change["severity"],
            "jurisdictions": ["DE", "CH", "EU"],
            "action": None,
        })

    # Sort by date
    deadlines.sort(key=lambda d: d["date"])

    return {
        "jurisdiction": "dach",
        "last_updated": _today(),
        "total_deadlines": len(deadlines),
        "deadlines": deadlines,
    }


@router.get("/compare")
async def compliance_compare(
    jurisdictions: str = Query(
        default="DE,CH",
        description="Comma-separated jurisdiction codes to compare (DE, CH, AT, EU)",
    ),
):
    """Side-by-side comparison of regulatory requirements across DACH jurisdictions."""
    jlist = [j.strip().upper() for j in jurisdictions.split(",") if j.strip()]

    comparison: dict[str, dict] = {
        "DE": {
            "name": "Germany",
            "regulator": "BaFin (Federal Financial Supervisory Authority)",
            "primary_framework": "MiCA + KWG (Kreditwesengesetz) + WpIG + GwG",
            "casp_license": "CASP license via BaFin (MiCA) or existing KWG crypto custody license with transition",
            "stablecoin_rules": "EMT/ART rules under MiCA; e-money institution or credit institution license required",
            "aml_framework": "GwG (Geldwaeschegesetz) implementing EU AMLD; FIU is the BKA/FIU",
            "tax_treatment": "Crypto gains tax-free after 1-year holding period; otherwise income tax up to 45%",
            "custody_regulation": "Kryptoverwahrgeschaeft license required under KWG since 2020; transitioning to MiCA",
            "fund_regulation": "KAGB/AIFMD for crypto funds; Spezialfonds may allocate up to 20% to crypto since 2021",
            "dlt_sandbox": "EU DLT Pilot Regime applicable; BaFin active participant",
            "key_deadlines": ["2026-07-01: MiCA transition ends", "2026-01-01: DAC8 reporting starts"],
            "unique_aspects": "Early mover in crypto regulation (2020 KWG amendment); largest EU market; strict BaFin oversight",
        },
        "CH": {
            "name": "Switzerland",
            "regulator": "FINMA (Financial Market Supervisory Authority)",
            "primary_framework": "FINIG + BankA + AMLA (GwG) + DLT Act",
            "casp_license": "FinTech license, banking license, or securities dealer license depending on activity",
            "stablecoin_rules": "Classified under FINMA token taxonomy; banking license may be required for deposit-like stablecoins",
            "aml_framework": "AMLA (GwG) via SRO membership (VQF, PolyReg); FIU is MROS",
            "tax_treatment": "No capital gains tax for private investors; wealth tax applies to crypto holdings",
            "custody_regulation": "Covered under Banking Act; DLT Act provides segregation rights in bankruptcy since 2021",
            "fund_regulation": "CISA (Collective Investment Schemes Act); limited partnerships for qualified investors",
            "dlt_sandbox": "DLT Act (2021) enables DLT trading facilities; FINMA sandbox for up to CHF 1M deposits",
            "key_deadlines": ["Ongoing: FINMA licensing applies", "No MiCA transition (non-EU)"],
            "unique_aspects": "Crypto Valley (Zug); DLT Act provides legal certainty; not subject to MiCA but bilateral equivalence discussions",
        },
        "AT": {
            "name": "Austria",
            "regulator": "FMA (Financial Market Authority)",
            "primary_framework": "MiCA + BWG (Bankwesengesetz) + FM-GwG",
            "casp_license": "CASP license via FMA under MiCA; existing national licenses transitioning",
            "stablecoin_rules": "MiCA EMT/ART rules apply; e-money institution license required for EMTs",
            "aml_framework": "FM-GwG implementing EU AMLD; FIU is the Austrian FMA/A-FIU",
            "tax_treatment": "Flat 27.5% tax on crypto gains (KESt) since March 2022; no holding period exemption",
            "custody_regulation": "Covered under MiCA CASP framework; transitioning from national regime",
            "fund_regulation": "AIFMG/AIFMD for alternative funds; InvFG for UCITS-like structures",
            "dlt_sandbox": "EU DLT Pilot Regime applicable via FMA",
            "key_deadlines": ["2026-07-01: MiCA transition ends", "2026-01-01: DAC8 reporting"],
            "unique_aspects": "Clear crypto tax regime since 2022; growing fintech hub in Vienna; close regulatory alignment with DE",
        },
        "EU": {
            "name": "European Union (Framework)",
            "regulator": "ESMA, EBA, ECB (supervisory convergence)",
            "primary_framework": "MiCA + TFR + DORA + AMLD + DAC8",
            "casp_license": "Harmonized CASP license with EU passporting rights",
            "stablecoin_rules": "ART: NCA authorization + EBA for significant; EMT: e-money institution + EBA for significant",
            "aml_framework": "AMLD6 + upcoming AML Package with AMLA (EU-level AML supervisor based in Frankfurt)",
            "tax_treatment": "DAC8 harmonizes tax reporting; actual tax rates set by member states",
            "custody_regulation": "Harmonized under MiCA Art. 75; depositary requirements for funds under AIFMD",
            "fund_regulation": "AIFMD II (transposition April 2026); ELTIF 2.0 for long-term investments",
            "dlt_sandbox": "DLT Pilot Regime (Regulation 2022/858) operational since March 2023",
            "key_deadlines": ["2026-07-01: Full MiCA enforcement", "2026-04-16: AIFMD II transposition"],
            "unique_aspects": "First comprehensive crypto regulation globally; single market passport; AMLA to be based in Frankfurt",
        },
    }

    result_jurisdictions = []
    for j in jlist:
        if j in comparison:
            result_jurisdictions.append({"code": j, **comparison[j]})

    return {
        "last_updated": _today(),
        "jurisdictions_compared": jlist,
        "comparison": result_jurisdictions,
    }


# ---------------------------------------------------------------------------
# MiCA/DORA Compliance Documentation Generator
# ---------------------------------------------------------------------------

_DOC_TYPE_MAP = {
    "fitness_propriety": "generate_fitness_propriety",
    "bcp": "generate_business_continuity_plan",
    "complaint_handling": "generate_complaint_handling",
    "ict_risk": "generate_ict_risk_framework",
    "aml_kyc": "generate_aml_kyc_policy",
    "conflicts": "generate_conflicts_of_interest",
    "investor_info": "generate_investor_information",
}


@router.get("/mica/package")
async def get_full_compliance_package():
    """Generate full MiCA/DORA compliance documentation package."""
    from app.compliance.mica_docs import generate_full_compliance_package
    return generate_full_compliance_package()


@router.get("/mica/{document_type}")
async def get_compliance_document(document_type: str):
    """Get a specific compliance document.

    document_type: fitness_propriety, bcp, complaint_handling, ict_risk,
                   aml_kyc, conflicts, investor_info
    """
    func_name = _DOC_TYPE_MAP.get(document_type)
    if not func_name:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Unknown document type '{document_type}'. "
                   f"Available: {', '.join(sorted(_DOC_TYPE_MAP.keys()))}",
        )
    import app.compliance.mica_docs as mica_docs
    generator = getattr(mica_docs, func_name)
    return generator()


@router.get("/score")
async def get_compliance_score():
    """Get overall compliance readiness score."""
    from app.compliance.mica_docs import _calculate_compliance_score
    return _calculate_compliance_score()
