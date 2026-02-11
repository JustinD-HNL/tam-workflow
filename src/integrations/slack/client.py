"""Slack API client for both internal and external workspaces."""

from typing import Optional

import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.integrations.base import IntegrationClient, IntegrationError
from src.models.integration import IntegrationType

logger = structlog.get_logger()


def _is_retryable(exc: BaseException) -> bool:
    """Check if a Slack error is retryable (rate limit, server error)."""
    if isinstance(exc, SlackApiError):
        return exc.response.status_code in (429, 500, 502, 503)
    return False


class SlackClient(IntegrationClient):
    """Slack client that works with either internal or external workspace."""

    def __init__(self, workspace: str = "internal"):
        if workspace == "internal":
            self.integration_type = IntegrationType.SLACK_INTERNAL
        elif workspace == "external":
            self.integration_type = IntegrationType.SLACK_EXTERNAL
        else:
            raise ValueError(f"Invalid workspace: {workspace}. Use 'internal' or 'external'.")
        self.workspace = workspace

    async def _get_client(self) -> AsyncWebClient:
        """Get an authenticated Slack WebClient."""
        token = await self.get_access_token()
        return AsyncWebClient(token=token)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list] = None,
        thread_ts: Optional[str] = None,
    ) -> dict:
        """Post a message to a Slack channel."""
        client = await self._get_client()
        try:
            kwargs = {"channel": channel, "text": text}
            if blocks:
                kwargs["blocks"] = blocks
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            response = await client.chat_postMessage(**kwargs)
            logger.info(
                "slack.message_posted",
                workspace=self.workspace,
                channel=channel,
                ts=response["ts"],
            )
            return response.data
        except SlackApiError as e:
            logger.error("slack.post_failed", error=str(e), channel=channel)
            raise IntegrationError(f"Slack post failed: {e.response['error']}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def get_channel_history(
        self,
        channel: str,
        limit: int = 20,
        oldest: Optional[str] = None,
    ) -> list[dict]:
        """Get recent messages from a channel."""
        client = await self._get_client()
        try:
            kwargs = {"channel": channel, "limit": limit}
            if oldest:
                kwargs["oldest"] = oldest
            response = await client.conversations_history(**kwargs)
            return response.data.get("messages", [])
        except SlackApiError as e:
            logger.error("slack.history_failed", error=str(e), channel=channel)
            raise IntegrationError(f"Slack history failed: {e.response['error']}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def get_thread_replies(self, channel: str, thread_ts: str) -> list[dict]:
        """Get replies in a thread."""
        client = await self._get_client()
        try:
            response = await client.conversations_replies(channel=channel, ts=thread_ts)
            return response.data.get("messages", [])
        except SlackApiError as e:
            logger.error("slack.thread_failed", error=str(e))
            raise IntegrationError(f"Slack thread fetch failed: {e.response['error']}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def get_user_info(self, user_id: str) -> dict:
        """Get user profile info."""
        client = await self._get_client()
        try:
            response = await client.users_info(user=user_id)
            return response.data.get("user", {})
        except SlackApiError as e:
            logger.error("slack.user_info_failed", error=str(e))
            raise IntegrationError(f"Slack user info failed: {e.response['error']}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def get_permalink(self, channel: str, message_ts: str) -> str:
        """Get a permalink for a message."""
        client = await self._get_client()
        try:
            response = await client.chat_getPermalink(channel=channel, message_ts=message_ts)
            return response.data.get("permalink", "")
        except SlackApiError as e:
            logger.error("slack.permalink_failed", error=str(e))
            return ""

    def format_agenda_blocks(self, customer_name: str, date: str, agenda_text: str) -> list:
        """Format an agenda as Slack Block Kit blocks."""
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Meeting Agenda: {customer_name} — {date}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": agenda_text[:3000]},
            },
        ]

    def format_notes_blocks(self, customer_name: str, date: str, notes_text: str) -> list:
        """Format meeting notes as Slack Block Kit blocks."""
        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Meeting Notes: {customer_name} — {date}"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": notes_text[:3000]},
            },
        ]
