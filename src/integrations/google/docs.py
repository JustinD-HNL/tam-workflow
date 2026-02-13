"""Google Docs API client."""

import asyncio

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential

from src.integrations.base import IntegrationClient
from src.models.integration import IntegrationType

logger = structlog.get_logger()


class GoogleDocsClient(IntegrationClient):
    integration_type = IntegrationType.GOOGLE

    async def _get_service(self):
        """Build the Google Docs API service with auto-refresh support."""
        try:
            token = await self.get_access_token()
        except Exception:
            # Token expired or missing — try to refresh
            token = await self.refresh_google_token()

        refresh_token = await self.get_refresh_token()
        client_id, client_secret = await self.get_oauth_client_credentials()
        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id or "",
            client_secret=client_secret or "",
        )
        return build("docs", "v1", credentials=creds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_document(self, document_id: str) -> dict:
        """Get a Google Doc by ID."""
        service = await self._get_service()
        return await asyncio.to_thread(service.documents().get(documentId=document_id).execute)

    async def get_document_text(self, document_id: str) -> str:
        """Extract plain text from a Google Doc."""
        doc = await self.get_document(document_id)
        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            if "paragraph" in element:
                for run in element["paragraph"].get("elements", []):
                    if "textRun" in run:
                        text_parts.append(run["textRun"]["content"])
        return "".join(text_parts)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_document(self, title: str, body_text: str = "") -> dict:
        """Create a new Google Doc."""
        service = await self._get_service()
        doc = await asyncio.to_thread(service.documents().create(body={"title": title}).execute)
        doc_id = doc["documentId"]

        if body_text:
            requests = [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": body_text,
                    }
                }
            ]
            await asyncio.to_thread(
                service.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                ).execute
            )

        logger.info("docs.created", doc_id=doc_id, title=title)
        return doc

    def extract_doc_id_from_url(self, url: str) -> str:
        """Extract document ID from a Google Docs URL."""
        # URLs like: https://docs.google.com/document/d/DOC_ID/edit
        parts = url.split("/d/")
        if len(parts) < 2:
            raise ValueError(f"Invalid Google Docs URL: {url}")
        return parts[1].split("/")[0]
