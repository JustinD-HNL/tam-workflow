"""Integration status and management routes."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import IntegrationStatusResponse, ManualTokenRequest
from src.config.settings import settings
from src.integrations.encryption import encrypt_token, decrypt_token
from src.integrations.oauth_helpers import get_oauth_credentials
from src.models.database import get_db
from src.models.integration import IntegrationCredential, IntegrationStatus, IntegrationType
from src.models.oauth_config import OAuthAppConfig

router = APIRouter()


# --- OAuth App Configuration (stored in DB, no .env editing needed) ---

class OAuthAppConfigRequest(BaseModel):
    integration_type: str
    client_id: str
    client_secret: str = ""
    extra_config: dict | None = None  # e.g., {"app_token": "xapp-..."} for Slack


@router.get("/oauth-config")
async def get_oauth_config(db: AsyncSession = Depends(get_db)):
    """Check which integrations have OAuth app credentials configured (DB or .env)."""
    result = {}
    for itype in ["google", "slack_internal", "slack_external", "linear", "notion"]:
        client_id, _ = await get_oauth_credentials(itype, db)
        result[itype] = bool(client_id)
    return result


@router.post("/oauth-app-config")
async def save_oauth_app_config(
    data: OAuthAppConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save OAuth app credentials (client_id, client_secret) to the database.

    This lets users configure integrations through the UI instead of editing .env.
    """
    valid_types = {"google", "slack_internal", "slack_external", "linear", "notion"}
    if data.integration_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid integration type: {data.integration_type}")

    if not data.client_id.strip():
        raise HTTPException(status_code=400, detail="Client ID is required")

    result = await db.execute(
        select(OAuthAppConfig).where(
            OAuthAppConfig.integration_type == data.integration_type
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        config = OAuthAppConfig(integration_type=data.integration_type)
        db.add(config)

    config.client_id_encrypted = encrypt_token(data.client_id.strip())
    if data.client_secret:
        config.client_secret_encrypted = encrypt_token(data.client_secret.strip())
    if data.extra_config:
        config.extra_config_encrypted = encrypt_token(json.dumps(data.extra_config))

    await db.flush()
    return {
        "message": f"OAuth app config saved for {data.integration_type}",
        "integration_type": data.integration_type,
        "configured": True,
    }


@router.delete("/oauth-app-config/{integration_type}")
async def delete_oauth_app_config(
    integration_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove OAuth app credentials for an integration."""
    result = await db.execute(
        select(OAuthAppConfig).where(
            OAuthAppConfig.integration_type == integration_type
        )
    )
    config = result.scalar_one_or_none()
    if config:
        await db.delete(config)
        await db.flush()
    return {"message": f"OAuth app config removed for {integration_type}"}


# --- Slack App Manifests ---

SLACK_MANIFEST_INTERNAL = {
    "display_information": {
        "name": "TAM Workflow (Internal)",
        "description": "Automated TAM workflow for internal Buildkite channels",
        "background_color": "#1a1a2e",
    },
    "features": {
        "bot_user": {
            "display_name": "TAM Workflow",
            "always_online": True,
        },
    },
    "oauth_config": {
        "redirect_urls": [
            f"{settings.oauth_redirect_base_url}/auth/slack/internal/callback"
        ],
        "scopes": {
            "bot": [
                "channels:read",
                "channels:history",
                "chat:write",
                "users:read",
                "app_mentions:read",
            ],
        },
    },
    "settings": {
        "event_subscriptions": {
            "bot_events": ["message.channels", "app_mention"],
        },
        "socket_mode_enabled": True,
        "org_deploy_enabled": False,
        "token_rotation_enabled": False,
    },
}

SLACK_MANIFEST_EXTERNAL = {
    "display_information": {
        "name": "TAM Workflow (External)",
        "description": "Automated TAM workflow for customer-facing Slack Connect channels",
        "background_color": "#16213e",
    },
    "features": {
        "bot_user": {
            "display_name": "TAM Workflow",
            "always_online": True,
        },
    },
    "oauth_config": {
        "redirect_urls": [
            f"{settings.oauth_redirect_base_url}/auth/slack/external/callback"
        ],
        "scopes": {
            "bot": [
                "channels:read",
                "channels:history",
                "chat:write",
                "users:read",
                "app_mentions:read",
            ],
        },
    },
    "settings": {
        "event_subscriptions": {
            "bot_events": ["app_mention"],
        },
        "socket_mode_enabled": True,
        "org_deploy_enabled": False,
        "token_rotation_enabled": False,
    },
}


@router.get("/slack-manifest/{workspace}")
async def get_slack_manifest(workspace: str):
    """Get the Slack App Manifest JSON for creating a Slack App."""
    if workspace == "internal":
        return SLACK_MANIFEST_INTERNAL
    elif workspace == "external":
        return SLACK_MANIFEST_EXTERNAL
    else:
        raise HTTPException(status_code=400, detail="Workspace must be 'internal' or 'external'")


# --- Google via gcloud CLI ---

# The gcloud CLI's well-known OAuth client credentials (public, used by all gcloud installations)
GCLOUD_CLIENT_ID = "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
GCLOUD_CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"
GCLOUD_ADC_PATH = "/app/gcloud/application_default_credentials.json"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
]


@router.post("/import-gcloud")
async def import_gcloud_credentials(db: AsyncSession = Depends(get_db)):
    """Import Google credentials from gcloud application-default credentials file.

    The user runs `gcloud auth application-default login --scopes=...` on their host machine.
    The credentials file is mounted into Docker at /app/gcloud/.
    """
    import json as json_module
    import os

    if not os.path.exists(GCLOUD_ADC_PATH):
        raise HTTPException(
            status_code=404,
            detail="gcloud credentials file not found. Run the gcloud command first, then try again.",
        )

    try:
        with open(GCLOUD_ADC_PATH) as f:
            adc = json_module.load(f)
    except (json_module.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=400, detail=f"Failed to read gcloud credentials: {e}")

    if adc.get("type") != "authorized_user":
        raise HTTPException(
            status_code=400,
            detail=f"Unexpected credential type: {adc.get('type')}. Expected 'authorized_user'.",
        )

    refresh_token = adc.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh_token found in gcloud credentials.")

    # Use the refresh token to get a fresh access token
    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": adc.get("client_id", GCLOUD_CLIENT_ID),
                "client_secret": adc.get("client_secret", GCLOUD_CLIENT_SECRET),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        token_data = resp.json()

    if "access_token" not in token_data:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get access token from refresh token: {token_data.get('error_description', token_data.get('error', 'Unknown error'))}",
        )

    access_token = token_data["access_token"]

    # Validate the token works by getting user info
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Access token validation failed.")
        user_info = resp.json()

    # Store tokens
    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == IntegrationType.GOOGLE
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=IntegrationType.GOOGLE)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(access_token)
    cred.refresh_token_encrypted = encrypt_token(refresh_token)
    cred.token_type = "Bearer"
    cred.scopes = " ".join(GOOGLE_SCOPES)
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)
    # Store the gcloud client creds so we can refresh later
    cred.extra_data = json_module.dumps({
        "auth_method": "gcloud_adc",
        "client_id": adc.get("client_id", GCLOUD_CLIENT_ID),
        "client_secret": adc.get("client_secret", GCLOUD_CLIENT_SECRET),
    })

    await db.flush()

    return {
        "message": "Google connected via gcloud credentials",
        "status": "connected",
        "user": user_info.get("name"),
        "email": user_info.get("email"),
    }


@router.get("/gcloud-status")
async def check_gcloud_status():
    """Check if the gcloud ADC file exists (is mounted and available)."""
    import os
    exists = os.path.exists(GCLOUD_ADC_PATH)
    return {"available": exists, "path": GCLOUD_ADC_PATH}


# --- Connection Status ---

@router.get("/status", response_model=list[IntegrationStatusResponse])
async def get_all_integration_status(db: AsyncSession = Depends(get_db)):
    """Get connection status for all integrations."""
    all_types = [t.value for t in IntegrationType]
    result = await db.execute(select(IntegrationCredential))
    creds = {c.integration_type: c for c in result.scalars().all()}

    statuses = []
    for itype in all_types:
        cred = creds.get(itype)
        statuses.append(
            IntegrationStatusResponse(
                integration_type=itype,
                status=cred.status if cred else IntegrationStatus.DISCONNECTED,
                last_verified=cred.last_verified if cred else None,
                scopes=cred.scopes if cred else None,
            )
        )
    return statuses


# --- Token Validation ---

async def _validate_token(integration_type: str, token: str) -> dict:
    """Actually call the service API to verify the token works. Returns user/workspace info."""
    import httpx

    if integration_type == "linear":
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                json={"query": "{ viewer { id name email } }"},
                headers={"Authorization": token, "Content-Type": "application/json"},
                timeout=10,
            )
            data = resp.json()
            if "errors" in data or "data" not in data:
                return {"valid": False, "error": data.get("errors", [{}])[0].get("message", "Invalid token")}
            viewer = data["data"]["viewer"]
            return {"valid": True, "user": viewer.get("name"), "email": viewer.get("email")}

    elif integration_type == "notion":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": "2022-06-28",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                data = resp.json()
                return {"valid": False, "error": data.get("message", f"HTTP {resp.status_code}")}
            data = resp.json()
            return {"valid": True, "user": data.get("name"), "type": data.get("type", "bot")}

    elif integration_type in ("slack_internal", "slack_external"):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                return {"valid": False, "error": data.get("error", "Invalid token")}
            return {"valid": True, "user": data.get("user"), "team": data.get("team")}

    elif integration_type == "google":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                return {"valid": False, "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            return {"valid": True, "user": data.get("name"), "email": data.get("email")}

    return {"valid": False, "error": "Unknown integration type"}


@router.post("/verify/{integration_type}")
async def verify_integration(
    integration_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify that a saved integration token actually works by calling the service API."""
    try:
        itype = IntegrationType(integration_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid integration type: {integration_type}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == itype
        )
    )
    cred = result.scalar_one_or_none()
    if not cred or not cred.access_token_encrypted:
        raise HTTPException(status_code=404, detail=f"{integration_type} is not connected")

    token = decrypt_token(cred.access_token_encrypted)

    try:
        validation = await _validate_token(integration_type, token)
    except Exception as e:
        validation = {"valid": False, "error": str(e)}

    if validation["valid"]:
        cred.status = IntegrationStatus.CONNECTED
        cred.last_verified = datetime.now(timezone.utc)
        await db.flush()
    else:
        cred.status = IntegrationStatus.EXPIRED
        await db.flush()

    return {
        "integration_type": integration_type,
        "valid": validation["valid"],
        "details": {k: v for k, v in validation.items() if k != "valid"},
        "status": "connected" if validation["valid"] else "expired",
    }


# --- Manual Token ---

@router.post("/manual-token")
async def set_manual_token(
    data: ManualTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a token and validate it by calling the service API."""
    try:
        itype = IntegrationType(data.integration_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid integration type: {data.integration_type}")

    # Validate the token first
    try:
        validation = await _validate_token(data.integration_type, data.token)
    except Exception as e:
        validation = {"valid": False, "error": str(e)}

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Token validation failed: {validation.get('error', 'Unknown error')}. "
            f"Please check the token and try again.",
        )

    # Token is valid — save it
    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == itype
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        cred = IntegrationCredential(integration_type=itype)
        db.add(cred)

    cred.access_token_encrypted = encrypt_token(data.token)
    cred.status = IntegrationStatus.CONNECTED
    cred.last_verified = datetime.now(timezone.utc)

    await db.flush()

    details = {k: v for k, v in validation.items() if k != "valid"}
    return {
        "message": f"{data.integration_type} connected successfully",
        "status": "connected",
        "details": details,
    }


@router.delete("/{integration_type}")
async def disconnect_integration(
    integration_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Disconnect an integration by removing its credentials."""
    try:
        itype = IntegrationType(integration_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid integration type: {integration_type}")

    result = await db.execute(
        select(IntegrationCredential).where(
            IntegrationCredential.integration_type == itype
        )
    )
    cred = result.scalar_one_or_none()
    if cred:
        await db.delete(cred)
        await db.flush()
    return {"message": f"{integration_type} disconnected"}


# --- Template Configuration ---

# In-memory template config (persisted would need a DB table, but this is sufficient for MVP)
_template_config = {
    "agenda_template_url": "",
    "notes_template_url": "",
}


@router.get("/settings/templates")
async def get_template_config():
    """Get template configuration."""
    return _template_config


@router.put("/settings/templates")
async def update_template_config(config: dict):
    """Update template configuration."""
    for key in ["agenda_template_url", "notes_template_url"]:
        if key in config:
            _template_config[key] = config[key]
    return _template_config
