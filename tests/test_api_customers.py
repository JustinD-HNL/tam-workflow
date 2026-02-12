"""Tests for the Customer CRUD API endpoints.

Tests POST, GET, PATCH, DELETE operations and error cases like duplicate slugs.
"""

import uuid

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Create customer
# ---------------------------------------------------------------------------

class TestCreateCustomer:
    """Test POST /api/customers/"""

    @pytest.mark.asyncio
    async def test_create_customer_minimal(self, client):
        """Creating a customer with only required fields should succeed."""
        response = await client.post(
            "/api/customers",
            json={"name": "Acme Corp", "slug": "acme-corp"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert data["id"] is not None
        assert data["cadence"] == "weekly"  # default
        assert data["health_status"] == "green"  # default

    @pytest.mark.asyncio
    async def test_create_customer_full(self, client):
        """Creating a customer with all fields should succeed."""
        response = await client.post(
            "/api/customers",
            json={
                "name": "Full Corp",
                "slug": "full-corp",
                "linear_project_id": "proj-123",
                "slack_internal_channel_id": "C111",
                "slack_external_channel_id": "C222",
                "notion_page_id": "page-abc",
                "google_calendar_event_pattern": "Full Corp Weekly",
                "google_docs_folder_id": "folder-xyz",
                "tam_slack_user_id": "U999",
                "cadence": "biweekly",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["linear_project_id"] == "proj-123"
        assert data["slack_internal_channel_id"] == "C111"
        assert data["cadence"] == "biweekly"

    @pytest.mark.asyncio
    async def test_create_customer_duplicate_slug_returns_409(self, client):
        """Creating two customers with the same slug should return 409."""
        await client.post(
            "/api/customers",
            json={"name": "First", "slug": "unique-slug"},
        )
        response = await client.post(
            "/api/customers",
            json={"name": "Second", "slug": "unique-slug"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_customer_missing_name_returns_422(self, client):
        """Missing required field 'name' should return validation error."""
        response = await client.post(
            "/api/customers",
            json={"slug": "no-name"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_customer_missing_slug_returns_422(self, client):
        """Missing required field 'slug' should return validation error."""
        response = await client.post(
            "/api/customers",
            json={"name": "No Slug"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# List customers
# ---------------------------------------------------------------------------

class TestListCustomers:
    """Test GET /api/customers/"""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        """Listing customers when none exist should return empty list."""
        response = await client.get("/api/customers")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_returns_created_customers(self, client):
        """After creating customers, listing should return them all."""
        await client.post(
            "/api/customers",
            json={"name": "Alpha", "slug": "alpha"},
        )
        await client.post(
            "/api/customers",
            json={"name": "Beta", "slug": "beta"},
        )
        response = await client.get("/api/customers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"Alpha", "Beta"}

    @pytest.mark.asyncio
    async def test_list_ordered_by_name(self, client):
        """Customers should be returned ordered by name."""
        await client.post(
            "/api/customers",
            json={"name": "Zebra", "slug": "zebra"},
        )
        await client.post(
            "/api/customers",
            json={"name": "Apple", "slug": "apple"},
        )
        response = await client.get("/api/customers")
        data = response.json()
        assert data[0]["name"] == "Apple"
        assert data[1]["name"] == "Zebra"


# ---------------------------------------------------------------------------
# Get single customer
# ---------------------------------------------------------------------------

class TestGetCustomer:
    """Test GET /api/customers/{id}"""

    @pytest.mark.asyncio
    async def test_get_existing_customer(self, client):
        """Should return the customer with matching ID."""
        create_resp = await client.post(
            "/api/customers",
            json={"name": "GetMe", "slug": "get-me"},
        )
        customer_id = create_resp.json()["id"]

        response = await client.get(f"/api/customers/{customer_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "GetMe"

    @pytest.mark.asyncio
    async def test_get_nonexistent_customer_returns_404(self, client):
        """Requesting a non-existent customer ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/customers/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_customer_with_invalid_uuid_returns_422(self, client):
        """An invalid UUID should return 422."""
        response = await client.get("/api/customers/not-a-uuid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Update customer
# ---------------------------------------------------------------------------

class TestUpdateCustomer:
    """Test PATCH /api/customers/{id}"""

    @pytest.mark.asyncio
    async def test_update_name(self, client):
        """Should update just the name when only name is provided."""
        create_resp = await client.post(
            "/api/customers",
            json={"name": "Original", "slug": "original"},
        )
        customer_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/customers/{customer_id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"
        assert response.json()["slug"] == "original"  # unchanged

    @pytest.mark.asyncio
    async def test_update_health_status(self, client):
        """Should update health_status."""
        create_resp = await client.post(
            "/api/customers",
            json={"name": "HealthTest", "slug": "health-test"},
        )
        customer_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/customers/{customer_id}",
            json={"health_status": "red"},
        )
        assert response.status_code == 200
        assert response.json()["health_status"] == "red"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, client):
        """Should update multiple fields at once."""
        create_resp = await client.post(
            "/api/customers",
            json={"name": "Multi", "slug": "multi"},
        )
        customer_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/customers/{customer_id}",
            json={
                "linear_project_id": "proj-new",
                "cadence": "monthly",
                "slack_internal_channel_id": "C-NEW",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["linear_project_id"] == "proj-new"
        assert data["cadence"] == "monthly"
        assert data["slack_internal_channel_id"] == "C-NEW"

    @pytest.mark.asyncio
    async def test_update_nonexistent_customer_returns_404(self, client):
        """Updating a non-existent customer should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.patch(
            f"/api/customers/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete customer
# ---------------------------------------------------------------------------

class TestDeleteCustomer:
    """Test DELETE /api/customers/{id}"""

    @pytest.mark.asyncio
    async def test_delete_existing_customer(self, client):
        """Should delete the customer and return 204."""
        create_resp = await client.post(
            "/api/customers",
            json={"name": "DeleteMe", "slug": "delete-me"},
        )
        customer_id = create_resp.json()["id"]

        response = await client.delete(f"/api/customers/{customer_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/customers/{customer_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_customer_returns_404(self, client):
        """Deleting a non-existent customer should return 404."""
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/customers/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_removes_from_list(self, client):
        """After deletion, the customer should not appear in the list."""
        await client.post(
            "/api/customers",
            json={"name": "Stay", "slug": "stay"},
        )
        create_resp = await client.post(
            "/api/customers",
            json={"name": "GoAway", "slug": "go-away"},
        )
        delete_id = create_resp.json()["id"]

        await client.delete(f"/api/customers/{delete_id}")

        list_resp = await client.get("/api/customers")
        slugs = [c["slug"] for c in list_resp.json()]
        assert "stay" in slugs
        assert "go-away" not in slugs
