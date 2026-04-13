"""Tests for MiCA/DORA compliance documentation generator — NO MOCKS."""

import pytest
from fastapi.testclient import TestClient

from app.compliance.mica_docs import (
    generate_fitness_propriety,
    generate_business_continuity_plan,
    generate_complaint_handling,
    generate_ict_risk_framework,
    generate_aml_kyc_policy,
    generate_conflicts_of_interest,
    generate_investor_information,
    generate_full_compliance_package,
    _calculate_compliance_score,
)
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests — document generators
# ---------------------------------------------------------------------------


class TestFitnessPropriety:
    def test_fitness_propriety_structure(self):
        """Has required sections per MiCA Art. 60."""
        doc = generate_fitness_propriety()
        assert doc["document_type"] == "fitness_propriety"
        assert doc["mica_article"] == "Art. 60"
        assert "generated_at" in doc
        sections = doc["sections"]
        assert "management_structure" in sections
        assert "professional_qualifications" in sections
        assert "good_repute" in sections
        assert "ongoing_training" in sections
        for section in sections.values():
            assert "title" in section
            assert "requirements" in section or "content" in section


class TestBusinessContinuityPlan:
    def test_bcp_has_risks(self):
        """BCP identifies operational risks."""
        doc = generate_business_continuity_plan()
        assert doc["document_type"] == "business_continuity_plan"
        assert doc["mica_article"] == "Art. 67"
        risks = doc["sections"]["risk_identification"]["identified_risks"]
        assert len(risks) >= 3
        risk_names = [r["risk"] for r in risks]
        assert "Database failure" in risk_names
        assert "DDoS attack" in risk_names

    def test_bcp_rto_values(self):
        """All identified risks have a Recovery Time Objective."""
        doc = generate_business_continuity_plan()
        risks = doc["sections"]["risk_identification"]["identified_risks"]
        for risk in risks:
            assert "rto_hours" in risk, f"Risk '{risk['risk']}' missing rto_hours"
            assert isinstance(risk["rto_hours"], (int, float))
            assert risk["rto_hours"] > 0


class TestICTRiskFramework:
    def test_ict_framework_third_party(self):
        """Lists all third-party ICT service providers."""
        doc = generate_ict_risk_framework()
        assert doc["regulation"] == "DORA"
        providers = doc["sections"]["third_party_risk"]["providers"]
        assert len(providers) >= 5
        provider_names = [p["name"] for p in providers]
        assert "Binance" in provider_names
        assert "Railway" in provider_names
        for p in providers:
            assert "service" in p
            assert "risk_level" in p
            assert "fallback" in p

    def test_ict_incident_levels(self):
        """Has 4 severity levels for incident classification."""
        doc = generate_ict_risk_framework()
        levels = doc["sections"]["incident_classification"]["levels"]
        assert len(levels) == 4
        level_names = [lv["level"] for lv in levels]
        assert "critical" in level_names
        assert "high" in level_names
        assert "medium" in level_names
        assert "low" in level_names
        for lv in levels:
            assert "response_time" in lv
            assert "report_to" in lv


class TestInvestorInformation:
    def test_investor_info_fees(self):
        """Fee structure is present and correct."""
        doc = generate_investor_information()
        fees = doc["sections"]["fee_structure"]
        assert fees["management_fee"] == "2% annual"
        assert fees["performance_fee"] == "20% above high water mark"
        assert fees["entry_fee"] == "None"

    def test_investor_info_risks(self):
        """Risk warnings are present and substantive."""
        doc = generate_investor_information()
        risks = doc["sections"]["risk_warnings"]["risks"]
        assert len(risks) >= 5
        risk_text = " ".join(risks).lower()
        assert "volatile" in risk_text or "loss" in risk_text
        assert "ai" in risk_text or "signal" in risk_text


class TestComplianceScore:
    def test_compliance_score(self):
        """Score is between 0 and 100."""
        score = _calculate_compliance_score()
        assert "score_pct" in score
        assert 0.0 <= score["score_pct"] <= 100.0
        assert "checks" in score
        assert isinstance(score["checks"], dict)
        assert score["passed"] <= score["total"]


class TestFullPackage:
    def test_full_package_has_all_docs(self):
        """Package contains all 7 compliance documents."""
        package = generate_full_compliance_package()
        assert package["package_name"] == "SignalDACH MiCA/DORA Compliance Package"
        assert "generated_at" in package
        docs = package["documents"]
        assert len(docs) == 7
        doc_types = {d["document_type"] for d in docs}
        expected = {
            "fitness_propriety",
            "business_continuity_plan",
            "complaint_handling",
            "ict_risk_framework",
            "aml_kyc_policy",
            "conflicts_of_interest",
            "investor_information",
        }
        assert doc_types == expected
        assert "compliance_score" in package


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestComplianceAPI:
    def test_api_compliance_package(self):
        """GET /compliance/mica/package returns 200 with full package."""
        resp = client.get("/compliance/mica/package")
        assert resp.status_code == 200
        data = resp.json()
        assert "documents" in data
        assert len(data["documents"]) == 7

    def test_api_single_document(self):
        """GET /compliance/mica/fitness_propriety returns 200."""
        resp = client.get("/compliance/mica/fitness_propriety")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "fitness_propriety"
        assert data["mica_article"] == "Art. 60"

    def test_api_compliance_score(self):
        """GET /compliance/score returns 200 with score data."""
        resp = client.get("/compliance/score")
        assert resp.status_code == 200
        data = resp.json()
        assert "score_pct" in data
        assert "checks" in data

    def test_api_unknown_document_type(self):
        """GET /compliance/mica/nonexistent returns 404."""
        resp = client.get("/compliance/mica/nonexistent")
        assert resp.status_code == 404

    def test_api_all_document_types(self):
        """All 7 document types are accessible via the API."""
        doc_types = [
            "fitness_propriety", "bcp", "complaint_handling",
            "ict_risk", "aml_kyc", "conflicts", "investor_info",
        ]
        for dt in doc_types:
            resp = client.get(f"/compliance/mica/{dt}")
            assert resp.status_code == 200, f"Failed for document type: {dt}"
            data = resp.json()
            assert "document_type" in data
