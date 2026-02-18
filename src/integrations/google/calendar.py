"""Google Calendar API client."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential

from src.integrations.base import IntegrationClient, IntegrationError
from src.models.integration import IntegrationType

logger = structlog.get_logger()


class GoogleCalendarClient(IntegrationClient):
    integration_type = IntegrationType.GOOGLE

    async def _get_service(self):
        """Build the Google Calendar API service with auto-refresh support."""
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
        return build("calendar", "v3", credentials=creds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def list_upcoming_events(
        self,
        days_ahead: int = 7,
        calendar_id: str = "primary",
        query: Optional[str] = None,
    ) -> list[dict]:
        """List upcoming calendar events."""
        service = await self._get_service()
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        kwargs = {
            "calendarId": calendar_id,
            "timeMin": now.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 50,
        }
        if query:
            kwargs["q"] = query

        result = await asyncio.to_thread(service.events().list(**kwargs).execute)
        events = result.get("items", [])
        logger.info("calendar.events_fetched", count=len(events), days_ahead=days_ahead)
        return events

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_event(self, event_id: str, calendar_id: str = "primary") -> dict:
        """Get a specific calendar event."""
        service = await self._get_service()
        return await asyncio.to_thread(service.events().get(calendarId=calendar_id, eventId=event_id).execute)

    async def find_customer_meetings(
        self,
        event_pattern: str,
        days_ahead: int = 7,
    ) -> list[dict]:
        """Find meetings matching a customer's event pattern."""
        pattern = event_pattern.strip()
        events = await self.list_upcoming_events(days_ahead=days_ahead, query=pattern)
        return [e for e in events if pattern.lower() in e.get("summary", "").lower()]

    async def find_meetings_on_date(
        self,
        target_date: datetime,
        query: Optional[str] = None,
    ) -> list[dict]:
        """Find meetings on a specific date."""
        service = await self._get_service()
        start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        kwargs = {
            "calendarId": "primary",
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if query:
            kwargs["q"] = query

        result = await asyncio.to_thread(service.events().list(**kwargs).execute)
        return result.get("items", [])
