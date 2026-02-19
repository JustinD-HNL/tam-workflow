"""Linear issue API routes."""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.customer import Customer
from src.models.database import get_db
from src.models.workflow import ActionItem, ApprovalItem, ApprovalItemType, ApprovalStatus

logger = structlog.get_logger()

router = APIRouter()


# --- Request / Response Schemas ---


class IssueUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    linear_state_id: Optional[str] = None
    label_ids: Optional[list[str]] = None


class BulkApproveRequest(BaseModel):
    ids: list[uuid.UUID]


def _serialize_action_item(item: ActionItem, customer: Optional[Customer] = None) -> dict:
    """Serialize an ActionItem into the issue response shape expected by the frontend."""
    import json as json_module

    status_value = item.status.value if hasattr(item.status, "value") else str(item.status)

    # Use stored label overrides, fall back to customer defaults
    label_ids: list[str] = []
    if item.label_ids_json:
        try:
            label_ids = json_module.loads(item.label_ids_json)
        except (json_module.JSONDecodeError, TypeError):
            pass
    if not label_ids and customer and customer.linear_task_defaults:
        label_ids = customer.linear_task_defaults.get("labels", [])

    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "status": status_value,
        "approval_status": status_value,
        "priority": item.priority,
        "assignee": item.assignee,
        "customer_id": str(item.approval_item.customer_id) if item.approval_item else None,
        "customer_name": customer.name if customer else None,
        "labels": label_ids,
        "label_ids": label_ids,
        "linear_state_id": item.linear_state_id,
        "linear_issue_id": item.linear_issue_id,
        "linear_issue_url": item.linear_issue_url,
        "source": item.approval_item.item_type if item.approval_item else "manual",
        "approval_item_id": str(item.approval_item_id),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def _load_action_item(
    issue_id: uuid.UUID, db: AsyncSession
) -> ActionItem:
    """Load an ActionItem by ID with its approval_item relationship, or raise 404."""
    result = await db.execute(
        select(ActionItem)
        .options(selectinload(ActionItem.approval_item))
        .where(ActionItem.id == issue_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Issue not found")
    return item


async def _load_customer_for_item(
    item: ActionItem, db: AsyncSession
) -> Optional[Customer]:
    """Load the Customer associated with an ActionItem (via its ApprovalItem)."""
    if not item.approval_item:
        return None
    result = await db.execute(
        select(Customer).where(Customer.id == item.approval_item.customer_id)
    )
    return result.scalar_one_or_none()


# --- Helper for Linear search ---

PRIORITY_MAP = {0: "None", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}


def _format_search_result(node: dict) -> dict:
    """Format a raw Linear GraphQL issue node into the API response shape."""
    state = node.get("state") or {}
    assignee = node.get("assignee") or {}
    project = node.get("project") or {}
    team = node.get("team") or {}
    labels = [l["name"] for l in (node.get("labels") or {}).get("nodes", [])]
    desc = node.get("description") or ""
    return {
        "id": node["id"],
        "identifier": node.get("identifier", ""),
        "title": node.get("title", ""),
        "description": desc[:500] if desc else None,
        "full_description": desc or None,
        "url": node.get("url", ""),
        "priority": node.get("priority", 0),
        "priority_label": PRIORITY_MAP.get(node.get("priority", 0), "None"),
        "status": state.get("name", ""),
        "status_type": state.get("type", ""),
        "assignee": assignee.get("name"),
        "project": project.get("name"),
        "team": team.get("name"),
        "team_key": team.get("key"),
        "labels": labels,
        "created_at": node.get("createdAt"),
        "updated_at": node.get("updatedAt"),
    }


async def _resolve_label_ids(
    raw_labels: list[str],
    team_id: str | None = None,
) -> list[str] | None:
    """Resolve a list of label references (names or UUIDs) to Linear label UUIDs.

    Handles mixed lists where some entries are already UUIDs and others are names.
    Returns None if the input list is empty or no labels could be resolved.
    """
    if not raw_labels:
        return None

    import re
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    uuids: list[str] = []
    names: list[str] = []
    for label in raw_labels:
        if uuid_pattern.match(label):
            uuids.append(label)
        else:
            names.append(label)

    if names:
        from src.integrations.linear.client import LinearClient
        linear = LinearClient()
        resolved = await linear.find_labels_by_names(names, team_id=team_id)
        uuids.extend(resolved)

    # Deduplicate while preserving order — Linear rejects duplicate labelIds
    seen: set[str] = set()
    unique: list[str] = []
    for uid in uuids:
        if uid not in seen:
            seen.add(uid)
            unique.append(uid)

    return unique if unique else None


# --- Endpoints ---


@router.get("/metadata/states/{team_id}")
async def get_team_states(team_id: str):
    """Get workflow states for a Linear team (for status dropdowns)."""
    try:
        from src.integrations.linear.client import LinearClient

        linear = LinearClient()
        states = await linear.list_team_states(team_id)
        return states
    except Exception as e:
        logger.error("linear.states_failed", team_id=team_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch states: {str(e)}")


@router.get("/metadata/labels")
async def get_labels(team_id: Optional[str] = Query(None)):
    """Get available labels from Linear (for label multi-select)."""
    try:
        from src.integrations.linear.client import LinearClient

        linear = LinearClient()
        labels = await linear.list_labels(team_id)
        return labels
    except Exception as e:
        logger.error("linear.labels_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Failed to fetch labels: {str(e)}")


@router.get("/search")
async def search_linear_issues(
    q: str = Query(..., min_length=1, description="Search query"),
    include_completed: bool = Query(False),
    limit: int = Query(100, ge=1, le=250),
):
    """Search Linear issues across all projects (full-text search)."""
    try:
        from src.integrations.linear.client import LinearClient

        linear = LinearClient()
        results = await linear.search_issues(q, limit=limit, include_completed=include_completed)
        return [_format_search_result(node) for node in results]
    except Exception as e:
        logger.error("linear.search_failed", query=q, error=str(e))
        raise HTTPException(status_code=502, detail=f"Linear search failed: {str(e)}")


@router.get("/search/csv")
async def search_linear_issues_csv(
    q: str = Query(..., min_length=1, description="Search query"),
    include_completed: bool = Query(False),
    limit: int = Query(250, ge=1, le=250),
):
    """Search Linear issues and return results as a CSV file."""
    try:
        from src.integrations.linear.client import LinearClient

        linear = LinearClient()
        results = await linear.search_issues(q, limit=limit, include_completed=include_completed)
        formatted = [_format_search_result(node) for node in results]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Identifier", "Title", "Description", "Status", "Priority",
            "Assignee", "Project", "Team", "Labels", "URL", "Created", "Updated",
        ])
        for item in formatted:
            writer.writerow([
                item["identifier"],
                item["title"],
                (item["full_description"] or "")[:2000],
                item["status"],
                item["priority_label"],
                item["assignee"] or "",
                item["project"] or "",
                item["team"] or "",
                ", ".join(item["labels"]),
                item["url"],
                item["created_at"] or "",
                item["updated_at"] or "",
            ])

        output.seek(0)
        safe_query = q.replace(" ", "_")[:30]
        filename = f"linear_search_{safe_query}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error("linear.search_csv_failed", query=q, error=str(e))
        raise HTTPException(status_code=502, detail=f"Linear search failed: {str(e)}")


@router.get("/issues")
async def list_issues(
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all action items (from meeting notes, manual creation, etc.) for the Linear Issues page."""
    query = (
        select(ActionItem)
        .join(ActionItem.approval_item)
        .options(selectinload(ActionItem.approval_item))
        .order_by(ActionItem.created_at.desc())
    )

    if customer_id:
        query = query.where(ApprovalItem.customer_id == uuid.UUID(customer_id))

    # Support filtering by status on either the action item or the query param name
    effective_status = approval_status or status
    if effective_status:
        query = query.where(ActionItem.status == effective_status)

    result = await db.execute(query)
    items = result.scalars().all()

    # Batch-load customers for all items to avoid N+1 queries
    customer_ids = {
        item.approval_item.customer_id
        for item in items
        if item.approval_item
    }
    customers_by_id: dict[uuid.UUID, Customer] = {}
    if customer_ids:
        cust_result = await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        for cust in cust_result.scalars().all():
            customers_by_id[cust.id] = cust

    return [
        _serialize_action_item(
            item,
            customers_by_id.get(item.approval_item.customer_id) if item.approval_item else None,
        )
        for item in items
    ]


@router.post("/issues")
async def create_issue(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """Create a Linear issue (queued for approval)."""
    customer_id = data.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=422, detail="customer_id is required")

    cust_uuid = uuid.UUID(customer_id)

    # Create the parent ApprovalItem
    approval_item = ApprovalItem(
        item_type=ApprovalItemType.LINEAR_ISSUE,
        status=ApprovalStatus.DRAFT,
        title=data.get("title", "New Linear Issue"),
        content=data.get("description", ""),
        customer_id=cust_uuid,
    )
    db.add(approval_item)
    await db.flush()

    # Create the ActionItem child
    action_item = ActionItem(
        title=data.get("title", "New Linear Issue"),
        description=data.get("description", ""),
        assignee=data.get("assignee"),
        priority=data.get("priority"),
        status=ApprovalStatus.DRAFT,
        approval_item_id=approval_item.id,
    )
    db.add(action_item)
    await db.flush()
    await db.refresh(action_item)

    # Load relationships for serialization
    action_item_loaded = await _load_action_item(action_item.id, db)
    customer = await _load_customer_for_item(action_item_loaded, db)

    return _serialize_action_item(action_item_loaded, customer)


@router.put("/issues/{issue_id}")
async def update_issue(
    issue_id: uuid.UUID,
    data: IssueUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a Linear issue (action item) fields."""
    import json as json_module

    item = await _load_action_item(issue_id, db)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Handle label_ids -> label_ids_json mapping
    if "label_ids" in update_data:
        item.label_ids_json = json_module.dumps(update_data.pop("label_ids"))

    for field, value in update_data.items():
        setattr(item, field, value)

    # Keep the parent ApprovalItem title/content in sync — but ONLY for
    # LINEAR_ISSUE type where there's a 1:1 relationship.  For MEETING_NOTES
    # and AGENDA the parent is the full document and must not be overwritten.
    if item.approval_item and item.approval_item.item_type == ApprovalItemType.LINEAR_ISSUE:
        if "title" in update_data:
            item.approval_item.title = update_data["title"]
        if "description" in update_data:
            item.approval_item.content = update_data["description"]

    await db.flush()
    await db.refresh(item)

    # Reload with relationships for serialization
    item = await _load_action_item(issue_id, db)
    customer = await _load_customer_for_item(item, db)

    return _serialize_action_item(item, customer)


@router.post("/issues/{issue_id}/approve")
async def approve_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Approve a single Linear issue — creates it in Linear."""
    item = await _load_action_item(issue_id, db)
    customer = await _load_customer_for_item(item, db)

    current_status = ApprovalStatus(item.status) if isinstance(item.status, str) else item.status
    allowed_from = {ApprovalStatus.DRAFT, ApprovalStatus.IN_REVIEW, ApprovalStatus.REJECTED}

    if current_status not in allowed_from:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve issue with status '{current_status.value}'",
        )

    # Create in Linear if not already created
    if not item.linear_issue_id and customer:
        try:
            import json as json_module
            from src.integrations.linear.client import LinearClient
            linear = LinearClient()
            defaults = customer.linear_task_defaults or {}

            # Convert priority string to Linear integer
            priority_map = {"urgent": 1, "high": 2, "medium": 3, "low": 4, "none": 0}
            raw_priority = defaults.get("priority", 0)
            if isinstance(raw_priority, str):
                priority_val = priority_map.get(raw_priority.lower(), 0)
            else:
                priority_val = int(raw_priority) if raw_priority else 0

            # Use stored label overrides, fall back to customer defaults
            raw_labels: list[str] = []
            if item.label_ids_json:
                try:
                    raw_labels = json_module.loads(item.label_ids_json)
                except (json_module.JSONDecodeError, TypeError):
                    pass
            if not raw_labels:
                raw_labels = defaults.get("labels") or []
            label_ids = await _resolve_label_ids(raw_labels, team_id=defaults.get("team_id"))

            # Build description with meeting context
            desc_parts = []
            if item.approval_item and item.approval_item.meeting_date:
                date_str = item.approval_item.meeting_date.strftime("%Y-%m-%d")
                desc_parts.append(f"**Source:** {customer.name} meeting ({date_str})\n")
            elif item.approval_item:
                desc_parts.append(f"**Source:** {customer.name}\n")
            if item.description:
                desc_parts.append(item.description)
            description = "\n".join(desc_parts) or ""

            issue = await linear.create_issue(
                title=item.title,
                description=description,
                team_id=defaults.get("team_id"),
                project_id=customer.linear_project_id,
                assignee_id=defaults.get("assignee_id"),
                priority=priority_val,
                label_ids=label_ids,
                state_id=item.linear_state_id,
            )
            item.linear_issue_id = issue.get("id")
            item.linear_issue_url = issue.get("url")
            logger.info("linear.issue_created_on_approve", identifier=issue.get("identifier"), title=item.title)
        except Exception as e:
            logger.error("linear.approve_create_failed", error=str(e), issue_id=str(issue_id))

    item.status = ApprovalStatus.PUBLISHED

    await db.flush()
    await db.refresh(item)

    item = await _load_action_item(issue_id, db)
    customer = await _load_customer_for_item(item, db)

    return _serialize_action_item(item, customer)


@router.delete("/issues/{issue_id}")
async def delete_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete/reject a Linear issue (action item) — removes it without creating in Linear."""
    item = await _load_action_item(issue_id, db)

    current_status = ApprovalStatus(item.status) if isinstance(item.status, str) else item.status
    if current_status == ApprovalStatus.PUBLISHED and item.linear_issue_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an issue that has already been created in Linear",
        )

    await db.delete(item)
    await db.flush()

    return {"message": "Issue deleted", "id": str(issue_id)}


@router.post("/issues/bulk-delete")
async def bulk_delete_issues(
    data: BulkApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk delete multiple Linear issues (action items) that haven't been published to Linear."""
    if not data.ids:
        raise HTTPException(status_code=400, detail="No issue IDs provided")

    result = await db.execute(
        select(ActionItem)
        .options(selectinload(ActionItem.approval_item))
        .where(ActionItem.id.in_(data.ids))
    )
    items = result.scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="No issues found for the given IDs")

    deleted_ids: list[str] = []
    skipped_ids: list[str] = []

    for item in items:
        current_status = ApprovalStatus(item.status) if isinstance(item.status, str) else item.status
        if current_status == ApprovalStatus.PUBLISHED and item.linear_issue_id:
            skipped_ids.append(str(item.id))
            continue
        await db.delete(item)
        deleted_ids.append(str(item.id))

    await db.flush()

    response: dict = {"deleted_ids": deleted_ids, "deleted_count": len(deleted_ids)}
    if skipped_ids:
        response["skipped_ids"] = skipped_ids
        response["skipped_reason"] = "Issues already created in Linear cannot be deleted"

    return response


@router.post("/issues/bulk-approve")
async def bulk_approve_issues(
    data: BulkApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve multiple Linear issues (action items)."""
    if not data.ids:
        raise HTTPException(status_code=400, detail="No issue IDs provided")

    result = await db.execute(
        select(ActionItem)
        .options(selectinload(ActionItem.approval_item))
        .where(ActionItem.id.in_(data.ids))
    )
    items = result.scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="No issues found for the given IDs")

    # Batch-load customers for Linear issue creation
    customer_ids = {
        item.approval_item.customer_id
        for item in items
        if item.approval_item
    }
    customers_by_id: dict[uuid.UUID, Customer] = {}
    if customer_ids:
        cust_result = await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        for cust in cust_result.scalars().all():
            customers_by_id[cust.id] = cust

    allowed_from = {ApprovalStatus.DRAFT, ApprovalStatus.IN_REVIEW, ApprovalStatus.REJECTED}
    updated_items: list[ActionItem] = []
    skipped_ids: list[str] = []

    for item in items:
        current_status = ApprovalStatus(item.status) if isinstance(item.status, str) else item.status
        if current_status not in allowed_from:
            skipped_ids.append(str(item.id))
            continue

        # Create in Linear if not already created
        customer = (
            customers_by_id.get(item.approval_item.customer_id)
            if item.approval_item else None
        )
        if not item.linear_issue_id and customer:
            try:
                from src.integrations.linear.client import LinearClient
                linear = LinearClient()
                defaults = customer.linear_task_defaults or {}

                priority_map = {"urgent": 1, "high": 2, "medium": 3, "low": 4, "none": 0}
                raw_priority = defaults.get("priority", 0)
                if isinstance(raw_priority, str):
                    priority_val = priority_map.get(raw_priority.lower(), 0)
                else:
                    priority_val = int(raw_priority) if raw_priority else 0

                import json as json_module
                raw_labels: list[str] = []
                if item.label_ids_json:
                    try:
                        raw_labels = json_module.loads(item.label_ids_json)
                    except (json_module.JSONDecodeError, TypeError):
                        pass
                if not raw_labels:
                    raw_labels = defaults.get("labels") or []
                label_ids = await _resolve_label_ids(raw_labels, team_id=defaults.get("team_id"))

                # Build description with meeting context
                desc_parts = []
                if item.approval_item and item.approval_item.meeting_date:
                    date_str = item.approval_item.meeting_date.strftime("%Y-%m-%d")
                    desc_parts.append(f"**Source:** {customer.name} meeting ({date_str})\n")
                elif item.approval_item:
                    desc_parts.append(f"**Source:** {customer.name}\n")
                if item.description:
                    desc_parts.append(item.description)
                description = "\n".join(desc_parts) or ""

                issue = await linear.create_issue(
                    title=item.title,
                    description=description,
                    team_id=defaults.get("team_id"),
                    project_id=customer.linear_project_id,
                    assignee_id=defaults.get("assignee_id"),
                    priority=priority_val,
                    label_ids=label_ids,
                )
                item.linear_issue_id = issue.get("id")
                item.linear_issue_url = issue.get("url")
                logger.info("linear.issue_created_on_approve", identifier=issue.get("identifier"), title=item.title)
            except Exception as e:
                logger.error("linear.bulk_approve_create_failed", error=str(e), item_id=str(item.id))

        item.status = ApprovalStatus.PUBLISHED
        updated_items.append(item)

    await db.flush()

    # Refresh and serialize
    serialized = []
    for item in updated_items:
        await db.refresh(item)
        customer = (
            customers_by_id.get(item.approval_item.customer_id)
            if item.approval_item
            else None
        )
        serialized.append(_serialize_action_item(item, customer))

    response: dict = {"items": serialized, "updated_count": len(updated_items)}
    if skipped_ids:
        response["skipped_ids"] = skipped_ids
        response["skipped_reason"] = "Issues were not in an approvable status"

    return response
