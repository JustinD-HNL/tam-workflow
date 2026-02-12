"""Google Calendar API routes."""

from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/events")
async def list_calendar_events(
    days: int = Query(7, ge=1, le=90, description="Number of days ahead to fetch events"),
):
    """List upcoming calendar events.

    Returns calendar events for the next N days. Returns an empty list
    when Google Calendar is not connected.
    """
    # TODO: Once Google Calendar integration is connected, fetch real events via
    # GoogleCalendarClient and match them against customer event patterns.
    return []


@router.get("/recent")
async def list_recent_events(
    customer_id: Optional[str] = Query(None, description="Filter events by customer ID"),
):
    """List recent calendar events, optionally filtered by customer.

    Returns calendar events matching the given customer. Returns an empty
    list when Google Calendar is not connected.
    """
    # TODO: Once Google Calendar integration is connected, fetch recent events
    # for the specified customer using their google_calendar_event_pattern.
    return []
