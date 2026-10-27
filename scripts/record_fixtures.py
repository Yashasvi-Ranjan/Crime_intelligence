#!/usr/bin/env python3
"""
Record offline-sample fixtures from REAL live runs, and write output_examples/.

For each input_examples/example_N.json this runs the investigation LIVE (Nightshift answering every
model call; Zetaris answering retrieval unless --local-retrieval) and stores each Nightshift response under
sha256(role, model, messages) in data/sample/model_fixtures/. It then replays the example through the offline
sample path and writes that response to output_examples/example_N.json, reporting how many model calls were
served by a recorded fixture (replayed) versus the code-only fallback. Aim: 100% replayed.

  python scripts/record_fixtures.py                      # needs Zetaris + Nightshift up and configured (.env)
  python scripts/record_fixtures.py --local-retrieval    # live models, retrieval from data/generated: use this if
                                                         # live Zetaris rows format differently and prompts miss
  python scripts/record_fixtures.py --outputs-only       # no live calls: regenerate output_examples/ from the
                                                         # CURRENT sample path (whatever fixtures exist). Run it INSIDE the
                                                         # image so engine availability matches the judge's environment:
  docker run --rm -v "$PWD/output_examples:/app/output_examples" oah-submission python scripts/record_fixtures.py --outputs-only

Fixtures hold what a model said about one prompt; they never contain a whole-investigation answer and are never
keyed to an example. Review `git diff data/sample` before committing: responses are synthetic-data only.

Each live recording also writes that run's trace to submission/live_trace/<name>.live.trace.jsonl, but only if it
passes `scripts/trace_check.py --require-live` (every model call answered live by Nemotron, with a receipt id).
That file is the committable evidence of a live run; a trace with replayed or code-only calls is never written there.
Verify before committing:  python scripts/trace_check.py --fixtures && python scripts/trace_check.py --require-live submission/live_trace/*.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.services.investigation_workflow import InvestigationWorkflow  # noqa: E402
from app.services.meterless_engines import HMemService, MarkovianService, ScoutIntentService  # noqa: E402
from app.services.meterless_service import meterless_service  # noqa: E402
from app.services.run_service import run_investigation  # noqa: E402
from app.services.sample_mode.fixtures import FixtureStore  # noqa: E402
from app.services.sample_mode.local_investigation import LocalInvestigationService  # noqa: E402
from app.services.sample_mode.registries import RecordingModelRegistry  # noqa: E402
from app.services.trace_logger import resolve_logs_dir  # noqa: E402
from app.services.zetaris_investigation_service import ZetarisInvestigationService  # noqa: E402
from trace_check import check_live  # noqa: E402  (scripts/ is on sys.path when this file is run as a script)

LIVE_TRACE_DIR = ROOT / "submission" / "live_trace"


def save_live_trace(trace_file: str, name: str) -> str:
    """Copy a live run's trace into submission/live_trace/ if (and only if) it proves live Nemotron calls."""
    src = resolve_logs_dir() / trace_file
    problems = check_live(src)
    if problems:
        return f"{name}: NOT saved as a live trace: " + "; ".join(problems[:4])
    LIVE_TRACE_DIR.mkdir(parents=True, exist_ok=True)
    dst = LIVE_TRACE_DIR / f"{name}.live.trace.jsonl"
    shutil.copyfile(src, dst)
    return f"{name}: live trace saved to {dst.relative_to(ROOT)}"


def preflight(local_retrieval: bool) -> list[str]:
    import httpx

    problems = []
    if not settings.nightshift_configured:
        problems.append("Nightshift is not configured: set NIGHTSHIFT_API_KEY / NIGHTSHIFT_API_KEY_FILE (or run on the Mac with Nightshift.app).")
    else:
        try:
            httpx.get(f"{settings.nightshift_base_url.rstrip('/')}/models", timeout=5,
                      headers={"Authorization": f"Bearer {settings.resolved_nightshift_token}"}).raise_for_status()
        except httpx.HTTPError as exc:
            problems.append(f"Nightshift not reachable at {settings.nightshift_base_url}: {type(exc).__name__}")
    if not local_retrieval:
        if not settings.zetaris_configured:
            problems.append("Zetaris is not configured: set ZETARIS_ENABLED=true and credentials in .env (or pass --local-retrieval).")
        else:
            try:
                httpx.get(settings.zetaris_base_url, timeout=5)
            except httpx.HTTPError as exc:
                problems.append(f"Zetaris not reachable at {settings.zetaris_base_url}: {type(exc).__name__} (or pass --local-retrieval)")
    return problems


