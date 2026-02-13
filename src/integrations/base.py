"""Base integration client with retry logic and token management."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.integrations.encryption import decrypt_token
from src.models.database import async_session
from src.models.integration import IntegrationCredential, IntegrationStatus, IntegrationType

logger = structlog.get_logger()


class IntegrationError(Exception):
    """Base exception for integration errors."""

    pass


class TokenExpiredError(IntegrationError):
    """Token has expired and needs refresh."""

    pass


class IntegrationClient:
    """Base class for integration API clients."""

    integration_type: IntegrationType = None

    async def get_access_token(self) -> str:
        """Get the decrypted access token from the database."""
        async with async_session() as session:
            result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.integration_type == self.integration_type
                )
            )
            cred = result.scalar_one_or_none()
            if not cred or not cred.access_token_encrypted:
                raise IntegrationError(
                    f"{self.integration_type.value} is not connected. "
                    "Please connect it in Settings."
                )
            if cred.status == IntegrationStatus.EXPIRED:
                raise TokenExpiredError(
                    f"{self.integration_type.value} token has expired. "
                    "Please reconnect in Settings."
                )
            return decrypt_token(cred.access_token_encrypted)

    async def get_refresh_token(self) -> str | None:
        """Get the decrypted refresh token from the database."""
        async with async_session() as session:
            result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.integration_type == self.integration_type
                )
            )
            cred = result.scalar_one_or_none()
            if cred and cred.refresh_token_encrypted:
                return decrypt_token(cred.refresh_token_encrypted)
            return None

    async def get_oauth_client_credentials(self) -> tuple[str | None, str | None]:
        """Get the OAuth client_id and client_secret from DB, falling back to .env.

        For Google, also checks the IntegrationCredential.extra_data field
        where gcloud ADC client credentials are stored during import.
        """
        import json as json_module
        from src.integrations.oauth_helpers import get_oauth_credentials
        # Map IntegrationType enum to the string key used by oauth_helpers
        type_map = {
            IntegrationType.GOOGLE: "google",
            IntegrationType.SLACK_INTERNAL: "slack_internal",
            IntegrationType.SLACK_EXTERNAL: "slack_external",
            IntegrationType.LINEAR: "linear",
            IntegrationType.NOTION: "notion",
        }
        key = type_map.get(self.integration_type)
        if not key:
            return None, None
        async with async_session() as session:
            client_id, client_secret = await get_oauth_credentials(key, session)
            if client_id:
                return client_id, client_secret

            # For Google: check extra_data on the credential (gcloud ADC import stores creds there)
            if self.integration_type == IntegrationType.GOOGLE:
                result = await session.execute(
                    select(IntegrationCredential).where(
                        IntegrationCredential.integration_type == self.integration_type
                    )
                )
                cred = result.scalar_one_or_none()
                if cred and cred.extra_data:
                    try:
                        extra = json_module.loads(cred.extra_data)
                        return extra.get("client_id"), extra.get("client_secret")
                    except (json_module.JSONDecodeError, TypeError):
                        pass

            return client_id, client_secret

    async def refresh_google_token(self) -> str:
        """Refresh the Google access token using the stored refresh token.

        Updates the stored access token in the database and returns the new token.
        """
        import httpx
        from src.integrations.encryption import encrypt_token

        refresh_token = await self.get_refresh_token()
        client_id, client_secret = await self.get_oauth_client_credentials()

        if not refresh_token or not client_id or not client_secret:
            raise TokenExpiredError("Cannot refresh: missing refresh token or OAuth credentials")

        async with httpx.AsyncClient() as http:
            resp = await http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if resp.status_code != 200:
                raise TokenExpiredError(f"Token refresh failed: {resp.text}")
            data = resp.json()

        new_access_token = data["access_token"]

        # Update stored token
        async with async_session() as session:
            result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.integration_type == self.integration_type
                )
            )
            cred = result.scalar_one_or_none()
            if cred:
                cred.access_token_encrypted = encrypt_token(new_access_token)
                cred.status = IntegrationStatus.CONNECTED
                from datetime import datetime, timezone, timedelta
                cred.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
                cred.last_verified = datetime.now(timezone.utc)
                await session.commit()

        logger.info("token.refreshed", integration=self.integration_type.value)
        return new_access_token
