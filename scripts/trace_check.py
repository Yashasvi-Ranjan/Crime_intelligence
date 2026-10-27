#!/usr/bin/env python3
"""Check every logs/trace-*.jsonl against the judge's trace checklist; exit 1 if any item is missing.

Checklist: routing/intent step, >= 2 named agents, a handoff, a Skeptic critique/branch, >= 1 Zetaris(-or-local)
query id, >= 1 engine event (a real op or an explicit engine_unavailable - never a fabricated one), and the
requested + reported model on every model call (Nemotron ids; never meterless/auto).

  python scripts/trace_check.py [TRACE.jsonl ...]            checklist over the given traces (default: logs/trace-*.jsonl)
  python scripts/trace_check.py --receipts TRACE.jsonl       also print every model call: source, requested/reported model, receipt id
  python scripts/trace_check.py --require-live TRACE.jsonl   a COMMITTABLE live trace: >= 1 model call and every call answered by
                                                             live Nightshift (source=live) with a receipt id and a Nemotron model;
                                                             replayed / code_fallback calls are rejected
  python scripts/trace_check.py --fixtures [DIR]             verify the recorded fixtures: receipt id, Nemotron reported model,
                                                             recorded_from live Nightshift
Receipt ids are Nightshift's own; this tool checks that they are present, well-formed and not replayed, it cannot
confirm them with Nightshift (no verification endpoint is available offline)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(path: Path) -> list[str]:
    ev = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    miss = []
    if not any(e["step"] == "routing" for e in ev):
        miss.append("routing/intent step")
    agents = {e["agent"] for e in ev if e["agent"] in ("planner", "finder", "skeptic", "reporter")}
    if len(agents) < 2:
        miss.append(f"named agents (found {sorted(agents)})")
    if not any(e["step"] == "handoff" for e in ev):
        miss.append("handoff")
    if not any(e["step"] in ("branch", "review") and e["agent"] in ("skeptic", "orchestrator") for e in ev):
        miss.append("Skeptic critique/branch")
    if not any((e.get("sql_meta") or {}).get("query_ids") for e in ev):
        miss.append("query id")
    if not any(e.get("engine_meta") or e.get("status") == "engine_unavailable" for e in ev):
        miss.append("engine event")
    for e in ev:
        pm = e.get("provider_meta")
        if not pm:
            continue
        if not pm.get("requested_model"):
            miss.append(f"requested model on {e['agent']} call")
        if pm.get("source") != "code_fallback" and not pm.get("reported_model"):
            miss.append(f"reported model on {e['agent']} call")
        if "meterless" in str(pm.get("requested_model")).lower() or str(pm.get("reported_model")).lower() == "auto":
            miss.append("non-Nemotron model id")
    return miss


RECEIPT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{5,127}$")


def _is_nemotron(model: object) -> bool:
    m = str(model or "").lower()
    return m.startswith("nvidia/") and "nemotron" in m


def model_calls(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            pm = json.loads(line).get("provider_meta")
            if pm:
                out.append(pm)
    return out


def check_live(path: Path) -> list[str]:
    """Problems that stop a trace from being committed as evidence of live Nemotron calls."""
    calls = model_calls(path)
    if not calls:
        return ["no model calls in the trace"]
    bad = []
    for i, pm in enumerate(calls, 1):
        who = f"call {i} ({pm.get('role', '?')})"
        if pm.get("source") != "live":
            bad.append(f"{who}: source={pm.get('source')!r}, not live")
        if not RECEIPT_RE.match(str(pm.get("receipt_id") or "")):
            bad.append(f"{who}: missing or malformed receipt_id")
        if not _is_nemotron(pm.get("reported_model")):
            bad.append(f"{who}: reported model {pm.get('reported_model')!r} is not a Nemotron id")
    return bad


def check_fixtures(directory: Path) -> list[str]:
    bad, files = [], [f for f in sorted(directory.glob("*.json")) if f.name != "catalog.json"]
    if not files:
        return [f"no fixtures in {directory}"]
    for f in files:
        d = json.loads(f.read_text())
        if not RECEIPT_RE.match(str(d.get("receipt_id") or "")):
            bad.append(f"{f.name}: missing or malformed receipt_id")
        if not _is_nemotron(d.get("reported_model")):
            bad.append(f"{f.name}: reported model {d.get('reported_model')!r} is not a Nemotron id")
        if "live Nightshift" not in str(d.get("recorded_from", "")):
            bad.append(f"{f.name}: not marked as recorded from live Nightshift")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("traces", nargs="*", type=Path)
    ap.add_argument("--receipts", action="store_true")
    ap.add_argument("--require-live", action="store_true")
    ap.add_argument("--fixtures", nargs="?", const=str(ROOT / "data/sample/model_fixtures"), metavar="DIR")
    a = ap.parse_args()
    bad = 0
    if a.fixtures:
        problems = check_fixtures(Path(a.fixtures))
        print(f"fixtures {a.fixtures}: {'OK' if not problems else 'PROBLEMS'}")
        for p in problems:
            print("   ", p)
        bad += bool(problems)
        if not a.traces:
            return 1 if bad else 0
    paths = a.traces or sorted((ROOT / "logs").glob("trace-*.jsonl"))
    if not paths:
        print("no traces found (pass a trace file, or run an investigation to create logs/trace-*.jsonl)")
        return 1
    for p in paths:
        m = check(p)
        print(f"{p.name}: {'OK' if not m else 'MISSING ' + ', '.join(sorted(set(m)))}")
        bad += bool(m)
        if a.receipts or a.require_live:
            for pm in model_calls(p):
                print(f"    {pm.get('role', '?'):9} {str(pm.get('source')):13} req={pm.get('requested_model')} "
                      f"rep={pm.get('reported_model')} receipt={pm.get('receipt_id')}")
        if a.require_live:
            live = check_live(p)
            print(f"{p.name}: {'LIVE OK' if not live else 'NOT A LIVE TRACE'}")
            for x in live:
                print("   ", x)
            bad += bool(live)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
