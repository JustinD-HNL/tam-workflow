"""Resolution endpoints for friendly names/URLs to integration IDs."""

from typing import Optional

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from tenacity import RetryError

from src.integrations.base import IntegrationError
from src.integrations.url_parsers import (
    is_slack_channel_id,
    is_slack_user_id,
    normalize_slack_channel_name,
    normalize_slack_user_name,
    parse_google_doc_url,
    parse_linear_project_url,
    parse_notion_page_url,
)

logger = structlog.get_logger()

router = APIRouter()


def _extract_error(e: Exception) -> str:
    """Extract a clean error message, unwrapping RetryError if needed."""
    if isinstance(e, RetryError) and e.last_attempt and e.last_attempt.exception():
        inner = e.last_attempt.exception()
        return str(inner)
    return str(e)


# --- Schemas ---


class ResolveResult(BaseModel):
    valid: bool
    id: Optional[str] = None
    name: Optional[str] = None
    error: Optional[str] = None
    extra: Optional[dict] = None


class SlackChannelRequest(BaseModel):
    workspace: str
    channel_name: str


class SlackUserRequest(BaseModel):
    workspace: str
    query: str


class LinearProjectRequest(BaseModel):
    url: str


class LinearTeamRequest(BaseModel):
    name: str


class LinearAssigneeRequest(BaseModel):
    query: str


class NotionPageRequest(BaseModel):
    url: str


class GoogleDocRequest(BaseModel):
    url: str


# --- Endpoints ---


