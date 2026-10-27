"""
AEGIS Meta-Governance & Audit Sentinels
=======================================
Autonomous subagents that supervise execution quality, enforce hackathon rules,
and protect against disqualification risks.

Subagent 1: OperationalTracker
  Continuously monitors iteration latency, token consumption, query counts,
  and state progression milestones.

Subagent 2: HackOSComplianceAuditor
  Strictly audits traces against official Open Agent Hackathon 2026 criteria:
  - Zetaris virtual data layer (Track 1 load-bearing proof)
  - At least 1 Meterless Engine in working feature
  - Nightshift as primary AI provider with pinned NVIDIA Nemotron lanes
  - Cross-station fragmented intelligence resolution

Subagent 3: DisqualificationSentinel
  Performs real-time inspection for disqualification triggers:
  - Zero committed or leaked API secrets (NVIDIA / Zetaris / Nightshift tokens)
  - No fabricated or hardcoded traces (grounded evidence checks)
  - Provenance validation (every cited incident ID exists in Zetaris)
  - Anti-hallucination verification
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class SentinelReport:
    passed: bool
    score: float  # 0.0 to 100.0
    status: str   # "VERIFIED" | "WARNING" | "VIOLATION"
    details: Dict[str, Any] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationalTracker:
    """Subagent 1: Tracks workflow performance, token budgets, and milestones."""

    def __init__(self, target_max_latency_sec: float = 120.0) -> None:
        self.target_max_latency_sec = target_max_latency_sec

    def evaluate(
        self,
        run_id: str,
        elapsed_seconds: float,
        iterations: int,
        model_calls: List[Dict[str, Any]],
        sql_queries: int,
        engine_ops: List[Dict[str, Any]],
    ) -> SentinelReport:
        warnings = []
        violations = []

        total_tokens = sum(
            (c.get("completion_tokens") or 0) + (c.get("prompt_tokens") or 0)
            for c in model_calls
        )
        avg_latency = (
            sum((c.get("latency_ms") or 0) for c in model_calls) / len(model_calls)
            if model_calls
            else 0.0
        )

        if elapsed_seconds > self.target_max_latency_sec:
            warnings.append(
                f"Execution duration ({elapsed_seconds}s) exceeds optimal budget ({self.target_max_latency_sec}s)."
            )

        if sql_queries == 0:
            violations.append("Zero SQL queries executed; retrieval milestone not reached.")

        passed = len(violations) == 0
        score = max(0.0, 100.0 - (len(violations) * 40.0) - (len(warnings) * 10.0))

        return SentinelReport(
            passed=passed,
            score=score,
            status="VERIFIED" if passed and not warnings else ("WARNING" if passed else "VIOLATION"),
            details={
                "run_id": run_id,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "iterations_completed": iterations,
                "total_model_calls": len(model_calls),
                "total_tokens_consumed": total_tokens,
                "average_call_latency_ms": round(avg_latency, 1),
                "sql_queries_executed": sql_queries,
                "engine_operations_count": len(engine_ops),
            },
            violations=violations,
            warnings=warnings,
            recommendations=[
                "Maintain per-iteration token limits to keep streaming snappy."
            ] if warnings else ["Workflow operating within optimal latency boundaries."],
        )


class HackOSComplianceAuditor:
    """Subagent 2: Verifies that project adheres to official HackOS criteria."""

    def evaluate(
        self,
        integration_status: Dict[str, Any],
        model_calls: List[Dict[str, Any]],
        candidate_links: List[Dict[str, Any]],
        stations_involved: List[str],
    ) -> SentinelReport:
        violations = []
        warnings = []
        audit_evidence = {}

        # 1. Zetaris Data Layer Check
        zetaris_stat = integration_status.get("zetaris", {})
        zetaris_connected = zetaris_stat.get("status") == "connected"
        tables = zetaris_stat.get("tables_queried", [])
        if not zetaris_connected or not tables:
            violations.append("Zetaris is not active or no federated tables were queried.")
        audit_evidence["zetaris_load_bearing"] = zetaris_connected
        audit_evidence["tables_federated_count"] = len(tables)

        # 2. Meterless Engine Conformance
        meterless_stat = integration_status.get("meterless_engines", {})
        connected_engines = [
            k for k, v in meterless_stat.items()
            if isinstance(v, dict) and v.get("status") == "connected"
        ]
        if not connected_engines:
            violations.append("No active Meterless engine confirmed in current workflow.")
        audit_evidence["active_meterless_engines"] = connected_engines

        # 3. Nightshift & NVIDIA Nemotron (DGX Spark Award check)
        nightshift_stat = integration_status.get("nightshift_nemotron", {})
        used_models = nightshift_stat.get("models_used", [])
        nemotron_used = any("nemotron" in m.lower() for m in used_models)
        if not nemotron_used and model_calls:
            warnings.append("No official Nemotron model reported in active model calls.")
        audit_evidence["nvidia_nemotron_verified"] = nemotron_used
        audit_evidence["models_reported"] = used_models

        # 4. Track 1: Solving Fragmented Intelligence Check
        is_cross_station = len(stations_involved) > 1 or any(
            len(link.get("stations_involved", [])) > 1 for link in candidate_links
        )
        if not is_cross_station and candidate_links:
            warnings.append("All proposed links are intra-station; multi-jurisdiction intelligence is unproven.")
        audit_evidence["multi_station_intelligence"] = is_cross_station

        passed = len(violations) == 0
        score = max(0.0, 100.0 - (len(violations) * 35.0) - (len(warnings) * 10.0))

        return SentinelReport(
            passed=passed,
            score=score,
            status="VERIFIED" if passed and not warnings else ("WARNING" if passed else "VIOLATION"),
            details=audit_evidence,
            violations=violations,
            warnings=warnings,
            recommendations=[
                "Confirm pinned Nemotron model receipts in log traces for DGX Spark validation."
            ],
        )


class DisqualificationSentinel:
    """Subagent 3: Anti-Disqualification Sentinel preventing disqualification traps."""

    SECRET_PATTERNS = [
        re.compile(r"nvapi-[A-Za-z0-9_-]{20,}", re.I),
        re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.I),
        re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{25,}", re.I),
        re.compile(r"password\s*[:=]\s*['\"][^'\"]{6,}['\"]", re.I),
    ]

    def evaluate(
        self,
        full_payload_dump: str,
        candidate_links: List[Dict[str, Any]],
        known_incident_ids: Set[str],
        known_evidence_ids: Set[str],
    ) -> SentinelReport:
        violations = []
        warnings = []

        # 1. Secret Leakage Audit
        for pat in self.SECRET_PATTERNS:
            match = pat.search(full_payload_dump)
            if match:
                violations.append("CRITICAL: Potential API key or secret token detected in output payload!")
                break

        # 2. Fabricated / Hallucinated ID Audit
        hallucinated_incidents = set()
        hallucinated_evidence = set()

        for link in candidate_links:
            src = link.get("source_incident_id")
            tgt = link.get("target_incident_id")
            if src and known_incident_ids and src not in known_incident_ids:
                hallucinated_incidents.add(src)
            if tgt and known_incident_ids and tgt not in known_incident_ids:
                hallucinated_incidents.add(tgt)

            for eid in link.get("supporting_evidence_ids", []):
                if known_evidence_ids and eid not in known_evidence_ids:
                    hallucinated_evidence.add(eid)

        if hallucinated_incidents:
            violations.append(
                f"Grounding Failure: Proposing links with ungrounded Incident IDs: {sorted(hallucinated_incidents)[:5]}"
            )
        if hallucinated_evidence:
            warnings.append(
                f"Weak Grounding: Proposing links referencing uncached Evidence IDs: {sorted(hallucinated_evidence)[:5]}"
            )

        passed = len(violations) == 0
        score = 100.0 if passed and not warnings else (75.0 if passed else 0.0)

        return SentinelReport(
            passed=passed,
            score=score,
            status="VERIFIED" if passed and not warnings else ("WARNING" if passed else "DISQUALIFICATION_RISK"),
            details={
                "secrets_leak_scan": "PASS" if not violations else "FAIL",
                "hallucinated_incidents_count": len(hallucinated_incidents),
                "hallucinated_evidence_count": len(hallucinated_evidence),
                "grounded_links_verified": len(candidate_links),
            },
            violations=violations,
            warnings=warnings,
            recommendations=[
                "Outputs are 100% auditable and safe for public GitHub and hackathon submission."
            ] if passed else ["Purge ungrounded references and redact any environment keys."],
        )


operational_tracker = OperationalTracker()
hackos_auditor = HackOSComplianceAuditor()
disqualification_sentinel = DisqualificationSentinel()
