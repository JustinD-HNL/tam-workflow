"""Avoma API client for fetching meeting transcripts."""

import asyncio
from datetime import datetime
from typing import Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.integrations.base import IntegrationClient, IntegrationError
from src.models.integration import IntegrationType

logger = structlog.get_logger()

# Rate limit: 1 second between API calls
_last_call_time: float = 0
_RATE_LIMIT_DELAY = 1.0


def _is_retryable(exc: BaseException) -> bool:
    """Check if an Avoma API error is retryable."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503)
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


class AvomaClient(IntegrationClient):
    """Client for the Avoma REST API."""

    integration_type = IntegrationType.AVOMA
    BASE_URL = "https://api.avoma.com"

    async def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        global _last_call_time
        import time

        now = time.monotonic()
        elapsed = now - _last_call_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_call_time = time.monotonic()

    async def _get_headers(self) -> dict:
        """Get authorization headers."""
        token = await self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_is_retryable),
    )
    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated API request to Avoma."""
        await self._rate_limit()
        headers = await self._get_headers()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method,
                f"{self.BASE_URL}{path}",
                headers=headers,
                **kwargs,
            )
            resp.raise_for_status()
            return resp.json()

    async def list_meetings(
        self, from_date: str, to_date: str, limit: int = 50
    ) -> list[dict]:
        """List meetings within a date range.

        Args:
            from_date: Start date in YYYY-MM-DD format.
            to_date: End date in YYYY-MM-DD format.
            limit: Max meetings to return.

        Returns:
            List of meeting dicts with id, subject, start_at, end_at, attendees, etc.
        """
        try:
            data = await self._request(
                "GET",
                "/v1/meetings",
                params={
                    "from": from_date,
                    "to": to_date,
                    "limit": limit,
                },
            )
            meetings = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(meetings, list):
                return meetings
            return meetings if isinstance(meetings, list) else []
        except httpx.HTTPStatusError as e:
            logger.error("avoma.list_meetings_failed", status=e.response.status_code, error=str(e))
            raise IntegrationError(f"Failed to list Avoma meetings: {e}")
        except Exception as e:
            logger.error("avoma.list_meetings_error", error=str(e))
            raise IntegrationError(f"Avoma API error: {e}")

    async def get_meeting(self, meeting_id: str) -> dict:
        """Get details for a specific meeting.

        Args:
            meeting_id: The Avoma meeting UUID.

        Returns:
            Meeting details dict.
        """
        try:
            return await self._request("GET", f"/v1/meetings/{meeting_id}")
        except httpx.HTTPStatusError as e:
            logger.error("avoma.get_meeting_failed", meeting_id=meeting_id, status=e.response.status_code)
            raise IntegrationError(f"Failed to get Avoma meeting {meeting_id}: {e}")
        except Exception as e:
            logger.error("avoma.get_meeting_error", meeting_id=meeting_id, error=str(e))
            raise IntegrationError(f"Avoma API error: {e}")

    async def get_transcript(self, meeting_id: str) -> Optional[str]:
        """Get the transcript text for a meeting.

        Args:
            meeting_id: The Avoma meeting UUID.

        Returns:
            Transcript text, or None if not available yet.
        """
        try:
            data = await self._request("GET", f"/v1/meetings/{meeting_id}/transcript")

            # Avoma may return transcript as a list of segments or as raw text
            if isinstance(data, dict):
                # Try common response shapes
                if "transcript" in data:
                    transcript = data["transcript"]
                    if isinstance(transcript, str):
                        return transcript
                    # Transcript as list of segments
                    if isinstance(transcript, list):
                        lines = []
                        for seg in transcript:
                            speaker = seg.get("speaker", seg.get("speaker_name", ""))
                            text = seg.get("text", seg.get("sentence", ""))
                            if speaker and text:
                                lines.append(f"{speaker}: {text}")
                            elif text:
                                lines.append(text)
                        return "\n".join(lines) if lines else None

                # Try "results" key
                if "results" in data and isinstance(data["results"], list):
                    lines = []
                    for seg in data["results"]:
                        speaker = seg.get("speaker", seg.get("speaker_name", ""))
                        text = seg.get("text", seg.get("sentence", ""))
                        if speaker and text:
                            lines.append(f"{speaker}: {text}")
                        elif text:
                            lines.append(text)
                    return "\n".join(lines) if lines else None

                # Try "text" key at top level
                if "text" in data:
                    return data["text"]

            # If response is a string directly
            if isinstance(data, str):
                return data

            logger.warning("avoma.transcript_unexpected_format", meeting_id=meeting_id, keys=list(data.keys()) if isinstance(data, dict) else type(data).__name__)
            return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Transcript not available yet
                return None
            logger.error("avoma.get_transcript_failed", meeting_id=meeting_id, status=e.response.status_code)
            raise IntegrationError(f"Failed to get transcript for meeting {meeting_id}: {e}")
        except Exception as e:
            logger.error("avoma.get_transcript_error", meeting_id=meeting_id, error=str(e))
            raise IntegrationError(f"Avoma API error: {e}")

    async def validate_token(self) -> dict:
        """Validate the API token by making a test request.

        Returns:
            Dict with validation result: {"valid": True/False, ...}
        """
        try:
            data = await self._request(
                "GET",
                "/v1/meetings",
                params={"limit": 1},
            )
            return {"valid": True, "message": "Avoma API key is valid"}
        except IntegrationError:
            raise
        except Exception as e:
            return {"valid": False, "error": str(e)}
