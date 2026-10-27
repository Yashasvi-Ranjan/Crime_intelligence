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


HOST_ALIAS = "host.docker.internal"
HOST_URL_VARS = ("NIGHTSHIFT_BASE_URL", "ZETARIS_BASE_URL", "ZETARIS_AUTH_URL", "ZETARIS_JDBC_HOST")


def _default_gateway() -> str | None:
    """The container's default gateway (the Docker host on a bridge network), from /proc/net/route."""
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            f = line.split()
            if f[1] == "00000000":
                return ".".join(str(int(f[2][i:i + 2], 16)) for i in (6, 4, 2, 0))
    except (OSError, IndexError, ValueError):
        pass
    return None


def fix_host_alias() -> None:
    """`docker run` on Linux has no host.docker.internal unless --add-host is given. If the alias does not
    resolve, point the host-facing URLs at the default gateway instead (before settings are read)."""
    import socket

    if not any(HOST_ALIAS in os.environ.get(v, "") for v in HOST_URL_VARS):
        return
    try:
        socket.gethostbyname(HOST_ALIAS)
        return
    except OSError:
        pass
    gw = _default_gateway()
    if not gw:
        return
    for v in HOST_URL_VARS:
        if HOST_ALIAS in os.environ.get(v, ""):
            os.environ[v] = os.environ[v].replace(HOST_ALIAS, gw)
    print(f"[run.py] {HOST_ALIAS} does not resolve; using the default gateway {gw} for Zetaris/Nightshift "
          f"(add --add-host {HOST_ALIAS}:host-gateway to be explicit)", flush=True)


def serve() -> None:
    fix_host_alias()
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