def record(payload: dict, store: FixtureStore, local_retrieval: bool) -> dict:
    scfg = settings.model_copy(update={"meterless_engine_backend": "reference"})   # same engine as the offline replay
    tmp = Path(tempfile.mkdtemp(prefix="crime-intel-record-"))
    registry = RecordingModelRegistry(scfg, store)
    data = LocalInvestigationService(scfg) if local_retrieval else ZetarisInvestigationService(scfg)
    wf = InvestigationWorkflow(cfg=scfg, ai_client=registry._client, world_model=meterless_service, data_service=data, registry=registry,
                               scout=ScoutIntentService(scfg), hmem=HMemService(scfg, store_file=tmp / "hmem-knowledge.json"),
                               markovian=MarkovianService(scfg))
    try:
        res = wf.run_investigation(query=payload["query"], incident_ids=payload.get("incident_ids"), station_ids=payload.get("station_ids"),
                                   crime_type=payload.get("crime_type"), date_from=payload.get("date_from"), date_to=payload.get("date_to"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"status": res["run_status"], "stopping_reason": res["stopping_reason"], "model_calls": len(res.get("model_calls", [])),
            "recorded": registry.recorded, "trace_file": res.get("trace_file")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--examples", nargs="*", type=int, default=[1, 2, 3])
    ap.add_argument("--local-retrieval", action="store_true")
    ap.add_argument("--outputs-only", action="store_true")
    ap.add_argument("--clean", action="store_true", help="delete existing fixtures first")
    ap.add_argument("--query", help="record ONE ad-hoc question (e.g. the exact request the dashboard sends) instead of the examples; "
                                    "fixtures only, no output_examples/ are written")
    ap.add_argument("--stations", nargs="*", default=None, help="station_ids for --query (e.g. NORTH CENTRAL RIVERSIDE)")
    ap.add_argument("--crime-type", default=None, help="crime_type for --query")
    a = ap.parse_args()

    store = FixtureStore(settings.sample_fixture_path)
    if not a.outputs_only:
        problems = preflight(a.local_retrieval)
        if problems:
            print("Cannot record; live services are required:\n  - " + "\n  - ".join(problems), file=sys.stderr)
            return 2
        if a.clean and store.dir.exists():
            shutil.rmtree(store.dir)

    rc = 0
    if a.query:
        payload = {"query": a.query, "station_ids": a.stations, "crime_type": a.crime_type}
        print("ad-hoc: recording live ...", flush=True)
        r = record(payload, store, a.local_retrieval)
        print(f"ad-hoc: live run {r['status']} / {r['stopping_reason']}; {r['recorded']} response(s) recorded", flush=True)
        print(save_live_trace(r["trace_file"], "adhoc"), flush=True)
        out = run_investigation(None, payload, True)
        sources: dict = {}
        for line in (ROOT / out["log_file"]).read_text().splitlines():
            pm = json.loads(line).get("provider_meta")
            if pm:
                sources[pm["source"]] = sources.get(pm["source"], 0) + 1
        print(f"ad-hoc: replay {out['status']} / {out['output']['stopping_reason']}; model calls by source: {sources or 'none'}")
        return 1 if sources.get("code_fallback") else 0
    for n in a.examples:
        payload = json.loads((ROOT / f"input_examples/example_{n}.json").read_text())["input"]
        if not a.outputs_only:
            print(f"example_{n}: recording live ...", flush=True)
            r = record(payload, store, a.local_retrieval)
            print(f"example_{n}: live run {r['status']} / {r['stopping_reason']}; {r['recorded']} response(s) recorded", flush=True)
            print(save_live_trace(r["trace_file"], f"example_{n}"), flush=True)
        out = run_investigation(None, payload, True)
        sources = {}
        for line in (ROOT / out["log_file"]).read_text().splitlines():
            pm = json.loads(line).get("provider_meta")
            if pm:
                sources[pm["source"]] = sources.get(pm["source"], 0) + 1
        (ROOT / "output_examples").mkdir(exist_ok=True)
        (ROOT / f"output_examples/example_{n}.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"example_{n}: replay {out['status']} / {out['output']['stopping_reason']}; model calls by source: {sources or 'none'}")
        if sources.get("code_fallback") and not a.outputs_only:
            print("  WARNING: some prompts were not served from fixtures - re-run with --local-retrieval", file=sys.stderr)
            rc = 1
    print(f"fixtures in {store.dir}: {store.count()}")
    if not a.outputs_only:
        print("\nNEXT: output_examples/ must reflect the judge's environment (no mounted engines, so Scout Intent and World Model\n"
              "report engine_unavailable). Rebuild the image, then regenerate them inside it:\n"
              "  docker build -t oah-submission . && docker run --rm -v \"$PWD/output_examples:/app/output_examples\" "
              "oah-submission python scripts/record_fixtures.py --outputs-only")
    return rc


if __name__ == "__main__":
    sys.exit(main())
