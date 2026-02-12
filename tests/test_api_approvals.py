"""Tests for the Approval API endpoints.

Tests listing approvals, approve/reject/publish/copy actions, and error cases.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_customer_and_approval(db_engine, status="draft", item_type="agenda"):
    """Helper to create a customer + approval item directly in the DB."""
    from src.models.customer import Customer, Cadence, HealthStatus
    from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        customer = Customer(
            id=uuid.uuid4(),
            name="Approval Test Co",
            slug=f"approval-{uuid.uuid4().hex[:8]}",
            cadence=Cadence.WEEKLY,
            health_status=HealthStatus.GREEN,
        )
        session.add(customer)
        await session.flush()

        status_enum = ApprovalStatus(status)
        type_enum = ApprovalItemType(item_type)

        item = ApprovalItem(
            id=uuid.uuid4(),
            item_type=type_enum,
            status=status_enum,
            title=f"Test {item_type} ({status})",
            content="Some test content here.",
            customer_id=customer.id,
        )
        session.add(item)
        await session.commit()
        return customer, item


# ---------------------------------------------------------------------------
# List approvals
# ---------------------------------------------------------------------------

class TestListApprovals:
    """Test GET /api/approvals/"""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """With no approval items, should return empty list."""
        response = await client.get("/api/approvals")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_returns_items(self, client, db_engine):
        """Created items should appear in the approval list."""
        _customer, item = await _create_customer_and_approval(db_engine)

        response = await client.get("/api/approvals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        ids = [a["id"] for a in data]
        assert str(item.id) in ids

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, client, db_engine):
        """Filtering by status should return only matching items."""
        await _create_customer_and_approval(db_engine, status="draft")
        await _create_customer_and_approval(db_engine, status="approved")

        response = await client.get("/api/approvals?status=draft")
        assert response.status_code == 200
        for item in response.json():
            assert item["status"] == "draft"


# ---------------------------------------------------------------------------
# Get single approval
# ---------------------------------------------------------------------------

class TestGetApproval:
    """Test GET /api/approvals/{item_id}"""

    @pytest.mark.asyncio
    async def test_get_existing_approval(self, client, db_engine):
        """Should return the specific approval item."""
        _customer, item = await _create_customer_and_approval(db_engine)

        response = await client.get(f"/api/approvals/{item.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(item.id)
        assert data["title"] == item.title

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client):
        """Non-existent approval ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/approvals/{fake_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Approve action
# ---------------------------------------------------------------------------

class TestApproveItem:
    """Test POST /api/approvals/{item_id}/approve"""

    @pytest.mark.asyncio
    async def test_approve_draft_item(self, client, db_engine):
        """Approving a DRAFT item should move it to APPROVED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(f"/api/approvals/{item.id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_in_review_item(self, client, db_engine):
        """Approving an IN_REVIEW item should move it to APPROVED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="in_review")

        response = await client.post(f"/api/approvals/{item.id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_rejected_item(self, client, db_engine):
        """Approving a REJECTED item should move it to APPROVED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="rejected")

        response = await client.post(f"/api/approvals/{item.id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_published_returns_400(self, client, db_engine):
        """Approving a PUBLISHED item should fail."""
        _customer, item = await _create_customer_and_approval(db_engine, status="published")

        response = await client.post(f"/api/approvals/{item.id}/approve")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_approve_nonexistent_returns_404(self, client):
        """Approving a non-existent item should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/approvals/{fake_id}/approve")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Reject action
# ---------------------------------------------------------------------------

class TestRejectItem:
    """Test POST /api/approvals/{item_id}/reject"""

    @pytest.mark.asyncio
    async def test_reject_draft_item(self, client, db_engine):
        """Rejecting a DRAFT item should move it to REJECTED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(f"/api/approvals/{item.id}/reject")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_in_review_item(self, client, db_engine):
        """Rejecting an IN_REVIEW item should move it to REJECTED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="in_review")

        response = await client.post(f"/api/approvals/{item.id}/reject")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_approved_item(self, client, db_engine):
        """Rejecting an APPROVED item should move it to REJECTED (per state machine)."""
        _customer, item = await _create_customer_and_approval(db_engine, status="approved")

        response = await client.post(f"/api/approvals/{item.id}/reject")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_published_returns_400(self, client, db_engine):
        """Rejecting a PUBLISHED item should fail (not a valid transition)."""
        _customer, item = await _create_customer_and_approval(db_engine, status="published")

        response = await client.post(f"/api/approvals/{item.id}/reject")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_nonexistent_returns_404(self, client):
        """Rejecting a non-existent item should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/approvals/{fake_id}/reject")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Publish action
# ---------------------------------------------------------------------------

class TestPublishItem:
    """Test POST /api/approvals/{item_id}/publish"""

    @pytest.mark.asyncio
    async def test_publish_approved_item(self, client, db_engine):
        """Publishing an APPROVED item should move it to PUBLISHED."""
        _customer, item = await _create_customer_and_approval(db_engine, status="approved")

        response = await client.post(f"/api/approvals/{item.id}/publish")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["published_at"] is not None

    @pytest.mark.asyncio
    async def test_publish_draft_item_approves_then_publishes(self, client, db_engine):
        """Publishing a DRAFT item should first approve, then publish."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(f"/api/approvals/{item.id}/publish")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"

    @pytest.mark.asyncio
    async def test_publish_already_published_returns_400(self, client, db_engine):
        """Publishing a PUBLISHED item should fail."""
        _customer, item = await _create_customer_and_approval(db_engine, status="published")

        response = await client.post(f"/api/approvals/{item.id}/publish")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_publish_nonexistent_returns_404(self, client):
        """Publishing a non-existent item should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/approvals/{fake_id}/publish")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Copy content action
# ---------------------------------------------------------------------------

class TestCopyContent:
    """Test POST /api/approvals/{item_id}/copy"""

    @pytest.mark.asyncio
    async def test_copy_returns_content(self, client, db_engine):
        """Copy endpoint should return the item's content."""
        _customer, item = await _create_customer_and_approval(db_engine)

        response = await client.post(f"/api/approvals/{item.id}/copy")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Some test content here."

    @pytest.mark.asyncio
    async def test_copy_empty_content_returns_empty_string(self, client, db_engine):
        """If the item has no content, should return empty string."""
        from src.models.customer import Customer, Cadence, HealthStatus
        from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus

        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                id=uuid.uuid4(),
                name="Empty Content Co",
                slug=f"empty-{uuid.uuid4().hex[:8]}",
                cadence=Cadence.WEEKLY,
                health_status=HealthStatus.GREEN,
            )
            session.add(customer)
            await session.flush()

            item = ApprovalItem(
                id=uuid.uuid4(),
                item_type=ApprovalItemType.AGENDA,
                status=ApprovalStatus.DRAFT,
                title="No Content",
                content=None,
                customer_id=customer.id,
            )
            session.add(item)
            await session.commit()
            item_id = item.id

        response = await client.post(f"/api/approvals/{item_id}/copy")
        assert response.status_code == 200
        assert response.json()["content"] == ""

    @pytest.mark.asyncio
    async def test_copy_nonexistent_returns_404(self, client):
        """Copying from non-existent item should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(f"/api/approvals/{fake_id}/copy")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Action endpoint (generic)
# ---------------------------------------------------------------------------

class TestActionEndpoint:
    """Test POST /api/approvals/{item_id}/action"""

    @pytest.mark.asyncio
    async def test_approve_via_action_endpoint(self, client, db_engine):
        """The generic action endpoint should handle approve."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(
            f"/api/approvals/{item.id}/action",
            json={"action": "approve"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_reject_via_action_endpoint(self, client, db_engine):
        """The generic action endpoint should handle reject."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(
            f"/api/approvals/{item.id}/action",
            json={"action": "reject"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_publish_via_action_endpoint(self, client, db_engine):
        """The generic action endpoint should handle publish."""
        _customer, item = await _create_customer_and_approval(db_engine, status="approved")

        response = await client.post(
            f"/api/approvals/{item.id}/action",
            json={"action": "publish"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "published"

    @pytest.mark.asyncio
    async def test_invalid_action_returns_422(self, client, db_engine):
        """An invalid action string should return 422 (validation error)."""
        _customer, item = await _create_customer_and_approval(db_engine, status="draft")

        response = await client.post(
            f"/api/approvals/{item.id}/action",
            json={"action": "invalid_action"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_transition_returns_400(self, client, db_engine):
        """A valid action on wrong status should return 400."""
        _customer, item = await _create_customer_and_approval(db_engine, status="published")

        response = await client.post(
            f"/api/approvals/{item.id}/action",
            json={"action": "approve"},
        )
        assert response.status_code == 400
