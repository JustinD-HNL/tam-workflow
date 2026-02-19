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

    @staticmethod
    def extract_page_title(page_data: dict) -> str:
        """Extract the title from a Notion page response."""
        properties = page_data.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
        return "Untitled"

    async def update_customer_health(
        self,
        page_id: str,
        health_status: str,
        summary: str,
        last_meeting_date: Optional[str] = None,
        key_risks: Optional[str] = None,
        opportunities: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> dict:
        """Update a customer health page by appending a new health update section.

        Works with standalone Notion pages (not database entries) by appending
        content blocks. Also tries to set database properties if they exist.
        """
        # Try to update properties if the page is a database entry
        try:
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
            await self.update_page(page_id, properties)
            logger.info("notion.health_properties_updated", page_id=page_id)
        except Exception:
            # Page is likely standalone (not a database entry) — that's fine
            logger.info("notion.health_properties_skipped", page_id=page_id, reason="not a database entry")

        # Always append a content block with the health update
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(health_status, "⚪")
        # Build heading: "🟡 Health Update — MYOB — 2026-02-19" or "🟡 Health Update — 2026-02-19"
        heading_parts = [f"{status_emoji} Health Update"]
        if customer_name:
            heading_parts.append(customer_name)
        if last_meeting_date:
            heading_parts.append(last_meeting_date)
        heading = " — ".join(heading_parts)

        blocks = [
            {"type": "divider", "divider": {}},
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": heading}}],
                },
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": summary[:2000]}}],
                },
            },
        ]
        if key_risks and key_risks.lower() != "none":
            blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Risks: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": key_risks[:2000]}},
                    ],
                },
            })
        if opportunities and opportunities.lower() != "none":
            blocks.append({
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Opportunities: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": opportunities[:2000]}},
                    ],
                },
            })

        result = await self.append_blocks(page_id, blocks)
        logger.info("notion.health_blocks_appended", page_id=page_id)
        return result

    async def get_page_text(self, page_id: str) -> str:
        """Extract plain text from a Notion page's content blocks."""
        blocks = await self.get_page_content(page_id)
        text_parts = []
        for block in blocks:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})
            rich_text = block_data.get("rich_text", [])
            for rt in rich_text:
                text_parts.append(rt.get("plain_text", ""))
            if block_type in ("heading_1", "heading_2", "heading_3", "paragraph"):
                text_parts.append("\n")
            if block_type == "divider":
                text_parts.append("\n---\n")
        return "".join(text_parts).strip()

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