@router.post("/slack-channel", response_model=ResolveResult)
async def resolve_slack_channel(data: SlackChannelRequest):
    """Resolve a Slack channel name to its ID."""
    from src.integrations.slack.client import SlackClient

    if data.workspace not in ("internal", "external"):
        return ResolveResult(valid=False, error="workspace must be 'internal' or 'external'")

    name = normalize_slack_channel_name(data.channel_name)
    if not name:
        return ResolveResult(valid=False, error="Channel name is required")

    try:
        client = SlackClient(workspace=data.workspace)

        # If it's already a channel ID, validate directly
        if is_slack_channel_id(name):
            slack_client = await client._get_client()
            response = await slack_client.conversations_info(channel=name)
            ch = response.get("channel", {})
            return ResolveResult(
                valid=True,
                id=name,
                name=f"#{ch.get('name', name)}",
                extra={"is_private": ch.get("is_private", False)},
            )

        # Resolve by name
        channel = await client.find_channel_by_name(name)
        if channel:
            return ResolveResult(
                valid=True,
                id=channel["id"],
                name=f"#{channel['name']}",
                extra={
                    "is_private": channel.get("is_private", False),
                    "num_members": channel.get("num_members", 0),
                },
            )
        return ResolveResult(
            valid=False, error=f"Channel '#{name}' not found in {data.workspace} workspace"
        )
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.slack_channel_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/slack-user", response_model=ResolveResult)
async def resolve_slack_user(data: SlackUserRequest):
    """Resolve a Slack @mention or display name to a user ID."""
    from src.integrations.slack.client import SlackClient

    if data.workspace not in ("internal", "external"):
        return ResolveResult(valid=False, error="workspace must be 'internal' or 'external'")

    query = normalize_slack_user_name(data.query)
    if not query:
        return ResolveResult(valid=False, error="User name is required")

    try:
        client = SlackClient(workspace=data.workspace)

        # If it's already a user ID, validate directly
        if is_slack_user_id(query):
            user = await client.get_user_info(query)
            if user:
                profile = user.get("profile", {})
                display = profile.get("display_name") or profile.get("real_name") or query
                return ResolveResult(
                    valid=True,
                    id=query,
                    name=f"@{display}",
                    extra={"real_name": profile.get("real_name")},
                )
            return ResolveResult(valid=False, error=f"User ID '{query}' not found")

        # Resolve by name
        user = await client.find_user_by_name(query)
        if user:
            profile = user.get("profile", {})
            display = profile.get("display_name") or profile.get("real_name") or user.get("name", "")
            return ResolveResult(
                valid=True,
                id=user["id"],
                name=f"@{display}",
                extra={"real_name": profile.get("real_name"), "username": user.get("name")},
            )
        return ResolveResult(
            valid=False, error=f"User '{query}' not found in {data.workspace} workspace"
        )
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.slack_user_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/linear-project", response_model=ResolveResult)
async def resolve_linear_project(data: LinearProjectRequest):
    """Resolve a Linear project URL to its ID."""
    from src.integrations.linear.client import LinearClient

    try:
        parsed = parse_linear_project_url(data.url)
    except ValueError as e:
        return ResolveResult(valid=False, error=str(e))

    try:
        client = LinearClient()
        project = await client.get_project(parsed["id"])
        return ResolveResult(
            valid=True,
            id=project["id"],
            name=project.get("name", ""),
            extra={"state": project.get("state")},
        )
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.linear_project_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/linear-team", response_model=ResolveResult)
async def resolve_linear_team(data: LinearTeamRequest):
    """Resolve a Linear team name to its ID."""
    from src.integrations.linear.client import LinearClient

    if not data.name.strip():
        return ResolveResult(valid=False, error="Team name is required")

    try:
        client = LinearClient()
        team = await client.find_team_by_name(data.name.strip())
        if team:
            return ResolveResult(
                valid=True,
                id=team["id"],
                name=team.get("name", ""),
                extra={"key": team.get("key")},
            )
        return ResolveResult(valid=False, error=f"Team '{data.name}' not found")
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.linear_team_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/linear-assignee", response_model=ResolveResult)
async def resolve_linear_assignee(data: LinearAssigneeRequest):
    """Resolve a Linear user by name or email."""
    from src.integrations.linear.client import LinearClient

    if not data.query.strip():
        return ResolveResult(valid=False, error="Name or email is required")

    try:
        client = LinearClient()
        user = await client.find_user(data.query.strip())
        if user:
            return ResolveResult(
                valid=True,
                id=user["id"],
                name=user.get("displayName") or user.get("name", ""),
                extra={"email": user.get("email")},
            )
        return ResolveResult(valid=False, error=f"User '{data.query}' not found")
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.linear_assignee_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/notion-page", response_model=ResolveResult)
async def resolve_notion_page(data: NotionPageRequest):
    """Resolve a Notion page URL to its ID and title."""
    from src.integrations.notion.client import NotionClient

    try:
        parsed = parse_notion_page_url(data.url)
    except ValueError as e:
        return ResolveResult(valid=False, error=str(e))

    try:
        client = NotionClient()
        page = await client.get_page(parsed["id"])
        title = NotionClient.extract_page_title(page)
        return ResolveResult(
            valid=True,
            id=parsed["id"],
            name=title,
            extra={"url": page.get("url")},
        )
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.notion_page_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))


@router.post("/google-doc", response_model=ResolveResult)
async def resolve_google_doc(data: GoogleDocRequest):
    """Resolve a Google Doc URL to its ID and verify access."""
    from src.integrations.google.docs import GoogleDocsClient

    try:
        parsed = parse_google_doc_url(data.url)
    except ValueError as e:
        return ResolveResult(valid=False, error=str(e))

    try:
        client = GoogleDocsClient()
        doc = await client.get_document(parsed["id"])
        return ResolveResult(
            valid=True,
            id=parsed["id"],
            name=doc.get("title", ""),
            extra={"url": f"https://docs.google.com/document/d/{parsed['id']}/edit"},
        )
    except IntegrationError as e:
        return ResolveResult(valid=False, error=str(e))
    except Exception as e:
        logger.error("resolve.google_doc_error", error=str(e))
        return ResolveResult(valid=False, error=_extract_error(e))
