"""Model registry tests - MOCKED Nightshift client (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.services.model_registry import (
    NEMOTRON_MODELS,
    ROLE_MODEL_PREFERENCES,
    ModelRegistry,
    analyze_cctv_frame,
)
from app.services.nightshift_client import (
    NightshiftClient, NightshiftQueryError, NightshiftResponse, NightshiftTimeoutError)

LIGHTNING = "nvidia/nemotron-3.5-lightning-30b-a3b"
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b"
SUPER_VL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
EMBED = "nvidia/nemotron-3-embed-1b"


def _cfg(**kw) -> Settings:
    base = dict(nightshift_model=LIGHTNING, nightshift_api_key="test-token", nightshift_model_skeptic=ULTRA,
                nightshift_model_planner="", nightshift_model_finder="", nightshift_model_reporter="", nightshift_model_embedding=EMBED,
                model_super_vl=SUPER_VL, nightshift_model_rerank="")
    base.update(kw)
    return Settings(**base)


def _resp(model: str) -> NightshiftResponse:
    return NightshiftResponse(content="{}", model=model, provider="nvidia", latency_ms=3.0, usage={"completion_tokens": 7})


def _client(models, generate=None) -> MagicMock:
    c = MagicMock(spec=NightshiftClient)
    c.list_models.return_value = models
    if generate:
        c.generate.side_effect = generate
    return c


def test_role_routing_uses_verified_models_and_lightning_default():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING, ULTRA, EMBED]))
    assert reg.assignment("planner").effective_model == LIGHTNING
    assert reg.assignment("reporter").effective_model == LIGHTNING
    sk = reg.assignment("skeptic")
    assert (sk.effective_model, sk.status, sk.fallback_model) == (ULTRA, "verified", LIGHTNING)


def test_unlisted_model_falls_back_and_says_so():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING]))
    a = reg.assignment("skeptic")
    assert a.status == "fallback" and a.effective_model == LIGHTNING
    assert ULTRA in a.reason
    client = reg._client
    client.generate.return_value = _resp(LIGHTNING)
    _, rec = reg.generate("skeptic", [{"role": "user", "content": "x"}])
    assert rec.fallback_used and rec.requested_model == LIGHTNING and ULTRA in rec.fallback_reason


def test_specialist_failure_retries_once_on_fallback_and_records_it():
    calls = []

    def gen(**kw):
        calls.append(kw["model"])
        if kw["model"] == ULTRA:
            raise NightshiftTimeoutError("slow")
        return _resp(LIGHTNING)

    reg = ModelRegistry(_cfg(), _client([LIGHTNING, ULTRA], gen))
    resp, rec = reg.generate("skeptic", [{"role": "user", "content": "x"}])
    assert calls == [ULTRA, LIGHTNING]
    assert rec.fallback_used and "failed" in rec.fallback_reason
    assert rec.reported_model == LIGHTNING          # reported model comes from the response, not the plan
    assert rec.completion_tokens == 7


def test_reported_model_is_taken_from_response_and_mismatch_is_visible():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING, ULTRA], lambda **kw: _resp("someone/else")))
    _, rec = reg.generate("skeptic", [{"role": "user", "content": "x"}])
    assert rec.requested_model == ULTRA and rec.reported_model == "someone/else" and rec.routed_as_requested is False


def test_fallback_failure_raises_structured_error():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING], lambda **kw: (_ for _ in ()).throw(NightshiftQueryError("boom"))))
    with pytest.raises(NightshiftQueryError):
        reg.generate("planner", [{"role": "user", "content": "x"}])


def test_rerank_never_enabled_without_verified_route():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING]))
    a = reg.assignment("rerank")
    assert a.status == "unavailable" and a.effective_model is None
    reg2 = ModelRegistry(_cfg(nightshift_model_rerank="nvidia/made-up-rerank"), _client([LIGHTNING]))
    assert reg2.assignment("rerank").effective_model is None


def test_embedding_requires_listing_and_working_route():
    client = _client([LIGHTNING, EMBED])
    reg = ModelRegistry(_cfg(), client)
    assert reg.assignment("embedding").status == "unverified"
    client.embed.side_effect = NightshiftQueryError("Nightshift embeddings returned HTTP 404")
    reg.probe_embeddings()
    a = reg.assignment("embedding")
    assert a.status == "unavailable" and "404" in a.reason and a.effective_model is None
    client.embed.side_effect = None
    client.embed.return_value = [[0.1, 0.2]]
    reg.probe_embeddings()
    assert reg.assignment("embedding").status == "verified"


def test_catalog_unavailable_is_reported_not_assumed():
    c = MagicMock(spec=NightshiftClient)
    c.list_models.side_effect = NightshiftQueryError("down")
    reg = ModelRegistry(_cfg(), c)
    assert reg.assignment("skeptic").status == "unverified"
    rep = reg.report()
    assert rep["catalog_checked"] is False and "down" in rep["catalog_error"]


def test_chat_roles_only():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING]))
    with pytest.raises(ValueError):
        reg.generate("embedding", [])


def test_env_variable_names_in_env_example_actually_load(monkeypatch):
    monkeypatch.setenv("NIGHTSHIFT_MODEL_SKEPTIC", "nvidia/some-other-model")
    monkeypatch.setenv("NIGHTSHIFT_MODEL_RERANK", "nvidia/x-rerank")
    monkeypatch.setenv("WORKFLOW_MAX_ITERATIONS", "5")
    s = Settings()
    assert s.nightshift_model_skeptic == "nvidia/some-other-model" and s.nightshift_model_rerank == "nvidia/x-rerank"
    assert s.workflow_max_iterations == 5


def test_nemotron_models_registered_and_returns_super_vl():
    assert "super-vl-120b" in NEMOTRON_MODELS
    assert NEMOTRON_MODELS["super-vl-120b"] == SUPER_VL
    assert NEMOTRON_MODELS["lightning-30b"] == LIGHTNING
    assert NEMOTRON_MODELS["ultra-550b"] == ULTRA
    assert NEMOTRON_MODELS["embed-1b"] == EMBED

    reg = ModelRegistry(_cfg(), _client([LIGHTNING, ULTRA, SUPER_VL, EMBED]))
    assert reg.nemotron_models["super-vl-120b"] == SUPER_VL


def test_role_model_preferences_explicitly_represents_quad_models():
    assert ROLE_MODEL_PREFERENCES["ingestion"] == LIGHTNING
    assert ROLE_MODEL_PREFERENCES["pii_sanitization"] == LIGHTNING
    assert ROLE_MODEL_PREFERENCES["report_generation"] == LIGHTNING
    assert ROLE_MODEL_PREFERENCES["cross_station_planning"] == ULTRA
    assert ROLE_MODEL_PREFERENCES["adversarial_skeptic"] == ULTRA
    assert ROLE_MODEL_PREFERENCES["visual_scene_analysis"] == SUPER_VL
    assert ROLE_MODEL_PREFERENCES["cctv_analysis"] == SUPER_VL
    assert ROLE_MODEL_PREFERENCES["semantic_mo_embedding"] == EMBED

    reg = ModelRegistry(_cfg(), _client([LIGHTNING]))
    assert reg.role_model_preferences["cctv_analysis"] == SUPER_VL


def test_settings_super_vl_configuration(monkeypatch):
    s = Settings()
    assert s.model_super_vl == SUPER_VL
    monkeypatch.setenv("MODEL_SUPER_VL", "nvidia/custom-super-vl")
    s2 = Settings()
    assert s2.model_super_vl == "nvidia/custom-super-vl"


def test_vision_role_assignment():
    reg = ModelRegistry(_cfg(), _client([LIGHTNING, SUPER_VL]))
    v_assign = reg.assignment("vision")
    assert v_assign.status == "verified"
    assert v_assign.effective_model == SUPER_VL

    reg_fallback = ModelRegistry(_cfg(), _client([LIGHTNING]))
    v_fb = reg_fallback.assignment("vision")
    assert v_fb.status == "fallback"
    assert v_fb.effective_model == LIGHTNING


def test_analyze_cctv_frame_optical_fallback_with_metadata():
    prompt = (
        "Optical observation for camera CAM-CEN-04-02: observed dark grey minivan with partial plate 7XYZ89 "
        "and suspect wearing dark hoodie near back door."
    )
    res = analyze_cctv_frame(
        image_bytes=b"mock_synthetic_frame_bytes",
        camera_id="CAM-CEN-04-02",
        prompt=prompt,
    )
    assert res["camera_id"] == "CAM-CEN-04-02"
    assert res["model"] == SUPER_VL
    assert res["fallback_used"] is True
    assert isinstance(res["receipt_id"], str) and res["receipt_id"].startswith("rcpt-")
    assert isinstance(res["description"], str) and len(res["description"]) > 10
    assert "CAM-CEN-04-02" in res["description"]
    assert "7XYZ89" in res["description"]
    assert isinstance(res["entities"], list)

    # Check extracted entities (plate, vehicle, suspect, camera)
    entities_str = [str(e) for e in res["entities"]]
    assert any("7XYZ89" in s for s in entities_str)
    assert any("minivan" in s.lower() for s in entities_str)
    assert any("hoodie" in s.lower() for s in entities_str)
    assert any("CAM-CEN-04-02" in s for s in entities_str)


def test_analyze_cctv_frame_fallback_json_prompt_parsing():
    import json
    json_prompt = json.dumps({
        "camera_id": "CAM-RIV-02",
        "partial_plate": "ABC-9999",
        "vehicle_description": "faded red hatchback",
        "suspect": "individual in high-vis vest",
        "observed_entities": ["pallet loading activity"],
    })
    res = analyze_cctv_frame(
        image_bytes=b"test_image_bytes",
        camera_id="CAM-RIV-02",
        prompt=json_prompt,
    )
    assert res["camera_id"] == "CAM-RIV-02"
    assert res["fallback_used"] is True
    assert res["model"] == SUPER_VL
    assert any("ABC-9999" in str(e) for e in res["entities"])
    assert any("hatchback" in str(e).lower() for e in res["entities"])
    assert any("vest" in str(e).lower() for e in res["entities"])


def test_analyze_cctv_frame_vision_online_success():
    mock_resp = NightshiftResponse(
        content="Optical detection confirmed: silver sedan bearing license plate 2XYZ45 heading westbound.",
        model=SUPER_VL,
        provider="nvidia",
        receipt_id="rcpt_vision_call_001",
    )
    c = _client([LIGHTNING, SUPER_VL], generate=lambda **kw: mock_resp)
    reg = ModelRegistry(_cfg(), c)

    # Non-mock bytes resembling valid image payload (>16 bytes and not mock prefix)
    valid_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    res = reg.analyze_cctv_frame(
        image_bytes=valid_bytes,
        camera_id="CAM-NORTH-01",
        prompt="Identify license plate and vehicle direction",
    )
    assert res["camera_id"] == "CAM-NORTH-01"
    assert res["fallback_used"] is False
    assert res["model"] == SUPER_VL
    assert res["receipt_id"] == "rcpt_vision_call_001"
    assert "Optical detection confirmed" in res["description"]
    assert any("2XYZ45" in str(e) for e in res["entities"])


def test_analyze_cctv_frame_handles_client_failure_gracefully():
    def _failing_generate(**kw):
        raise NightshiftQueryError("Nightshift vision API unavailable (HTTP 503)")

    c = _client([LIGHTNING, SUPER_VL], generate=_failing_generate)
    reg = ModelRegistry(_cfg(), c)
    valid_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 32
    res = reg.analyze_cctv_frame(
        image_bytes=valid_bytes,
        camera_id="CAM-NORTH-05",
        prompt="License plate 8KLM22 observed on dark blue truck",
    )
    # Resilient fallback must take over without unhandled exception
    assert res["camera_id"] == "CAM-NORTH-05"
    assert res["fallback_used"] is True
    assert res["model"] == SUPER_VL
    assert res["receipt_id"].startswith("rcpt-")
    assert any("8KLM22" in str(e) for e in res["entities"])
    assert any("truck" in str(e).lower() for e in res["entities"])


def test_analyze_cctv_frame_minimal_prompt_and_empty_bytes():
    res = analyze_cctv_frame(
        image_bytes=b"",
        camera_id="CAM-DEF-99",
        prompt="",
    )
    assert res["camera_id"] == "CAM-DEF-99"
    assert res["fallback_used"] is True
    assert res["model"] == SUPER_VL
    assert isinstance(res["entities"], list)
    assert len(res["entities"]) >= 1  # Camera entity at least
    assert res["entities"][0].get("id") == "CAM-DEF-99"

