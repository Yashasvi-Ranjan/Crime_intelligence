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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    # ── Derived helpers ──────────────────────────────────────────────────────
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


settings = Settings()
