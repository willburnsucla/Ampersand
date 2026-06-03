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

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

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
    ampersand_backend_mode: str = Field(default="mock", alias="AMPERSAND_BACKEND_MODE")

    # ── Server ────────────────────────────────────────────────────────────────
    port: int = 8000
    log_level: str = "INFO"

    @property
    def is_mock(self) -> bool:
        return self.ampersand_backend_mode == "mock"


settings = Settings()
