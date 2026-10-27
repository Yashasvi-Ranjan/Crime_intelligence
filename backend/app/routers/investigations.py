"""
Investigations and Agent Intelligence API Router
================================================
Endpoints:
- POST /api/investigations/analyze: Multi-agent cross-station investigation
- GET  /api/investigations/samples: List available offline sample scenarios
- GET  /api/ai/diagnostic: Live diagnostic check for Nightshift + Nemotron
- GET  /api/engine/health: Live health check for Meterless World Model
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.config import settings
from app.schemas import (
    AIDiagnosticResponse,
    EngineHealthResponse,
    InvestigationRequest,
    InvestigationResponse,
)
from app.services.investigation_workflow import investigation_workflow
from app.services.meterless_service import meterless_service
from app.services.nightshift_client import (
    NightshiftAuthError,
    NightshiftClient,
    NightshiftNotConfiguredError,
    NightshiftQueryError,
    NightshiftTimeoutError,
)
from app.services.sample_scenarios import SAMPLE_SCENARIOS, get_sample_investigation
from app.services.trace_logger import TraceLogger
from app.services.zetaris_adapter import (
    ZetarisAuthError,
    ZetarisConnectionError,
    ZetarisNotConfiguredError,
    ZetarisQueryError,
)

logger = logging.getLogger(__name__)


class TraceEvent(BaseModel):
    timestamp: str
    phase: str
    agent: str
    model: str
    receipt_id: str
    details: Dict[str, Any] = {}


class InvestigationTraceResponse(BaseModel):
    run_id: str
    events: List[TraceEvent]
    total_events: int


router = APIRouter(prefix="/api", tags=["Investigations & AI Intelligence"])
ai_client = NightshiftClient(settings)


@router.post(
    "/investigations/analyze",
    response_model=InvestigationResponse,
    summary="Run Cross-Station Investigative Reasoning",
    description=(
        "Executes a multi-agent investigation across North, Central, and Riverside stations. "
        "When live, retrieves records via Zetaris SQL, shares state via Meterless World Model, "
        "and reasons via Nightshift (NVIDIA Nemotron). If sample_mode=true is specified, "
        "runs the same agent loop offline over local sample data with recorded model responses (labelled in the trace); "
        "demo_content=true returns a pre-built demo scenario instead."
    ),
)
async def analyze_investigation(req: InvestigationRequest) -> InvestigationResponse:
    # 1a. Demo content: pre-built scenarios, clearly labelled, nothing executes. Only on explicit request.
    if req.demo_content:
        logger.info("Returning DEMO CONTENT (scenario: %s); no agents run", req.scenario_id)
        return InvestigationResponse(**get_sample_investigation(req.scenario_id, req.query))

    # 1b. Sample mode: the real Planner/Finder/Skeptic/verifier/Reporter loop over local data, offline.
    use_sample_mode = req.sample_mode if req.sample_mode is not None else settings.sample_mode
    if use_sample_mode:
        logger.info("Executing investigation in SAMPLE MODE (real loop, local data, replayed model responses)")
        from app.services.run_service import run_workflow
        return InvestigationResponse(**run_workflow(
            sample=True, query=req.query, incident_ids=req.incident_ids, station_ids=req.station_ids, crime_type=req.crime_type,
            date_from=req.date_from, date_to=req.date_to, continue_from=req.continue_from))

    # 2. Live Mode Pre-flight Checks (Strict: Never silently fall back to sample data)
    if not settings.zetaris_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Zetaris integration is NOT CONFIGURED. Live investigations require active Zetaris NDP. "
                "Set ZETARIS_ENABLED=true in backend/.env or select Sample Mode for demonstration."
            ),
        )

    if not settings.nightshift_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Nightshift AI provider is NOT CONFIGURED. Live investigations require Nightshift on port 8088. "
                "Ensure Nightshift is running and NIGHTSHIFT_BASE_URL is set, or enable Sample Mode."
            ),
        )

    # 3. Execute multi-agent workflow
    try:
        res = investigation_workflow.run_investigation(
            query=req.query,
            incident_ids=req.incident_ids,
            station_ids=req.station_ids,
            crime_type=req.crime_type,
            date_from=req.date_from,
            date_to=req.date_to,
            continue_from=req.continue_from,
        )
        return InvestigationResponse(**res)
    except ZetarisNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Zetaris configuration error: {exc}",
        )
    except (ZetarisConnectionError, ZetarisQueryError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Zetaris SQL query failed: {exc}",
        )
    except (NightshiftNotConfiguredError, NightshiftAuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Nightshift AI provider error: {exc}",
        )
    except NightshiftTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Nightshift AI request timed out: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during investigation analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation analysis failed: {exc}",
        )


@router.get(
    "/investigations/samples",
    summary="List Available Offline Sample Scenarios",
    description="Returns metadata and queries for the 3 documented multi-station sample scenarios.",
)
async def list_sample_scenarios() -> List[Dict[str, Any]]:
    samples = []
    for sc_id, sc in SAMPLE_SCENARIOS.items():
        samples.append({
            "scenario_id": sc_id,
            "title": sc["title"],
            "query": sc["query"],
            "target_stations": sc["target_stations"],
            "crime_type": sc["crime_type"],
            "incidents_count": len(sc["candidate_incidents"]),
            "links_count": len(sc["candidate_links"]),
        })
    return samples


def generate_sample_trace_events(run_id: str) -> List[Dict[str, Any]]:
    # Map scenario if run_id indicates one
    scenario_id = (
        run_id.replace("sample-", "")
        if run_id.startswith("sample-")
        else "crowbar_safe_cracking"
    )
    sc = SAMPLE_SCENARIOS.get(scenario_id, SAMPLE_SCENARIOS["crowbar_safe_cracking"])
    stations = sc.get("target_stations", ["NORTH", "CENTRAL"])

    base_time = 1747365300.0  # reference epoch

    events = [
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_time)),
            "phase": "planning",
            "agent": "planner",
            "model": "",
            "receipt_id": "",
            "details": {
                "demo_content": True,
                "step": "intent_and_partitioning",
                "target_stations": stations,
                "crime_type": sc.get("crime_type", "BURGLARY"),
                "query": sc.get("query"),
                "meterless_engine": "scout_intent",
                "action": "cross_station_decomposition",
                "notes": "Partitioned search space across jurisdictions to uncover fragmented syndicate MO",
            },
        },
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_time + 4)),
            "phase": "retrieval",
            "agent": "finder",
            "model": "",
            "receipt_id": "",
            "details": {
                "demo_content": True,
                "step": "federated_sql_pushdown",
                "tables_queried": [
                    "police_incidents",
                    "forensic_reports",
                    "cctv_reports",
                    "witness_reports",
                    "newspaper_reports",
                ],
                "candidate_incidents_found": len(sc.get("candidate_incidents", [])),
                "meterless_engine": "world_model",
                "records_correlated": [
                    inc["incident_id"] for inc in sc.get("candidate_incidents", [])
                ],
            },
        },
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_time + 12)),
            "phase": "adversarial_critique",
            "agent": "skeptic",
            "model": "",
            "receipt_id": "",
            "details": {
                "demo_content": True,
                "step": "adversarial_grounding_audit",
                "unsupported_claims_rejected": 0,
                "contradictions_evaluated": sc.get("contradictions_and_limitations", [])[:2],
                "skeptic_status": "CLEARED_GROUNDED",
                "grounding_ratio": 1.0,
                "meterless_engine": "h_mem",
                "decision": "All candidate links verified directly against Zetaris virtual records with zero hallucinated IDs",
            },
        },
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_time + 16)),
            "phase": "dossier_synthesis",
            "agent": "reporter",
            "model": "",
            "receipt_id": "",
            "details": {
                "demo_content": True,
                "step": "court_dossier_compilation",
                "dossier_ready": True,
                "facts_grounded_count": len(sc.get("candidate_links", [{}])[0].get("supporting_evidence_ids", [])),
                "unsupported_claims_count": 0,
                "meterless_engine": "markovian",
                "action": "finalize_intelligence_dossier",
            },
        },
    ]
    return events


@router.get(
    "/investigations/{run_id}/trace",
    response_model=InvestigationTraceResponse,
    summary="Retrieve Structured Investigation Execution Trace",
    description=(
        "Retrieves chronological multi-agent execution events for the specified run_id. "
        "Reads from logs/trace-{run_id}.jsonl or in-memory trace logger. If in sample mode or "
        "not yet flushed, returns structured execution events with verifiable receipt IDs and model lanes."
    ),
)
async def get_investigation_trace(run_id: str) -> InvestigationTraceResponse:
    tracer = TraceLogger(run_id)
    raw_events = tracer.get_events()

    formatted_events: List[TraceEvent] = []

    if raw_events:
        for idx, ev in enumerate(raw_events):
            iso_time = ev.get("iso_time")
            if not iso_time and "timestamp" in ev:
                try:
                    iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ev["timestamp"])))
                except Exception:
                    iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if not iso_time:
                iso_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            provider_meta = ev.get("provider_meta") or {}
            # Only what the trace file recorded: no default model and no invented receipt. A step that made no
            # Nightshift call (routing, retrieval, verification, engine ops) has an empty model and receipt.
            model_name = provider_meta.get("reported_model") or ev.get("model") or ""
            agent_name = ev.get("agent") or "system"
            receipt_id = provider_meta.get("receipt_id") or ev.get("receipt_id") or ""
            details = dict(ev.get("details") or {})
            if provider_meta:
                details.update({"latency_ms": provider_meta.get("latency_ms"), "source": provider_meta.get("source"),
                                "requested_model": provider_meta.get("requested_model"),
                                "fallback_reason": provider_meta.get("fallback_reason")})
            if ev.get("engine_meta"):
                details["engine"] = ev["engine_meta"]
            if ev.get("sql_meta"):
                details["sql"] = ev["sql_meta"]
            details["status"] = ev.get("status")
            if ev.get("error"):
                details["error"] = ev["error"]

            formatted_events.append(
                TraceEvent(
                    timestamp=iso_time,
                    phase=ev.get("step") or ev.get("phase") or "execution",
                    agent=agent_name,
                    model=model_name,
                    receipt_id=receipt_id,
                    details=details,
                )
            )

    if not formatted_events and run_id.startswith("sample-"):
        # Only the pre-built DEMO scenarios have no trace file; their events are labelled demo_content and carry no receipt.
        formatted_events = [TraceEvent(**ev) for ev in generate_sample_trace_events(run_id)]

    return InvestigationTraceResponse(
        run_id=run_id,
        events=formatted_events,
        total_events=len(formatted_events),
    )


@router.get(
    "/ai/diagnostic",
    response_model=AIDiagnosticResponse,
    summary="Test Nightshift + NVIDIA Nemotron Connectivity",
    description=(
        "Executes a restricted diagnostic request through Nightshift to verify model routing, "
        "reporting model identifier and latency without exposing credentials."
    ),
)
async def ai_diagnostic() -> AIDiagnosticResponse:
    diag = ai_client.diagnostic_check()
    return AIDiagnosticResponse(**diag)


@router.get(
    "/models/registry",
    summary="Nemotron role -> model registry (verified against Nightshift)",
    description="Reports each role's configured model, whether Nightshift lists it, the effective model and fallback. "
                "probe=true makes one real /v1/embeddings call.",
)
async def model_registry_report(probe: bool = Query(False)) -> Dict[str, Any]:
    return investigation_workflow._registry.report(probe=probe)


@router.get(
    "/engines/health",
    summary="Health of all four Meterless Engines",
    description="Runs one real operation per engine (World Model init/stats, Scout detect, H-MEM stats, Markovian config validation).",
)
async def engines_health() -> Dict[str, Any]:
    from app.services.meterless_engines import EngineUnavailableError, HMemService, MarkovianService, ScoutIntentService

    out: Dict[str, Any] = {"world_model": meterless_service.health_check()}
    for name, fn in (("scout_intent", lambda: ScoutIntentService().selftest()),
                     ("h_mem", lambda: HMemService().stats()),
                     ("markovian", lambda: MarkovianService().validate())):
        try:
            _, op = fn()
            out[name] = {**op.as_dict(), "status": "connected"}
        except EngineUnavailableError as exc:
            out[name] = {"status": "engine_unavailable", "message": str(exc)}
    return out


@router.get(
    "/engine/health",
    response_model=EngineHealthResponse,
    summary="Meterless World Model Engine Health",
    description="Probes the local Meterless Engine Node runner and reports schema version and storage status.",
)
async def engine_health() -> EngineHealthResponse:
    h = meterless_service.health_check()
    return EngineHealthResponse(**h)
