"""
AEGIS Crime Intelligence - Empirical Adversarial Challenge Suite
================================================================
Role: Challenger 1 (Adversarial API & Deterministic Verifier Stress Tester)

This test suite empirically and adversarially challenges:
1. POST /api/investigations/analyze
   - Offline sample mode across all 3 scenarios
   - Adversarial inputs: empty string, whitespace, SQL injection, oversized queries, null bytes
   - Rejection of unconfigured live mode without 500 crashes
2. GET /api/investigations/{run_id}/trace
   - Sample run IDs, non-existent run IDs, empty strings, path traversal, injection
   - Verification of HTTP 200, valid events list, pinned Nemotron models, receipt IDs
3. backend/app/services/evidence_verifier.py
   - Contradictory evidence (vehicle color mismatch, witness flags, forensic exclusions, timeline inversions)
   - Rejection/downgrading of ungrounded claims, missing IDs, fabricated quotes, one-sided attributes
   - Non-independent evidence clustering and collapse
4. model_registry.analyze_cctv_frame
   - Corrupted, empty, truncated, and random binary image bytes
   - Optical metadata extraction from structured JSON and regex from raw prompts
   - Graceful fallback with conforming contract
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
from fastapi.testclient import TestClient

# Setup sys.path
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.main import app
from app.services.evidence_verifier import (
    EvidenceIndex,
    cluster_independent,
    detect_contradictions,
    verify_link,
)
from app.services.model_registry import (
    NEMOTRON_MODELS,
    ROLE_MODEL_PREFERENCES,
    ModelRegistry,
    _extract_cctv_metadata,
    analyze_cctv_frame,
)
from app.services.sample_scenarios import SAMPLE_SCENARIOS, get_sample_investigation

client = TestClient(app)


# =============================================================================
# SUITE 1: ADVERSARIAL STRESS TESTING ON POST /api/investigations/analyze
# =============================================================================

class TestAdversarialAnalyzeEndpoint:
    """Stress testing POST /api/investigations/analyze under hostile and edge conditions."""

    @pytest.mark.parametrize("scenario_key", [
        "crowbar_safe_cracking",
        "catalytic_converter",
        "keyless_suv_relay",
    ])
    def test_sample_mode_all_scenarios_fidelity(self, scenario_key: str):
        """Verify each known scenario in sample mode produces 100% compliant payload."""
        payload = {
            "query": f"investigate {scenario_key}",
            "scenario_id": scenario_key,
            "demo_content": True,
        }
        res = client.post("/api/investigations/analyze", json=payload)
        assert res.status_code == 200, f"Failed for scenario {scenario_key}: {res.text}"
        data = res.json()

        # Contract checks
        assert data["is_sample"] is True
        assert data["data_mode"] == "demo_content"
        assert len(data["candidate_incidents"]) >= 2
        assert len(data["candidate_links"]) >= 1

        # Sentinels check
        assert "sentinels" in data and data["sentinels"] is not None
        sentinels = data["sentinels"]
        assert "operational_tracker" in sentinels
        assert "hackos_auditor" in sentinels
        assert "disqualification_sentinel" in sentinels
        assert sentinels["operational_tracker"]["status"] in ("PASS", "VERIFIED")
        assert sentinels["hackos_auditor"]["status"] in ("COMPLIANT", "VERIFIED")
        assert sentinels["disqualification_sentinel"]["status"] in ("CLEAN", "VERIFIED")

        # Report & Dossier check
        assert "report" in data and data["report"] is not None
        report = data["report"]
        assert report.get("dossier_ready") is True
        assert "synthesis" in report
        assert "facts" in report
        assert report.get("confidence", 0) >= 0.8

    @pytest.mark.parametrize("query,expected_scenario", [
        ("Investigate safe burglaries in North industrial park", "crowbar_safe_cracking"),
        ("Catalytic converter saw exhaust theft in Central", "catalytic_converter"),
        ("Luxury SUV keyless relay antenna bypass", "keyless_suv_relay"),
    ])
    def test_sample_mode_query_auto_dispatch(self, query: str, expected_scenario: str):
        """Verify query-based scenario dispatch without explicit scenario_id."""
        payload = {
            "query": query,
            "demo_content": True,
        }
        res = client.post("/api/investigations/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["scenario_id"] == expected_scenario
        assert data["report"]["dossier_ready"] is True

    @pytest.mark.parametrize("adversarial_query", [
        "",                                      # Empty query
        "   \t\r\n   ",                          # Whitespace only
        "'; DROP TABLE police_incidents; --",    # Destructive SQL injection
        "' OR '1'='1' --",                       # SQL tautology injection
        "1; EXEC xp_cmdshell('dir'); --",        # Command execution injection
        "<script>alert('xss')</script>",         # XSS injection
        "{{7*7}} ${7*7}",                        # SSTI injection
        "A" * 32768,                             # 32KB buffer stress
        "🚨 Safe Cracking 🔍 \u202e RLO \u202d", # Unicode / Emojis / RTL
        "burglary\x00safe\x00pry",              # Null bytes inside text
    ], ids=["empty", "whitespace", "sql_drop", "sql_tautology", "cmd_exec", "xss", "ssti", "oversized_32k", "unicode_rlo", "null_bytes"])
    def test_sample_mode_adversarial_queries(self, adversarial_query: str):
        """Submit hostile, malformed, and injection queries. Must never crash with 500."""
        payload = {
            "query": adversarial_query,
            "demo_content": True,
        }
        res = client.post("/api/investigations/analyze", json=payload)
        # 200 (graceful fallback) or 422 (validation error) are acceptable; NEVER 500.
        assert res.status_code in (200, 422), f"Hostile query crashed server: {res.status_code} - {res.text}"
        if res.status_code == 200:
            data = res.json()
            assert data["is_sample"] is True
            assert data["sentinels"] is not None
            assert data["report"]["dossier_ready"] is True

    def test_live_mode_unconfigured_graceful_rejection(self):
        """Live mode execution without Zetaris/Nightshift credentials must reject with 503, not 500."""
        payload = {
            "query": "Investigate safe burglaries in North industrial park",
            "sample_mode": False,
        }
        res = client.post("/api/investigations/analyze", json=payload)
        # Should be 503 Service Unavailable with clear actionable detail
        assert res.status_code == 503, f"Expected 503, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "")
        assert "NOT CONFIGURED" in detail or "Zetaris" in detail or "Nightshift" in detail

    @pytest.mark.parametrize("bad_payload", [
        {"sample_mode": "not_a_bool"},
        {"station_ids": "not_a_list"},
        {"incident_ids": 12345},
    ])
    def test_malformed_type_payloads(self, bad_payload: Dict[str, Any]):
        """Verify Pydantic request validation returns 422 for type errors."""
        res = client.post("/api/investigations/analyze", json=bad_payload)
        assert res.status_code == 422


# =============================================================================
# SUITE 2: ADVERSARIAL STRESS TESTING ON GET /api/investigations/{run_id}/trace
# =============================================================================

class TestAdversarialTraceEndpoint:
    """Stress testing GET /api/investigations/{run_id}/trace."""

    @pytest.mark.parametrize("run_id", [
        "sample-crowbar_safe_cracking",
        "sample-catalytic_converter",
        "sample-keyless_suv_relay",
    ])
    def test_trace_sample_scenarios(self, run_id: str):
        """Verify trace retrieval for sample scenario run IDs."""
        res = client.get(f"/api/investigations/{run_id}/trace")
        assert res.status_code == 200
        data = res.json()
        assert data["run_id"] == run_id
        assert data["total_events"] >= 5
        events = data["events"]

        # Verify all 4 Nemotron lanes are represented in trace events
        models_in_trace = {ev["model"] for ev in events}
        assert NEMOTRON_MODELS["ultra-550b"] in models_in_trace
        assert NEMOTRON_MODELS["lightning-30b"] in models_in_trace
        assert NEMOTRON_MODELS["super-vl-120b"] in models_in_trace

        # Verify receipt IDs
        for ev in events:
            assert ev["receipt_id"].startswith("rcpt-"), f"Invalid receipt ID: {ev['receipt_id']}"
            assert ev["phase"] in ("planning", "retrieval", "vision_analysis", "adversarial_critique", "dossier_synthesis")
            assert ev["agent"] in ("planner", "finder", "vision_analyst", "skeptic", "reporter")

    @pytest.mark.parametrize("arbitrary_run_id", [
        "nonexistent-run-999999",
        "uuid-550e8400-e29b-41d4-a716-446655440000",
        "arbitrary_custom_trace_01",
    ])
    def test_trace_nonexistent_run_id_returns_synthetic_trace(self, arbitrary_run_id: str):
        """Non-existent run IDs should gracefully return structured synthetic trace without 404/500."""
        res = client.get(f"/api/investigations/{arbitrary_run_id}/trace")
        assert res.status_code == 200
        data = res.json()
        assert data["run_id"] == arbitrary_run_id
        assert data["total_events"] > 0
        for ev in data["events"]:
            assert ev["receipt_id"].startswith("rcpt-")

    @pytest.mark.parametrize("hostile_run_id", [
        "..%2F..%2Fetc%2Fpasswd",
        "..%5C..%5Cwindows%5Csystem32",
        "%20",
        "<script>alert('xss')</script>",
        "'; DROP TABLE traces; --",
        "A" * 500,
    ], ids=["path_traversal_unix", "path_traversal_win", "whitespace", "xss", "sql_drop", "oversized_id"])
    def test_trace_adversarial_run_ids(self, hostile_run_id: str):
        """Hostile path traversal, injection, and oversized run IDs must never crash with 500."""
        res = client.get(f"/api/investigations/{hostile_run_id}/trace")
        assert res.status_code in (200, 404, 422), f"Hostile run_id caused {res.status_code}: {res.text}"

    def test_trace_empty_run_id(self):
        """Empty run_id in path (/api/investigations//trace) must return 404/307, not 500."""
        res = client.get("/api/investigations//trace")
        assert res.status_code in (404, 307)


# =============================================================================
# SUITE 3: DETERMINISTIC EVIDENCE VERIFIER ADVERSARIAL STRESS TESTING
# =============================================================================

class TestDeterministicVerifierStress:
    """Stress testing backend/app/services/evidence_verifier.py with hostile and contradictory data."""

    def _build_test_index(self) -> EvidenceIndex:
        idx = EvidenceIndex()
        idx.add_incidents([
            {
                "incident_id": "INC-NORTH-0001",
                "station_id": "NORTH",
                "location_id": "LOC-NORTH-01",
                "occurred_from": "2025-03-01T02:00:00Z",
                "occurred_to": "2025-03-01T03:00:00Z",
                "crime_type": "BURGLARY",
                "method_description": "Forced entry safe door peeled with chisel",
            },
            {
                "incident_id": "INC-CENTRAL-0002",
                "station_id": "CENTRAL",
                "location_id": "LOC-CEN-02",
                "occurred_from": "2025-03-05T02:30:00Z",
                "occurred_to": "2025-03-05T03:30:00Z",
                "crime_type": "BURGLARY",
                "method_description": "Reinforced vault pried with chisel",
            },
        ])
        return idx

    def test_vehicle_color_contradiction_detection(self):
        """CCTV observation (grey vehicle) vs Witness observation (red vehicle) MUST produce contradiction."""
        idx = self._build_test_index()
        idx.add_evidence({
            "cctv_reports": [
                {
                    "cctv_report_id": "CCTV-0010",
                    "incident_id": "INC-NORTH-0001",
                    "related_incident_ids": ["INC-NORTH-0001"],
                    "vehicle_color": "grey",
                    "vehicle_description": "Dark grey Dodge Grand Caravan",
                }
            ],
            "witness_reports": [
                {
                    "witness_report_id": "WIT-0020",
                    "incident_id": "INC-CENTRAL-0002",
                    "related_incident_ids": ["INC-CENTRAL-0002"],
                    "vehicle_description": "Bright red four-door sedan speeding away",
                }
            ],
        })

        link = {
            "link_id": "LINK-TEST-001",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-CENTRAL-0002",
            "supporting_evidence_ids": ["CCTV-0010", "WIT-0020"],
        }
        val = verify_link(link, idx)
        # Contradictions must be detected
        assert len(val.contradictions) >= 1
        flags = [c["type"] for c in val.contradictions]
        assert "vehicle_color_conflict" in flags

        # Contradiction description must pinpoint the conflict
        desc = next(c["description"] for c in val.contradictions if c["type"] == "vehicle_color_conflict")
        assert "grey" in desc and "red" in desc

    def test_witness_contradiction_flags(self):
        """Witness reports carrying internal contradiction flags MUST be surfaced."""
        idx = self._build_test_index()
        idx.add_evidence({
            "witness_reports": [
                {
                    "witness_report_id": "WIT-FLAGGED-01",
                    "incident_id": "INC-NORTH-0001",
                    "related_incident_ids": ["INC-NORTH-0001"],
                    "contradiction_flags": ["retracted_statement", "conflicting_direction"],
                }
            ]
        })
        link = {
            "link_id": "LINK-TEST-002",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-CENTRAL-0002",
            "supporting_evidence_ids": ["WIT-FLAGGED-01"],
        }
        val = verify_link(link, idx)
        c_types = [c["type"] for c in val.contradictions]
        assert "source_flag" in c_types
        flags_found = [c["flag"] for c in val.contradictions if c["type"] == "source_flag"]
        assert "retracted_statement" in flags_found

    def test_forensic_exclusion_contradiction(self):
        """Forensic report with EXCLUSION status MUST produce contradiction and not be counted as corroborating."""
        idx = self._build_test_index()
        idx.add_evidence({
            "forensic_reports": [
                {
                    "evidence_report_id": "FOR-EXCL-01",
                    "incident_id": "INC-NORTH-0001",
                    "evidence_item_id": "EVD-TOOL-01",
                    "result_status": "EXCLUSION",
                    "result_summary": "Toolmark striations definitely excluded from test pry bar",
                }
            ]
        })
        link = {
            "link_id": "LINK-TEST-003",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-CENTRAL-0002",
            "supporting_evidence_ids": ["FOR-EXCL-01"],
        }
        val = verify_link(link, idx)
        assert any(c["type"] == "forensic_exclusion" for c in val.contradictions)
        # Probative list must be empty
        assert "FOR-EXCL-01" not in val.corroborating_ids

    def test_timeline_inversion_and_physical_impossibility(self):
        """Overlapping occurrence windows at different stations/locations must be flagged as impossible for one actor."""
        idx = EvidenceIndex()
        idx.add_incidents([
            {
                "incident_id": "INC-NORTH-SIMUL",
                "station_id": "NORTH",
                "location_id": "LOC-NORTH-01",
                "occurred_from": "2025-03-01T02:00:00Z",
                "occurred_to": "2025-03-01T02:30:00Z",
            },
            {
                "incident_id": "INC-CENTRAL-SIMUL",
                "station_id": "CENTRAL",
                "location_id": "LOC-CEN-02",
                "occurred_from": "2025-03-01T02:15:00Z",
                "occurred_to": "2025-03-01T02:45:00Z",
            },
        ])
        link = {
            "link_id": "LINK-SIMUL",
            "source_incident_id": "INC-NORTH-SIMUL",
            "target_incident_id": "INC-CENTRAL-SIMUL",
            "stations_involved": ["NORTH", "CENTRAL"],
            "supporting_evidence_ids": [],
        }
        val = verify_link(link, idx)
        timeline_checks = [c for c in val.checks if c.check == "timeline"]
        assert len(timeline_checks) > 0
        assert timeline_checks[0].status == "warn"
        assert any(c["type"] == "incompatible_timeline" for c in val.contradictions)

    def test_ungrounded_claims_and_hallucinated_ids(self):
        """Links citing non-existent incident IDs MUST fail hard with status UNSUPPORTED."""
        idx = self._build_test_index()
        link = {
            "link_id": "LINK-HALLUCINATED",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-GHOST-9999",  # Fake ID
            "supporting_evidence_ids": ["EVD-NONEXISTENT-01"],
        }
        val = verify_link(link, idx)
        assert val.status == "UNSUPPORTED"
        assert any(c.check == "ids_exist" and c.status == "fail" for c in val.checks)
        assert "INC-GHOST-9999" in val.rejected_ids or "EVD-NONEXISTENT-01" in val.rejected_ids

    def test_identical_source_and_target_rejected(self):
        """Link where source_incident_id == target_incident_id must be rejected as UNSUPPORTED."""
        idx = self._build_test_index()
        link = {
            "link_id": "LINK-SELF",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-NORTH-0001",
            "supporting_evidence_ids": [],
        }
        val = verify_link(link, idx)
        assert val.status == "UNSUPPORTED"
        assert any(c.check == "ids_exist" and c.status == "fail" for c in val.checks)

    def test_fabricated_quotes_and_attributes_rejected(self):
        """Quotes not found in record and attributes evidenced on only one side must be flagged."""
        idx = self._build_test_index()
        idx.add_evidence({
            "witness_reports": [
                {
                    "witness_report_id": "WIT-001",
                    "incident_id": "INC-NORTH-0001",
                    "related_incident_ids": ["INC-NORTH-0001"],
                    "observation_text": "Witness saw blue jacket and white shoes.",
                }
            ]
        })
        link = {
            "link_id": "LINK-FABRICATED",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-CENTRAL-0002",
            "supporting_evidence_ids": ["WIT-001"],
            "quotes": [
                {"source_id": "WIT-001", "text": "I definitely saw a green laser beam cutter"}  # Fabricated quote
            ],
            "shared_attributes": [
                {"attribute": "tool", "value": "green laser beam", "source_ids": ["WIT-001"]}  # Fabricated attribute
            ],
        }
        val = verify_link(link, idx)
        # Must fail hard because quote is fabricated
        assert val.status == "UNSUPPORTED"
        assert any(c.check == "quotes" and c.status == "fail" for c in val.checks)
        assert any(c.check == "attributes" and c.status == "fail" for c in val.checks)

    def test_derivative_and_non_independent_sources_collapse(self):
        """Newspaper reports deriving from police incidents must not count as independent corroboration."""
        idx = self._build_test_index()
        idx.add_evidence({
            "newspaper_reports": [
                {
                    "news_id": "NEWS-001",
                    "related_incident_ids": ["INC-NORTH-0001"],
                    "headline": "Burglary at logistics warehouse bay 4",
                },
                {
                    "news_id": "NEWS-002",
                    "related_incident_ids": ["INC-NORTH-0001"],
                    "headline": "Police investigate North warehouse heist",
                },
            ]
        })
        link = {
            "link_id": "LINK-DERIVATIVE",
            "source_incident_id": "INC-NORTH-0001",
            "target_incident_id": "INC-CENTRAL-0002",
            "supporting_evidence_ids": ["NEWS-001", "NEWS-002"],
        }
        val = verify_link(link, idx)
        # Even though 2 news articles are cited, independent count must be 0 or 1, not 2
        assert val.independent_source_count < 2
        # Therefore status cannot be SUPPORTED
        assert val.status in ("WEAK", "UNSUPPORTED")


# =============================================================================
# SUITE 4: CCTV OPTICAL FALLBACK & CORRUPT FRAME RESILIENCE
# =============================================================================

class TestCCTVOpticalFallbackStress:
    """Stress testing model_registry.analyze_cctv_frame with corrupt and adversarial payloads."""

    @pytest.mark.parametrize("corrupt_bytes", [
        b"",                                      # Zero bytes
        b"\x00" * 4,                              # Short null bytes (< 16)
        b"mock_frame_data",                       # Mock indicator
        b"synthetic_cctv_test_frame",             # Synthetic indicator
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 2,       # Truncated PNG header
        b"\xff\xd8\xff\xe0" + b"\x00" * 4,       # Truncated JPEG header
        b"Corrupt binary string not an image!",  # Text garbage
        b"\xaa" * 1024,                          # 1KB binary pattern
    ], ids=["zero", "null4", "mock", "synthetic", "png_trunc", "jpeg_trunc", "garbage_text", "binary_pattern"])
    def test_cctv_corrupt_payloads_fallback(self, corrupt_bytes: bytes):
        """Corrupted image bytes must never throw; must trigger resilient local optical fallback."""
        res = analyze_cctv_frame(
            image_bytes=corrupt_bytes,
            camera_id="CAM-STRESS-01",
            prompt="Suspect in dark jacket observed fleeing in grey minivan license plate 7XK123",
        )
        assert isinstance(res, dict)
        assert res["camera_id"] == "CAM-STRESS-01"
        assert res["model"] == NEMOTRON_MODELS["super-vl-120b"]
        assert res["fallback_used"] is True
        assert res["receipt_id"].startswith("rcpt-opt-")
        assert len(res["description"]) > 0

        # Optical extraction must have captured entities from prompt
        entity_values = [str(e) for e in res["entities"]]
        assert any("7XK123" in v for v in entity_values)
        assert any("grey minivan" in v.lower() for v in entity_values)

    def test_cctv_structured_json_prompt_extraction(self):
        """Verify prompt with structured JSON metadata extracts all entities accurately."""
        json_prompt = json.dumps({
            "camera_id": "CAM-NORTH-04",
            "partial_plate": "3ABC890",
            "vehicle_color": "dark red sedan",
            "suspect": "individual in high-vis vest",
            "observed_entities": ["dented bumper", "portable grinder"],
        })
        res = analyze_cctv_frame(
            image_bytes=b"mock_bytes",
            camera_id="CAM-NORTH-04",
            prompt=json_prompt,
        )
        assert res["fallback_used"] is True
        entity_values = [str(e) for e in res["entities"]]
        assert any("3ABC890" in v for v in entity_values)
        assert any("dark red sedan" in v for v in entity_values)
        assert any("high-vis vest" in v for v in entity_values)

    @pytest.mark.parametrize("adversarial_prompt", [
        "",
        "   ",
        "'; DROP TABLE cctv_reports; --",
        "<script>alert(1)</script>",
        "A" * 8192,
        "\x00\x00\x00",
    ])
    def test_cctv_adversarial_prompts(self, adversarial_prompt: str):
        """Adversarial prompts must be handled gracefully without exception."""
        res = analyze_cctv_frame(
            image_bytes=b"",
            camera_id="CAM-ADV-01",
            prompt=adversarial_prompt,
        )
        assert isinstance(res, dict)
        assert res["camera_id"] == "CAM-ADV-01"
        assert res["fallback_used"] is True
        assert res["receipt_id"].startswith("rcpt-opt-")


if __name__ == "__main__":
    pytest.main(["-v", __file__])
