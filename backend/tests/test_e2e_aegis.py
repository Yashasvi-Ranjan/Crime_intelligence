"""
End-to-End Verification Test Suite for AEGIS Cross-Station Crime Intelligence
=============================================================================
Validates:
1. Triple Meta-Governance Sentinels (Milestone 2)
2. Offline sample mode and trace retrieval API (Milestone 3/4)
3. Anti-disqualification and zero-hallucination compliance
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.meta_sentinels import (
    operational_tracker,
    hackos_auditor,
    disqualification_sentinel,
)

client = TestClient(app)


# ── 2. Triple Meta-Governance Sentinels ───────────────────────────────────────

def test_meta_sentinels_initialization_and_audit():
    """Verify Tracker, Auditor, and Disqualification sentinels execute and audit state."""
    # 1. Operational Tracker
    tracker_rep = operational_tracker.evaluate(
        run_id="inv_test_e2e_001",
        elapsed_seconds=12.4,
        iterations=2,
        model_calls=[{"completion_tokens": 100, "prompt_tokens": 200, "latency_ms": 300}],
        sql_queries=4,
        engine_ops=[{"engine": "world_model", "op": "stats"}],
    )
    assert tracker_rep.passed is True
    assert tracker_rep.score >= 90.0

    # 2. HackOS Compliance Auditor
    valid_integration = {
        "zetaris": {
            "status": "connected",
            "tables_queried": ["police_incidents", "forensic_reports", "cctv_reports"],
        },
        "meterless_engines": {
            "world_model": {"status": "connected"},
        },
        "nightshift_nemotron": {
            "status": "connected",
            "models_used": ["nvidia/nemotron-3-ultra-550b-a55b"],
        },
    }
    audit_rep = hackos_auditor.evaluate(
        integration_status=valid_integration,
        model_calls=[{"reported_model": "nvidia/nemotron-3-ultra-550b-a55b"}],
        candidate_links=[{"stations_involved": ["NORTH", "CENTRAL"]}],
        stations_involved=["NORTH", "CENTRAL"],
    )
    assert audit_rep.passed is True
    assert audit_rep.details["zetaris_load_bearing"] is True

    # 3. Disqualification Sentinel
    clean_payload = "Cross-station pattern verified against Zetaris federated indices."
    disqual_rep = disqualification_sentinel.evaluate(
        full_payload_dump=clean_payload,
        candidate_links=[
            {"source_incident_id": "INC-NORTH-0042", "target_incident_id": "INC-CEN-0118"}
        ],
        known_incident_ids={"INC-NORTH-0042", "INC-CEN-0118"},
        known_evidence_ids=set(),
    )
    assert disqual_rep.passed is True
    assert disqual_rep.score == 100.0


def test_anti_disqualification_catches_secret_leakage():
    """Sentinel must strictly fail if simulated secret tokens are present."""
    leaked_payload = "Session initialized with token " + "nvapi" + "-secretkey1234567890abcdef123"
    report = disqualification_sentinel.evaluate(
        full_payload_dump=leaked_payload,
        candidate_links=[],
        known_incident_ids=set(),
        known_evidence_ids=set(),
    )
    assert report.passed is False
    assert report.status == "DISQUALIFICATION_RISK"
    assert any("secret" in v.lower() or "api key" in v.lower() for v in report.violations)


# ── 3. End-to-End API Workflows ──────────────────────────────────────────────

def test_api_sample_scenarios_listing():
    """Verify offline sample scenarios are available for zero-credential exploration."""
    response = client.get("/api/investigations/samples")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 3
    scenario_ids = [s["scenario_id"] for s in scenarios]
    assert "crowbar_safe_cracking" in scenario_ids
    assert "catalytic_converter" in scenario_ids
    assert "keyless_suv_relay" in scenario_ids


def test_api_sample_investigation_run():
    """Verify executing investigation with sample_mode=true succeeds and returns sentinels."""
    payload = {
        "query": "Investigate safe cracking burglaries across North and Central",
        "demo_content": True,
        "scenario_id": "crowbar_safe_cracking",
    }
    response = client.post("/api/investigations/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["is_sample"] is True
    assert data["data_mode"] == "demo_content"
    assert len(data["candidate_incidents"]) >= 2
    assert len(data["candidate_links"]) >= 1
    assert "sentinels" in data
    assert data["sentinels"]["hackos_auditor"]["status"] in ("VERIFIED", "COMPLIANT", "PASS")
    assert data["sentinels"]["disqualification_sentinel"]["status"] in ("VERIFIED", "CLEAN", "PASS")


def test_api_investigation_trace_retrieval():
    """Verify retrieving investigation trace returns model receipts and execution steps."""
    response = client.get("/api/investigations/sample-crowbar_safe_cracking/trace")
    assert response.status_code == 200
    trace = response.json()

    assert trace["run_id"] == "sample-crowbar_safe_cracking"
    assert len(trace["events"]) > 0
    assert trace["total_events"] > 0
    for ev in trace["events"]:
        assert "phase" in ev
        assert "model" in ev
        assert "receipt_id" in ev
