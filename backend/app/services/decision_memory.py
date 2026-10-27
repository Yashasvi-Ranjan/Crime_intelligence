"""
Decision memory: a small, deterministic, auditable layer on top of H-MEM.

Write gate (unchanged, enforced by the caller before anything is written here): only links the deterministic
verifier marked SUPPORTED, in a run with a completed Skeptic review and no open high-severity objection, become
"verified leads". Verifier-REJECTED or Finder-withdrawn links are kept separately as "rejected" records that can
only SUPPRESS; they never raise anything.

Read effect (deterministic, no model involved): on the first iteration, a prior verified lead whose incident
IDs or shared-attribute values overlap the new question becomes a *starting hypothesis*: its incident IDs are
fetched first from Zetaris. It is not evidence, adds no corroboration, and the Finder, verifier and Skeptic
still run on whatever records this run actually retrieves. Every influence is returned as ``memory_influence``
with source memory ids so the effect is visible and attributable.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

MEMORY_SOURCE_PREFIX = "DMEM-"          # memory ids; never valid evidence IDs
_TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")
_INC = re.compile(r"\bINC-[A-Z0-9]+-\d+\b")


def _tokens(text: str) -> set:
    return set(_TOKEN.findall(text.lower()))


class DecisionMemory:
    def __init__(self, state_dir: Path, scope: str = "crime-intel") -> None:
        self._file = Path(state_dir) / f"decision-memory-{re.sub(r'[^A-Za-z0-9_-]', '_', scope)}.json"

    # ── storage ──
    def _load(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._file.read_text())
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, rows: List[Dict[str, Any]]) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(rows, indent=1, sort_keys=True))

    # ── write ──
    def write_verified(self, run_id: str, links: List[Dict[str, Any]]) -> List[str]:
        """links: dicts with link_id, source/target incident ids, stations, shared_attributes, corroborating_ids.
        The caller has already applied the gate; as defence in depth, only status == SUPPORTED is accepted."""
        rows, ids = self._load(), []
        for l in links:
            if l.get("status") != "SUPPORTED" or l.get("open_high_objection"):
                continue
            mid = f"{MEMORY_SOURCE_PREFIX}{run_id}-{l['link_id']}"
            rows = [r for r in rows if r["memory_id"] != mid]
            rows.append({"memory_id": mid, "kind": "verified", "run_id": run_id, "link_id": l["link_id"],
                         "incident_ids": sorted([l["source_incident_id"], l["target_incident_id"]]),
                         "stations": l.get("stations_involved", []),
                         "attributes": [f"{a['attribute']}={a['value']}" for a in l.get("shared_attributes", [])][:6],
                         "attribute_tokens": sorted(set().union(*[_tokens(str(a["value"])) for a in l.get("shared_attributes", [])] or [set()])),
                         "corroborating_ids": list(l.get("corroborating_ids", []))[:8], "written_at": time.time()})
            ids.append(mid)
        if ids:
            self._save(rows)
        return ids

    def write_rejected(self, run_id: str, links: List[Dict[str, Any]]) -> List[str]:
        rows, ids = self._load(), []
        for l in links:
            if l.get("status") != "REJECTED" and not l.get("withdrawn"):
                continue
            mid = f"{MEMORY_SOURCE_PREFIX}{run_id}-{l['link_id']}-rej"
            rows = [r for r in rows if r["memory_id"] != mid]
            rows.append({"memory_id": mid, "kind": "rejected", "run_id": run_id, "link_id": l["link_id"],
                         "incident_ids": sorted([l["source_incident_id"], l["target_incident_id"]]),
                         "reason": "withdrawn" if l.get("withdrawn") else "verifier_rejected", "written_at": time.time()})
            ids.append(mid)
        if ids:
            self._save(rows)
        return ids

    # ── read ──
    def influence(self, query: str, route_incident_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Deterministic: which prior records relate to this question, and what that changes."""
        q_inc = set(route_incident_ids or []) | set(_INC.findall(query.upper()))
        q_tok = _tokens(query)
        verified, rejected, flagged = [], [], []
        for r in self._load():
            inc = set(r["incident_ids"])
            overlap_inc = sorted(inc & q_inc)
            overlap_tok = sorted(set(r.get("attribute_tokens", [])) & q_tok)
            if r["kind"] == "rejected":
                if overlap_inc:
                    flagged.append({"memory_id": r["memory_id"], "incident_ids": r["incident_ids"], "reason": r["reason"],
                                    "effect": "suppressed: not used as a starting hypothesis; flagged for the Planner"})
                continue
            if overlap_inc or overlap_tok:
                verified.append({"memory_id": r["memory_id"], "incident_ids": r["incident_ids"], "attributes": r["attributes"],
                                 "matched_on": {"incident_ids": overlap_inc, "attribute_tokens": overlap_tok}})
        rejected_pairs = {tuple(f["incident_ids"]) for f in flagged}
        starting = [v for v in verified if tuple(v["incident_ids"]) not in rejected_pairs]
        priority_ids = list(dict.fromkeys(i for v in starting for i in v["incident_ids"]))
        return {"applied": bool(starting or flagged), "starting_hypotheses": starting, "flagged_rejected": flagged,
                "priority_incident_ids": priority_ids,
                "source_memory_ids": [x["memory_id"] for x in starting + flagged],
                "note": "memory-derived priority only; not evidence, adds no corroboration; Finder, verifier and Skeptic "
                        "must still support/challenge every link from records retrieved in this run"}
