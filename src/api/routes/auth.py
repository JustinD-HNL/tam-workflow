"""OAuth authentication routes for all integrations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.integrations.oauth_helpers import get_oauth_credentials
from src.models.database import get_db
from src.models.integration import IntegrationCredential, IntegrationStatus, IntegrationType

router = APIRouter()


# --- Google OAuth ---
@router.get("/google/connect")
async def google_oauth_start(db: AsyncSession = Depends(get_db)):
    """Redirect to Google OAuth consent screen."""
    client_id, client_secret = await get_oauth_credentials("google", db)
    if not client_id or not client_secret:
        return RedirectResponse(
            f"{settings.frontend_url}/settings?error=google&reason=not_configured"
        )

    from google_auth_oauthlib.flow import Flow

    scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file",
    ]
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=scopes,
        redirect_uri=f"{settings.oauth_redirect_base_url}/auth/google/callback",
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback."""
    from google_auth_oauthlib.flow import Flow
    from src.integrations.encryption import encrypt_token

    client_id, client_secret = await get_oauth_credentials("google", db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth not configured")

    scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive.file",
    ]
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=scopes,
        redirect_uri=f"{settings.oauth_redirect_base_url}/auth/google/callback",
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Upsert integration credential
    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.GOOGLE
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.GOOGLE)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(credentials.token)
    cred.refresh_token_encrypted = (
        encrypt_token(credentials.refresh_token) if credentials.refresh_token else cred.refresh_token_encrypted
    )
    cred.token_type = "Bearer"
    cred.scopes = " ".join(scopes)
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)
    if credentials.expiry:
        cred.expires_at = credentials.expiry.replace(tzinfo=timezone.utc)

    await db.flush()
    return RedirectResponse(f"{settings.frontend_url}/settings?connected=google")


# --- Slack Internal OAuth ---
@router.get("/slack/internal/connect")
async def slack_internal_oauth_start(db: AsyncSession = Depends(get_db)):
    """Redirect to Slack OAuth for internal workspace."""
    client_id, client_secret = await get_oauth_credentials("slack_internal", db)
    if not client_id or not client_secret:
        return RedirectResponse(
            f"{settings.frontend_url}/settings?error=slack_internal&reason=not_configured"
        )
    scopes = "channels:read,channels:history,chat:write,users:read,app_mentions:read"
    url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={settings.oauth_redirect_base_url}/auth/slack/internal/callback"
    )
    return RedirectResponse(url)


@router.get("/slack/internal/callback")
async def slack_internal_oauth_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack internal workspace OAuth callback."""
    import httpx
    from src.integrations.encryption import encrypt_token

    client_id, client_secret = await get_oauth_credentials("slack_internal", db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Slack Internal OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/slack/internal/callback",
            },
        )
        data = resp.json()

    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=f"Slack OAuth failed: {data.get('error')}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.SLACK_INTERNAL
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.SLACK_INTERNAL)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(data["access_token"])
    cred.token_type = "Bearer"
    cred.scopes = ",".join(data.get("scope", "").split(","))
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)
    cred.extra_data = str({"team": data.get("team", {}), "bot_user_id": data.get("bot_user_id")})

    await db.flush()
    return RedirectResponse(f"{settings.frontend_url}/settings?connected=slack_internal")


# --- Slack External OAuth ---
@router.get("/slack/external/connect")
async def slack_external_oauth_start(db: AsyncSession = Depends(get_db)):
    """Redirect to Slack OAuth for external workspace."""
    client_id, client_secret = await get_oauth_credentials("slack_external", db)
    if not client_id or not client_secret:
        return RedirectResponse(
            f"{settings.frontend_url}/settings?error=slack_external&reason=not_configured"
        )
    scopes = "channels:read,channels:history,chat:write,users:read,app_mentions:read"
    url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={settings.oauth_redirect_base_url}/auth/slack/external/callback"
    )
    return RedirectResponse(url)


@router.get("/slack/external/callback")
async def slack_external_oauth_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack external workspace OAuth callback."""
    import httpx
    from src.integrations.encryption import encrypt_token

    client_id, client_secret = await get_oauth_credentials("slack_external", db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Slack External OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/slack/external/callback",
            },
        )
        data = resp.json()

    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=f"Slack OAuth failed: {data.get('error')}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.SLACK_EXTERNAL
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.SLACK_EXTERNAL)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(data["access_token"])
    cred.token_type = "Bearer"
    cred.scopes = ",".join(data.get("scope", "").split(","))
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)
    cred.extra_data = str({"team": data.get("team", {}), "bot_user_id": data.get("bot_user_id")})

    await db.flush()
    return RedirectResponse(f"{settings.frontend_url}/settings?connected=slack_external")


# --- Linear OAuth ---
@router.get("/linear/connect")
async def linear_oauth_start(db: AsyncSession = Depends(get_db)):
    """Redirect to Linear OAuth."""
    client_id, client_secret = await get_oauth_credentials("linear", db)
    if not client_id or not client_secret:
        return RedirectResponse(
            f"{settings.frontend_url}/settings?error=linear&reason=not_configured"
        )
    import secrets

    state = secrets.token_urlsafe(32)
    url = (
        f"https://linear.app/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={settings.oauth_redirect_base_url}/auth/linear/callback"
        f"&response_type=code"
        f"&scope=read,write"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/linear/callback")
async def linear_oauth_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Linear OAuth callback."""
    import httpx
    from src.integrations.encryption import encrypt_token

    client_id, client_secret = await get_oauth_credentials("linear", db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Linear OAuth not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.linear.app/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/linear/callback",
                "grant_type": "authorization_code",
            },
        )
        data = resp.json()

    if "access_token" not in data:
        raise HTTPException(status_code=400, detail=f"Linear OAuth failed: {data}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.LINEAR
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.LINEAR)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(data["access_token"])
    cred.token_type = "Bearer"
    cred.scopes = "read,write"
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)

    await db.flush()
    return RedirectResponse(f"{settings.frontend_url}/settings?connected=linear")


# --- Notion OAuth ---
@router.get("/notion/connect")
async def notion_oauth_start(db: AsyncSession = Depends(get_db)):
    """Redirect to Notion OAuth."""
    client_id, client_secret = await get_oauth_credentials("notion", db)
    if not client_id or not client_secret:
        return RedirectResponse(
            f"{settings.frontend_url}/settings?error=notion&reason=not_configured"
        )
    url = (
        f"https://api.notion.com/v1/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={settings.oauth_redirect_base_url}/auth/notion/callback"
        f"&response_type=code"
        f"&owner=user"
    )
    return RedirectResponse(url)


@router.get("/notion/callback")
async def notion_oauth_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Notion OAuth callback."""
    import base64
    import httpx
    from src.integrations.encryption import encrypt_token

    client_id, client_secret = await get_oauth_credentials("notion", db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Notion OAuth not configured")

    auth_header = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.notion.com/v1/oauth/token",
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.oauth_redirect_base_url}/auth/notion/callback",
            },
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json",
            },
        )
        data = resp.json()

    if "access_token" not in data:
        raise HTTPException(status_code=400, detail=f"Notion OAuth failed: {data}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.NOTION
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.NOTION)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(data["access_token"])
    cred.token_type = "Bearer"
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)
    cred.extra_data = str({"workspace_name": data.get("workspace_name"), "workspace_id": data.get("workspace_id")})

    await db.flush()
    return RedirectResponse(f"{settings.frontend_url}/settings?connected=notion")
