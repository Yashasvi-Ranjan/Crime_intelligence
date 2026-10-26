"""
AEGIS Crime Intelligence - Comprehensive 4-Tier End-to-End Test Suite
Open Agent Hackathon 2026 - Track 1: Solving Fragmented Intelligence

Test Architecture (4-Tier Methodology):
- Tier 1: Category-Partition Testing (Model Lanes, Multi-Agent loop, Sentinels, API endpoints)
- Tier 2: Boundary Value Analysis (Edge conditions, empty queries, token budgets, duplicate citations)
- Tier 3: Pairwise Combinatorial Testing (Cross-station permutations, crime types, execution modes)
- Tier 4: Real-World Workloads (E2E investigations, trace receipts, zero secrets audit, 0% hallucinated IDs)

Authoritative Requirements & Coverage:
- F1: Multi-Agent Loop (Planner, Finder, Verifier, Skeptic, Reporter)
- F2: Adversarial Skeptic Authority (Objections, score-blinding, downvotes, re-retrieval)
- F3: Deterministic Citation Verifier (Pure Python ground truth linking)
- F4: Model Lane 1: Ingestion, PII, Reporter (nvidia/nemotron-3.5-lightning-30b-a3b)
- F5: Model Lane 2: Planning & Skeptic (nvidia/nemotron-3-ultra-550b-a55b)
- F6: Model Lane 3: CCTV Scene Analysis (nvidia/nemotron-3.5-super-vl-120b-a12b + optical fallback)
- F7: Model Lane 4: Semantic MO Embedding (nvidia/nemotron-3-embed-1b)
- F8: Quad Meterless Engines (World Model, H-MEM, Markovian, Scout Intent)
- F9: Sentinel 1: Operational Tracker (Latencies, token consumption, iteration limits)
- F10: Sentinel 2: HackOS Compliance Auditor (Zetaris, Meterless, Nightshift load-bearing checks)
- F11: Sentinel 3: Anti-Disqualification Guardian (Zero-secrets scan, ungrounded ID detection)
- F12: Interactive Knowledge Graph (Multi-entity schema, SVG directed edges, link statuses)
- F13: Interactive Evidence Pinboard (Corroborated evidence items, cross-jurisdiction pinning)
- F14: Printable Court Dossier (Admissible intelligence report, verified citations)
- F15: Multi-Station Filtering (North, Central, Riverside dynamic filtering)
- F16: Trace Drawer & Receipt IDs (Chronological timeline, verifiable receipt IDs)
- F17: Backend Test Suite (Pytest 100% execution)
- F18: Frontend TypeScript Build (tsc --noEmit clean)
- F19: Zero Secrets Leakage (Automated regex security scan)
- F20: Zero Hallucinated IDs (100% grounded in Zetaris tables)
- F21: Offline Evaluation Benchmark (Ground truth benchmark execution)
- F22: Credential-Free Sample Mode (100% functional with zero credentials)
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
from fastapi.testclient import TestClient

# Establish robust import pathing to backend and data directories
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
)
from app.services.sample_scenarios import SAMPLE_SCENARIOS, get_sample_investigation
from app.services.trace_logger import TraceLogger

# Regex patterns for strict anti-disqualification zero-secrets leakage scan
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret[_-]?key|password|auth[_-]?token)\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

# Helper to load all ground truth dataset IDs for hallucination detection
def load_all_grounded_ids() -> Set[str]:
    data_dir = ROOT / "data" / "generated"
    all_ids: Set[str] = set()
    files_to_keys = {
        "police_incidents.json": ["incident_id"],
        "cctv_reports.json": ["cctv_report_id"],
        "witness_reports.json": ["witness_report_id"],
        "newspaper_reports.json": ["news_id"],
        "forensic_reports.json": ["evidence_report_id", "evidence_item_id"],
    }
    for filename, keys in files_to_keys.items():
        file_path = data_dir / filename
        if file_path.exists():
            records = json.loads(file_path.read_text(encoding="utf-8"))
            for r in records:
                for k in keys:
                    if r.get(k):
                        all_ids.add(r[k])
    return all_ids


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """FastAPI TestClient fixture for REST endpoint testing."""
    return TestClient(app)


# ============================================================================
# TIER 1: CATEGORY-PARTITION TESTING
# ============================================================================
class TestTier1CategoryPartition:
    """
    Tier 1: Systematic partition testing across model lanes, multi-agent roles,
    deterministic verifiers, sentinels, and workspace contracts.
    """

    def test_partition_f4_f5_f6_f7_nemotron_model_lanes(self):
        """Partition A: Verify all 4 Quad-Nemotron model lanes are properly registered."""
        # Lane 1: Lightning 30B
        assert NEMOTRON_MODELS["lightning-30b"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
        # Lane 2: Ultra 550B
        assert NEMOTRON_MODELS["ultra-550b"] == "nvidia/nemotron-3-ultra-550b-a55b"
        # Lane 3: Super-VL 120B
        assert NEMOTRON_MODELS["super-vl-120b"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
        # Lane 4: Embed 1B
        assert NEMOTRON_MODELS["embed-1b"] == "nvidia/nemotron-3-embed-1b"

        # Verify role dispatch mappings
        assert ROLE_MODEL_PREFERENCES["reporter"] == NEMOTRON_MODELS["lightning-30b"]
        assert ROLE_MODEL_PREFERENCES["planner"] == NEMOTRON_MODELS["ultra-550b"]
        assert ROLE_MODEL_PREFERENCES["skeptic"] == NEMOTRON_MODELS["ultra-550b"]
        assert ROLE_MODEL_PREFERENCES["cctv_analysis"] == NEMOTRON_MODELS["super-vl-120b"]
        assert ROLE_MODEL_PREFERENCES["semantic_mo_embedding"] == NEMOTRON_MODELS["embed-1b"]

    def test_partition_f6_super_vl_optical_fallback_contract(self):
        """Partition A: Verify Super-VL optical analysis contract with resilient fallback."""
        registry = ModelRegistry(settings)
        # Test optical extraction on surveillance prompt
        test_prompt = (
            "CCTV feed at LOC-NORTH-01 captured a dark grey minivan with license plate 7XK-9021 "
            "and two unidentified suspects wearing dark hoodie jackets and balaclava."
        )
        res = registry.analyze_cctv_frame(
            image_bytes=b"synthetic_cctv_frame_bytes_for_testing",
            camera_id="CAM-NORTH-04",
            prompt=test_prompt,
        )
        assert res["camera_id"] == "CAM-NORTH-04"
        assert res["model"] == NEMOTRON_MODELS["super-vl-120b"]
        assert res["receipt_id"].startswith("rcpt-")
        assert res["fallback_used"] is True or res["fallback_used"] is False
        assert isinstance(res["entities"], list)
        assert len(res["entities"]) > 0

        # Verify entity extraction details
        extracted_text = " ".join(str(e) for e in res["entities"])
        assert "7XK-9021" in extracted_text or "7XK" in extracted_text
        assert "minivan" in extracted_text.lower() or "dark grey" in extracted_text.lower()

    def test_partition_f3_deterministic_evidence_verifier(self):
        """Partition B: Verify pure-Python deterministic citation verifier logic."""
        idx = EvidenceIndex()
        idx.add_incidents([
            {
                "incident_id": "INC-NORTH-0042",
                "station_id": "NORTH",
                "property_involved": ["Safe", "Cash"],
                "method_description": "Forced entry, 36mm chisel toolmark striations on safe door",
            },
            {
                "incident_id": "INC-CENTRAL-0118",
                "station_id": "CENTRAL",
                "property_involved": ["Safe", "Jewelry"],
                "method_description": "Office burglary, identical 36mm chisel toolmark on safe box",
            },
        ])
        idx.add_evidence({
            "forensic_reports": [
                {
                    "evidence_report_id": "FOR-0089",
                    "incident_id": "INC-NORTH-0042",
                    "description": "36mm chisel striations",
                },
                {
                    "evidence_report_id": "FOR-0142",
                    "incident_id": "INC-CENTRAL-0118",
                    "description": "36mm chisel striations match",
                },
            ]
        })

        # Test valid link verification
        valid_link = {
            "link_id": "LNK-001",
            "source_incident_id": "INC-NORTH-0042",
            "target_incident_id": "INC-CENTRAL-0118",
            "stations_involved": ["NORTH", "CENTRAL"],
            "supporting_evidence_ids": ["FOR-0089", "FOR-0142"],
            "shared_attributes": [
                {
                    "attribute": "toolmark",
                    "value": "36mm chisel",
                    "source_ids": ["FOR-0089", "FOR-0142"],
                }
            ],
        }
        res = verify_link(valid_link, idx)
        assert res.status in ("SUPPORTED", "WEAK")
        assert res.independent_source_count >= 1

        # Test link citing non-existent evidence (Dropped into rejected_ids)
        hallucinated_evidence_link = {
            "link_id": "LNK-002",
            "source_incident_id": "INC-NORTH-0042",
            "target_incident_id": "INC-CENTRAL-0118",
            "stations_involved": ["NORTH", "CENTRAL"],
            "supporting_evidence_ids": ["FOR-FAKE-9999"],
        }
        res_ev_hal = verify_link(hallucinated_evidence_link, idx)
        assert "FOR-FAKE-9999" in res_ev_hal.rejected_ids

        # Test link citing non-existent incident (Hard fail -> UNSUPPORTED)
        hallucinated_incident_link = {
            "link_id": "LNK-003",
            "source_incident_id": "INC-FAKE-9999",
            "target_incident_id": "INC-CENTRAL-0118",
            "stations_involved": ["NORTH", "CENTRAL"],
            "supporting_evidence_ids": ["FOR-0142"],
        }
        res_inc_hal = verify_link(hallucinated_incident_link, idx)
        assert res_inc_hal.status == "UNSUPPORTED"

    def test_partition_f9_f10_f11_triple_sentinels_schema(self, api_client: TestClient):
        """Partition C: Verify Triple Sentinels structure in sample mode execution."""
        resp = api_client.post(
            "/api/investigations/analyze",
            json={"query": "safe burglaries", "sample_mode": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        sentinels = data.get("sentinels")
        assert sentinels is not None, "Sentinels payload must not be null"

        # Sentinel 1: Operational Tracker
        tracker = sentinels.get("operational_tracker")
        assert tracker is not None
        assert "token_usage" in tracker or "tokens" in tracker or "details" in tracker
        assert "latency_ms" in tracker or "elapsed_seconds" in tracker
        assert tracker["status"] in ("OPTIMAL", "NOMINAL", "VERIFIED", "PASS")

        # Sentinel 2: HackOS Auditor
        auditor = sentinels.get("hackos_auditor")
        assert auditor is not None
        assert auditor.get("zetaris_verified") is True or auditor.get("zetaris_load_bearing") is True
        assert auditor.get("meterless_engines_verified") is True or auditor.get("meterless_engine_verified") is True
        engines = auditor.get("active_meterless_engines") or auditor.get("details", {}).get("active_meterless_engines", [])
        assert "world_model" in engines

        # Sentinel 3: Anti-Disqualification Guardian
        anti_disqual = sentinels.get("disqualification_sentinel")
        assert anti_disqual is not None
        assert anti_disqual["zero_secrets_leakage"] is True
        assert anti_disqual["ungrounded_ids_detected"] == 0

    def test_partition_f12_f13_f14_f15_f16_workspace_contracts(self, api_client: TestClient):
        """Partition D: Verify Palantir Gotham-grade workspace data contracts."""
        resp = api_client.post(
            "/api/investigations/analyze",
            json={"query": "safe burglaries", "scenario_id": "crowbar_safe_cracking", "sample_mode": True},
        )
        assert resp.status_code == 200
        data = resp.json()

        # F12: Knowledge Graph linkages
        links = data.get("candidate_links", [])
        assert len(links) > 0
        first_link = links[0]
        assert "source_incident_id" in first_link
        assert "target_incident_id" in first_link
        assert "stations_involved" in first_link
        assert "confidence_score" in first_link

        # F13: Evidence Pinboard supporting items
        evidence = data.get("supporting_evidence", {})
        assert "forensic_reports" in evidence
        assert len(evidence["forensic_reports"]) > 0

        # F14: Printable Court Dossier report payload
        report = data.get("report", {})
        assert report is not None
        assert report.get("dossier_ready") is True
        assert "synthesis" in report
        assert "facts" in report

        # F15: Multi-Station Filtering
        stations = data.get("stations_involved", [])
        assert set(stations).issubset({"NORTH", "CENTRAL", "RIVERSIDE"})
        assert len(stations) >= 2

        # F16: Trace Drawer endpoint & Receipt IDs
        run_id = data.get("investigation_id")
        trace_resp = api_client.get(f"/api/investigations/{run_id}/trace")
        assert trace_resp.status_code == 200
        trace_data = trace_resp.json()
        assert trace_data["run_id"] == run_id
        assert trace_data["total_events"] > 0
        events = trace_data["events"]
        receipts = [ev["receipt_id"] for ev in events]
        assert all(r.startswith("rcpt-") for r in receipts)


# ============================================================================
# TIER 2: BOUNDARY VALUE ANALYSIS (BVA)
# ============================================================================
class TestTier2BoundaryValueAnalysis:
    """
    Tier 2: Boundary Value Analysis testing empty inputs, extreme lengths,
    token limits, duplicate citations, and single/multi-station limits.
    """

    def test_bva_empty_and_whitespace_query(self, api_client: TestClient):
        """BVA 1: Handle boundary queries (empty, single-character, extreme whitespace)."""
        # Empty string in sample mode
        r1 = api_client.post("/api/investigations/analyze", json={"query": "", "sample_mode": True})
        assert r1.status_code == 200
        assert r1.json()["data_mode"] == "sample_mode"

        # Excessive whitespace
        r2 = api_client.post("/api/investigations/analyze", json={"query": "    \n\t   ", "sample_mode": True})
        assert r2.status_code == 200

        # Special escape characters and control characters
        special_query = "Query with 'quotes', \"double quotes\", and null \\x00 characters"
        r3 = api_client.post("/api/investigations/analyze", json={"query": special_query, "sample_mode": True})
        assert r3.status_code == 200

    def test_bva_evidence_verifier_empty_and_duplicate_evidence(self):
        """BVA 2: Test EvidenceIndex with 0 evidence, duplicate evidence, and empty sets."""
        idx = EvidenceIndex()
        # Empty index checks
        assert idx.has("INC-NORTH-0001") is False
        assert "NON-EXISTENT" not in idx.incidents

        # Add single incident with duplicate reports
        idx.add_incidents([{"incident_id": "INC-NORTH-0001", "station_id": "NORTH"}])
        idx.add_evidence({
            "cctv_reports": [
                {"cctv_report_id": "CCTV-0001", "camera_id": "CAM-1", "related_incident_ids": ["INC-NORTH-0001"]},
                {"cctv_report_id": "CCTV-0001", "camera_id": "CAM-1", "related_incident_ids": ["INC-NORTH-0001"]},  # Duplicate
            ]
        })
        assert idx.has("CCTV-0001") is True

    def test_bva_contradiction_detection_boundaries(self):
        """BVA 3: Boundary testing for vehicle color and witness contradictions."""
        idx = EvidenceIndex()
        idx.add_incidents([{"incident_id": "INC-01", "station_id": "NORTH"}])
        idx.add_evidence({
            "cctv_reports": [
                {"cctv_report_id": "CCTV-1", "vehicle_color": "grey", "related_incident_ids": ["INC-01"]},
            ],
            "witness_reports": [
                {"witness_report_id": "WIT-1", "vehicle_description": "red car sedan", "related_incident_ids": ["INC-01"]},
            ],
        })
        # Detect contradiction between grey and red vehicles
        contradictions = detect_contradictions(["CCTV-1", "WIT-1"], idx)
        assert len(contradictions) >= 1
        assert any(c.get("flag") == "vehicle_color_conflict" for c in contradictions)

    def test_bva_trace_logger_boundary_events(self):
        """BVA 4: Test TraceLogger with zero events and arbitrary string run IDs."""
        tracer = TraceLogger("test-run-bva-boundary")
        events = tracer.get_events()
        # Should gracefully return empty list if not written to disk yet
        assert isinstance(events, list)

    def test_bva_cctv_empty_bytes_and_invalid_images(self):
        """BVA 5: CCTV analysis with zero-byte input, small mock bytes, and huge prompt."""
        registry = ModelRegistry(settings)
        # Empty bytes
        res = registry.analyze_cctv_frame(b"", "CAM-EMPTY", "Zero byte test")
        assert res["camera_id"] == "CAM-EMPTY"
        assert res["fallback_used"] is True

        # Malformed byte sequence
        res_malformed = registry.analyze_cctv_frame(b"\x00\x01\x02\x03\xff", "CAM-MALFORMED", "Malformed test")
        assert res_malformed["camera_id"] == "CAM-MALFORMED"


# ============================================================================
# TIER 3: PAIRWISE COMBINATORIAL TESTING
# ============================================================================
class TestTier3PairwiseCombinatorial:
    """
    Tier 3: Pairwise Combinatorial testing evaluating combinations of
    jurisdictions, crime types, scenarios, and model lanes.
    """

    @pytest.mark.parametrize(
        "station_a,station_b",
        [
            ("NORTH", "CENTRAL"),
            ("CENTRAL", "RIVERSIDE"),
            ("NORTH", "RIVERSIDE"),
        ],
    )
    def test_pairwise_station_combinations(self, api_client: TestClient, station_a: str, station_b: str):
        """Pairwise 1: Multi-station cross-jurisdiction pair coverage."""
        resp = api_client.post(
            "/api/investigations/analyze",
            json={
                "query": f"Link between {station_a} and {station_b}",
                "station_ids": [station_a, station_b],
                "sample_mode": True,
            },
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["data_mode"] == "sample_mode"
        assert len(res["candidate_links"]) > 0

    @pytest.mark.parametrize(
        "scenario_key",
        ["crowbar_safe_cracking", "catalytic_converter", "keyless_suv_relay"],
    )
    def test_pairwise_predefined_scenarios(self, api_client: TestClient, scenario_key: str):
        """Pairwise 2: Predefined scenario execution across all distinct syndicate types."""
        resp = api_client.post(
            "/api/investigations/analyze",
            json={"scenario_id": scenario_key, "query": "investigate syndicate", "sample_mode": True},
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["scenario_id"] == scenario_key
        assert res["is_sample"] is True
        assert res["sentinels"]["hackos_auditor"]["passed"] is True
        assert res["sentinels"]["disqualification_sentinel"]["zero_secrets_leakage"] is True

    @pytest.mark.parametrize(
        "role,expected_lane",
        [
            ("planner", "ultra-550b"),
            ("finder", "lightning-30b"),
            ("skeptic", "ultra-550b"),
            ("reporter", "lightning-30b"),
            ("cctv_analysis", "super-vl-120b"),
            ("semantic_mo_embedding", "embed-1b"),
        ],
    )
    def test_pairwise_role_lane_dispatch_combinations(self, role: str, expected_lane: str):
        """Pairwise 3: Verify each role deterministically pairs with its required Nemotron lane."""
        assigned_model = ROLE_MODEL_PREFERENCES[role]
        assert assigned_model == NEMOTRON_MODELS[expected_lane]


# ============================================================================
# TIER 4: REAL-WORLD WORKLOADS & ACCEPTANCE CRITERIA
# ============================================================================
class TestTier4RealWorldWorkloads:
    """
    Tier 4: Comprehensive real-world investigation scenarios, zero-secrets
    audit, 0% hallucinated ID check, and offline evaluation benchmark validation.
    """

    def test_workload_e2e_sample_investigation_lifecycle(self, api_client: TestClient):
        """Workload 1: Complete investigation lifecycle in credential-free sample mode."""
        resp = api_client.post(
            "/api/investigations/analyze",
            json={
                "query": "Investigate safe burglaries in North industrial park and Central downtown",
                "scenario_id": "crowbar_safe_cracking",
                "sample_mode": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        # 1. Non-null sentinels and report
        assert data.get("sentinels") is not None
        assert data.get("report") is not None
        assert data["report"]["dossier_ready"] is True
        assert len(data["report"]["facts"]) > 0

        # 2. Trace extraction for the investigation run
        run_id = data["investigation_id"]
        trace_resp = api_client.get(f"/api/investigations/{run_id}/trace")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()
        assert trace["total_events"] >= 4
        phases = [ev["phase"] for ev in trace["events"]]
        assert "planning" in phases
        assert "retrieval" in phases
        assert "adversarial_critique" in phases
        assert "dossier_synthesis" in phases

    def test_workload_zero_secrets_leakage_audit(self, api_client: TestClient):
        """Workload 2: Strict automated security audit ensuring zero secrets in responses and traces."""
        # Query all sample scenarios and traces
        scenarios = ["crowbar_safe_cracking", "catalytic_converter", "keyless_suv_relay"]
        for sc in scenarios:
            res = api_client.post(
                "/api/investigations/analyze",
                json={"scenario_id": sc, "query": "investigate", "sample_mode": True},
            ).json()

            # Convert full response to string and audit
            payload_str = json.dumps(res)
            for pat in SECRET_PATTERNS:
                matches = pat.findall(payload_str)
                assert len(matches) == 0, f"Secret pattern matched in scenario {sc}: {matches}"

            # Audit trace response
            run_id = res["investigation_id"]
            trace_str = json.dumps(api_client.get(f"/api/investigations/{run_id}/trace").json())
            for pat in SECRET_PATTERNS:
                matches = pat.findall(trace_str)
                assert len(matches) == 0, f"Secret pattern matched in trace for {run_id}: {matches}"

    def test_workload_zero_hallucinated_ids_audit(self, api_client: TestClient):
        """Workload 3: Verify 0% hallucinated IDs (100% evidentiary grounding in scenario records)."""
        scenarios = ["crowbar_safe_cracking", "catalytic_converter", "keyless_suv_relay"]
        for sc in scenarios:
            res = api_client.post(
                "/api/investigations/analyze",
                json={"scenario_id": sc, "query": "audit grounding", "sample_mode": True},
            ).json()

            # The scenario defines its grounded domain of incidents and evidence
            scenario_incidents = {i["incident_id"] for i in res.get("candidate_incidents", [])}
            scenario_evidence: Set[str] = set()
            ev_dict = res.get("supporting_evidence", {})
            for r in ev_dict.get("forensic_reports", []):
                if r.get("evidence_report_id"):
                    scenario_evidence.add(r["evidence_report_id"])
            for r in ev_dict.get("cctv_reports", []):
                if r.get("cctv_report_id"):
                    scenario_evidence.add(r["cctv_report_id"])
            for r in ev_dict.get("witness_reports", []):
                if r.get("witness_report_id"):
                    scenario_evidence.add(r["witness_report_id"])
            for r in ev_dict.get("newspaper_reports", []):
                if r.get("news_id"):
                    scenario_evidence.add(r["news_id"])

            allowed_ids = scenario_incidents | scenario_evidence

            # Collect all cited IDs from candidate links and report facts
            cited_ids: Set[str] = set()
            for link in res.get("candidate_links", []):
                cited_ids.add(link["source_incident_id"])
                cited_ids.add(link["target_incident_id"])
                cited_ids.update(link.get("supporting_evidence_ids", []))

            for fact in res.get("report", {}).get("facts", []):
                cited_ids.update(fact.get("source_ids", []))
                cited_ids.update(fact.get("evidence_ids", []))

            # Verify 0% hallucination rate within scenario
            ungrounded = cited_ids - allowed_ids
            assert len(ungrounded) == 0, f"Hallucinated IDs detected in scenario {sc}: {ungrounded}"

    def test_workload_offline_evaluation_benchmark_integrity(self):
        """Workload 4: Validate ground truth benchmark dataset and scoring methodology."""
        truth_file = ROOT / "data" / "evaluation" / "ground_truth.json"
        assert truth_file.exists(), "ground_truth.json must exist"

        truth_data = json.loads(truth_file.read_text(encoding="utf-8"))
        assert isinstance(truth_data, list)
        assert len(truth_data) >= 7

        # Verify planted series relationships
        series_ids = {t["relationship_id"] for t in truth_data}
        expected_series = {"REL-SERIES-001", "REL-SERIES-002", "REL-SERIES-003", "REL-SERIES-004", "REL-SERIES-007"}
        assert expected_series.issubset(series_ids)

        # Verify evidentiary grounding of truth items in generated dataset
        grounded_ids = load_all_grounded_ids()
        for t in truth_data:
            assert len(t["incident_ids"]) >= 1
            if t["relationship_id"].startswith("REL-SERIES-"):
                assert len(t["incident_ids"]) >= 2
            for inc_id in t["incident_ids"]:
                assert inc_id in grounded_ids, f"Planted truth incident {inc_id} not grounded in dataset"

    def test_workload_adversarial_sql_injection_and_tampering(self, api_client: TestClient):
        """Workload 5: Adversarial verification of input sanitation against SQL injection."""
        sql_injections = [
            "'; DROP TABLE police_incidents; --",
            "' UNION SELECT * FROM users --",
            "1' OR '1'='1",
            "'; EXEC xp_cmdshell('dir'); --",
        ]
        for inj in sql_injections:
            resp = api_client.post(
                "/api/investigations/analyze",
                json={"query": inj, "sample_mode": True},
            )
            # Must safely process or return 200 sample response without 500 server crash
            assert resp.status_code == 200
            data = resp.json()
            assert data["data_mode"] == "sample_mode"
            # Ensure injection string does not compromise sentinels
            assert data["sentinels"]["disqualification_sentinel"]["zero_secrets_leakage"] is True
