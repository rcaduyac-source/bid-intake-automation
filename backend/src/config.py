from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Mailbox label (informational; OAuth user is "me")
    email_address: str = ""

    # User OAuth (preferred — no Workspace admin / domain-wide delegation)
    gmail_oauth_client_secrets: str = "./secrets/gmail_oauth_client.json"
    gmail_token_path: str = "./secrets/gmail_token.json"

    # Legacy service-account path (unused when token file exists)
    google_application_credentials: str = ""

    gmail_poll_seconds: int = 60
    gmail_enabled: bool = False

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    openai_embed_dims: int = 1536
    short_text_token_threshold: int = 8000

    postgres_url: str = "postgresql+asyncpg://bid:bid@localhost:5432/bid_intake"
    pgvector_url: str = "postgresql+asyncpg://bid:bid@localhost:5433/bid_vectors"

    cors_origins: str = "http://localhost:5173,http://localhost:80"
    attachment_dir: str = "./data/attachments"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_mode(self) -> str:
        return "openai" if self.openai_api_key else "mock"

    @property
    def ai_model_label(self) -> str:
        if self.openai_api_key:
            return self.openai_chat_model
        return "heuristic mock (set OPENAI_API_KEY)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
