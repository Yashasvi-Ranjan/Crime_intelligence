"""
Recorded Nightshift responses for offline sample mode.

A fixture is the response a REAL live Nightshift call returned, stored under a hash of
(role, requested model, messages). Matching is by prompt content only: it is never keyed to an example,
run id or scenario, and a fixture never contains a final answer to a whole investigation - only what one
model call said about the prompt it was given. Prompts built by the workflow carry no run ids or
timestamps, so the same inputs reproduce the same hash on any machine.

``scripts/record_fixtures.py`` is the only writer. A fixture that does not match is simply absent;
the caller then runs the documented code-only fallback and traces it.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOG_FILE = "catalog.json"


def prompt_hash(role: str, model: str, messages: List[Dict[str, str]]) -> str:
    canon = json.dumps({"role": role, "model": model, "messages": [[m["role"], m["content"]] for m in messages]},
                       sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class FixtureStore:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def put(self, key: str, fixture: Dict[str, Any]) -> None:
        self._atomic(self._path(key), fixture)

    def catalog(self) -> Optional[List[str]]:
        p = self.dir / CATALOG_FILE
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data.get("models") if isinstance(data, dict) else None

    def put_catalog(self, models: List[str]) -> None:
        self._atomic(self.dir / CATALOG_FILE, {"models": models, "note": "Model ids Nightshift listed at /v1/models when recorded"})

    def count(self) -> int:
        return len([p for p in self.dir.glob("*.json") if p.name != CATALOG_FILE]) if self.dir.exists() else 0

    def _atomic(self, path: Path, obj: Dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.dir, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
