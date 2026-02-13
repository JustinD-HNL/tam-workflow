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
        username: Optional[str] = None,
        icon_url: Optional[str] = None,
    ) -> dict:
        """Post a message to a Slack channel.

        If username/icon_url are provided, the message appears with that
        display name and avatar instead of the default bot identity.
        """
        client = await self._get_client()
        try:
            kwargs = {"channel": channel, "text": text}
            if blocks:
                kwargs["blocks"] = blocks
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            if username:
                kwargs["username"] = username
            if icon_url:
                kwargs["icon_url"] = icon_url
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
        """List all channels the bot has access to.

        Tries public + private channels first; falls back to public-only
        if the bot lacks the groups:read scope.
        """
        client = await self._get_client()
        channel_types = "public_channel,private_channel"

        for attempt in range(2):
            channels = []
            cursor = None
            try:
                while True:
                    kwargs = {
                        "types": channel_types,
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
                if e.response["error"] == "missing_scope" and "private_channel" in channel_types:
                    logger.info("slack.list_channels_fallback", workspace=self.workspace,
                                detail="groups:read scope missing, retrying with public channels only")
                    channel_types = "public_channel"
                    continue
                logger.error("slack.list_channels_failed", error=str(e))
                raise IntegrationError(f"Slack list channels failed: {e.response['error']}") from e
        return []

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

    async def resolve_user_ids_in_text(self, text: str) -> str:
        """Replace <@USER_ID> patterns in text with real display names."""
        import re
        user_ids = re.findall(r"<@(U[A-Z0-9]+)>", text)
        if not user_ids:
            return text
        for uid in set(user_ids):
            try:
                user_info = await self.get_user_info(uid)
                profile = user_info.get("profile", {})
                name = profile.get("display_name") or profile.get("real_name") or user_info.get("name", uid)
                text = text.replace(f"<@{uid}>", f"@{name}")
            except Exception:
                pass
        return text

    async def get_user_profile_photo(self, user_id: str) -> Optional[str]:
        """Get a user's profile photo URL."""
        try:
            user_info = await self.get_user_info(user_id)
            profile = user_info.get("profile", {})
            return profile.get("image_72") or profile.get("image_48") or profile.get("image_192")
        except Exception:
            return None

    async def get_user_display_name(self, user_id: str) -> Optional[str]:
        """Get a user's display name."""
        try:
            user_info = await self.get_user_info(user_id)
            profile = user_info.get("profile", {})
            return profile.get("display_name") or profile.get("real_name") or user_info.get("name")
        except Exception:
            return None

    @staticmethod
    def _split_text_to_blocks(text: str, max_len: int = 3000) -> list:
        """Split long text into multiple Slack section blocks.

        Tries to split on paragraph boundaries, falling back to line
        boundaries, then hard-cutting at max_len.
        """
        if len(text) <= max_len:
            return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]

        blocks = []
        remaining = text
        while remaining:
            if len(remaining) <= max_len:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining}})
                break

            # Try to split at a paragraph boundary
            cut = remaining[:max_len].rfind("\n\n")
            if cut < max_len // 2:
                # Try line boundary
                cut = remaining[:max_len].rfind("\n")
            if cut < max_len // 4:
                # Hard cut
                cut = max_len

            chunk = remaining[:cut].rstrip()
            remaining = remaining[cut:].lstrip()
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})

        return blocks

    def format_agenda_blocks(self, customer_name: str, date: str, agenda_text: str) -> list:
        """Format an agenda as Slack Block Kit blocks."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Meeting Agenda: {customer_name} — {date}"},
            },
            {"type": "divider"},
        ]
        blocks.extend(self._split_text_to_blocks(agenda_text))
        return blocks

    def format_notes_blocks(self, customer_name: str, date: str, notes_text: str) -> list:
        """Format meeting notes as Slack Block Kit blocks."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Meeting Notes: {customer_name} — {date}"},
            },
            {"type": "divider"},
        ]
        blocks.extend(self._split_text_to_blocks(notes_text))
        return blocks
