"""Offline tests for scripts/redact_trace.py and the credential gate of scripts/capture_live_trace.py.
Only synthetic strings are used; no network, no real credentials."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import redact_trace as rt  # noqa: E402
import capture_live_trace as clt  # noqa: E402

UUID = "3f2b8c1e-9a4d-4e7b-8c55-0d1e2f3a4b5c"


def test_bearer_and_authorization_removed():
    s = rt.redact_text("Authorization: Bearer abcDEF1234567890xyz and Bearer zzzzzzzzzzzz12345")
    assert "abcDEF" not in s and "zzzzzzzz" not in s


def test_key_shapes_and_jwt_removed():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcd1234"
    s = rt.redact_text(f"k=nvapi-ABCDEFGHIJKLMNOPQRST1234 j={jwt} sk-ABCDEFGHIJKLMNOPQRSTUV AKIAABCDEFGHIJKLMNOP")
    for frag in ("ABCDEFGHIJKLMNOPQRST1234", "eyJhbGci", "AKIAABCDEFGHIJKLMNOP", "sk-ABCDEF"):
        assert frag not in s


def test_hostnames_ips_urls_emails_paths():
    s = rt.redact_text("http://host.docker.internal:8888/v1/q https://user:pw@zeta.example.internal/x 10.1.2.3:8088 "
                       "abc-123.trycloudflare.com me@example.com /Users/alice/proj /home/bob/x localhost:8000")
    for frag in ("host.docker.internal", "user:pw", "zeta.example", "10.1.2.3", "trycloudflare", "me@example.com", "alice", "bob", "localhost"):
        assert frag not in s, frag
    assert "/v1/q" in s  # path kept


def test_keyed_values_redacted_counters_kept():
    o = rt.redact_obj({"password": "hunter2", "api_key": "abc", "headers": {"Authorization": "Basic Zm9v"},
                       "prompt_tokens": 120, "usage": {"total_tokens": 300}, "note": "ok"})
    assert o["password"] == "[REDACTED_SECRET]" and o["api_key"] == "[REDACTED_SECRET]"
    assert o["headers"]["Authorization"] == "[REDACTED_SECRET]"
    assert o["prompt_tokens"] == 120 and o["usage"]["total_tokens"] == 300 and o["note"] == "ok"


def test_evidence_ids_preserved():
    text = f"query {UUID} receipt rcpt_9f8e7d6c model nvidia/nemotron-3-ultra-550b-a55b INC-NORTH-0042 CCTV-0112"
    assert rt.redact_text(text) == text


def test_env_literals_redacted_exactly():
    lits = rt.env_literals({"ZETARIS_PASSWORD": "S3cr3t!pw", "NIGHTSHIFT_API_KEY": "tok-literal-value", "ZETARIS_USERNAME": "ab"})
    assert lits == ["S3cr3t!pw", "tok-literal-value"] or sorted(lits) == sorted(["S3cr3t!pw", "tok-literal-value"])
    s = rt.redact_text("login S3cr3t!pw / tok-literal-value ok", lits)
    assert "S3cr3t" not in s and "tok-literal" not in s


def test_jsonl_roundtrip_and_check(tmp_path):
    src = tmp_path / "t.jsonl"
    ev = {"step": "sql", "sql_meta": {"query_ids": [UUID], "url": "http://10.0.0.5:8888/x"}, "token": "abc123abc123"}
    src.write_text(json.dumps(ev) + "\n")
    out = tmp_path / "t.redacted.jsonl"
    assert subprocess.run([sys.executable, str(SCRIPTS / "redact_trace.py"), str(src), str(out)]).returncode == 0
    red = out.read_text()
    assert UUID in red and "10.0.0.5" not in red and "abc123abc123" not in red
    assert subprocess.run([sys.executable, str(SCRIPTS / "redact_trace.py"), str(out), "--check"]).returncode == 0
    assert subprocess.run([sys.executable, str(SCRIPTS / "redact_trace.py"), str(src), "--check"]).returncode == 1


def test_capture_fails_fast_without_credentials(tmp_path):
    assert clt.missing_credentials({}, token_files=[tmp_path / "nope"])  # no creds at all
    ok = {"ZETARIS_USERNAME": "u", "ZETARIS_PASSWORD": "p", "NIGHTSHIFT_API_KEY": "k"}
    assert clt.missing_credentials(ok) == []
    assert clt.missing_credentials({**ok, "SAMPLE_MODE": "true"})
    assert clt.missing_credentials({**ok, "ZETARIS_ENABLED": "false"})


def test_capture_script_exits_2_with_empty_env(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, str(SCRIPTS / "capture_live_trace.py")], env=env, capture_output=True, text=True)
    assert r.returncode == 2 and "NOT RUNNING" in r.stderr


def test_liveness_rejects_replayed_runs():
    ev = [{"step": "sql", "sql_meta": {"query_ids": ["local-abc"], "source": "local_sample"}},
          {"step": "llm", "agent": "planner", "provider_meta": {"source": "replayed", "requested_model": "m", "reported_model": "m"}}]
    s = clt.summarise(ev)
    assert clt.liveness_problems(s, {"output": {"data_mode": "local_sample"}})
    good = [{"step": "sql", "sql_meta": {"query_ids": [UUID], "source": "zetaris_live"}},
            {"step": "llm", "agent": "planner", "provider_meta": {"source": "live", "receipt_id": "r1", "requested_model": "m", "reported_model": "m"}}]
    assert clt.liveness_problems(clt.summarise(good), {"output": {"data_mode": "zetaris_live"}}) == []
