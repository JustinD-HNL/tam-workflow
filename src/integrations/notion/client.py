"""Notion API client with rate limiting."""

import asyncio
import time
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.integrations.base import IntegrationClient, IntegrationError
from src.models.integration import IntegrationType

logger = structlog.get_logger()

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Rate limiting: Notion allows 3 requests per second
_last_request_time = 0.0
_rate_limit_lock = asyncio.Lock()


async def _rate_limit():
    """Enforce Notion's 3 requests/second rate limit."""
    global _last_request_time
    async with _rate_limit_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < 0.34:  # ~3 req/s
            await asyncio.sleep(0.34 - elapsed)
        _last_request_time = time.monotonic()


class NotionClient(IntegrationClient):
    integration_type = IntegrationType.NOTION

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Make a rate-limited request to the Notion API."""
        await _rate_limit()
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{NOTION_API_URL}{path}",
                json=json_data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": NOTION_VERSION,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                logger.warning("notion.rate_limited", retry_after=retry_after)
                await asyncio.sleep(retry_after)
                raise IntegrationError("Rate limited by Notion")
            response.raise_for_status()
            return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_page(self, page_id: str) -> dict:
        """Get a Notion page by ID."""
        data = await self._request("GET", f"/pages/{page_id}")
        logger.info("notion.page_fetched", page_id=page_id)
        return data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def update_page(self, page_id: str, properties: dict) -> dict:
        """Update a Notion page's properties."""
        data = await self._request(
            "PATCH",
            f"/pages/{page_id}",
            json_data={"properties": properties},
        )
        logger.info("notion.page_updated", page_id=page_id)
        return data

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_page_content(self, page_id: str) -> list[dict]:
        """Get the block children (content) of a page."""
        data = await self._request("GET", f"/blocks/{page_id}/children?page_size=100")
        return data.get("results", [])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def append_blocks(self, page_id: str, blocks: list[dict]) -> dict:
        """Append content blocks to a page."""
        data = await self._request(
            "PATCH",
            f"/blocks/{page_id}/children",
            json_data={"children": blocks},
        )
        logger.info("notion.blocks_appended", page_id=page_id, count=len(blocks))
        return data

    async def update_customer_health(
        self,
        page_id: str,
        health_status: str,
        summary: str,
        last_meeting_date: Optional[str] = None,
        key_risks: Optional[str] = None,
        opportunities: Optional[str] = None,
    ) -> dict:
        """Update a customer health page with standard fields.

        Expects the Notion page to have these properties:
        - Health Status (select): green/yellow/red
        - Summary (rich_text)
        - Last Meeting Date (date)
        - Key Risks (rich_text)
        - Opportunities (rich_text)
        """
        properties = {
            "Health Status": {
                "select": {"name": health_status.capitalize()},
            },
            "Summary": {
                "rich_text": [{"text": {"content": summary[:2000]}}],
            },
        }
        if last_meeting_date:
            properties["Last Meeting Date"] = {
                "date": {"start": last_meeting_date},
            }
        if key_risks:
            properties["Key Risks"] = {
                "rich_text": [{"text": {"content": key_risks[:2000]}}],
            }
        if opportunities:
            properties["Opportunities"] = {
                "rich_text": [{"text": {"content": opportunities[:2000]}}],
            }

        return await self.update_page(page_id, properties)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def query_database(
        self,
        database_id: str,
        filter_obj: Optional[dict] = None,
        sorts: Optional[list] = None,
    ) -> list[dict]:
        """Query a Notion database."""
        body = {}
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts

        data = await self._request("POST", f"/databases/{database_id}/query", json_data=body)
        return data.get("results", [])
