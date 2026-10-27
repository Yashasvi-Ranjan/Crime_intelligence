"""
Backend test suite for Cross-Station Crime Intelligence API.
Covers all endpoints, query parameters, error cases, and isolation checks.
"""

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.config import settings

client = TestClient(app)


# ── Health Endpoints ──────────────────────────────────────────────────────────


def test_app_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


def test_zetaris_health_unconfigured(monkeypatch):
    """When ZETARIS_ENABLED is forced off, the health endpoint must report not_configured."""
    monkeypatch.setattr(settings, "zetaris_enabled", False)
    response = client.get("/api/health/zetaris")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["mode"] == "local_fallback"
    assert data["configured"] is False
    assert "NOT CONFIGURED" in data["message"]


def test_zetaris_health_configured_flag(monkeypatch):
    """When ZETARIS_ENABLED is true the health endpoint must report configured=True."""
    # Patch the computed property directly since zetaris_configured requires credentials+enabled
    monkeypatch.setattr(
        type(settings), "zetaris_configured", property(lambda self: True)
    )
    # We only check that the key is present and True; a live connection is not required
    response = client.get("/api/health/zetaris")
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True


# ── Dashboard Summary ─────────────────────────────────────────────────────────


def test_dashboard_summary():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["total_incidents"] == 3000
    assert len(data["by_station"]) == 3
    station_names = {s["station_id"] for s in data["by_station"]}
    assert station_names == {"NORTH", "CENTRAL", "RIVERSIDE"}

    # Crime types: local loader returns exactly 10; Zetaris may return up to 20
    assert len(data["by_crime_type"]) >= 10
    assert len(data["by_status"]) == 4

    sources = {s["source"]: s["count"] for s in data["by_source"]}
    assert sources["police_incidents"] == 3000
    assert sources["newspaper_reports"] == 1500
    assert sources["witness_reports"] == 2000
    assert sources["cctv_reports"] == 2000
    assert sources["forensic_reports"] == 1500

    assert len(data["incident_timeline"]) > 0
    # Accept either live Zetaris or local fallback
    assert data["data_mode"] in {"zetaris_live", "local_fallback"}


# ── Incidents Endpoints ───────────────────────────────────────────────────────


def test_list_incidents_default():
    response = client.get("/api/incidents")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 3000
    assert len(data["items"]) == 50
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["total_pages"] == 60


