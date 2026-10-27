#!/usr/bin/env python3
"""Check every logs/trace-*.jsonl against the judge's trace checklist; exit 1 if any item is missing.

Checklist: routing/intent step, >= 2 named agents, a handoff, a Skeptic critique/branch, >= 1 Zetaris(-or-local)
query id, >= 1 engine event (a real op or an explicit engine_unavailable - never a fabricated one), and the
requested + reported model on every model call (Nemotron ids; never meterless/auto)."""

from __future__ import annotations

import json
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


if __name__ == "__main__":
    bad = 0
    for p in sorted((ROOT / "logs").glob("trace-*.jsonl")):
        m = check(p)
        print(f"{p.name}: {'OK' if not m else 'MISSING ' + ', '.join(sorted(set(m)))}")
        bad += bool(m)
    sys.exit(1 if bad else 0)
