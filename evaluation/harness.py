"""
Pure evaluation logic shared by scripts/evaluate_agents.py and the tests.

Nothing here imports the backend, touches the network, or needs credentials. It defines
the pre-registered case sets, the metrics, and the provenance stamp. See PREREGISTRATION.md.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import math
import random
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
PREREG_PATH = ROOT / "evaluation" / "PREREGISTRATION.md"

HELDOUT_SEED = 7919
STANDIN_LABEL = "NOT A MODEL BENCHMARK"

# Development cases: the original seven. The scripted stand-in and any prompt tuning were written
# against these, so they are NOT held out. The held-out set below is frozen by seed and hash.
DEV_POSITIVE = ("REL-SERIES-001", "REL-SERIES-002", "REL-SERIES-003", "REL-SERIES-004", "REL-SERIES-007")
DEV_DECOYS = (("REL-DISTRACTOR-006", "REL-SERIES-004"), ("REL-DISTRACTOR-008", "REL-SERIES-001"))
HELDOUT_POSITIVE = DEV_POSITIVE
PLANTED_DECOYS = ("REL-DISTRACTOR-006", "REL-DISTRACTOR-008")


def _query(ids: List[str]) -> str:
    return f"Are incidents {', '.join(ids)} related to one another?"


def _pairs(ids: Iterable[str]) -> Set[frozenset]:
    return {frozenset(p) for p in itertools.combinations(ids, 2)}


def _case(name: str, kind: str, split: str, ids: List[str], truth: Set[frozenset],
          foils: Optional[Set[str]] = None, planted_decoys: Optional[Set[str]] = None) -> Dict[str, Any]:
    return {
        "case": name, "kind": kind, "split": split, "incident_ids": ids,
        "truth_pairs": truth, "foils": set(foils or ()), "planted_decoys": set(planted_decoys or ()),
        "query": _query(ids),
    }


def build_dev_cases(truth: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {t["relationship_id"]: t for t in truth}
    cases = []
    for rid in DEV_POSITIVE:
        ids = by_id[rid]["incident_ids"]
        cases.append(_case(rid[-3:], "positive", "dev", list(ids), _pairs(ids)))
    for rid, base in DEV_DECOYS:
        decoy = by_id[rid]["incident_ids"][0]
        base_ids = by_id[base]["incident_ids"][:2]
        cases.append(_case(rid[-3:], "decoy", "dev", [decoy, *base_ids], {frozenset(base_ids)},
                           foils={decoy}, planted_decoys={decoy}))
    return cases


def build_heldout_cases(truth: List[Dict[str, Any]], incidents: List[Dict[str, Any]],
                        seed: int = HELDOUT_SEED) -> List[Dict[str, Any]]:
    """Deterministic: the same (truth, incidents, seed) always yields the same cases in the same order."""
    rng = random.Random(seed)
    by_id = {t["relationship_id"]: t for t in truth}
    planted = {i for t in truth for i in t["incident_ids"]}
    background = sorted((i for i in incidents if i["incident_id"] not in planted), key=lambda i: i["incident_id"])
    ctype = {i["incident_id"]: i.get("crime_type") for i in incidents}
    station = {i["incident_id"]: i.get("station_id") for i in incidents}
    cases: List[Dict[str, Any]] = []

    # H-POS: a full planted series plus one same-crime-type background incident from another station.
    for rid in HELDOUT_POSITIVE:
        ids = list(by_id[rid]["incident_ids"])
        stations = {station[i] for i in ids}
        pool = [b for b in background if b["crime_type"] == ctype[ids[0]] and b["station_id"] not in stations] \
            or [b for b in background if b["station_id"] not in stations]
        extra = rng.choice(pool)["incident_id"]
        cases.append(_case(f"H-POS-{rid[-3:]}", "positive", "heldout", ids + [extra], _pairs(ids), foils={extra}))

    # H-DEC: planted distractors mixed into series pairs that the dev set did not pair them with.
    d6, d8 = (by_id[r]["incident_ids"][0] for r in PLANTED_DECOYS)
    s2 = by_id["REL-SERIES-002"]["incident_ids"][:2]
    s3 = by_id["REL-SERIES-003"]["incident_ids"][:2]
    s7 = by_id["REL-SERIES-007"]["incident_ids"][:2]
    cases.append(_case("H-DEC-006-S002", "decoy", "heldout", [d6, *s2], {frozenset(s2)}, {d6}, {d6}))
    cases.append(_case("H-DEC-008-S003", "decoy", "heldout", [d8, *s3], {frozenset(s3)}, {d8}, {d8}))
    cases.append(_case("H-DEC-BOTH-S007", "decoy", "heldout", [d6, d8, *s7], {frozenset(s7)}, {d6, d8}, {d6, d8}))

    # H-NEG: three unrelated background incidents from three different stations; no true link exists.
    for k in range(1, 4):
        picked: List[str] = []
        used: Set[str] = set()
        for b in rng.sample(background, len(background)):
            if b["station_id"] not in used:
                picked.append(b["incident_id"])
                used.add(b["station_id"])
            if len(picked) == 3:
                break
        cases.append(_case(f"H-NEG-{k}", "negative", "heldout", picked, set(), foils=set(picked)))

    # H-CROSS: one incident from each of three different planted series; truth says none are related.
    ids = [by_id[r]["incident_ids"][0] for r in ("REL-SERIES-001", "REL-SERIES-002", "REL-SERIES-004")]
    cases.append(_case("H-CROSS-001-002-004", "negative", "heldout", ids, set(), foils=set(ids)))
    return cases


def case_set_hash(cases: List[Dict[str, Any]], seed: int = HELDOUT_SEED) -> str:
    canon = [{
        "case": c["case"], "kind": c["kind"], "split": c["split"], "incident_ids": c["incident_ids"],
        "truth_pairs": sorted(sorted(p) for p in c["truth_pairs"]),
        "foils": sorted(c["foils"]), "planted_decoys": sorted(c["planted_decoys"]), "query": c["query"],
    } for c in cases]
    blob = json.dumps({"seed": seed, "cases": canon}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── metrics ──────────────────────────────────────────────────────────────

def pair_key(link: Dict[str, Any]) -> frozenset:
    return frozenset((link["source_incident_id"], link["target_incident_id"]))


def case_pair_counts(case: Dict[str, Any], reported: Set[frozenset], supported: Set[frozenset]) -> Dict[str, Any]:
    """Per-case raw counts. `reported` = every active link the system output; `supported` = the subset an
    independent re-verification (verify_link) marks SUPPORTED. The same rule is applied to every system."""
    truth = case["truth_pairs"]
    foils = case["foils"]
    return {
        "truth_pairs": len(truth),
        "reported": len(reported),
        "reported_true": len(reported & truth),
        "reported_false": len(reported - truth),
        "supported": len(supported),
        "supported_true": len(supported & truth),
        "supported_false": len(supported - truth),
        "foil_links": sum(1 for p in reported if p & foils),
        "planted_decoy_links": sum(1 for p in reported if p & case["planted_decoys"]),
        "has_foils": bool(foils),
        "has_planted_decoys": bool(case["planted_decoys"]),
    }


def _ratio(num: int, den: int) -> Optional[float]:
    return round(num / den, 3) if den else None


def wilson(k: int, n: int, z: float = 1.96) -> Optional[List[float]]:
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def aggregate(counts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Micro-aggregate per-case counts (pre-registered metric definitions; see PREREGISTRATION.md)."""
    s = lambda k: sum(c[k] for c in counts)  # noqa: E731
    foil_cases = [c for c in counts if c["has_foils"]]
    decoy_cases = [c for c in counts if c["has_planted_decoys"]]
    rejected = sum(1 for c in foil_cases if c["foil_links"] == 0)
    decoy_rejected = sum(1 for c in decoy_cases if c["planted_decoy_links"] == 0)
    return {
        "cases": len(counts),
        "truth_pairs_total": s("truth_pairs"),
        "reported_links_total": s("reported"),
        "supported_links_total": s("supported"),
        "supported_precision": _ratio(s("supported_true"), s("supported")),
        "supported_recall": _ratio(s("supported_true"), s("truth_pairs")),
        "supported_recall_wilson95": wilson(s("supported_true"), s("truth_pairs")),
        "reported_precision": _ratio(s("reported_true"), s("reported")),
        "reported_recall": _ratio(s("reported_true"), s("truth_pairs")),
        "false_link_rate": _ratio(s("reported_false"), s("reported")),
        "false_links_total": s("reported_false"),
        "foil_rejection_rate": _ratio(rejected, len(foil_cases)),
        "foil_cases": len(foil_cases),
        "planted_decoy_rejection_rate": _ratio(decoy_rejected, len(decoy_cases)),
        "planted_decoy_cases": len(decoy_cases),
        "planted_decoy_rejection_wilson95": wilson(decoy_rejected, len(decoy_cases)),
    }