def test_list_incidents_filtered_by_station():
    response = client.get("/api/incidents?station=NORTH&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] == 971
    assert len(data["items"]) == 20
    assert all(item["station_id"] == "NORTH" for item in data["items"])


def test_list_incidents_filtered_by_crime_type():
    response = client.get("/api/incidents?crime_type=BURGLARY&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert all(item["crime_type"] == "BURGLARY" for item in data["items"])


def test_list_incidents_search():
    response = client.get("/api/incidents?search=theft&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["total"] > 0
    assert len(data["items"]) <= 10


def test_get_incident_by_id_success():
    # Fetch first incident to get a real ID
    list_resp = client.get("/api/incidents?page_size=1")
    assert list_resp.status_code == 200
    real_id = list_resp.json()["items"][0]["incident_id"]

    response = client.get(f"/api/incidents/{real_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == real_id
    assert "station_id" in data
    assert "crime_type" in data
    assert "method_description" in data


def test_get_incident_by_id_not_found():
    response = client.get("/api/incidents/INC-NONEXISTENT-999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── Sources Endpoints ─────────────────────────────────────────────────────────


def test_list_sources():
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    source_names = {s["name"] for s in data["sources"]}
    assert source_names == {
        "police_incidents",
        "newspaper_reports",
        "witness_reports",
        "cctv_reports",
        "forensic_reports",
    }


def test_list_source_records():
    for src in ["police_incidents", "newspaper_reports", "witness_reports", "cctv_reports", "forensic_reports"]:
        response = client.get(f"/api/sources/{src}/records?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == src
        assert len(data["items"]) == 5
        assert data["pagination"]["total"] > 0


def test_list_source_records_invalid_source():
    response = client.get("/api/sources/unknown_source/records")
    assert response.status_code == 404


def test_get_source_record_by_id():
    # Fetch first record to get a valid ID
    list_resp = client.get("/api/sources/cctv_reports/records?page_size=1")
    assert list_resp.status_code == 200
    real_id = list_resp.json()["items"][0]["cctv_report_id"]

    response = client.get(f"/api/sources/cctv_reports/records/{real_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "cctv_reports"
    assert data["record"]["cctv_report_id"] == real_id


def test_get_source_record_by_id_not_found():
    response = client.get("/api/sources/cctv_reports/records/CCTV-999999")
    assert response.status_code == 404


# ── Evidence Linkage ──────────────────────────────────────────────────────────


def test_incident_evidence():
    # Get a real incident ID
    list_resp = client.get("/api/incidents?page_size=1")
    assert list_resp.status_code == 200
    real_id = list_resp.json()["items"][0]["incident_id"]

    response = client.get(f"/api/incidents/{real_id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["incident"]["incident_id"] == real_id
    assert "direct_links" in data
    assert "inferred_links" in data
    assert "data_mode" in data
    for item in data["direct_links"]:
        assert item["link_type"] == "direct_reference"
    for item in data["inferred_links"]:
        assert "inferred" in item["link_type"]


# ── Ground Truth Isolation Check ──────────────────────────────────────────────


def test_ground_truth_never_leaked():
    import sys
    for mod_name in sys.modules:
        assert "ground_truth" not in mod_name, f"ground_truth was imported as module: {mod_name}"


# ── Milestone 2: Sample Mode Sentinels & Investigation Trace ─────────────────


def test_sample_scenarios_list():
    response = client.get("/api/investigations/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) == 3
    scenario_ids = {s["scenario_id"] for s in samples}
    assert scenario_ids == {"crowbar_safe_cracking", "catalytic_converter", "keyless_suv_relay"}
    for s in samples:
        assert "title" in s
        assert "query" in s
        assert len(s["target_stations"]) >= 2


def test_investigations_analyze_sample_mode_crowbar():
    payload = {
        "query": "Investigate safe burglaries involving crowbars",
        "demo_content": True,
        "scenario_id": "crowbar_safe_cracking",
    }
    response = client.post("/api/investigations/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Core sample mode flags
    assert data["is_sample"] is True
    assert data["data_mode"] == "demo_content"
    assert data["scenario_id"] == "crowbar_safe_cracking"

    # Sentinels verification (Milestone 2 requirement)
    assert data["sentinels"] is not None
    sentinels = data["sentinels"]

    # Operational Tracker
    tracker = sentinels["operational_tracker"]
    assert tracker["status"] == "PASS"
    assert tracker["passed"] is True
    assert tracker["latency_ms"] > 0
    assert "token_usage" in tracker
    assert tracker["token_usage"]["total_tokens"] > 0
    assert len(tracker["query_milestones"]) >= 3

    # HackOS Compliance Auditor
    compliance = sentinels["hackos_auditor"]
    assert compliance["status"] == "COMPLIANT"
    assert compliance["passed"] is True
    assert compliance["zetaris_verified"] is True
    assert compliance["meterless_engines_verified"] is True
    assert compliance["nightshift_verified"] is True
    assert compliance["multi_station_coverage"] is True

    # Disqualification Sentinel
    anti_disqual = sentinels["disqualification_sentinel"]
    assert anti_disqual["status"] == "CLEAN"
    assert anti_disqual["passed"] is True
    assert anti_disqual["zero_secrets_leakage"] is True
    assert anti_disqual["ungrounded_ids_detected"] == 0
    assert anti_disqual["synthetic_data_valid"] is True

    # Frontend UI compatibility aliases
    assert sentinels["tracker"]["status"] == "VERIFIED"
    assert sentinels["tracker"]["score"] == 100.0
    assert sentinels["compliance"]["status"] == "VERIFIED"
    assert sentinels["compliance"]["score"] == 100.0
    assert sentinels["anti_disqualification"]["status"] == "VERIFIED"
    assert sentinels["anti_disqualification"]["score"] == 100.0

    # Report verification (Milestone 2 requirement)
    assert data["report"] is not None
    report = data["report"]
    assert isinstance(report["synthesis"], str)
    assert len(report["synthesis"]) > 0
    assert isinstance(report["facts"], list)
    assert len(report["facts"]) >= 3
    assert report["unsupported_claims"] == []
    assert report["confidence"] > 0.8
    assert report["dossier_ready"] is True

    # Check that facts contain cited evidence IDs matching the sample scenario
    all_cited_sources = [src for f in report["facts"] for src in f.get("source_ids", [])]
    assert "FOR-0089" in all_cited_sources
    assert "FOR-0142" in all_cited_sources


def test_investigations_analyze_sample_mode_all_scenarios():
    for sc_id in ["catalytic_converter", "keyless_suv_relay"]:
        payload = {"query": f"test query for {sc_id}", "demo_content": True, "scenario_id": sc_id}
        resp = client.post("/api/investigations/analyze", json=payload)
        assert resp.status_code == 200
        res = resp.json()
        assert res["sentinels"] is not None
        assert res["sentinels"]["operational_tracker"]["status"] == "PASS"
        assert res["sentinels"]["hackos_auditor"]["status"] == "COMPLIANT"
        assert res["sentinels"]["disqualification_sentinel"]["status"] == "CLEAN"
        assert res["report"] is not None
        assert res["report"]["dossier_ready"] is True
        assert len(res["report"]["facts"]) >= 2


def test_get_investigation_trace_sample_mode():
    run_id = "sample-crowbar_safe_cracking"
    response = client.get(f"/api/investigations/{run_id}/trace")
    assert response.status_code == 200
    data = response.json()

    assert data["run_id"] == run_id
    assert isinstance(data["events"], list)
    assert data["total_events"] == len(data["events"])
    assert data["total_events"] >= 4

    agents = {e["agent"] for e in data["events"]}
    assert "planner" in agents
    assert "finder" in agents
    assert "skeptic" in agents
    assert "reporter" in agents

    for ev in data["events"]:
        assert "timestamp" in ev
        assert "T" in ev["timestamp"]
        assert "phase" in ev
        assert "agent" in ev
        assert "model" in ev
        assert "receipt_id" in ev
        assert ev["receipt_id"] == ""                  # demo content: no real Nightshift call, so no receipt
        assert ev["details"]["demo_content"] is True
        assert "details" in ev
        assert isinstance(ev["details"], dict)


def test_get_investigation_trace_live_logger_roundtrip(tmp_path):
    from app.services.trace_logger import TraceLogger

    test_run_id = "inv_test_m2_roundtrip_12345"
    logger = TraceLogger(test_run_id)

    # Log two distinct events
    logger.log_event(
        step="planning",
        agent="planner",
        action="formulate_retrieval_plan",
        details={"target": "NORTH"},
        provider_meta={"reported_model": "nvidia/nemotron-3-ultra-550b-a55b", "receipt_id": "rcpt-ultra-test-01"},
    )
    logger.log_event(
        step="verification",
        agent="skeptic",
        action="adversarial_critique",
        details={"result": "grounded"},
        provider_meta={"reported_model": "nvidia/nemotron-3-ultra-550b-a55b", "receipt_id": "rcpt-ultra-test-02"},
    )

    response = client.get(f"/api/investigations/{test_run_id}/trace")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == test_run_id
    assert data["total_events"] >= 2

    # Clean up test trace file
    if logger.log_file.exists():
        logger.log_file.unlink()


def test_get_investigation_trace_unflushed_or_unknown_fallback():
    # An unknown or unflushed run_id returns NO events: a trace is only what a run recorded, never invented.
    response = client.get("/api/investigations/inv_unknown_fallback_99999/trace")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "inv_unknown_fallback_99999"
    assert data["total_events"] == 0 and data["events"] == []

