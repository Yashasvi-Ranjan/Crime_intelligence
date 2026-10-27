"""
Execution service behind ``POST /run``.

Builds the investigation workflow for the requested mode and maps its result onto the /run contract.

  sample   Real Planner/Finder/Skeptic/verifier/Reporter loop over data/generated (LocalInvestigationService);
           model output from recorded Nightshift fixtures (SampleModelRegistry, code-only fallback on a miss);
           H-MEM in a throwaway store so runs cannot influence each other; no network.
  live     Zetaris + Nightshift + engines as configured. Each Zetaris/Nightshift call is bounded by its
           timeout; if one is unreachable the run continues on the sample path for that integration and the
           trace and the response say so (Resilient* wrappers).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.config import Settings, settings
from app.services.investigation_workflow import InvestigationWorkflow
from app.services.meterless_engines import HMemService, MarkovianService, ScoutIntentService
from app.services.meterless_service import meterless_service
from app.services.sample_mode.fixtures import FixtureStore
from app.services.trace_logger import DEFAULT_LOGS_DIR, resolve_logs_dir, safe_trace_name
from app.services.sample_mode.local_investigation import LocalInvestigationService
from app.services.sample_mode.registries import ResilientModelRegistry, SampleModelRegistry
from app.services.sample_mode.resilient_data import ResilientInvestigationService
from app.services.zetaris_investigation_service import ZetarisInvestigationService

logger = logging.getLogger(__name__)


def build_workflow(cfg: Settings, sample: bool) -> Tuple[InvestigationWorkflow, Callable[[], None]]:
    store = FixtureStore(cfg.sample_fixture_path)
    local = LocalInvestigationService(cfg)
    if sample:
        # "reference": prompts built from engine output (Markovian) must not depend on what the host mounts.
        scfg = cfg.model_copy(update={"meterless_engine_backend": "reference"})
        tmp = Path(tempfile.mkdtemp(prefix="crime-intel-hmem-"))
        registry = SampleModelRegistry(scfg, store)
        wf = InvestigationWorkflow(
            cfg=scfg, ai_client=registry._client, world_model=meterless_service, data_service=local,
            registry=registry, scout=ScoutIntentService(scfg),
            hmem=HMemService(scfg, store_file=tmp / "hmem-knowledge.json"), markovian=MarkovianService(scfg))
        return wf, lambda: shutil.rmtree(tmp, ignore_errors=True)

    registry = ResilientModelRegistry(cfg, SampleModelRegistry(cfg, store))
    wf = InvestigationWorkflow(cfg=cfg, ai_client=registry._client, world_model=meterless_service,
                               data_service=ResilientInvestigationService(ZetarisInvestigationService(cfg), local),
                               registry=registry)
    return wf, lambda: None


def run_workflow(sample: bool, query: str, cfg: Optional[Settings] = None, run_id: Optional[str] = None, **kw: Any) -> Dict[str, Any]:
    """Run the workflow and return its native result dict (used by /api/investigations/analyze)."""
    wf, cleanup = build_workflow(cfg or settings, sample)
    try:
        return wf.run_investigation(query=query, run_id=run_id, **kw)
    finally:
        cleanup()


def _log_file(rid: str) -> str:
    d = resolve_logs_dir()
    name = f"trace-{safe_trace_name(rid)}.jsonl"
    return f"logs/{name}" if d == DEFAULT_LOGS_DIR else str(d / name)


def _engines(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    me = (res.get("integration_status") or {}).get("meterless_engines") or {}
    out: List[Dict[str, Any]] = []
    for name in ("scout_intent", "h_mem", "markovian", "world_model"):
        e = me.get(name)
        if e:
            out.append({"engine": name, "status": e.get("status"), "backend": e.get("backend", []),
                        "operations": e.get("operations", []), "calls": e.get("calls", 0)})
    return out


def run_investigation(run_id: Optional[str], payload: Dict[str, Any], sample_mode: Optional[bool],
                      cfg: Optional[Settings] = None) -> Dict[str, Any]:
    cfg = cfg or settings
    sample = cfg.sample_mode if sample_mode is None else sample_mode
    t0 = time.time()
    wf, cleanup = build_workflow(cfg, sample)
    try:
        res = wf.run_investigation(
            query=payload["query"], incident_ids=payload.get("incident_ids"), station_ids=payload.get("station_ids"),
            crime_type=payload.get("crime_type"), date_from=payload.get("date_from"), date_to=payload.get("date_to"),
            continue_from=payload.get("continue_from"), run_id=run_id)
    finally:
        cleanup()
    rid = res["investigation_id"]
    skeptic = res.get("skeptic") or {}
    return {
        "run_id": rid,
        "status": res.get("run_status"),
        "output": {
            "links": res.get("candidate_links", []),
            "report": {"title": res.get("title"), "executive_summary": res.get("executive_summary"),
                       "contradictions_and_limitations": res.get("contradictions_and_limitations", []),
                       "unresolved_questions": res.get("unresolved_questions", []),
                       "follow_up_actions": res.get("follow_up_actions", []), **(res.get("report") or {})},
            "stopping_reason": res.get("stopping_reason"),
            "summary": res.get("executive_summary"),
            "intent": res.get("intent"),
            "data_mode": res.get("data_mode"),
            "is_sample": res.get("is_sample"),
            "stations_involved": res.get("stations_involved", []),
            "candidate_incident_ids": [i.get("incident_id") for i in res.get("candidate_incidents", [])],
            "skeptic": {"review_status": skeptic.get("review_status"), "history": skeptic.get("history", [])},
            "counts": res.get("counts"),
            "partial_failures": res.get("partial_failures", []),
            "clarification": res.get("clarification"),
        },
        "agents": res.get("agents", []),
        "engines": _engines(res),
        "trace_id": rid,
        "log_file": _log_file(rid),
        "execution_time_seconds": round(time.time() - t0, 3),
    }
