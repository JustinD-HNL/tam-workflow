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
            return dict(response)
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
            return response.get("messages", [])
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
            return response.get("messages", [])
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
            return response.get("user", {})
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
            return response.get("permalink", "")
        except SlackApiError as e:
            logger.error("slack.permalink_failed", error=str(e))
            return ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def list_channels(self, limit: int = 1000) -> list[dict]:
        """List all channels the bot has access to."""
        client = await self._get_client()
        channels = []
        cursor = None
        try:
            while True:
                kwargs = {
                    "types": "public_channel,private_channel",
                    "limit": min(limit, 200),
                    "exclude_archived": True,
                }
                if cursor:
                    kwargs["cursor"] = cursor
                response = await client.conversations_list(**kwargs)
                channels.extend(response.get("channels", []))
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor or len(channels) >= limit:
                    break
            return channels
        except SlackApiError as e:
            logger.error("slack.list_channels_failed", error=str(e))
            raise IntegrationError(f"Slack list channels failed: {e.response['error']}") from e

    async def find_channel_by_name(self, name: str) -> Optional[dict]:
        """Find a channel by name (case-insensitive). Returns channel dict or None."""
        channels = await self.list_channels()
        name_lower = name.lower()
        for ch in channels:
            if ch.get("name", "").lower() == name_lower:
                return ch
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable),
    )
    async def list_users(self, limit: int = 500) -> list[dict]:
        """List all users in the workspace."""
        client = await self._get_client()
        users = []
        cursor = None
        try:
            while True:
                kwargs = {"limit": min(limit, 200)}
                if cursor:
                    kwargs["cursor"] = cursor
                response = await client.users_list(**kwargs)
                users.extend(response.get("members", []))
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor or len(users) >= limit:
                    break
            return users
        except SlackApiError as e:
            logger.error("slack.list_users_failed", error=str(e))
            raise IntegrationError(f"Slack list users failed: {e.response['error']}") from e

    async def find_user_by_name(self, query: str) -> Optional[dict]:
        """Find a user by display name, real name, or username (case-insensitive)."""
        users = await self.list_users()
        q = query.lower().strip()
        for user in users:
            if user.get("deleted") or user.get("is_bot"):
                continue
            profile = user.get("profile", {})
            # Match against various name fields
            if q == user.get("name", "").lower():
                return user
            if q == profile.get("display_name", "").lower():
                return user
            if q == profile.get("real_name", "").lower():
                return user
            if q == profile.get("display_name_normalized", "").lower():
                return user
            # Partial match on real name
            if q in profile.get("real_name_normalized", "").lower():
                return user
        return None

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
