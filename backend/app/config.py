"""
Configuration for Cross-Station Crime Intelligence backend.
All secrets and connection details are loaded from environment variables.
Nothing sensitive is ever hardcoded or logged.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # The documented location is <repo root>/.env (copied from .env.example). backend/.env is still
    # read if present (older checkouts); the root file wins. Real environment variables win over both.
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / "backend" / ".env"), str(REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_environment: str = "development"
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:4173"

    # ── Zetaris REST API & Local Docker ─────────────────────────────────────
    zetaris_enabled: bool = False
    zetaris_base_url: str = "http://localhost:8888"
    zetaris_auth_url: str = "http://localhost:8889"
    zetaris_org_id: str = "1"
    zetaris_username: str = ""
    zetaris_password: str = ""          # loaded from env; never logged
    zetaris_api_token: str = ""
    zetaris_engine_id: str = ""
    zetaris_timeout_seconds: int = 30
    zetaris_max_query_rows: int = 500

    # ── Zetaris JDBC / Thrift Connection (port 10000) ────────────────────────
    zetaris_jdbc_host: str = "localhost"
    zetaris_jdbc_port: int = 10000
    zetaris_database: str = "default"

    # ── Zetaris Table Names ──────────────────────────────────────────────────
    zetaris_namespace: str = "lightning.ndp_filestore"
    zetaris_table_police_incidents: str = "police_incidents"
    zetaris_table_newspaper_reports: str = "newspaper_reports"
    zetaris_table_witness_reports: str = "witness_reports"
    zetaris_table_cctv_reports: str = "cctv_reports"
    zetaris_table_forensic_reports: str = "forensic_reports"

    # ── Local fallback ───────────────────────────────────────────────────────
    local_data_dir: str = "../data/generated"

    # ── Nightshift / AI Provider (OpenAI-compatible) ─────────────────────────
    nightshift_base_url: str = "http://127.0.0.1:8088/v1"
    nightshift_api_key: str = ""          # token/key; never logged
    nightshift_api_key_file: str = ""     # path to a file holding the token (Docker/K8s secret mount); never logged
    nightshift_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nightshift_app_name: str = "crime-intel"
    nightshift_timeout_seconds: int = 60
    nightshift_max_retries: int = 3

    # ── Role → model registry (verified against Nightshift /v1/models at runtime)
    # Empty string = use nightshift_model (Lightning). Never an invented ID.
    nightshift_model_planner: str = ""
    nightshift_model_finder: str = ""
    nightshift_model_skeptic: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nightshift_model_reporter: str = ""
    nightshift_model_embedding: str = "nvidia/nemotron-3-embed-1b"
    model_super_vl: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nightshift_model_vision: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nightshift_model_rerank: str = ""                # no rerank model is served by this Nightshift build
    nightshift_model_fallback: str = ""              # defaults to nightshift_model
    nightshift_skeptic_timeout_seconds: int = 180

    # ── Investigation workflow budgets ──────────────────────────────────────
    workflow_max_iterations: int = 3
    workflow_max_model_calls: int = 24
    workflow_time_budget_seconds: int = 900
    workflow_retrieval_limit: int = 10
    workflow_evidence_limit_per_source: int = 8
    state_dir: str = "../.state"          # Markovian run state + H-MEM store (gitignored)

    # ── Meterless Engines: H-MEM / Scout Intent / Markovian ─────────────────
    meterless_engine_dir: str = "/Applications/Nightshift.app/Contents/Resources/engine/js/engine"
    hmem_enabled: bool = True
    hmem_scope: str = "crime-intel"

    # Engine backend per engine: "mounted" = the host's Nightshift engine directory (METERLESS_ENGINE_DIR),
    # "reference" = the vendored Apache-2.0 Meterless reference implementations (H-MEM, Markovian) built into the
    # image, "auto" = mounted when its file exists, else reference when one exists, else the engine is unavailable.
    meterless_engine_backend: str = "auto"
    meterless_reference_dir: str = ""     # built reference engines; defaults to <repo>/third_party/meterless/build

    # ── Meterless Engine / World Model ──────────────────────────────────────
    meterless_world_model_path: str = "/Applications/Nightshift.app/Contents/Resources/engine/js/engine/worldmodel.js"
    meterless_world_dir: str = ""         # Defaults to ~/Library/Application Support/ai.meterless.runtime/world

    # ── Sample Mode Toggle ──────────────────────────────────────────────────
    sample_mode: bool = False
    # Recorded Nightshift responses replayed in sample mode (see scripts/record_fixtures.py).
    sample_fixture_dir: str = "../data/sample/model_fixtures"

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def state_path(self) -> Path:
        base = Path(__file__).parent.parent
        p = (base / self.state_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def fallback_model(self) -> str:
        return self.nightshift_model_fallback or self.nightshift_model

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def local_data_path(self) -> Path:
        base = Path(__file__).parent.parent  # backend/
        return (base / self.local_data_dir).resolve()

    def table_fqn(self, table_key: str) -> str:
        """Return fully-qualified table name.

        If the table variable already contains a dot it is treated as a
        full FQN (e.g. ``crime_police_db.police_incidents``) and returned
        as-is.  Otherwise it is prefixed with ``zetaris_namespace``.
        """
        table = getattr(self, f"zetaris_table_{table_key}", table_key)
        if "." in table:
            return table  # already a fully-qualified name
        if self.zetaris_namespace:
            return f"{self.zetaris_namespace}.{table}"
        return table

    @property
    def zetaris_configured(self) -> bool:
        """True only if enabled and valid credentials/token are present."""
        has_creds = (bool(self.zetaris_username) and bool(self.zetaris_password)) or bool(self.zetaris_api_token)
        return (
            self.zetaris_enabled
            and bool(self.zetaris_base_url)
            and self.zetaris_base_url != "https://YOUR_ZETARIS_INSTANCE_URL_HERE"
            and has_creds
        )

    @property
    def sample_fixture_path(self) -> Path:
        return (Path(__file__).parent.parent / self.sample_fixture_dir).resolve()

    @property
    def reference_engine_path(self) -> Path:
        if self.meterless_reference_dir:
            return Path(self.meterless_reference_dir).resolve()
        return REPO_ROOT / "third_party" / "meterless" / "build"

    @property
    def resolved_nightshift_token(self) -> str:
        """Nightshift token: NIGHTSHIFT_API_KEY, else the file named by NIGHTSHIFT_API_KEY_FILE, else the
        local Nightshift proxy-token file (macOS host install)."""
        if self.nightshift_api_key:
            return self.nightshift_api_key
        if self.nightshift_api_key_file:
            try:
                return Path(self.nightshift_api_key_file).read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        token_path = Path.home() / "Library/Application Support/ai.meterless.runtime/proxy-token"
        if token_path.exists():
            try:
                return token_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    @property
    def nightshift_configured(self) -> bool:
        """True if Nightshift base URL is set and auth token is available."""
        return bool(self.nightshift_base_url) and bool(self.resolved_nightshift_token)


settings = Settings()
