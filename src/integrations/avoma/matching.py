"""Match Avoma meetings to customers using a scoring algorithm."""

import re
from typing import Optional

import structlog

from src.models.customer import Customer

logger = structlog.get_logger()

# Minimum score required to consider a match valid
MIN_MATCH_THRESHOLD = 5


def _score_title_match(title: str, customer_name: str, customer_slug: str) -> int:
    """Score based on customer name/slug appearing in the meeting title."""
    score = 0
    title_lower = title.lower()

    # Full name match (case-insensitive)
    if customer_name.lower() in title_lower:
        score += 10

    # Slug match
    if customer_slug.lower() in title_lower:
        score += 8

    return score


def _score_calendar_pattern(title: str, calendar_pattern: Optional[str]) -> int:
    """Score based on the customer's Google Calendar event pattern matching the title."""
    if not calendar_pattern:
        return 0

    try:
        if re.search(calendar_pattern, title, re.IGNORECASE):
            return 10
    except re.error:
        # Invalid regex — try as plain substring
        if calendar_pattern.lower() in title.lower():
            return 10

    return 0


def _score_attendee_domains(
    attendee_emails: list[str], customer_contacts: list[dict]
) -> int:
    """Score based on attendee email domains matching customer contact domains."""
    if not attendee_emails or not customer_contacts:
        return 0

    # Extract domains from customer contacts
    customer_domains = set()
    for contact in customer_contacts:
        email = contact.get("email", "")
        if "@" in email:
            domain = email.split("@")[1].lower()
            customer_domains.add(domain)

    if not customer_domains:
        return 0

    score = 0
    for email in attendee_emails:
        if "@" in email:
            domain = email.split("@")[1].lower()
            if domain in customer_domains:
                score += 5

    return score


def match_meeting_to_customer(
    meeting: dict, customers: list[Customer]
) -> Optional[Customer]:
    """Match an Avoma meeting to the best-matching customer.

    Uses a scoring algorithm based on:
    - Meeting title contains customer name (+10)
    - Meeting title contains customer slug (+8)
    - Google Calendar event pattern matches title (+10)
    - Attendee email domains match customer contacts (+5 per match)

    Args:
        meeting: Avoma meeting dict with subject, attendees, etc.
        customers: List of Customer model instances.

    Returns:
        Best matching Customer, or None if no match above threshold.
    """
    title = meeting.get("subject", meeting.get("title", ""))
    if not title:
        return None

    # Extract attendee emails from meeting
    attendee_emails = []
    attendees = meeting.get("attendees", [])
    for att in attendees:
        email = att.get("email", "")
        if email:
            attendee_emails.append(email)

    best_customer = None
    best_score = 0

    for customer in customers:
        score = 0

        # Title matching
        score += _score_title_match(title, customer.name, customer.slug)

        # Calendar pattern matching
        score += _score_calendar_pattern(
            title, customer.google_calendar_event_pattern
        )

        # Attendee domain matching
        contacts = customer.primary_contacts or []
        score += _score_attendee_domains(attendee_emails, contacts)

        if score > best_score:
            best_score = score
            best_customer = customer

    if best_score >= MIN_MATCH_THRESHOLD:
        logger.info(
            "avoma.match_found",
            meeting_title=title,
            customer=best_customer.name,
            score=best_score,
        )
        return best_customer

    logger.warning(
        "avoma.no_match",
        meeting_title=title,
        best_score=best_score,
        best_customer=best_customer.name if best_customer else None,
    )
    return None
