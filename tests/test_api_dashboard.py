"""Tests for the Dashboard API endpoint.

Tests the GET /api/dashboard endpoint structure, health counts, and
pending approvals count.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Dashboard structure tests
# ---------------------------------------------------------------------------

class TestDashboardStructure:
    """Test that the dashboard endpoint returns the correct structure."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_expected_keys(self, client):
        """Dashboard response should contain all required top-level keys."""
        response = await client.get("/api/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "upcoming_meetings" in data
        assert "pending_approvals" in data
        assert "recent_activity" in data
        assert "customer_health" in data

    @pytest.mark.asyncio
    async def test_dashboard_empty_state(self, client):
        """With no data, dashboard should return zeros and empty lists."""
        response = await client.get("/api/dashboard")
        data = response.json()
        assert data["pending_approvals"] == 0
        assert data["upcoming_meetings"] == []
        assert data["recent_activity"] == []
        assert data["customer_health"] == {"green": 0, "yellow": 0, "red": 0}

    @pytest.mark.asyncio
    async def test_dashboard_types(self, client):
        """Verify the types of dashboard response fields."""
        response = await client.get("/api/dashboard")
        data = response.json()
        assert isinstance(data["upcoming_meetings"], list)
        assert isinstance(data["pending_approvals"], int)
        assert isinstance(data["recent_activity"], list)
        assert isinstance(data["customer_health"], dict)


# ---------------------------------------------------------------------------
# Health count tests
# ---------------------------------------------------------------------------

class TestDashboardHealthCounts:
    """Test that customer_health counts reflect actual customer data."""

    @pytest.mark.asyncio
    async def test_single_green_customer(self, client):
        """One green customer should show green: 1."""
        await client.post(
            "/api/customers",
            json={"name": "Green Co", "slug": "green-co"},
        )

        response = await client.get("/api/dashboard")
        data = response.json()
        assert data["customer_health"]["green"] == 1
        assert data["customer_health"]["yellow"] == 0
        assert data["customer_health"]["red"] == 0

    @pytest.mark.asyncio
    async def test_mixed_health_statuses(self, client):
        """Multiple customers with different health statuses should be counted."""
        # Create customers with different health statuses
        resp1 = await client.post(
            "/api/customers",
            json={"name": "Green Co", "slug": "green-co-mix"},
        )
        resp2 = await client.post(
            "/api/customers",
            json={"name": "Yellow Co", "slug": "yellow-co-mix"},
        )
        resp3 = await client.post(
            "/api/customers",
            json={"name": "Red Co", "slug": "red-co-mix"},
        )

        # Update health statuses
        cid2 = resp2.json()["id"]
        cid3 = resp3.json()["id"]
        await client.patch(f"/api/customers/{cid2}", json={"health_status": "yellow"})
        await client.patch(f"/api/customers/{cid3}", json={"health_status": "red"})

        response = await client.get("/api/dashboard")
        data = response.json()
        assert data["customer_health"]["green"] == 1
        assert data["customer_health"]["yellow"] == 1
        assert data["customer_health"]["red"] == 1


# ---------------------------------------------------------------------------
# Pending approvals count tests
# ---------------------------------------------------------------------------

class TestDashboardPendingApprovals:
    """Test that pending_approvals count reflects DRAFT and IN_REVIEW items."""

    @pytest.mark.asyncio
    async def test_no_approvals_returns_zero(self, client):
        """With no approval items, count should be 0."""
        response = await client.get("/api/dashboard")
        data = response.json()
        assert data["pending_approvals"] == 0

    @pytest.mark.asyncio
    async def test_pending_approvals_count_with_draft_items(self, client, db_engine):
        """DRAFT approval items should be counted as pending."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus
        from src.models.customer import Customer, Cadence, HealthStatus

        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                id=uuid.uuid4(),
                name="Approval Test Co",
                slug="approval-test-co",
                cadence=Cadence.WEEKLY,
                health_status=HealthStatus.GREEN,
            )
            session.add(customer)
            await session.flush()

            # Create 2 DRAFT items and 1 APPROVED item
            for i in range(2):
                item = ApprovalItem(
                    id=uuid.uuid4(),
                    item_type=ApprovalItemType.AGENDA,
                    status=ApprovalStatus.DRAFT,
                    title=f"Draft Agenda {i}",
                    customer_id=customer.id,
                )
                session.add(item)

            approved_item = ApprovalItem(
                id=uuid.uuid4(),
                item_type=ApprovalItemType.AGENDA,
                status=ApprovalStatus.APPROVED,
                title="Approved Agenda",
                customer_id=customer.id,
            )
            session.add(approved_item)
            await session.commit()

        response = await client.get("/api/dashboard")
        data = response.json()
        # Only DRAFT and IN_REVIEW count as pending
        assert data["pending_approvals"] == 2


# ---------------------------------------------------------------------------
# Recent activity tests
# ---------------------------------------------------------------------------

class TestDashboardRecentActivity:
    """Test that recent_activity shows the latest approval items."""

    @pytest.mark.asyncio
    async def test_recent_activity_includes_items(self, client, db_engine):
        """Created approval items should appear in recent_activity."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus
        from src.models.customer import Customer, Cadence, HealthStatus

        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                id=uuid.uuid4(),
                name="Activity Test Co",
                slug="activity-test-co",
                cadence=Cadence.WEEKLY,
                health_status=HealthStatus.GREEN,
            )
            session.add(customer)
            await session.flush()

            item = ApprovalItem(
                id=uuid.uuid4(),
                item_type=ApprovalItemType.MEETING_NOTES,
                status=ApprovalStatus.DRAFT,
                title="Test Meeting Notes",
                customer_id=customer.id,
            )
            session.add(item)
            await session.commit()

        response = await client.get("/api/dashboard")
        data = response.json()
        assert len(data["recent_activity"]) >= 1

        # Find our item in the recent activity
        titles = [a["title"] for a in data["recent_activity"]]
        assert "Test Meeting Notes" in titles

    @pytest.mark.asyncio
    async def test_recent_activity_item_structure(self, client, db_engine):
        """Each recent activity item should have id, title, type, status, created_at."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        from src.models.workflow import ApprovalItem, ApprovalItemType, ApprovalStatus
        from src.models.customer import Customer, Cadence, HealthStatus

        session_factory = async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            customer = Customer(
                id=uuid.uuid4(),
                name="Structure Test Co",
                slug="structure-test-co",
                cadence=Cadence.WEEKLY,
                health_status=HealthStatus.GREEN,
            )
            session.add(customer)
            await session.flush()

            item = ApprovalItem(
                id=uuid.uuid4(),
                item_type=ApprovalItemType.AGENDA,
                status=ApprovalStatus.DRAFT,
                title="Structure Test",
                customer_id=customer.id,
            )
            session.add(item)
            await session.commit()

        response = await client.get("/api/dashboard")
        data = response.json()
        assert len(data["recent_activity"]) >= 1

        activity = data["recent_activity"][0]
        assert "id" in activity
        assert "title" in activity
        assert "type" in activity
        assert "status" in activity
        assert "created_at" in activity
