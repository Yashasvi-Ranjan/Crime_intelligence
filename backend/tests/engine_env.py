"""Which Meterless engines the core workflow tests run against.

Real engines (the Nightshift engine dir mounted on this machine) are used whenever they are present. On a clean
machine the tests fall back to ``stub_engines/``: minimal, clearly-labelled TEST DOUBLES (see
stub_engines/STUB_ENGINES.txt). Operations served by them are traced with backend="test_double", so a run on
stubs can never be mistaken for a run on the real engines. Real-engine-only tests (registry size, scoring,
reference builds) keep their own skip conditions and explicit reasons.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import Settings

STUB_DIR = Path(__file__).parent / "stub_engines"
_real = Settings()
REAL_ENGINES = bool(shutil.which("node")) and Path(_real.meterless_engine_dir, "hmem.js").exists()
REAL_WORLD_MODEL = bool(shutil.which("node")) and Path(_real.meterless_world_model_path).exists()

ENGINE_DIR = _real.meterless_engine_dir if REAL_ENGINES else str(STUB_DIR)
WORLD_MODEL_PATH = _real.meterless_world_model_path if REAL_WORLD_MODEL else str(STUB_DIR / "worldmodel_test_double.js")
engine_settings = {"meterless_engine_dir": ENGINE_DIR, "meterless_world_model_path": WORLD_MODEL_PATH}

requires_node = pytest.mark.skipif(not shutil.which("node"), reason="Node is not installed (engines and test doubles are Node programs)")
requires_real_engines = pytest.mark.skipif(
    not REAL_ENGINES, reason="real Nightshift engine modules not installed (METERLESS_ENGINE_DIR); test doubles do not count")
requires_real_world_model = pytest.mark.skipif(
    not REAL_WORLD_MODEL, reason="real Meterless World Model (worldmodel.js) not installed; test doubles do not count")
