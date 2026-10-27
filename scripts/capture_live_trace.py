#!/usr/bin/env python3
"""Capture ONE live AEGIS investigation (real Zetaris + real Nightshift/Nemotron), then redact it. Stdlib only.

  python scripts/capture_live_trace.py [--url http://localhost:8000] [--input input_examples/example_1.json]
                                       [--logs-dir logs] [--raw-dir .state/live_capture] [--out docs/live_traces]

Run it against a backend you started yourself with live credentials (see docs/LIVE_RUN_RUNBOOK.md). It:
  1. fails fast (exit 2) if the credentials are not in THIS shell's environment, or the server does not report zetaris/nightshift "live";
  2. POSTs the input to /run with options.sample_mode=false and a long timeout;
  3. reads the run's trace (logs/trace-<run_id>.jsonl, or `docker logs` TRACE lines if you pass --docker-container);
  4. saves the RAW capture under --raw-dir (gitignored .state/, never commit it) and a REDACTED summary + redacted trace under --out;
  5. exits 1 and prints why if the run was not actually live (any query with source != zetaris_live, any model call with
     source != live), so a replayed/fallback run can never be committed as "live evidence".
Nothing here is simulated: with no credentials and no live services it only prints the failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import redact_trace  # noqa: E402  (sibling script)

NIGHTSHIFT_TOKEN_FILES = [
    Path.home() / "Library/Application Support/ai.meterless.runtime/proxy-token",
]


def missing_credentials(env: Dict[str, str], token_files: Optional[List[Path]] = None) -> List[str]:
    """Names of what is missing for a live run. Empty list = credentials present (not proof they are valid)."""
    miss = []
    if env.get("SAMPLE_MODE", "").lower() == "true":
        miss.append("SAMPLE_MODE=true is set (unset it, or set SAMPLE_MODE=false)")
    if env.get("ZETARIS_ENABLED", "true").lower() == "false":
        miss.append("ZETARIS_ENABLED=false")
    if not env.get("ZETARIS_USERNAME") and not env.get("ZETARIS_API_TOKEN"):
        miss.append("ZETARIS_USERNAME (+ ZETARIS_PASSWORD) or ZETARIS_API_TOKEN")
    elif not env.get("ZETARIS_API_TOKEN") and not env.get("ZETARIS_PASSWORD"):
        miss.append("ZETARIS_PASSWORD")
    key_file = env.get("NIGHTSHIFT_API_KEY_FILE")
    files = [Path(key_file)] if key_file else (NIGHTSHIFT_TOKEN_FILES if token_files is None else token_files)
    if not env.get("NIGHTSHIFT_API_KEY") and not any(p.is_file() for p in files):
        miss.append("NIGHTSHIFT_API_KEY or NIGHTSHIFT_API_KEY_FILE (or a Nightshift proxy-token file on this host)")
    return miss


def http_json(url: str, body: Optional[dict] = None, timeout: float = 30) -> Tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "null")
        except ValueError:
            return e.code, None


def read_trace(run_id: str, logs_dir: Path, container: Optional[str]) -> List[dict]:
    path = logs_dir / f"trace-{redact_trace_safe_name(run_id)}.jsonl"
    if path.is_file():
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if container:
        out = subprocess.run(["docker", "logs", container], capture_output=True, text=True, check=False)
        evs = []
        for line in (out.stdout + out.stderr).splitlines():
            if line.startswith("TRACE "):
                try:
                    ev = json.loads(line[6:])
                except ValueError:
                    continue
                if ev.get("run_id") == run_id:
                    evs.append(ev)
        return evs
    return []


def redact_trace_safe_name(run_id: str) -> str:
    import re
    return run_id if re.match(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$", run_id) else re.sub(r"[^A-Za-z0-9_\-]", "_", run_id)[:32]


def summarise(events: List[dict]) -> Dict[str, Any]:
    """Facts that can be read straight off the trace. Nothing is inferred or filled in."""
    qids: List[str] = []
    sql_sources, model_sources = set(), set()
    receipts, models = [], []
    for e in events:
        sm = e.get("sql_meta") or {}
        qids += [q for q in (sm.get("query_ids") or []) if q not in qids]
        if sm.get("source"):
            sql_sources.add(sm["source"])
        pm = e.get("provider_meta") or {}
        if pm:
            model_sources.add(pm.get("source", "live"))
            rid = pm.get("receipt_id") or pm.get("receipt")
            receipts.append({"agent": e.get("agent"), "receipt_id": rid, "requested_model": pm.get("requested_model"),
                             "reported_model": pm.get("reported_model"), "source": pm.get("source", "live"),
                             "fallback_used": pm.get("fallback_used")})
            if rid and rid not in models:
                models.append(rid)
    return {"zetaris_query_ids": qids, "sql_sources": sorted(sql_sources), "model_call_sources": sorted(model_sources),
            "nightshift_calls": receipts, "events": len(events),
            "engine_events": [e.get("engine_meta") or {"status": e.get("status")} for e in events
                              if e.get("engine_meta") or e.get("status") == "engine_unavailable"]}


def liveness_problems(summary: Dict[str, Any], run: Dict[str, Any]) -> List[str]:
    bad = []
    if run.get("output", {}).get("data_mode") not in (None, "zetaris_live"):
        bad.append(f"output.data_mode is {run['output']['data_mode']!r}, not 'zetaris_live'")
    if not summary["zetaris_query_ids"]:
        bad.append("no Zetaris query ids in the trace")
    if set(summary["sql_sources"]) - {"zetaris_live"}:
        bad.append(f"retrieval sources were {summary['sql_sources']}, not only zetaris_live")
    if not summary["nightshift_calls"]:
        bad.append("no model calls in the trace")
    if set(summary["model_call_sources"]) - {"live"}:
        bad.append(f"model call sources were {summary['model_call_sources']} (replayed/code_fallback are not live)")
    if any(c["receipt_id"] is None for c in summary["nightshift_calls"] if c["source"] == "live"):
        bad.append("a live model call has no Nightshift receipt id")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--input", default=str(ROOT / "input_examples/example_1.json"))
    ap.add_argument("--logs-dir", default=str(ROOT / "logs"))
    ap.add_argument("--raw-dir", default=str(ROOT / ".state/live_capture"))
    ap.add_argument("--out", default=str(ROOT / "docs/live_traces"))
    ap.add_argument("--docker-container", help="read the trace from `docker logs <name>` if logs/ is not mounted on the host")
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()

    miss = missing_credentials(dict(os.environ))
    if miss:
        print("NOT RUNNING: live credentials are not in this shell's environment. Missing: " + "; ".join(miss), file=sys.stderr)
        print("Export them (see .env.example and docs/LIVE_RUN_RUNBOOK.md), then re-run. No sample/replayed run is substituted.", file=sys.stderr)
        return 2

    base = a.url.rstrip("/")
    try:
        _, health = http_json(base + "/health", timeout=15)
    except (urllib.error.URLError, OSError) as e:
        print(f"NOT RUNNING: cannot reach {base}/health ({e}). Start the backend first (docs/LIVE_RUN_RUNBOOK.md).", file=sys.stderr)
        return 2
    states = {k: (health or {}).get(k, {}).get("state") for k in ("zetaris", "nightshift")}
    if states != {"zetaris": "live", "nightshift": "live"}:
        print(f"NOT RUNNING: /health reports {states}; both must be 'live' (the server did not pick up the credentials or a service is down).", file=sys.stderr)
        return 2

    body = json.loads(Path(a.input).read_text(encoding="utf-8"))
    body.setdefault("options", {})["sample_mode"] = False
    print(f"POST {base}/run (live; this takes minutes) ...", flush=True)
    status, run = http_json(base + "/run", body, timeout=a.timeout)
    if status != 200 or not isinstance(run, dict):
        print(f"run failed: HTTP {status}", file=sys.stderr)
        return 1
    run_id = run.get("run_id", "")
    events = read_trace(run_id, Path(a.logs_dir), a.docker_container)
    if not events:
        print(f"run {run_id} finished but no trace was found in {a.logs_dir} (mount logs/ or pass --docker-container).", file=sys.stderr)
        return 1
    summary = summarise(events)
    problems = liveness_problems(summary, run)

    raw_dir, out_dir = Path(a.raw_dir), Path(a.out)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"run-{run_id}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    (raw_dir / f"trace-{run_id}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    print(f"RAW (do not commit): {raw_dir}")
    if problems:
        print("NOT LIVE EVIDENCE, nothing written for commit:\n  - " + "\n  - ".join(problems), file=sys.stderr)
        return 1

    lits = redact_trace.env_literals()
    doc = {"run_id": run_id, "status": run.get("status"), "input": body.get("input"), "execution_time_seconds": run.get("execution_time_seconds"),
           "data_mode": (run.get("output") or {}).get("data_mode"), "stopping_reason": (run.get("output") or {}).get("stopping_reason"),
           "engines": run.get("engines"), "agents": run.get("agents"), "summary": summary}
    out_dir.mkdir(parents=True, exist_ok=True)
    red_summary = redact_trace.redact_file_text(json.dumps(doc), lits)
    red_trace = redact_trace.redact_file_text("\n".join(json.dumps(e) for e in events), lits)
    for name, text in ((f"live-run-{run_id}.summary.redacted.json", red_summary), (f"live-run-{run_id}.trace.redacted.jsonl", red_trace)):
        left = redact_trace.findings(text, lits)
        if left:
            print(f"refusing to write {name}: redaction left {left}", file=sys.stderr)
            return 1
        (out_dir / name).write_text(text, encoding="utf-8")
        print(f"wrote {out_dir / name}")
    print(f"Zetaris query ids: {len(summary['zetaris_query_ids'])}; Nightshift receipts: {sum(1 for c in summary['nightshift_calls'] if c['receipt_id'])}")
    print("Read both redacted files by eye before committing them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
