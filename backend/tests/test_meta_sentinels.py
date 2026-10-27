"""
Tests for AEGIS Meta-Governance & Audit Sentinels
=================================================
Verifies that:
1. OperationalTracker reports latency, tokens, and milestones.
2. HackOSComplianceAuditor checks Zetaris, Meterless, Nightshift, and Cross-Station links.
3. DisqualificationSentinel flags API key leaks and ungrounded hallucinated IDs.
"""

from app.services.meta_sentinels import (
    disqualification_sentinel,
    hackos_auditor,
    operational_tracker,
)


def test_operational_tracker_normal_run():
    report = operational_tracker.evaluate(
        run_id="inv_test_001",
        elapsed_seconds=14.5,
        iterations=2,
        model_calls=[
            {"completion_tokens": 120, "prompt_tokens": 300, "latency_ms": 450},
            {"completion_tokens": 80, "prompt_tokens": 200, "latency_ms": 320},
        ],
        sql_queries=5,
        engine_ops=[{"engine": "world_model", "op": "stats"}],
    )
    assert report.passed is True
    assert report.score >= 90.0
    assert report.details["sql_queries_executed"] == 5
    assert report.details["total_tokens_consumed"] == 700


def test_hackos_auditor_conformance_check():
    valid_integration = {
        "zetaris": {
            "status": "connected",
            "tables_queried": ["police_incidents", "forensic_reports"],
        },
        "meterless_engines": {
            "world_model": {"status": "connected"},
            "scout_intent": {"status": "connected"},
        },
        "nightshift_nemotron": {
            "status": "connected",
            "models_used": ["nvidia/nemotron-3-ultra-550b-a55b"],
        },
    }
    report = hackos_auditor.evaluate(
        integration_status=valid_integration,
        model_calls=[{"reported_model": "nvidia/nemotron-3-ultra-550b-a55b"}],
        candidate_links=[{"stations_involved": ["NORTH", "CENTRAL"]}],
        stations_involved=["NORTH", "CENTRAL"],
    )
    assert report.passed is True
    assert report.details["zetaris_load_bearing"] is True
    assert report.details["multi_station_intelligence"] is True


def test_disqualification_sentinel_catches_api_key():
    payload_with_key = "Analysis completed. " + "nvapi" + "-SECRETKEY1234567890ABCDEFGH found in report."
    report = disqualification_sentinel.evaluate(
        full_payload_dump=payload_with_key,
        candidate_links=[],
        known_incident_ids=set(),
        known_evidence_ids=set(),
    )
    assert report.passed is False
    assert any("Potential API key" in v for v in report.violations)


def test_disqualification_sentinel_catches_hallucinated_ids():
    candidate_links = [
        {
            "source_incident_id": "INC-NORTH-0042",
            "target_incident_id": "INC-FAKE-9999",
            "supporting_evidence_ids": ["FOR-0089"],
        }
    ]
    known_incidents = {"INC-NORTH-0042", "INC-CENTRAL-0010"}
    known_evidence = {"FOR-0089"}

    report = disqualification_sentinel.evaluate(
        full_payload_dump="Safe payload with no secrets.",
        candidate_links=candidate_links,
        known_incident_ids=known_incidents,
        known_evidence_ids=known_evidence,
    )
    assert report.passed is False
    assert any("Grounding Failure" in v for v in report.violations)
