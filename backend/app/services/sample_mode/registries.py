"""
Model registries for the three ways a run can obtain model output.

  SampleModelRegistry      offline: replay recorded Nightshift responses by prompt hash; no match ->
                           the documented code-only fallback. Never touches the network.
  RecordingModelRegistry   live Nightshift, and every successful response is written as a fixture
                           (used only by scripts/record_fixtures.py).
  ResilientModelRegistry   live Nightshift; if Nightshift is unreachable/unconfigured/failing, the call is
                           served by a SampleModelRegistry and the call record says so. After the first
                           failure live calls are skipped for the rest of the run (one timeout, not many).

All three keep ModelRegistry's contract: ``generate`` returns ``(NightshiftResponse, CallRecord)`` and the
CallRecord carries the requested model, the reported model and ``source`` (live | replayed | code_fallback).
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

from app.config import Settings
from app.services.model_registry import CHAT_ROLES, CallRecord, ModelRegistry
from app.services.nightshift_client import (
    NightshiftAuthError,
    NightshiftClient,
    NightshiftNotConfiguredError,
    NightshiftQueryError,
    NightshiftResponse,
    NightshiftTimeoutError,
)
from app.services.sample_mode import code_agents
from app.services.sample_mode.fixtures import FixtureStore, prompt_hash

logger = logging.getLogger(__name__)

LIVE_FAILURES = (NightshiftNotConfiguredError, NightshiftAuthError, NightshiftQueryError, NightshiftTimeoutError)


class _OfflineClient(NightshiftClient):
    """No network, ever. Serves the recorded model catalogue; every other call is refused."""

    def __init__(self, cfg: Settings, store: FixtureStore) -> None:
        super().__init__(cfg)
        self._store = store

    def list_models(self) -> List[str]:
        models = self._store.catalog()
        if models is None:
            raise NightshiftNotConfiguredError("offline sample mode: no recorded model catalogue")
        return models

    def generate(self, *a, **k):                        # pragma: no cover - guarded by SampleModelRegistry
        raise NightshiftNotConfiguredError("offline sample mode makes no network calls")

    embed = generate


def _target(registry: ModelRegistry, role: str) -> str:
    a = registry.assignment(role)
    return a.effective_model or registry.fallback_model


class SampleModelRegistry(ModelRegistry):
    def __init__(self, cfg: Settings, store: FixtureStore) -> None:
        super().__init__(cfg, _OfflineClient(cfg, store))
        self._store = store

    def generate(self, role: str, messages: List[Dict[str, str]], max_tokens: int = 1200, temperature: float = 0.2,
                 timeout_seconds: Optional[float] = None) -> Tuple[NightshiftResponse, CallRecord]:
        if role not in CHAT_ROLES:
            raise ValueError(f"role {role!r} is not a chat role")
        target = _target(self, role)
        key = prompt_hash(role, target, messages)
        fx = self._store.get(key)
        if fx:
            resp = NightshiftResponse(content=fx["content"], model=fx["reported_model"], provider=fx.get("provider") or "unknown",
                                      receipt_id=fx.get("receipt_id"), latency_ms=fx.get("latency_ms"), usage=fx.get("usage"),
                                      finish_reason=fx.get("finish_reason"))
            rec = CallRecord(
                role=role, requested_model=fx["requested_model"], reported_model=fx["reported_model"], provider=fx.get("provider"),
                receipt_id=fx.get("receipt_id"), fallback_used=bool(fx.get("fallback_used")), fallback_reason=fx.get("fallback_reason"),
                latency_ms=fx.get("latency_ms"), routed_as_requested=fx.get("routed_as_requested"),
                prompt_tokens=(fx.get("usage") or {}).get("prompt_tokens"), completion_tokens=(fx.get("usage") or {}).get("completion_tokens"),
                source="replayed")
            logger.info("sample mode: replayed %s response %s (recorded from live %s)", role, key[:10], fx["reported_model"])
            return resp, rec
        content = code_agents.respond(role, messages)
        rec = CallRecord(role=role, requested_model=target, reported_model=None, provider=None, fallback_used=True,
                         fallback_reason=f"no recorded fixture for this prompt (sha256 {key[:12]}); code-only fallback ran, no model answered",
                         latency_ms=0.0, source="code_fallback")
        logger.info("sample mode: no fixture for %s prompt %s; code-only fallback", role, key[:10])
        return NightshiftResponse(content=content, model="", provider="code_fallback", latency_ms=0.0, finish_reason="stop"), rec


class RecordingModelRegistry(ModelRegistry):
    """Live registry that records each successful response as a fixture (see scripts/record_fixtures.py)."""

    def __init__(self, cfg: Settings, store: FixtureStore, client: Optional[NightshiftClient] = None) -> None:
        super().__init__(cfg, client)
        self._store = store
        self.recorded = 0

    def generate(self, role: str, messages: List[Dict[str, str]], max_tokens: int = 1200, temperature: float = 0.2,
                 timeout_seconds: Optional[float] = None) -> Tuple[NightshiftResponse, CallRecord]:
        target = _target(self, role)
        catalog = self.catalog()
        if catalog:
            self._store.put_catalog(catalog)
        resp, rec = super().generate(role, messages, max_tokens, temperature, timeout_seconds)
        self._store.put(prompt_hash(role, target, messages), {
            "role": role, "requested_model": rec.requested_model, "reported_model": rec.reported_model, "provider": rec.provider,
            "receipt_id": rec.receipt_id, "latency_ms": rec.latency_ms, "usage": resp.usage, "finish_reason": resp.finish_reason,
            "content": resp.content, "fallback_used": rec.fallback_used, "fallback_reason": rec.fallback_reason,
            "routed_as_requested": rec.routed_as_requested,
            "recorded_at": time.strftime("%Y-%m-%d", time.gmtime()), "recorded_from": "live Nightshift /v1/chat/completions"})
        self.recorded += 1
        return resp, rec


class ResilientModelRegistry(ModelRegistry):
    """Live first; on a Nightshift failure fall back to the offline sample path, loudly and once."""

    def __init__(self, cfg: Settings, sample: SampleModelRegistry, client: Optional[NightshiftClient] = None) -> None:
        super().__init__(cfg, client)
        self._sample = sample
        self.live_down: Optional[str] = None

    def catalog(self, refresh: bool = False):
        # once live Nightshift has failed, use the recorded catalogue instead of re-probing a dead endpoint
        return self._sample.catalog(refresh) if self.live_down else super().catalog(refresh)

    def generate(self, role: str, messages: List[Dict[str, str]], max_tokens: int = 1200, temperature: float = 0.2,
                 timeout_seconds: Optional[float] = None) -> Tuple[NightshiftResponse, CallRecord]:
        if self.live_down is None:
            try:
                return super().generate(role, messages, max_tokens, temperature, timeout_seconds)
            except LIVE_FAILURES as exc:
                self.live_down = f"{type(exc).__name__}: {str(exc)[:160]}"
                logger.warning("Nightshift unavailable (%s); serving model calls from the offline sample path", self.live_down)
        resp, rec = self._sample.generate(role, messages, max_tokens, temperature, timeout_seconds)
        rec.fallback_used = True
        rec.fallback_reason = f"live Nightshift unavailable ({self.live_down}); {rec.fallback_reason or 'recorded response replayed'}"
        return resp, rec
