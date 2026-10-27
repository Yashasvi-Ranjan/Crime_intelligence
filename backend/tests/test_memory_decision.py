"""
Decision memory tests.

MOCKED:  model outputs (scripted FakeRegistry) and Zetaris (FakeData, in-memory). No live calls.
REAL:    H-MEM (Node engine), decision memory, the deterministic verifier.
"""

from __future__ import annotations

import json

from app.services import evidence_verifier as ev
from app.services.decision_memory import DecisionMemory
from tests.fakes import FOR_A, FOR_B, INC_A, INC_B, INC_C, PLAN_KEYWORDS, REPORT_OK, SKEPTIC_OK, FakeData, good_link
from tests.test_multiagent_workflow import EV, FINDER_OK, QUERY, SKEPTIC_ACCEPT, env  # noqa: F401  (env fixture; skips w/o Node)


def SCRIPT():
    return {"planner": [PLAN_KEYWORDS], "finder": [FINDER_OK], "skeptic": [SKEPTIC_OK], "reporter": [REPORT_OK]}


# Related case: different wording and no incident IDs; only the shared tool signature (chisel-tip) connects it to run 1.
QUERY2 = "Any other safe burglaries in the region involving a chisel-tip tool?"


def _data():
    return FakeData([INC_A, INC_B, INC_C], EV)


def _trace(env, run_id):
    f = next((env.tmp / "logs").glob(f"*{run_id}*"))
    return [json.loads(l) for l in f.read_text().splitlines()]


def test_two_run_flip_memory_changes_retrieval_order_and_is_attributed(env):  # noqa: F811
    r1 = env(SCRIPT(), data=_data()).run_investigation(QUERY)
    assert r1["memory"]["write"]["stored"] is True and r1["memory_influence"]["applied"] is False
    d2 = _data()
    r2 = env(SCRIPT(), data=d2).run_investigation(QUERY2)                       # memory present
    d3 = _data()
    r3 = env(SCRIPT(), data=d3, state_dir=str(env.tmp / "empty"), hmem_scope="control").run_investigation(QUERY2)  # empty memory
    assert r3["memory_influence"]["applied"] is False
    mi = r2["memory_influence"]
    assert mi["applied"] and mi["source_memory_ids"][0].startswith("DMEM-")
    assert set(mi["priority_incident_ids"]) == {"INC-NORTH-0001", "INC-CEN-0002"}
    # decision differs: memory run fetches the prior lead's incidents first; control starts with the Planner's keyword search
    assert d2.calls[0] == "by_ids" and d3.calls[0] == "search"
    t2 = json.dumps(_trace(env, r2["investigation_id"]))
    assert "memory_influence" in t2 and mi["source_memory_ids"][0] in t2
    assert "memory_influence" not in json.dumps(_trace(env, r3["investigation_id"]))
    # the lead is still re-verified and re-challenged from this run's records
    assert [a["agent"] for a in r2["agents"]] == ["planner", "finder", "skeptic", "reporter"]
    assert r2["candidate_links"][0]["validation_status"] == "SUPPORTED"


def test_memory_cannot_raise_a_link_to_supported(env):  # noqa: F811
    env(SCRIPT(), data=_data()).run_investigation(QUERY)
    dm = DecisionMemory(env.cfg.state_path, env.cfg.hmem_scope)
    mem_id = dm.influence(QUERY2)["source_memory_ids"][0]
    # Run 2 retrieves only the two incidents (no evidence rows); the Finder cites the memory id and prior evidence ids.
    d2 = FakeData([INC_A, INC_B], {k: [] for k in EV})
    link = good_link(supporting_evidence_ids=[mem_id, "FOR-0001", "FOR-0002"])
    r2 = env({"planner": [PLAN_KEYWORDS], "finder": [{"links": [link]}], "skeptic": [SKEPTIC_ACCEPT], "reporter": [REPORT_OK]},
             data=d2).run_investigation(QUERY2)
    cl = r2["candidate_links"][0]
    assert cl["validation_status"] != "SUPPORTED" and cl["independent_source_count"] == 0
    assert r2["memory"]["write"]["attempted"] is False        # so it cannot be re-promoted into memory either
    assert len([x for x in dm._load() if x["kind"] == "verified"]) == 1


def test_verifier_treats_memory_ids_as_non_evidence():
    idx = ev.EvidenceIndex()
    idx.add_incidents([INC_A, INC_B])
    v = ev.verify_link(good_link(supporting_evidence_ids=["DMEM-run-LINK-01", "FOR-0001"]), idx)
    assert v.status != "SUPPORTED" and v.independent_source_count == 0


def test_objected_or_unverified_links_are_not_written(env):  # noqa: F811
    high = {"review_status": "rejected", "objections": [{"link_id": "LINK-01", "kind": "alternative_explanation",
            "description": "Same bar sold everywhere.", "cited_ids": ["FOR-0001"], "severity": "high"}]}
    r = env({"planner": [PLAN_KEYWORDS], "finder": [FINDER_OK], "skeptic": [high], "reporter": [REPORT_OK]},
            data=_data()).run_investigation(QUERY)
    assert r["memory"]["write"]["attempted"] is False
    weak = {"links": [good_link(supporting_evidence_ids=["FOR-0001"])]}
    r = env({"planner": [PLAN_KEYWORDS], "finder": [weak], "skeptic": [SKEPTIC_OK], "reporter": [REPORT_OK]},
            data=_data()).run_investigation(QUERY)
    assert r["candidate_links"][0]["validation_status"] != "SUPPORTED" and r["memory"]["write"]["attempted"] is False
    assert [x for x in DecisionMemory(env.cfg.state_path, env.cfg.hmem_scope)._load() if x["kind"] == "verified"] == []


def test_write_gate_defence_in_depth(tmp_path):
    dm = DecisionMemory(tmp_path)
    base = {"link_id": "L1", "source_incident_id": "A", "target_incident_id": "B", "shared_attributes": []}
    assert dm.write_verified("r", [{**base, "status": "WEAK"}, {**base, "status": "SUPPORTED", "open_high_objection": True}]) == []
    assert dm._load() == []


def test_rejected_link_is_suppressed_and_flagged_not_promoted(tmp_path):
    dm = DecisionMemory(tmp_path)
    base = {"link_id": "L1", "source_incident_id": "INC-NORTH-0001", "target_incident_id": "INC-CEN-0002",
            "shared_attributes": [{"attribute": "tool", "value": "chisel-tip"}]}
    dm.write_verified("r1", [{**base, "status": "SUPPORTED"}])
    dm.write_rejected("r2", [{**base, "link_id": "L9", "status": "REJECTED"}])
    inf = dm.influence("look at INC-NORTH-0001")
    assert inf["starting_hypotheses"] == [] and inf["priority_incident_ids"] == []      # suppressed
    assert inf["flagged_rejected"][0]["reason"] == "verifier_rejected"
    dm2 = DecisionMemory(tmp_path / "x")
    dm2.write_rejected("r", [{**base, "status": "REJECTED"}])
    assert dm2.influence("INC-NORTH-0001")["priority_incident_ids"] == []              # rejected alone never raises


def test_empty_memory_changes_nothing(tmp_path):
    inf = DecisionMemory(tmp_path).influence("anything INC-NORTH-0001")
    assert inf["applied"] is False and inf["priority_incident_ids"] == []
