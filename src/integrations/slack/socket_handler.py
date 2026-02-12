"""Slack Socket Mode event handlers for real-time monitoring."""

import asyncio
from typing import Callable, Optional

import structlog
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from src.config.settings import settings

logger = structlog.get_logger()


class SlackSocketHandler:
    """Handles real-time Slack events via Socket Mode."""

    def __init__(self, workspace: str = "internal"):
        self.workspace = workspace
        if workspace == "internal":
            self.app_token = settings.slack_internal_app_token
        else:
            self.app_token = settings.slack_external_app_token
        self._client: Optional[SocketModeClient] = None
        self._on_new_thread: Optional[Callable] = None
        self._on_mention: Optional[Callable] = None

    def on_new_thread(self, handler: Callable):
        """Register handler for new thread events."""
        self._on_new_thread = handler
        return handler

    def on_mention(self, handler: Callable):
        """Register handler for @mention events."""
        self._on_mention = handler
        return handler

    async def _handle_event(self, client: SocketModeClient, req: SocketModeRequest):
        """Process incoming Socket Mode events."""
        # Acknowledge the event
        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_socket_mode_response(response)

        if req.type != "events_api":
            return

        event = req.payload.get("event", {})
        event_type = event.get("type")

        logger.info(
            "slack.event_received",
            workspace=self.workspace,
            event_type=event_type,
            channel=event.get("channel"),
        )

        # New message in a channel (potential new thread)
        if event_type == "message" and not event.get("subtype"):
            # It's a new thread if there's no thread_ts or thread_ts == ts
            if not event.get("thread_ts") or event.get("thread_ts") == event.get("ts"):
                if self._on_new_thread:
                    await self._on_new_thread(event, self.workspace)

        # App mention
        if event_type == "app_mention":
            if self._on_mention:
                await self._on_mention(event, self.workspace)

    async def start(self):
        """Start the Socket Mode connection."""
        if not self.app_token:
            logger.warning("slack.socket_mode_skipped", workspace=self.workspace, reason="no app token")
            return

        from slack_sdk.web.async_client import AsyncWebClient

        from src.integrations.slack.client import SlackClient

        if self.workspace == "internal":
            client = SlackClient("internal")
        else:
            client = SlackClient("external")

        try:
            bot_token = await client.get_access_token()
        except Exception as e:
            logger.warning("slack.socket_mode_skipped", workspace=self.workspace, reason=str(e))
            return

        web_client = AsyncWebClient(token=bot_token)
        self._client = SocketModeClient(
            app_token=self.app_token,
            web_client=web_client,
        )
        self._client.socket_mode_request_listeners.append(self._handle_event)

        logger.info("slack.socket_mode_starting", workspace=self.workspace)
        await self._client.connect()

    async def stop(self):
        """Stop the Socket Mode connection."""
        if self._client:
            await self._client.close()
            logger.info("slack.socket_mode_stopped", workspace=self.workspace)
