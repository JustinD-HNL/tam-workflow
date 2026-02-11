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
