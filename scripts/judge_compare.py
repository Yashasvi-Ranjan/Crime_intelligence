#!/usr/bin/env python3
"""
Compare live /run outputs against output_examples/, ignoring what legitimately differs between runs:
execution_time_seconds, run ids / trace ids / log file names (derived from the run id), timestamps,
latencies, and query ids (Zetaris request ids or local-<hash> ids).

  python scripts/judge_compare.py [--url http://localhost:8000] [--examples 1 2 3]

POSTs input_examples/example_N.json to <url>/run and diffs against output_examples/example_N.json.
Exit code 0 = all match, 1 = a difference, 2 = server unreachable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IGNORED_KEYS = {"execution_time_seconds", "run_id", "trace_id", "log_file", "investigation_id", "timestamp", "iso_time",
                "latency_ms", "avg_latency_ms", "elapsed_seconds", "query_ids", "query_id", "recorded_at"}
ID_RE = re.compile(r"\binv_\d+_[0-9a-f]{6}\b|\blocal-[0-9a-f]{12}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def normalise(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: normalise(x) for k, x in v.items() if k not in IGNORED_KEYS}
    if isinstance(v, list):
        return [normalise(x) for x in v]
    if isinstance(v, str):
        return ID_RE.sub("<id>", v)
    return v


def diff(a: Any, b: Any, path: str = "$") -> list[str]:
    if type(a) is not type(b):
        return [f"{path}: {type(a).__name__} vs {type(b).__name__}"]
    if isinstance(a, dict):
        out = [f"{path}.{k}: only in {'expected' if k in a else 'actual'}" for k in sorted(set(a) ^ set(b))]
        for k in sorted(set(a) & set(b)):
            out += diff(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} vs {len(b)}"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: expected {str(a)[:80]!r} got {str(b)[:80]!r}"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--examples", nargs="*", type=int, default=[1, 2, 3])
    args = ap.parse_args()
    import httpx

    failed = 0
    for n in args.examples:
        body = json.loads((ROOT / f"input_examples/example_{n}.json").read_text())
        expected = json.loads((ROOT / f"output_examples/example_{n}.json").read_text())
        try:
            r = httpx.post(f"{args.url.rstrip('/')}/run", json=body, timeout=1800)
        except httpx.HTTPError as exc:
            print(f"example_{n}: cannot reach {args.url}: {exc}")
            return 2
        if r.status_code != 200:
            print(f"example_{n}: FAIL HTTP {r.status_code} {r.text[:200]}")
            failed += 1
            continue
        d = diff(normalise(expected), normalise(r.json()))
        print(f"example_{n}: {'PASS' if not d else 'FAIL'} (status={r.json().get('status')}, links={len(r.json()['output']['links'])})")
        for line in d[:15]:
            print("   ", line)
        failed += bool(d)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
