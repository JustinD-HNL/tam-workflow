"""Helper to resolve OAuth app credentials from DB first, then .env fallback."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.integrations.encryption import decrypt_token
from src.models.oauth_config import OAuthAppConfig


# Map integration type to .env setting names
_ENV_FALLBACKS = {
    "google": ("google_client_id", "google_client_secret"),
    "slack_internal": ("slack_internal_client_id", "slack_internal_client_secret"),
    "slack_external": ("slack_external_client_id", "slack_external_client_secret"),
    "linear": ("linear_client_id", "linear_client_secret"),
    "notion": ("notion_client_id", "notion_client_secret"),
}


async def get_oauth_credentials(
    integration_type: str, db: AsyncSession
) -> tuple[Optional[str], Optional[str]]:
    """Get client_id and client_secret for an integration.

    Checks the database first (UI-configured), then falls back to .env values.
    Returns (client_id, client_secret) — either or both may be None if not configured.
    """
    # Check DB first
    result = await db.execute(
        select(OAuthAppConfig).where(
            OAuthAppConfig.integration_type == integration_type
        )
    )
    config = result.scalar_one_or_none()

    if config and config.client_id_encrypted:
        try:
            client_id = decrypt_token(config.client_id_encrypted)
            client_secret = (
                decrypt_token(config.client_secret_encrypted)
                if config.client_secret_encrypted
                else None
            )
            if client_id:
                return client_id, client_secret
        except ValueError:
            pass  # Decryption failed, fall through to .env

    # Fall back to .env
    env_keys = _ENV_FALLBACKS.get(integration_type)
    if env_keys:
        client_id = getattr(settings, env_keys[0], "") or None
        client_secret = getattr(settings, env_keys[1], "") or None
        return client_id, client_secret

    return None, None


async def get_extra_config(
    integration_type: str, db: AsyncSession
) -> Optional[str]:
    """Get extra config (e.g., Slack app_token) from DB."""
    result = await db.execute(
        select(OAuthAppConfig).where(
            OAuthAppConfig.integration_type == integration_type
        )
    )
    config = result.scalar_one_or_none()
    if config and config.extra_config_encrypted:
        try:
            return decrypt_token(config.extra_config_encrypted)
        except ValueError:
            pass
    return None


async def is_configured(integration_type: str, db: AsyncSession) -> bool:
    """Check if an integration has OAuth credentials configured (DB or .env)."""
    client_id, client_secret = await get_oauth_credentials(integration_type, db)
    return bool(client_id)
