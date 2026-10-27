"""Vendored Meterless reference engines (H-MEM, Markovian) behind the same adapters. Skip if not built."""

import shutil

import pytest

from app.config import Settings
from app.services.meterless_engines import HMemService, MarkovianService, WorkingState, resolve_engine_backend

CFG = Settings(meterless_engine_dir="/nonexistent", meterless_engine_backend="reference")
pytestmark = pytest.mark.skipif(
    not shutil.which("node") or not (CFG.reference_engine_path / "hmem.cjs").exists(),
    reason="Node or the built reference engines (scripts/build_reference_engines.sh) not available")


def test_backend_resolution_without_mounted_engines():
    assert resolve_engine_backend(CFG, "hmem") == "reference" and resolve_engine_backend(CFG, "markovian") == "reference"
    assert resolve_engine_backend(CFG, "scout") is None        # Scout Intent has no open reference


def test_markovian_reference_ops():
    m = MarkovianService(CFG)
    cfg, op = m.validate()
    assert cfg["maxChunks"] == 3 and op.status == "ok" and op.detail["backend"] == "reference"
    st = WorkingState(run_id="r", objective="o", intent="i", iteration=1, completed_steps=["retrieved 3"])
    carry, op = m.checkpoint(st)
    assert "COMPLETED" in carry and op.detail["strategy"] == "marker"
    prompt, _ = m.continuation_prompt("find the ring", carry)
    assert "[CARRYOVER STATE]" in prompt and "find the ring" in prompt
    eff, _ = m.efficiency([100, 120, 90])
    assert eff["totalTokensUsed"] == 310


def test_hmem_reference_gates_and_roundtrip(tmp_path):
    h = HMemService(Settings(meterless_engine_dir="/nonexistent", meterless_engine_backend="reference", hmem_scope="t"),
                    store_file=tmp_path / "hmem-knowledge.json")
    stored, _ = h.store_verified_summary("q", "x", 0.2, "m", None, [])            # below the 0.6 floor
    assert stored is False
    stored, _ = h.store_verified_summary("q", "key nvapi-" + "a" * 30, 0.8, "m", None, [])   # secret gate
    assert stored is False
    stored, op = h.store_verified_summary("safe burglaries chisel pry bar", "Lead: INC-A and INC-B share a chisel-tip pry bar.", 0.8,
                                         "nvidia/nemotron-3.5-lightning-30b-a3b", "rcpt-1", ["FOR-1"])
    assert stored is True and op.detail["backend"] == "reference"
    hits, _ = h.retrieve("chisel pry bar safe burglaries")
    assert hits and "chisel" in hits[0]["content"]
