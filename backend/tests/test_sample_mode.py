"""Offline sample mode: the real loop over local data, replayed/fallback model output, /run contract."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.sample_mode.fixtures import FixtureStore, prompt_hash
from app.services.sample_mode.local_investigation import LocalInvestigationService
from app.services.sample_mode.registries import SampleModelRegistry

client = TestClient(app)
Q = "Are the commercial safe burglaries across NORTH and CENTRAL linked by the same heavy pry bar or crowbar?"
Q2 = "Do the keyless SUV relay thefts in NORTH and RIVERSIDE form one series?"
TOP = {"run_id", "status", "output", "agents", "engines", "trace_id", "log_file", "execution_time_seconds"}
ROOT = Path(__file__).resolve().parents[2]


def _run(query, **extra):
    r = client.post("/run", json={"input": {"query": query}, "options": {"sample_mode": True}, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _trace(body):
    return [json.loads(l) for l in (ROOT / body["log_file"]).read_text().splitlines()]


def test_run_contract_and_trace_evidence():
    body = _run(Q)
    assert set(body) == TOP and body["trace_id"] == body["run_id"]
    assert {"links", "report", "stopping_reason", "summary"} <= set(body["output"])
    assert body["output"]["data_mode"] == "local_sample" and body["output"]["is_sample"] is True
    ev = _trace(body)
    steps = {e["step"] for e in ev}
    assert {"routing", "handoff", "branch", "retrieval", "analysis", "review", "report"} <= steps
    assert len({e["agent"] for e in ev if (e.get("provider_meta") or {}).get("role")}) >= 2
    sql = [e for e in ev if e.get("sql_meta")]
    assert sql and all(e["sql_meta"]["source"] == "local_sample" and e["sql_meta"]["query_ids"] for e in sql)
    assert any(e.get("engine_meta") or e["status"] == "engine_unavailable" for e in ev)
    for e in ev:                                   # every model call names its source; none is a made-up engine event
        pm = e.get("provider_meta")
        if pm:
            assert pm["source"] in ("replayed", "code_fallback") and "requested_model" in pm and "reported_model" in pm
            assert pm["reported_model"] not in ("auto", "meterless")


def test_different_inputs_give_different_outputs():
    a, b = _run(Q), _run(Q2)
    assert a["output"]["candidate_incident_ids"] != b["output"]["candidate_incident_ids"]
    assert a["output"]["summary"] != b["output"]["summary"]


def test_ids_are_grounded_in_local_data():
    body = _run(Q)
    known = {r["incident_id"] for r in json.loads((ROOT / "data/generated/police_incidents.json").read_text())}
    assert set(body["output"]["candidate_incident_ids"]) <= known
    for l in body["output"]["links"]:
        assert {l["source_incident_id"], l["target_incident_id"]} <= known


@pytest.mark.parametrize("bad", [{}, {"input": {}}, {"input": {"query": ""}}, {"input": {"query": "x"}, "run_id": "../etc/passwd"}])
def test_invalid_body_is_422(bad):
    assert client.post("/run", json=bad).status_code == 422


def test_health_reports_state_per_integration():
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["zetaris"]["state"] in ("live", "sample", "down")
    assert h["nightshift"]["state"] in ("live", "sample", "down")


def test_local_service_matches_zetaris_contract():
    svc = LocalInvestigationService()
    rows = svc.search_candidate_incidents(keywords=["pry"], station_ids=["NORTH"], limit=3)
    assert len(rows) <= 3 and all(r["station_id"] == "NORTH" for r in rows)
    assert [r["reported_at"] for r in rows] == sorted((r["reported_at"] for r in rows), reverse=True)
    ids = svc.take_query_ids()
    assert ids and ids[0].startswith("local-") and svc.query_count == 1 and svc.source == "local_sample"
    assert svc.get_incidents_by_ids(["INC-NORTH-0042"])[0]["incident_id"] == "INC-NORTH-0042"


def test_fixture_replay_is_keyed_by_prompt_and_labelled(tmp_path):
    cfg = Settings()
    store = FixtureStore(tmp_path)
    reg = SampleModelRegistry(cfg, store)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    _, miss = reg.generate("planner", msgs)
    assert miss.source == "code_fallback" and miss.reported_model is None
    target = reg.assignment("planner").effective_model or reg.fallback_model
    store.put(prompt_hash("planner", target, msgs), {"requested_model": target, "reported_model": target, "provider": "nvidia",
                                                   "receipt_id": "r1", "latency_ms": 5.0, "content": "{}", "usage": {}})
    resp, hit = reg.generate("planner", msgs)
    assert hit.source == "replayed" and hit.reported_model == target and resp.content == "{}"
    _, other = reg.generate("planner", [*msgs[:1], {"role": "user", "content": "different"}])
    assert other.source == "code_fallback"          # a different prompt never matches


def test_trace_endpoint_shows_only_what_was_recorded():
    body = _run(Q)
    ev = client.get(f"/api/investigations/{body['run_id']}/trace").json()["events"]
    raw = _trace(body)
    assert len(ev) == len(raw)
    for api_ev, rec in zip(ev, raw):
        pm = rec.get("provider_meta") or {}
        assert api_ev["model"] == (pm.get("reported_model") or "")          # no default model on non-model steps
        assert api_ev["receipt_id"] == (pm.get("receipt_id") or "")         # no invented receipt
        if not pm:
            assert api_ev["model"] == "" and api_ev["receipt_id"] == ""
        else:
            assert api_ev["details"]["source"] in ("replayed", "code_fallback")


def test_recorded_fixtures_are_world_readable(tmp_path):
    # mkstemp makes 0600 files; a root-built image would then hide them from the non-root container user
    store = FixtureStore(tmp_path)
    store.put("abc", {"content": "x"})
    store.put_catalog(["m"])
    for p in tmp_path.glob("*.json"):
        assert p.stat().st_mode & 0o044 == 0o044, p