# ── provenance ───────────────────────────────────────────────────────────

def sha256_file(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def git_state(root: Path = ROOT) -> Dict[str, Any]:
    def run(*a: str) -> Optional[str]:
        try:
            return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        except Exception:
            return None
    status = run("status", "--porcelain", "--", "backend", "evaluation", "scripts", "data")
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None}


def models_called(call_log: List[Dict[str, Any]]) -> List[str]:
    """Models that actually answered: only calls that carry a Nightshift receipt id count."""
    return sorted({c["reported_model"] for c in call_log if c.get("reported_model") and c.get("receipt_id")})


def provenance(mode: str, case_set: str, cases: List[Dict[str, Any]], call_log: List[Dict[str, Any]],
               now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    if mode not in ("live", "offline-standin"):
        raise ValueError(f"unknown mode: {mode}")
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp: Dict[str, Any] = {}
    if mode == "offline-standin":
        stamp["label"] = STANDIN_LABEL
        stamp["label_detail"] = ("Scripted, model-free stand-in. It tests the pipeline, verifier and scoring only. "
                                 "No model was called; no receipts exist.")
    stamp.update({
        "mode": mode,
        "git": git_state(),
        "case_set": case_set,
        "case_set_hash": case_set_hash(cases),
        "heldout_seed": HELDOUT_SEED,
        "preregistration_sha256": sha256_file(PREREG_PATH),
        "ground_truth_sha256": sha256_file(ROOT / "data/evaluation/ground_truth.json"),
        "incidents_sha256": sha256_file(ROOT / "data/generated/police_incidents.json"),
        "date_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "models_called": models_called(call_log),
        "model_call_receipts": sum(1 for c in call_log if c.get("receipt_id")),
    })
    if mode == "offline-standin" and (stamp["models_called"] or stamp["model_call_receipts"]):
        raise AssertionError("stand-in output must never carry model names or receipts")
    return stamp
