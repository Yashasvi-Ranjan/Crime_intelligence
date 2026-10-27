"""
Unit tests for Nightshift AI Provider Client
============================================
Fast, deterministic tests using mocked httpx transport.
Tests model routing verification, error handling, retries, and timeouts.
"""

import httpx
import pytest

from app.config import Settings
from app.services.nightshift_client import (
    NightshiftAuthError,
    NightshiftClient,
    NightshiftNotConfiguredError,
    NightshiftQueryError,
    NightshiftTimeoutError,
)


def make_mock_settings(token="mock-token-xyz"):
    return Settings(
        nightshift_base_url="http://127.0.0.1:8088/v1",
        nightshift_api_key=token,
        nightshift_model="nvidia/nemotron-3.5-lightning-30b-a3b",
        nightshift_timeout_seconds=5,
        nightshift_max_retries=2,
    )


def test_nightshift_success_with_model_metadata():
    cfg = make_mock_settings()

    def handler(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer mock-token-xyz"
        assert request.headers["meterless-app"] == "crime-intel"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test-01",
                "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Toolmark matches 36mm chisel."},
                        "finish_reason": "stop",
                    }
                ],
                "meterless": {
                    "receipt_id": "rcpt_test_123",
                    "winning_route": {
                        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                        "provider": "nvidia",
                        "tier": "A",
                    },
                },
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    ai = NightshiftClient(cfg=cfg, client=mock_client)

    resp = ai.generate(messages=[{"role": "user", "content": "Analyze toolmarks"}])
    assert resp.content == "Toolmark matches 36mm chisel."
    assert resp.model == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert resp.provider == "nvidia"
    assert resp.receipt_id == "rcpt_test_123"
    assert resp.winning_route["tier"] == "A"


def test_nightshift_auth_error():
    cfg = make_mock_settings()

    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": {"message": "unauthorized"}})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    ai = NightshiftClient(cfg=cfg, client=mock_client)

    with pytest.raises(NightshiftAuthError) as exc_info:
        ai.generate(messages=[{"role": "user", "content": "Hello"}])
    assert "401" in str(exc_info.value)


def test_nightshift_transient_retry_and_recovery():
    cfg = make_mock_settings()
    attempts = 0

    def handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(
            200,
            json={
                "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                "choices": [{"message": {"role": "assistant", "content": "Recovered"}}],
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    ai = NightshiftClient(cfg=cfg, client=mock_client)

    resp = ai.generate(messages=[{"role": "user", "content": "Test"}])
    assert attempts == 2
    assert resp.content == "Recovered"


def test_nightshift_timeout():
    cfg = make_mock_settings()

    def handler(request: httpx.Request):
        raise httpx.TimeoutException("Connection timed out")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    ai = NightshiftClient(cfg=cfg, client=mock_client)

    with pytest.raises(NightshiftTimeoutError):
        ai.generate(messages=[{"role": "user", "content": "Test"}])


def test_nightshift_malformed_response():
    cfg = make_mock_settings()

    def handler(request: httpx.Request):
        return httpx.Response(200, json={"unexpected": "payload"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    ai = NightshiftClient(cfg=cfg, client=mock_client)

    with pytest.raises(NightshiftQueryError):
        ai.generate(messages=[{"role": "user", "content": "Test"}])


def test_nightshift_unconfigured():
    cfg = Settings(nightshift_base_url="", nightshift_api_key="")
    ai = NightshiftClient(cfg=cfg)
    with pytest.raises(NightshiftNotConfiguredError):
        ai.generate(messages=[{"role": "user", "content": "Test"}])


def test_nightshift_401_logs_redacted_diagnostics(caplog):
    """Mocked transport: verifies logging/redaction only, NOT live authentication."""
    cfg = make_mock_settings(token="super-secret-token-123")

    def handler(request: httpx.Request):
        return httpx.Response(
            401, text='{"error":"bad key","echo":"Bearer super-secret-token-123 nvapi-ABCDEF123456"}'
        )

    ai = NightshiftClient(cfg=cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    with caplog.at_level("ERROR", logger="app.services.nightshift_client"):
        with pytest.raises(NightshiftAuthError):
            ai.generate(messages=[{"role": "user", "content": "Hello"}])

    log = caplog.text
    assert "127.0.0.1:8088" in log
    assert "nvidia/nemotron-3.5-lightning-30b-a3b" in log
    assert "status=401" in log
    assert "super-secret-token-123" not in log
    assert "nvapi-ABCDEF123456" not in log
    assert "[REDACTED]" in log


def test_nightshift_missing_credentials(monkeypatch, tmp_path):
    """No key, no key file, and no local proxy-token -> NotConfigured, no HTTP call made."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    cfg = Settings(
        nightshift_base_url="http://127.0.0.1:8088/v1", nightshift_api_key="", nightshift_api_key_file=""
    )
    calls = []
    client = httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200)))
    with pytest.raises(NightshiftNotConfiguredError):
        NightshiftClient(cfg=cfg, client=client).generate(messages=[{"role": "user", "content": "x"}])
    assert calls == []


def test_nightshift_authenticated_request_sends_bearer_to_chat_completions():
    """Mocked transport: checks the request shape the client sends, not live authentication."""
    cfg = make_mock_settings(token="tok-abc")
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["path"] = request.url.path
        return httpx.Response(
            200, json={"model": cfg.nightshift_model, "choices": [{"message": {"content": "ok"}}]}
        )

    ai = NightshiftClient(cfg=cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert ai.generate(messages=[{"role": "user", "content": "hi"}]).content == "ok"
    assert seen == {"auth": "Bearer tok-abc", "path": "/v1/chat/completions"}
