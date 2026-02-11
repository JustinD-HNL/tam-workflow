"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tamworkflow:tamworkflow@localhost:5432/tamworkflow"

    # Encryption
    encryption_key: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Slack — Internal
    slack_internal_client_id: str = ""
    slack_internal_client_secret: str = ""
    slack_internal_app_token: str = ""

    # Slack — External
    slack_external_client_id: str = ""
    slack_external_client_secret: str = ""
    slack_external_app_token: str = ""

    # Linear
    linear_client_id: str = ""
    linear_client_secret: str = ""

    # Notion
    notion_client_id: str = ""
    notion_client_secret: str = ""

    # OAuth
    oauth_redirect_base_url: str = "http://localhost:8000"

    # App
    log_level: str = "INFO"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
