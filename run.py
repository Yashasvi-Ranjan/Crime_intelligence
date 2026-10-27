#!/usr/bin/env python3
"""
Entry point.

  python run.py                    start the API (uvicorn app.main:app) on $PORT (default 8000)
  python run.py --once FILE.json   POST one input file to /run on a running server and print the JSON
                                   (--url overrides http://localhost:$PORT)

No PYTHONPATH setup is needed: the backend package directory is added here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def serve() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")),
                app_dir=str(ROOT / "backend"))


def once(path: str, url: str) -> int:
    import httpx

    body = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        resp = httpx.post(f"{url.rstrip('/')}/run", json=body, timeout=float(os.environ.get("RUN_TIMEOUT_SECONDS", "1800")))
    except httpx.HTTPError as exc:
        print(f"could not reach {url}: {exc}", file=sys.stderr)
        return 2
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", metavar="FILE", help="post one input JSON to /run and print the response")
    ap.add_argument("--url", default=f"http://localhost:{os.environ.get('PORT', '8000')}")
    a = ap.parse_args()
    sys.exit(once(a.once, a.url)) if a.once else serve()
