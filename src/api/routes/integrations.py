"""Integration status and management routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import IntegrationStatusResponse, ManualTokenRequest
from src.models.database import get_db
from src.models.integration import IntegrationCredential, IntegrationStatus, IntegrationType

router = APIRouter()


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


@router.post("/manual-token")
async def set_manual_token(
    data: ManualTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually set a token for an integration (fallback)."""
    from src.integrations.encryption import encrypt_token

    try:
        itype = IntegrationType(data.integration_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid integration type: {data.integration_type}")

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
    return {"message": f"{data.integration_type} token saved", "status": "connected"}
