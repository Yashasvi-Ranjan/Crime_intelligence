"""
Judge entry point: ``POST /run`` and ``GET /health``.

``POST /run``   body {run_id?, input: {...}, options: {sample_mode?}} -> the investigation workflow.
``GET /health`` alias of /api/health that reports each integration as live, sample or down.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import __version__
from app.config import settings
from app.services.meterless_engines import ENGINE_FILES, resolve_engine_backend
from app.services.run_service import run_investigation

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Run"])


class RunInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query: str = Field(min_length=1, max_length=2000)
    incident_ids: Optional[List[str]] = None
    station_ids: Optional[List[str]] = None
    crime_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    continue_from: Optional[str] = None


class RunOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sample_mode: Optional[bool] = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")   # becomes a log file name
    input: RunInput
    options: RunOptions = Field(default_factory=RunOptions)


class RunResponse(BaseModel):
    run_id: str
    status: Optional[str]
    output: Dict[str, Any]
    agents: List[Dict[str, Any]]
    engines: List[Dict[str, Any]]
    trace_id: str
    log_file: str
    execution_time_seconds: float


@router.post("/run", response_model=RunResponse, summary="Run one cross-station investigation")
def run(req: RunRequest) -> RunResponse:
    try:
        return RunResponse(**run_investigation(req.run_id, req.input.model_dump(), req.options.sample_mode))
    except Exception as exc:
        logger.exception("POST /run failed")
        raise HTTPException(status_code=500, detail=f"Investigation failed: {type(exc).__name__}: {exc}")


def _probe(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """None if the endpoint answered with any HTTP response within 1 s, else why not."""
    try:
        httpx.get(url, headers=headers, timeout=1.0)
        return None
    except httpx.HTTPError as exc:
        return type(exc).__name__


def integration_health() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if settings.sample_mode:
        out["zetaris"] = {"state": "sample", "detail": "SAMPLE_MODE=true: local data over data/generated, no network"}
        out["nightshift"] = {"state": "sample", "detail": "SAMPLE_MODE=true: recorded responses replayed, no network"}
    else:
        if not settings.zetaris_configured:
            out["zetaris"] = {"state": "sample", "detail": "not configured: runs use local sample data (traced)"}
        else:
            why = _probe(settings.zetaris_base_url)
            out["zetaris"] = {"state": "down" if why else "live", "detail": why or settings.zetaris_base_url}
        if not settings.nightshift_configured:
            out["nightshift"] = {"state": "sample", "detail": "no token/URL: runs replay recorded responses (traced)"}
        else:
            why = _probe(f"{settings.nightshift_base_url.rstrip('/')}/models",
                         {"Authorization": f"Bearer {settings.resolved_nightshift_token}"})
            out["nightshift"] = {"state": "down" if why else "live", "detail": why or settings.nightshift_base_url}
    engines: Dict[str, Any] = {}
    for name in ENGINE_FILES:
        backend = resolve_engine_backend(settings, name)
        engines[name] = {"state": "down" if backend is None else "live", "backend": backend or "engine_unavailable"}
    wm = Path(settings.meterless_world_model_path).exists() and bool(shutil.which("node"))
    engines["world_model"] = {"state": "live" if wm else "down", "backend": "mounted" if wm else "engine_unavailable"}
    out["engines"] = engines
    return out


@router.get("/health", summary="Liveness plus live/sample/down state of each integration")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": __version__, "environment": settings.app_environment,
            "sample_mode": settings.sample_mode, **integration_health()}
