"""URL and name parsers for resolving friendly inputs to integration IDs."""

import re
from typing import Optional


def parse_linear_project_url(url: str) -> dict:
    """Parse a Linear project URL to extract the project identifier.

    URL format: https://linear.app/{org}/project/{name}-{uuid}/
    Also accepts raw UUIDs or hex IDs directly.
    """
    url = url.strip()

    # Raw UUID passthrough
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",
        re.I,
    )
    if uuid_re.match(url):
        return {"id": url, "source": "raw_id"}

    # Parse URL: https://linear.app/{org}/project/{slug}-{hex}/
    match = re.search(r"linear\.app/[^/]+/project/[^/]+-([0-9a-f]+)/?", url)
    if match:
        return {"id": match.group(1), "source": "url"}

    # Try just extracting any hex ID from the URL path
    match = re.search(r"linear\.app/[^/]+/project/([^/]+)/?", url)
    if match:
        slug = match.group(1)
        # The ID is everything after the last dash
        parts = slug.rsplit("-", 1)
        if len(parts) == 2 and re.match(r"^[0-9a-f]+$", parts[1], re.I):
            return {"id": parts[1], "source": "url"}
        return {"id": slug, "source": "url"}

    raise ValueError(
        f"Could not parse Linear project URL: {url}. "
        "Expected format: https://linear.app/ORG/project/NAME-ID/"
    )


def parse_notion_page_url(url: str) -> dict:
    """Parse a Notion page URL to extract the page ID.

    URL format: https://www.notion.so/{workspace}/{Title}-{32-hex-chars}
    or: https://www.notion.so/{32-hex-chars}

    The 32 hex chars at the end become a UUID with dashes.
    """
    url = url.strip()

    # Raw UUID passthrough (with or without dashes)
    clean = url.replace("-", "")
    if len(clean) == 32 and re.match(r"^[0-9a-f]+$", clean, re.I):
        formatted = _hex_to_uuid(clean)
        return {"id": formatted, "source": "raw_id"}

    # Already-formatted UUID
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    )
    if uuid_re.match(url):
        return {"id": url, "source": "raw_id"}

    # Strip query params and hash
    path = url.split("?")[0].split("#")[0]

    # Find 32 consecutive hex chars (ignoring dashes in the URL)
    # Notion URLs embed dashes in the ID: e.g., 21bb8dbc2c8981e7a908fd0d2b98f307
    # but sometimes they appear as 21bb8dbc-2c89-81e7-a908-fd0d2b98f307
    path_no_dashes = path.replace("-", "")
    match = re.search(r"([0-9a-f]{32})", path_no_dashes, re.I)
    if match:
        formatted = _hex_to_uuid(match.group(1))
        return {"id": formatted, "source": "url"}

    raise ValueError(
        f"Could not parse Notion page URL: {url}. "
        "Expected format: https://www.notion.so/workspace/Page-Title-{32hexchars}"
    )


def parse_google_doc_url(url: str) -> dict:
    """Parse a Google Docs URL to extract the document ID.

    URL format: https://docs.google.com/document/d/{doc_id}/edit
    """
    url = url.strip()

    # Raw ID passthrough (alphanumeric + hyphens/underscores, no slashes)
    if "/" not in url and len(url) > 10:
        return {"id": url, "source": "raw_id"}

    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return {"id": match.group(1), "source": "url"}

    raise ValueError(
        f"Could not parse Google Doc URL: {url}. "
        "Expected format: https://docs.google.com/document/d/DOC_ID/edit"
    )


def normalize_slack_channel_name(name: str) -> str:
    """Normalize a Slack channel name — strip leading '#' and whitespace."""
    name = name.strip()
    if name.startswith("#"):
        name = name[1:]
    return name.strip()


def normalize_slack_user_name(name: str) -> str:
    """Normalize a Slack user @mention — strip leading '@' and whitespace."""
    name = name.strip()
    if name.startswith("@"):
        name = name[1:]
    return name.strip()


def is_slack_channel_id(value: str) -> bool:
    """Check if a value looks like a Slack channel ID (starts with C or G)."""
    return bool(re.match(r"^[CG][A-Z0-9]{8,}$", value.strip()))


def is_slack_user_id(value: str) -> bool:
    """Check if a value looks like a Slack user ID (starts with U or W)."""
    return bool(re.match(r"^[UW][A-Z0-9]{8,}$", value.strip()))


def _hex_to_uuid(hex_str: str) -> str:
    """Convert a 32-char hex string to UUID format with dashes."""
    h = hex_str.lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
