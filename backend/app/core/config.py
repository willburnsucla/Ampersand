"""
Application settings loaded from environment variables / .env file.
All other modules import `settings` from here — never read env vars directly.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://ampersand:ampersand@localhost:5432/ampersand"
    sync_database_url: str = "postgresql://ampersand:ampersand@localhost:5432/ampersand"

    # ── Extractor backend ─────────────────────────────────────────────────────
    # which extractor get_extractor wires, independent of the repo mode: "mock"
    # (MockExtractorV2, deterministic, no key) or "gemini" (GeminiExtractorV2). defaults
    # to mock so nothing calls a keyed api until set; flip to gemini to run real extraction
    # even under make dev-mock (no db needed). free key at aistudio.google.com.
    extractor_backend: str = "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_escalation_model: str = ""  # falls back to gemini_model (a plain retry) if unset

    # ── Voyage AI (embeddings) ────────────────────────────────────────────────
    voyage_api_key: str = ""

    # -- Supabase ---------------------------------
    # Project URL (https://<ref>.supabase.co). Used to fetch the public JWKS
    # for verifying asymmetric (ES256) JWTs.
    supabase_url: str = ""
    # Legacy shared secret for symmetric (HS256) JWTs. Fallback if the project
    # still signs with HS256.
    supabase_jwt_secret: str = ""


    # ── Backend mode ──────────────────────────────────────────────────────────
    # "mock"  → InMemoryGraphRepo + MockExtractor + MockAuthGate (no DB)
    # "real"  → PostgresGraphRepo + ClaudeExtractor + SupabaseAuthGate
    # defaults to real so a missing/misset env fails closed (auth on), not open.
    # make dev-mock sets mock explicitly; tests pin mock in conftest.
    ampersand_backend_mode: str = Field(default="real", alias="AMPERSAND_BACKEND_MODE")

    # ── Server ────────────────────────────────────────────────────────────────
    port: int = 8000
    log_level: str = "INFO"

    @property
    def is_mock(self) -> bool:
        return self.ampersand_backend_mode == "mock"


settings = Settings()
