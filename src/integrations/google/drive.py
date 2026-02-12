"""Google Drive API client."""

import asyncio

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.integrations.base import IntegrationClient
from src.models.integration import IntegrationType

logger = structlog.get_logger()


class GoogleDriveClient(IntegrationClient):
    integration_type = IntegrationType.GOOGLE

    async def _get_service(self):
        """Build the Google Drive API service."""
        token = await self.get_access_token()
        refresh_token = await self.get_refresh_token()
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        return build("drive", "v3", credentials=creds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def move_to_folder(self, file_id: str, folder_id: str) -> dict:
        """Move a file (e.g., a new Google Doc) into a specific folder."""
        service = await self._get_service()
        # Get current parents
        file = await asyncio.to_thread(service.files().get(fileId=file_id, fields="parents").execute)
        previous_parents = ",".join(file.get("parents", []))

        result = await asyncio.to_thread(
            service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute
        )
        logger.info("drive.moved_to_folder", file_id=file_id, folder_id=folder_id)
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_folder(self, folder_id: str) -> list[dict]:
        """List files in a Drive folder."""
        service = await self._get_service()
        result = await asyncio.to_thread(
            service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
            ).execute
        )
        return result.get("files", [])
