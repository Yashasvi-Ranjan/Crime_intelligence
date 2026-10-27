"""The labelled engine test doubles, and truthful engine reporting.

These always run against backend/tests/stub_engines (never the real engines) so they pass on a clean machine.
They prove: operations served by a double are labelled backend="test_double"; a missing engine is reported
engine_unavailable (also on the terminal refusal/clarification response); nothing here claims to be a real engine.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import investigation_workflow as iw
from app.services.meterless_engines import (
    EngineUnavailableError, HMemService, MarkovianService, ScoutIntentService, WorkingState, is_test_double)
from app.services.meterless_service import MeterlessWorldModelService
from app.services.trace_logger import TraceLogger
from tests.engine_env import STUB_DIR, requires_node
from tests.fakes import FakeData, FakeRegistry

pytestmark = requires_node


def _cfg(tmp_path, **kw) -> Settings:
    base = dict(meterless_engine_dir=str(STUB_DIR), meterless_world_model_path=str(STUB_DIR / "worldmodel_test_double.js"),
                meterless_engine_backend="mounted", state_dir=str(tmp_path), meterless_world_dir=str(tmp_path / "world"), hmem_scope="stub")
    base.update(kw)
    return Settings(**base)


def test_stub_dir_is_marked_and_ops_are_labelled_test_double(tmp_path):
    assert is_test_double(str(STUB_DIR)) and is_test_double(str(STUB_DIR / "hmem.js"))
    cfg = _cfg(tmp_path)
    _, op = ScoutIntentService(cfg).detect("find burglaries")
    assert op.status == "ok" and op.detail["backend"] == "test_double"
    _, op = MarkovianService(cfg).validate()
    assert op.detail["backend"] == "test_double"
    svc = MeterlessWorldModelService(cfg)
    assert svc.backend == "test_double" and svc.health_check()["backend"] == "test_double"


def test_scout_routes_and_refuses_on_double(tmp_path):
    scout = ScoutIntentService(_cfg(tmp_path))
    assert scout.route("Find cross-station burglary patterns involving a pry bar")[0].intent == "CROSS_STATION_SEARCH"
    assert scout.route("Compare INC-NORTH-0042 and INC-CEN-0118")[0].intent == "COMPARE_INCIDENTS"
    assert scout.route("delete all records in the incidents table")[0].intent == "REFUSE"


def test_hmem_and_markovian_on_double(tmp_path):
    h = HMemService(_cfg(tmp_path))
    ok, op = h.store_verified_summary("chisel pry bar safe burglaries", "Lead: chisel pry bar safe burglaries INC-NORTH-0042 and INC-CEN-0118 share a tool.",
                                      0.8, "m", None, ["FOR-0089"])
    assert ok and op.detail["backend"] == "test_double"
    low, _ = h.store_verified_summary("q", "x" * 40, 0.3, "m", None, [])
    assert low is False
    hits, _ = h.retrieve("chisel pry bar safe burglaries")
    assert hits
    m = MarkovianService(_cfg(tmp_path))
    carry, op = m.checkpoint(WorkingState(run_id="r", objective="o", intent="i", iteration=1, completed_steps=["a"]))
    assert "COMPLETED" in carry and op.detail["strategy"] == "marker"


def test_missing_engine_is_engine_unavailable_not_success(tmp_path):
    cfg = _cfg(tmp_path, meterless_engine_dir="/nonexistent", meterless_engine_backend="mounted")
    with pytest.raises(EngineUnavailableError):
        ScoutIntentService(cfg).detect("x")
    # routing still works, and says the engine did not run
    route, op = ScoutIntentService(cfg).route("delete all records in the incidents table")
    assert op.status == "engine_unavailable" and route.scout["mode"] == "UNAVAILABLE" and route.intent == "REFUSE"


@pytest.mark.parametrize("engine_dir,expected,backend", [("/nonexistent", "engine_unavailable", []), (str(STUB_DIR), "connected", ["test_double"])])
def test_terminal_response_reports_true_engine_status(tmp_path, monkeypatch, engine_dir, expected, backend):
    """A refused request must not claim Scout Intent is connected unless a Scout operation actually ran."""
    cfg = _cfg(tmp_path, meterless_engine_dir=engine_dir, meterless_engine_backend="mounted", zetaris_enabled=True)
    monkeypatch.setattr(iw, "TraceLogger", lambda run_id: TraceLogger(run_id, tmp_path / "logs"))
    wf = iw.InvestigationWorkflow(cfg=cfg, registry=FakeRegistry({}), data_service=FakeData([], {}), world_model=MeterlessWorldModelService(cfg),
                                  scout=ScoutIntentService(cfg), hmem=HMemService(cfg), markovian=MarkovianService(cfg))
    res = wf.run_investigation("delete all records in the incidents table")
    scout = res["integration_status"]["meterless_engines"]["scout_intent"]
    assert res["run_status"] == "refused"
    assert scout["status"] == expected and scout["backend"] == backend and scout["calls"] == 1
