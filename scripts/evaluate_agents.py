#!/usr/bin/env python3
"""
Evaluate the iterative multi-agent system (AEGIS pipeline) against the Lightning-only baseline.

Two clearly separated modes (exactly one is required):

  --live              Real Nemotron through Nightshift and the production retrieval path (live Zetaris).
                      Requires credentials; fails fast with a clear message when they are absent.
                      Protocol: evaluation/PREREGISTRATION.md. Default case set: held-out.
  --offline-standin   Scripted, model-free stand-in (OfflineModelRegistry + local data adapter). Tests the
                      pipeline, verifier and scoring only. Stamped "NOT A MODEL BENCHMARK"; it never emits
                      receipts or model names, because it calls no model.

Ground truth (data/evaluation/ground_truth.json) is read ONLY here and in evaluation/harness.py, for scoring;
the application never loads it. Every output file carries a provenance stamp (mode, git commit, case-set
hash, date, models actually called).

Usage:
  python scripts/evaluate_agents.py --live [--case-set heldout|dev|all] [--cases ID,ID] [--out PATH] [--skip-baseline]
  python scripts/evaluate_agents.py --offline-standin [--case-set all] [--out evaluation/results.json]
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
LAUNCH_DIR = Path.cwd()      # --out is relative to where the user ran the script, not backend/
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
os.chdir(ROOT / "backend")   # Settings reads backend/.env relative to the working directory

from app.config import settings  # noqa: E402
from evaluation import harness  # noqa: E402
from app.services.agents import (  # noqa: E402
    Fact,
    FinderLink,
    FinderOutput,
    Hypothesis,
    Objection,
    PlannerDecision,
    ReportOutput,
    RetrievalRequest,
    SharedAttribute,
    SkepticReview,
)
from app.services.evidence_verifier import (  # noqa: E402
    EvidenceIndex,
    cluster_independent,
    detect_contradictions,
    verify_link,
)
from app.services.investigation_workflow import InvestigationWorkflow  # noqa: E402
from app.services.legacy_pipeline_workflow import LegacyInvestigationWorkflow  # noqa: E402
from app.services.meterless_engines import (  # noqa: E402
    EngineOp,
    HMemService,
    MarkovianService,
    ScoutIntentService,
)
from app.services.model_registry import CallRecord, ModelRegistry  # noqa: E402
from app.services.nightshift_client import (  # noqa: E402
    NightshiftClient,
    NightshiftNotConfiguredError,
    NightshiftResponse,
)
from app.services.zetaris_investigation_service import ZetarisInvestigationService  # noqa: E402

ID_RE = re.compile(r"\b(?:INC-[A-Z]+-\d+|CCTV-\d+|WIT-\d+|FOR-\d+|EVD-\d+|NEWS-\d+)\b")


# ── Offline Local Fallbacks for Offline / CI Environments ────────────────────


class OfflineZetarisDataService:
    """
    Offline local table adapter that queries data/generated/ JSON files
    when Zetaris NDP is not configured or offline.
    """

    def __init__(self, data_dir: Path) -> None:
        self.incidents: List[Dict[str, Any]] = json.loads((data_dir / "police_incidents.json").read_text(encoding="utf-8"))
        self.forensics: List[Dict[str, Any]] = json.loads((data_dir / "forensic_reports.json").read_text(encoding="utf-8"))
        self.cctv: List[Dict[str, Any]] = json.loads((data_dir / "cctv_reports.json").read_text(encoding="utf-8"))
        self.witness: List[Dict[str, Any]] = json.loads((data_dir / "witness_reports.json").read_text(encoding="utf-8"))
        self.newspaper: List[Dict[str, Any]] = json.loads((data_dir / "newspaper_reports.json").read_text(encoding="utf-8"))
        self.inc_by_id: Dict[str, Dict[str, Any]] = {i["incident_id"]: i for i in self.incidents}
        self.query_count: int = 0
        self.errors: List[str] = []

    def search_candidate_incidents(
        self,
        keywords: Optional[List[str]] = None,
        crime_types: Optional[List[str]] = None,
        station_ids: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        self.query_count += 1
        res = self.incidents
        if station_ids:
            st_set = {s.upper() for s in station_ids}
            res = [i for i in res if i.get("station_id") in st_set]
        if crime_types:
            ct_set = {c.upper() for c in crime_types}
            res = [i for i in res if i.get("crime_type") in ct_set]
        if keywords:
            clean_kw = [k.lower() for k in keywords if len(k) >= 3]
            if clean_kw:
                res = [
                    i for i in res
                    if any(k in (i.get("method_description") or "").lower() or
                           any(k in str(p).lower() for p in (i.get("property_involved") or []))
                           for k in clean_kw)
                ]
        return res[:limit]

    def get_incidents_by_ids(self, incident_ids: List[str]) -> List[Dict[str, Any]]:
        self.query_count += 1
        return [self.inc_by_id[i] for i in incident_ids if i in self.inc_by_id]

    def get_incidents_by_locations(self, location_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        self.query_count += 1
        loc_set = set(location_ids)
        return [i for i in self.incidents if i.get("location_id") in loc_set][:limit]

    def retrieve_supporting_evidence(
        self,
        incident_ids: List[str],
        location_ids: List[str],
        limit_per_source: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        self.query_count += 4
        inc_set = set(incident_ids)
        loc_set = set(location_ids)
        direct_limit = min(24, limit_per_source * max(1, (len(incident_ids) + 1) // 2))
        context_limit = max(2, limit_per_source // 2)

        ev: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Forensic reports
        dir_f = [dict(f, link_basis="direct_reference") for f in self.forensics if f.get("incident_id") in inc_set]
        loc_f = [dict(f, link_basis="location_proximity") for f in self.forensics if f.get("location_id") in loc_set and f.get("incident_id") not in inc_set]
        ev["forensic_reports"] = dir_f[:direct_limit] + loc_f[:context_limit]

        # 2. CCTV reports
        dir_c = [dict(c, link_basis="direct_reference") for c in self.cctv if set(c.get("related_incident_ids") or []) & inc_set]
        loc_c = [dict(c, link_basis="location_proximity") for c in self.cctv if c.get("location_id") in loc_set and not (set(c.get("related_incident_ids") or []) & inc_set)]
        ev["cctv_reports"] = dir_c[:direct_limit] + loc_c[:context_limit]

        # 3. Witness reports
        dir_w = [dict(w, link_basis="direct_reference") for w in self.witness if set(w.get("related_incident_ids") or []) & inc_set]
        loc_w = [dict(w, link_basis="location_proximity") for w in self.witness if w.get("location_id") in loc_set and not (set(w.get("related_incident_ids") or []) & inc_set)]
        ev["witness_reports"] = dir_w[:direct_limit] + loc_w[:context_limit]

        # 4. Newspaper reports
        dir_n = [dict(n, link_basis="direct_reference") for n in self.newspaper if set(n.get("related_incident_ids") or []) & inc_set]
        loc_n = [dict(n, link_basis="location_proximity") for n in self.newspaper if (set(n.get("mentioned_location_ids") or []) & loc_set) and not (set(n.get("related_incident_ids") or []) & inc_set)]
        ev["newspaper_reports"] = dir_n[:direct_limit] + loc_n[:context_limit]

        return ev


class OfflineScout(ScoutIntentService):
    """Offline adapter for Scout Intent when Nightshift app JS files are not present."""

    def detect(self, text: str) -> Tuple[Dict[str, Any], EngineOp]:
        return {
            "mode": "DEFAULT",
            "score": 0.95,
            "tierHint": "A",
            "ms": 1.0,
            "registrySize": 142,
            "candidates": [],
        }, EngineOp("scout", "detect", "ok", 1.0)

    def selftest(self) -> Tuple[Dict[str, Any], EngineOp]:
        return {"maxMs": 1.0, "registrySize": 142}, EngineOp("scout", "selftest", "ok", 1.0)


class OfflineHMem(HMemService):
    """Offline adapter for H-MEM when Nightshift app JS files are not present."""

    def retrieve(self, prompt: str, k: int = 3) -> Tuple[List[Dict[str, Any]], EngineOp]:
        return [], EngineOp("hmem", "retrieve", "ok", 1.0)

    def store_verified_summary(
        self,
        prompt: str,
        summary: str,
        confidence: float,
        model: str,
        receipt_id: Optional[str],
        verified_ids: List[str],
    ) -> Tuple[bool, EngineOp]:
        return True, EngineOp("hmem", "mine", "ok", 1.0)

    def stats(self) -> Tuple[Dict[str, Any], EngineOp]:
        return {"entries": 0}, EngineOp("hmem", "stats", "ok", 1.0)


class OfflineMarkovian(MarkovianService):
    """Offline adapter for Markovian when Nightshift app JS files are not present."""

    def validate(self) -> Tuple[Dict[str, Any], EngineOp]:
        return self.chunk_config(), EngineOp("markovian", "validate", "ok", 1.0)

    def checkpoint(self, st: Any) -> Tuple[str, EngineOp]:
        return self.carryover_text(st)[:800], EngineOp("markovian", "extract_carryover", "ok", 1.0)

    def continuation_prompt(self, goal: str, carryover: str) -> Tuple[str, EngineOp]:
        return f"{goal}\n\n{carryover}", EngineOp("markovian", "build_prompt", "ok", 1.0)

    def efficiency(self, tokens: List[int]) -> Tuple[Dict[str, Any], EngineOp]:
        return {"compression_ratio": 1.0}, EngineOp("markovian", "efficiency", "ok", 1.0)


class OfflineModelRegistry(ModelRegistry):
    """
    SCRIPTED stand-in for the model registry. Hand-written planner/finder/skeptic/reporter logic over
    data/generated; NO model is called. It therefore reports no model name, provider or receipt id.
    """

    STANDIN_NAME = "scripted-standin"

    def __init__(self, cfg: Any, data_service: OfflineZetarisDataService) -> None:
        super().__init__(cfg)
        self._data_service = data_service

    def catalog(self, refresh: bool = False) -> List[str]:
        return [self.STANDIN_NAME]

    def generate(
        self,
        role: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1200,
        temperature: float = 0.2,
        timeout_seconds: Optional[float] = None,
    ) -> Tuple[NightshiftResponse, CallRecord]:
        user_content = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        model = self.STANDIN_NAME

        content = ""
        if role == "planner":
            inc_ids = list(dict.fromkeys(re.findall(r"INC-[A-Z]+-\d{3,5}", user_content)))
            if "i1:retrieved" in user_content or "iteration: 2" in user_content.lower() or "iteration 2" in user_content.lower():
                plan = PlannerDecision(
                    action="conclude",
                    rationale="Retrieved records establish sufficient evidentiary domain across precincts.",
                    evidence_needed=[],
                    retrieval_requests=[],
                    outstanding_questions=[],
                )
            else:
                plan = PlannerDecision(
                    action="retrieve",
                    rationale="Retrieve target incident records and supporting forensic, CCTV, and witness evidence.",
                    evidence_needed=["forensic_reports", "cctv_reports", "witness_reports", "newspaper_reports"],
                    retrieval_requests=[
                        RetrievalRequest(
                            kind="by_incident_ids",
                            incident_ids=inc_ids,
                            reason="retrieve specific case incidents",
                        )
                    ] if inc_ids else [],
                    outstanding_questions=[],
                )
            content = plan.model_dump_json()

        elif role == "finder":
            try:
                data_str = user_content.split("\n\nPropose cross-station links")[0]
                prompt_data = json.loads(data_str)
                prompt_incidents = prompt_data.get("incidents", [])
                candidate_incs = [i for i in prompt_incidents if i.get("incident_id")]
                prompt_ev = prompt_data.get("evidence", {})
            except Exception:
                inc_matches = list(dict.fromkeys(re.findall(r"INC-[A-Z]+-\d{3,5}", user_content)))
                candidate_incs = [self._data_service.inc_by_id[i] for i in inc_matches if i in self._data_service.inc_by_id]
                prompt_ev = {}

            forensic_pool = prompt_ev.get("forensic_reports") or self._data_service.forensics
            cctv_pool = prompt_ev.get("cctv_reports") or self._data_service.cctv
            news_pool = prompt_ev.get("newspaper_reports") or self._data_service.newspaper

            links: List[FinderLink] = []

            for pair in itertools.combinations(candidate_incs, 2):
                ia, ib = pair
                id_a, id_b = ia["incident_id"], ib["incident_id"]

                # Exclude forensic reports with EXCLUSION status (e.g. decoys)
                fa_list = [f for f in forensic_pool if f.get("incident_id") == id_a and f.get("result_status") != "EXCLUSION"]
                fb_list = [f for f in forensic_pool if f.get("incident_id") == id_b and f.get("result_status") != "EXCLUSION"]

                ev_ids: List[str] = []
                shared_attrs: List[SharedAttribute] = []

                # 1. Forensic toolmark / chemical / digital matching
                for fa in fa_list:
                    for fb in fb_list:
                        comp_a = set(fa.get("compared_evidence_ids") or [])
                        comp_b = set(fb.get("compared_evidence_ids") or [])
                        item_a = fa.get("evidence_item_id")
                        item_b = fb.get("evidence_item_id")
                        if (item_b and item_b in comp_a) or (item_a and item_a in comp_b) or (
                            fa.get("evidence_type") == fb.get("evidence_type")
                            and fa.get("result_status") == "MATCH_CONFIRMED"
                            and fb.get("result_status") == "MATCH_CONFIRMED"
                        ):
                            ev_ids.extend([fa["evidence_report_id"], fb["evidence_report_id"]])
                            val = (fa.get("evidence_type") or "toolmark").lower()
                            shared_attrs.append(SharedAttribute(
                                attribute="forensic_match",
                                value=val,
                                match_type="exact",
                                source_ids=[fa["evidence_report_id"], fb["evidence_report_id"]],
                            ))

                # 2. Newspaper co-occurrence
                for n in news_pool:
                    rel = set(n.get("related_incident_ids") or [])
                    if id_a in rel and id_b in rel:
                        ev_ids.append(n["news_id"])
                        hw = n["headline"].split()
                        shared_attrs.append(SharedAttribute(
                            attribute="news_coverage",
                            value=hw[0].lower() if hw else "theft",
                            match_type="exact",
                            source_ids=[n["news_id"]],
                        ))

                # 3. Surveillance CCTV partial plate matching
                ca_list = [c for c in cctv_pool if id_a in (c.get("related_incident_ids") or [])]
                cb_list = [c for c in cctv_pool if id_b in (c.get("related_incident_ids") or [])]
                for ca in ca_list:
                    for cb in cb_list:
                        if ca.get("partial_plate") and ca.get("partial_plate") == cb.get("partial_plate"):
                            ev_ids.extend([ca["cctv_report_id"], cb["cctv_report_id"]])
                            shared_attrs.append(SharedAttribute(
                                attribute="vehicle_plate",
                                value=ca["partial_plate"],
                                match_type="exact",
                                source_ids=[ca["cctv_report_id"], cb["cctv_report_id"]],
                            ))

                # 4. Transitive syndicate link for vehicle theft series (e.g. REL-SERIES-002 plate 88M***)
                if not ev_ids and ia.get("crime_type") == ib.get("crime_type") and ia.get("crime_type") == "VEHICLE_THEFT":
                    plate_matches = [c["cctv_report_id"] for c in ca_list + cb_list if "88M***" in str(c.get("partial_plate"))]
                    if plate_matches:
                        ev_ids.extend(plate_matches)
                        shared_attrs.append(SharedAttribute(
                            attribute="vehicle_plate",
                            value="88M***",
                            match_type="exact",
                            source_ids=plate_matches,
                        ))

                if ev_ids:
                    dedup_ev = list(dict.fromkeys(ev_ids))
                    st_inv = sorted(list({ia["station_id"], ib["station_id"]}))
                    links.append(FinderLink(
                        link_id=f"LINK-{len(links)+1:02d}",
                        source_incident_id=id_a,
                        target_incident_id=id_b,
                        stations_involved=st_inv,
                        similarity_basis=f"Corroborated evidence linking {id_a} and {id_b} across {st_inv}.",
                        shared_attributes=shared_attrs,
                        differences=[],
                        missing_evidence=[],
                        supporting_evidence_ids=dedup_ev,
                        quotes=[],
                        heuristic_score=0.89,
                        score_note="High laboratory forensic and surveillance confidence.",
                    ))

            finder_out = FinderOutput(links=links, withdrawn_link_ids=[], notes="Multi-agent evidence discovery completed.")
            content = finder_out.model_dump_json()

        elif role == "skeptic":
            objections: List[Objection] = []
            if "sedan" in user_content.lower() and "minivan" in user_content.lower():
                objections.append(Objection(
                    link_id="LINK-01",
                    kind="contradiction",
                    description="Witness reported red sedan conflicting with CCTV recording of grey minivan.",
                    cited_ids=["WIT-0105"],
                    severity="medium",
                    is_missing_evidence_only=False,
                    requests_retrieval=False,
                    retrieval_hint="",
                ))
            review = SkepticReview(
                review_status="accepted_with_objections" if objections else "accepted",
                objections=objections,
                alternative_explanations=[],
                suggested_retrieval=[],
            )
            content = review.model_dump_json()

        elif role == "reporter":
            inc_matches = list(dict.fromkeys(re.findall(r"INC-[A-Z]+-\d{3,5}", user_content)))
            ev_matches = list(dict.fromkeys(re.findall(r"(?:FOR|CCTV|WIT|NEWS|EVD)-\d{3,5}", user_content)))
            facts: List[Fact] = []
            if inc_matches:
                facts.append(Fact(
                    statement=f"Cross-jurisdictional intelligence identified linkage between incidents {', '.join(inc_matches)}.",
                    source_ids=ev_matches[:4] if ev_matches else inc_matches[:2],
                ))
            report = ReportOutput(
                title="Cross-Station Crime Intelligence Dossier",
                executive_summary="Multi-jurisdiction intelligence synthesis identifying corroborated investigative links across police precincts.",
                facts=facts,
                hypotheses=[Hypothesis(statement="Suspect syndicate operating across multiple jurisdiction sectors", link_id="LINK-01")],
                similarities=["Matching forensic signatures and surveillance descriptions"],
                differences=[],
                contradictions_and_limitations=["All identified links represent investigatory leads requiring operational follow-up."],
                unresolved_questions=[],
                follow_up_actions=["Submit formal warrant for intermodal shipping container inspection."],
            )
            content = report.model_dump_json()

        resp = NightshiftResponse(content=content, model=model, provider="none", receipt_id=None)
        rec = CallRecord(
            role=role,
            requested_model=model,
            reported_model=None,
            provider=None,
            receipt_id=None,
            routed_as_requested=None,
            source="scripted_standin",
        )
        return resp, rec


def _offline_data_service() -> OfflineZetarisDataService:
    """Fresh local table adapter per run (stand-in only; live mode uses the production retrieval service)."""
    return OfflineZetarisDataService(ROOT / "data" / "generated")


def load_truth() -> List[Dict[str, Any]]:
    return json.loads((ROOT / "data/evaluation/ground_truth.json").read_text(encoding="utf-8"))


def dataset_ids() -> Set[str]:
    ids: Set[str] = set()
    for name, keys in {
        "police_incidents": ["incident_id"],
        "cctv_reports": ["cctv_report_id"],
        "witness_reports": ["witness_report_id"],
        "newspaper_reports": ["news_id"],
        "forensic_reports": ["evidence_report_id", "evidence_item_id"],
    }.items():
        for r in json.loads((ROOT / f"data/generated/{name}.json").read_text(encoding="utf-8")):
            ids.update(r[k] for k in keys if r.get(k))
    return ids


def select_cases(case_set: str, only: str = "") -> List[Dict[str, Any]]:
    truth = load_truth()
    incidents = json.loads((ROOT / "data/generated/police_incidents.json").read_text(encoding="utf-8"))
    cases: List[Dict[str, Any]] = []
    if case_set in ("dev", "all"):
        cases += harness.build_dev_cases(truth)
    if case_set in ("heldout", "all"):
        cases += harness.build_heldout_cases(truth, incidents)
    if only:
        want = set(only.split(","))
        cases = [c for c in cases if c["case"] in want]
    return cases


class CountingClient(NightshiftClient):
    """Real Nightshift client that logs what each call actually returned (model and receipt from the response)."""

    calls = 0
    log: List[Dict[str, Any]] = []

    def generate(self, *a, **k):
        type(self).calls += 1
        resp = super().generate(*a, **k)
        type(self).log.append({"role": "baseline", "reported_model": resp.model, "receipt_id": resp.receipt_id,
                               "provider": resp.provider, "source": "live"})
        return resp


class NoModelClient(NightshiftClient):
    """Stand-in baseline client: no model is reachable, so the legacy pipeline runs its code-only fallbacks."""

    calls = 0
    log: List[Dict[str, Any]] = []

    def generate(self, *a, **k):
        raise NightshiftNotConfiguredError("offline stand-in: no model is called")


SYSTEMS = {
    "live": {"baseline": "baseline_lightning_only", "agents": "multi_agent_nemotron"},
    "offline-standin": {"baseline": "baseline_code_fallback_only_STANDIN", "agents": "multi_agent_scripted_STANDIN"},
}
FALLBACK_MARK = "adjacent county jurisdictions"   # confidence_rationale of the legacy pipeline's code-only fallback link


def score(case: Dict[str, Any], res: Dict[str, Any], known_ids: Set[str], active_only: bool = True) -> Dict[str, Any]:
    links = [l for l in res["candidate_links"] if not l.get("withdrawn")] if active_only else res["candidate_links"]
    pairs = {harness.pair_key(l) for l in links}
    truth = case["truth_pairs"]
    verified = {harness.pair_key(l) for l in links if l.get("validation_status") in ("SUPPORTED", "WEAK")}
    false_pairs = pairs - truth

    idx = EvidenceIndex()
    idx.add_incidents(res["candidate_incidents"])
    idx.add_evidence(res["supporting_evidence"])
    # Independent re-verification of whatever each system reports.
    reverify = [verify_link({
        "link_id": l["link_id"],
        "source_incident_id": l["source_incident_id"],
        "target_incident_id": l["target_incident_id"],
        "stations_involved": l["stations_involved"],
        "supporting_evidence_ids": l["supporting_evidence_ids"],
        "shared_attributes": l.get("shared_attributes", []),
    }, idx) for l in links]
    fabricated = [l for l in links if FALLBACK_MARK in (l.get("confidence_rationale") or "")]
    # Pre-registered, system-symmetric rule: a link is "supported" iff independent re-verification says SUPPORTED.
    supported = {harness.pair_key(l) for l, v in zip(links, reverify) if v.status == "SUPPORTED"}
    no_fallback = {harness.pair_key(l) for l in links if FALLBACK_MARK not in (l.get("confidence_rationale") or "")}
    text = " ".join([res["executive_summary"], *res["contradictions_and_limitations"], *res["follow_up_actions"]])
    cited = ID_RE.findall(text) + [i for l in links for i in l["supporting_evidence_ids"]]
    cited_ok = sum(1 for i in cited if i in known_ids)
    rejected = sum(len(l.get("rejected_ids") or []) for l in res["candidate_links"])
    duplicate_links = sum(
        1 for l in links
        if cluster_independent([i for i in l["supporting_evidence_ids"] if idx.has(i)], idx, [l["source_incident_id"], l["target_incident_id"]])[1]
    )
    case_ids = [i for i in case["incident_ids"] if idx.has(i)]
    source_contradictions = detect_contradictions(
        case_ids + [i for l in links for i in l["supporting_evidence_ids"]] +
        [r.get("witness_report_id") for r in res["supporting_evidence"].get("witness_reports", []) if r.get("witness_report_id")], idx
    )
    surfaced = bool([l for l in links if l.get("contradictions")]) or any(
        re.search(r"contradict|conflict|discrepan|inconsisten|dispute|differ", x, re.I) for x in res["contradictions_and_limitations"]
    )
    return {
        "counts": harness.case_pair_counts(case, pairs, supported),
        "counts_excluding_code_fallback": harness.case_pair_counts(case, no_fallback, supported & no_fallback),
        "links_reported": len(links),
        "pairs_reported": sorted(map(sorted, pairs)),
        "valid_link_recall_proposed": round(len(pairs & truth) / len(truth), 3) if truth else None,
        "valid_link_recall_verified": round(len(verified & truth) / len(truth), 3) if truth else None,
        "false_links": len(false_pairs),
        "decoy_links": sum(1 for p in pairs if p & case["planted_decoys"]),
        "citation_accuracy_final_output": round(cited_ok / len(cited), 3) if cited else None,
        "cited_ids_final_output": len(cited),
        "raw_model_citations_rejected": rejected,
        "links_not_supported_on_reverification": sum(1 for v in reverify if v.status != "SUPPORTED"),
        "links_unsupported_on_reverification": sum(1 for v in reverify if v.status == "UNSUPPORTED"),
        "fabricated_fallback_links": len(fabricated),
        "links_citing_duplicate_reports": duplicate_links,
        "links_without_any_evidence": sum(1 for l in links if not l["supporting_evidence_ids"]),
        "source_contradictions_present": len(source_contradictions),
        "contradiction_surfaced_in_output": surfaced,
        "reports_it_reports_duplicates": any(v.duplicate_groups for v in reverify),
    }


def run_one(system: str, case: Dict[str, Any], known: Set[str], mode: str) -> Dict[str, Any]:
    t0 = time.time()
    standin = mode == "offline-standin"
    names = SYSTEMS[mode]
    CountingClient.calls = 0
    CountingClient.log = []
    out: Dict[str, Any] = {"system": system, "case": case["case"], "kind": case["kind"], "split": case["split"],
                           "call_log": []}

    # Live mode: data_service=None -> the production Zetaris retrieval path. Stand-in: local table adapter.
    data_service = _offline_data_service() if standin else None
    scout_engine = hmem_engine = markov_engine = None
    model_registry = None
    if standin:
        scout_engine, hmem_engine, markov_engine = OfflineScout(settings), OfflineHMem(settings), OfflineMarkovian(settings)
        model_registry = OfflineModelRegistry(settings, data_service)

    try:
        if system == names["baseline"]:
            client = NoModelClient(settings) if standin else CountingClient(settings)
            wf = LegacyInvestigationWorkflow(ai_client=client, data_service=data_service)
            q0 = wf._data.query_count
            res = wf.run_investigation(query=case["query"], incident_ids=case["incident_ids"])
            out.update(model_calls=0 if standin else CountingClient.calls, sql_queries=wf._data.query_count - q0)
            out["call_log"] = [] if standin else list(CountingClient.log)
        else:
            wf = InvestigationWorkflow(
                cfg=settings,
                data_service=data_service,
                registry=model_registry,
                scout=scout_engine,
                hmem=hmem_engine,
                markovian=markov_engine,
            )
            res = wf.run_investigation(query=case["query"], incident_ids=case["incident_ids"])
            out.update(
                model_calls=res["counts"]["model_calls"],
                sql_queries=res["counts"]["sql_queries"],
                iterations=res["iterations_used"],
                stopping_reason=res["stopping_reason"],
                run_status=res["run_status"],
                agent_output_failures=[f for f in res["partial_failures"] if f["component"] in ("planner", "finder", "skeptic", "reporter")],
                repaired_outputs=sum(1 for c in res["model_calls"] if c.get("status") != "ok"),
                fallback_to_lightning=any(a["fallback_used"] for a in res["agents"]),
                models={a["agent"]: a["reported_models"] for a in res["agents"]},
                skeptic_status=res["skeptic"]["review_status"],
                open_objections=sum(1 for o in res["skeptic"]["objections"] if o["open"]),
            )
            out["call_log"] = [{k: c.get(k) for k in ("role", "reported_model", "receipt_id", "provider", "source", "status")}
                               for c in res["model_calls"]]
        if standin:
            out["call_log"] = []   # the stand-in calls no model: never carry model names or receipts
            out["models"] = {}
            out["scripted_calls"] = out.pop("model_calls", 0)   # scripted steps, not model calls
        out["ok"] = True
        out["metrics"] = score(case, res, known)
    except Exception as exc:  # a failed run is data, not something to hide
        out.update(ok=False, error=f"{type(exc).__name__}: {str(exc)[:200]}")
    out["latency_s"] = round(time.time() - t0, 1)
    return out


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def mean(vals):
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    ok = [r for r in rows if r["ok"]]
    m = [r["metrics"] for r in ok]
    pos = [r["metrics"] for r in ok if r["kind"] == "positive"]
    return {
        "preregistered": harness.aggregate([r["metrics"]["counts"] for r in ok]),
        "preregistered_excluding_baseline_code_fallback": harness.aggregate(
            [r["metrics"]["counts_excluding_code_fallback"] for r in ok]),
        "runs": len(rows),
        "failed_runs": len(rows) - len(ok),
        "failure_rate": round((len(rows) - len(ok)) / len(rows), 3) if rows else None,
        "mean_latency_s": mean([r["latency_s"] for r in rows]),
        "mean_model_calls": mean([r.get("model_calls") for r in ok]),
        "mean_scripted_calls": mean([r.get("scripted_calls") for r in ok]),
        "mean_sql_queries": mean([r.get("sql_queries") for r in ok]),
        "valid_link_recall_proposed(positive cases)": mean([x["valid_link_recall_proposed"] for x in pos]),
        "valid_link_recall_verified(positive cases)": mean([x["valid_link_recall_verified"] for x in pos]),
        "false_links_total": sum(x["false_links"] for x in m),
        "decoy_links_total": sum(x["decoy_links"] for x in m),
        "citation_accuracy_final_output": mean([x["citation_accuracy_final_output"] for x in m]),
        "raw_model_citations_rejected_total": sum(x["raw_model_citations_rejected"] for x in m),
        "links_total": sum(x["links_reported"] for x in m),
        "links_not_supported_on_reverification": sum(x["links_not_supported_on_reverification"] for x in m),
        "links_unsupported_on_reverification": sum(x["links_unsupported_on_reverification"] for x in m),
        "fabricated_fallback_links": sum(x["fabricated_fallback_links"] for x in m),
        "links_citing_duplicate_reports": sum(x["links_citing_duplicate_reports"] for x in m),
        "cases_with_source_contradictions": sum(1 for x in m if x["source_contradictions_present"]),
        "of_which_surfaced_in_output": sum(1 for x in m if x["source_contradictions_present"] and x["contradiction_surfaced_in_output"]),
    }


def preflight_live() -> None:
    missing = []
    if not settings.nightshift_configured:
        missing.append("Nightshift (set NIGHTSHIFT_BASE_URL and NIGHTSHIFT_API_KEY or NIGHTSHIFT_API_KEY_FILE)")
    if not settings.zetaris_configured:
        missing.append("Zetaris (set ZETARIS_ENABLED=true, ZETARIS_BASE_URL and credentials)")
    if missing:
        sys.exit("--live requires real credentials and refuses to fall back to a stand-in. Not configured: "
                 + "; ".join(missing) + ". Use --offline-standin for a pipeline-only dry run (NOT A MODEL BENCHMARK).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true", help="real Nemotron via Nightshift + production retrieval")
    g.add_argument("--offline-standin", action="store_true", help="scripted stand-in; NOT A MODEL BENCHMARK")
    ap.add_argument("--case-set", choices=("heldout", "dev", "all"), default=None,
                    help="default: heldout for --live, all for --offline-standin")
    ap.add_argument("--cases", default="", help="comma-separated case ids to keep")
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-baseline", action="store_true")
    args = ap.parse_args()
    mode = "live" if args.live else "offline-standin"
    if args.live:
        preflight_live()
    case_set = args.case_set or ("heldout" if args.live else "all")
    out_path = args.out or str(ROOT / ("evaluation/results_live.json" if args.live else "evaluation/results.json"))
    known = dataset_ids()
    cases = select_cases(case_set, args.cases)
    names = SYSTEMS[mode]
    systems = [names["agents"]] if args.skip_baseline else [names["baseline"], names["agents"]]
    rows: List[Dict[str, Any]] = []
    for c in cases:
        for s in systems:
            print(f"[{time.strftime('%H:%M:%S')}] {s} case {c['case']} ({c['kind']}, {c['split']}) ...", flush=True)
            r = run_one(s, c, known, mode)
            print(f"   -> ok={r['ok']} latency={r['latency_s']}s {r.get('error', '')}", flush=True)
            rows.append(r)
    call_log = [x for r in rows for x in r.get("call_log", [])]
    summary: Dict[str, Any] = {}
    for split in sorted({c["split"] for c in cases}):
        summary[split] = {s: summarize([r for r in rows if r["system"] == s and r["split"] == split]) for s in systems}
    doc = {"provenance": harness.provenance(mode, case_set, cases, call_log), "cases": len(cases),
           "summary": summary, "rows": rows}
    out_file = Path(out_path) if Path(out_path).is_absolute() else LAUNCH_DIR / out_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"provenance": doc["provenance"], "summary": summary}, indent=1, default=str))


if __name__ == "__main__":
    main()
