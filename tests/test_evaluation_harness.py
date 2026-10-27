"""Evaluation harness: metrics, held-out determinism, provenance stamp, and stand-in honesty."""

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation import harness as h  # noqa: E402

TRUTH = json.loads((ROOT / "data/evaluation/ground_truth.json").read_text(encoding="utf-8"))
INCIDENTS = json.loads((ROOT / "data/generated/police_incidents.json").read_text(encoding="utf-8"))
P = lambda a, b: frozenset((a, b))  # noqa: E731


def _case(truth, foils=(), decoys=()):
    return {"truth_pairs": set(truth), "foils": set(foils), "planted_decoys": set(decoys)}


def test_counts_and_aggregate_definitions():
    c1 = _case({P("A", "B"), P("A", "C"), P("B", "C")})
    r1 = {P("A", "B"), P("A", "X")}          # one true, one false
    s1 = {P("A", "B")}                        # only the true one is verified
    c2 = _case(set(), foils={"X", "Y"})
    r2 = {P("X", "Y")}                        # a link touching a foil
    c3 = _case({P("D", "E")}, foils={"F"}, decoys={"F"})
    r3 = {P("D", "E")}
    counts = [h.case_pair_counts(c1, r1, s1), h.case_pair_counts(c2, r2, set()), h.case_pair_counts(c3, r3, r3)]
    a = h.aggregate(counts)
    assert a["truth_pairs_total"] == 4
    assert a["reported_links_total"] == 4 and a["supported_links_total"] == 2
    assert a["supported_precision"] == 1.0
    assert a["supported_recall"] == 0.5                       # 2 of 4 true pairs
    assert a["reported_precision"] == 0.5 and a["false_link_rate"] == 0.5
    assert a["foil_cases"] == 2 and a["foil_rejection_rate"] == 0.5   # c2 touched a foil, c3 is clean
    assert a["planted_decoy_cases"] == 1 and a["planted_decoy_rejection_rate"] == 1.0


def test_zero_denominators_are_null_not_zero():
    a = h.aggregate([h.case_pair_counts(_case(set()), set(), set())])
    assert a["supported_precision"] is None and a["supported_recall"] is None
    assert a["false_link_rate"] is None and a["foil_rejection_rate"] is None


def test_wilson_interval_bounds():
    lo, hi = h.wilson(3, 3)
    assert 0 < lo < hi == 1.0
    assert h.wilson(0, 0) is None


def test_heldout_split_is_deterministic_and_frozen():
    a = h.build_heldout_cases(TRUTH, INCIDENTS)
    b = h.build_heldout_cases(TRUTH, list(reversed(INCIDENTS)))   # input order must not matter
    assert h.case_set_hash(a) == h.case_set_hash(b)
    assert [c["case"] for c in a] == [c["case"] for c in b]
    assert h.case_set_hash(h.build_heldout_cases(TRUTH, INCIDENTS, seed=1)) != h.case_set_hash(a)
    assert len(a) == 12 and sum(len(c["truth_pairs"]) for c in a) == 12
    # the hash recorded in the pre-registration is the one the code produces
    prereg = h.PREREG_PATH.read_text(encoding="utf-8")
    assert h.case_set_hash(a) in prereg


def test_heldout_disjoint_from_dev_and_decoys_present():
    dev = h.build_dev_cases(TRUTH)
    held = h.build_heldout_cases(TRUTH, INCIDENTS)
    assert {c["case"] for c in dev}.isdisjoint({c["case"] for c in held})
    assert {frozenset(c["incident_ids"]) for c in dev}.isdisjoint({frozenset(c["incident_ids"]) for c in held})
    assert sum(1 for c in held if c["planted_decoys"]) == 3
    assert all(not c["truth_pairs"] for c in held if c["kind"] == "negative")


def test_provenance_stamp_fields_and_standin_label():
    cases = h.build_heldout_cases(TRUTH, INCIDENTS)
    now = dt.datetime(2030, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    st = h.provenance("offline-standin", "heldout", cases, [], now=now)
    assert list(st)[0] == "label" and st["label"] == "NOT A MODEL BENCHMARK"
    assert st["mode"] == "offline-standin" and st["models_called"] == []
    assert st["case_set_hash"] == h.case_set_hash(cases) and st["date_utc"] == "2030-01-02T03:04:05Z"
    assert set(st["git"]) == {"commit", "dirty"} and st["preregistration_sha256"]
    live = h.provenance("live", "heldout", cases, [
        {"reported_model": "m-real", "receipt_id": "r1"},
        {"reported_model": "m-no-receipt", "receipt_id": None},   # no receipt: does not count as called
    ])
    assert "label" not in live and live["models_called"] == ["m-real"]
    with pytest.raises(ValueError):
        h.provenance("bogus", "heldout", cases, [])


def test_standin_provenance_rejects_receipts():
    with pytest.raises(AssertionError):
        h.provenance("offline-standin", "heldout", [], [{"reported_model": "x", "receipt_id": "r"}])


def test_standin_run_emits_no_receipts_or_model_names(tmp_path):
    out = tmp_path / "r.json"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NIGHTSHIFT", "ZETARIS"))}
    env["SAMPLE_MODE"] = "true"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_agents.py"), "--offline-standin",
                        "--cases", "001,H-NEG-1", "--out", str(out)],
                       capture_output=True, text=True, env=env, cwd=tmp_path, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert list(doc["provenance"])[0] == "label"
    assert doc["provenance"]["models_called"] == [] and doc["provenance"]["model_call_receipts"] == 0
    assert all(row["ok"] for row in doc["rows"])
    text = out.read_text(encoding="utf-8")
    assert not re.search(r"nemotron|rcpt_|nvidia", text, re.I)
    assert all(not row["call_log"] and not any(row.get("models", {}).values()) for row in doc["rows"])


def test_live_mode_fails_fast_without_credentials(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("NIGHTSHIFT", "ZETARIS"))}
    env.update(SAMPLE_MODE="true", NIGHTSHIFT_API_KEY="", ZETARIS_ENABLED="false", HOME=str(tmp_path))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_agents.py"), "--live", "--out", str(tmp_path / "x.json")],
                       capture_output=True, text=True, env=env, cwd=tmp_path, timeout=120)
    assert r.returncode != 0 and "requires real credentials" in r.stderr
    assert not (tmp_path / "x.json").exists()


def test_committed_results_are_honestly_stamped():
    doc = json.loads((ROOT / "evaluation/results.json").read_text(encoding="utf-8"))
    assert list(doc)[0] == "provenance" and doc["provenance"]["label"] == "NOT A MODEL BENCHMARK"
    assert doc["provenance"]["models_called"] == []
