"""Tests for the Integration API endpoints.

Tests integration status listing, template configuration get/put,
and manual token submission.
"""

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Integration status
# ---------------------------------------------------------------------------

class TestIntegrationStatus:
    """Test GET /api/integrations/status"""

    @pytest.mark.asyncio
    async def test_status_returns_all_five_integrations(self, client):
        """Should return status for all 5 integration types."""
        response = await client.get("/api/integrations/status")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

        types = {item["integration_type"] for item in data}
        expected_types = {"google", "slack_internal", "slack_external", "linear", "notion"}
        assert types == expected_types

    @pytest.mark.asyncio
    async def test_status_default_is_disconnected(self, client):
        """All integrations should default to disconnected when no tokens are set."""
        response = await client.get("/api/integrations/status")
        data = response.json()
        for item in data:
            assert item["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_status_item_structure(self, client):
        """Each status item should have the expected fields."""
        response = await client.get("/api/integrations/status")
        data = response.json()
        for item in data:
            assert "integration_type" in item
            assert "status" in item
            assert "last_verified" in item
            assert "scopes" in item


# ---------------------------------------------------------------------------
# Template configuration
# ---------------------------------------------------------------------------

class TestTemplateConfig:
    """Test GET/PUT /api/integrations/settings/templates"""

    @pytest.mark.asyncio
    async def test_get_default_templates(self, client):
        """Default template config should have empty URLs."""
        response = await client.get("/api/integrations/settings/templates")
        assert response.status_code == 200
        data = response.json()
        assert "agenda_template_url" in data
        assert "notes_template_url" in data

    @pytest.mark.asyncio
    async def test_update_agenda_template(self, client):
        """Should update the agenda template URL."""
        new_url = "https://docs.google.com/document/d/abc123/edit"
        response = await client.put(
            "/api/integrations/settings/templates",
            json={"agenda_template_url": new_url},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agenda_template_url"] == new_url

    @pytest.mark.asyncio
    async def test_update_notes_template(self, client):
        """Should update the notes template URL."""
        new_url = "https://docs.google.com/document/d/xyz789/edit"
        response = await client.put(
            "/api/integrations/settings/templates",
            json={"notes_template_url": new_url},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notes_template_url"] == new_url

    @pytest.mark.asyncio
    async def test_update_both_templates(self, client):
        """Should update both template URLs at once."""
        agenda_url = "https://docs.google.com/document/d/agenda/edit"
        notes_url = "https://docs.google.com/document/d/notes/edit"
        response = await client.put(
            "/api/integrations/settings/templates",
            json={
                "agenda_template_url": agenda_url,
                "notes_template_url": notes_url,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agenda_template_url"] == agenda_url
        assert data["notes_template_url"] == notes_url

    @pytest.mark.asyncio
    async def test_get_after_update_persists(self, client):
        """After updating, GET should return the updated values."""
        new_url = "https://docs.google.com/document/d/persist/edit"
        await client.put(
            "/api/integrations/settings/templates",
            json={"agenda_template_url": new_url},
        )

        response = await client.get("/api/integrations/settings/templates")
        data = response.json()
        assert data["agenda_template_url"] == new_url

    @pytest.mark.asyncio
    async def test_update_ignores_unknown_keys(self, client):
        """Unknown keys in the payload should be silently ignored."""
        response = await client.put(
            "/api/integrations/settings/templates",
            json={"unknown_key": "value", "agenda_template_url": "https://test.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "unknown_key" not in data


# ---------------------------------------------------------------------------
# Manual token
# ---------------------------------------------------------------------------

class TestManualToken:
    """Test POST /api/integrations/manual-token"""

    @pytest.mark.asyncio
    async def test_set_manual_token_valid_type(self, client):
        """Setting a manual token for a valid integration type should succeed."""
        from unittest.mock import patch, AsyncMock

        # Mock both encryption and token validation (which calls external API)
        with patch("src.integrations.encryption.encrypt_token", return_value="encrypted_value"), \
             patch("src.api.routes.integrations._validate_token", new_callable=AsyncMock, return_value={"valid": True, "details": {"user": "test"}}):
            response = await client.post(
                "/api/integrations/manual-token",
                json={"integration_type": "linear", "token": "lin_api_test123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "linear" in data["message"]

    @pytest.mark.asyncio
    async def test_set_manual_token_invalid_type_returns_400(self, client):
        """Setting a token for an invalid integration type should return 400."""
        response = await client.post(
            "/api/integrations/manual-token",
            json={"integration_type": "invalid_service", "token": "some-token"},
        )
        assert response.status_code == 400
        assert "Invalid integration type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_set_manual_token_updates_status(self, client):
        """After setting a manual token, integration status should show connected."""
        from unittest.mock import patch, AsyncMock

        with patch("src.integrations.encryption.encrypt_token", return_value="encrypted_value"), \
             patch("src.api.routes.integrations._validate_token", new_callable=AsyncMock, return_value={"valid": True, "details": {"user": "test"}}):
            await client.post(
                "/api/integrations/manual-token",
                json={"integration_type": "notion", "token": "ntn_test123"},
            )

        response = await client.get("/api/integrations/status")
        data = response.json()
        notion_status = next(
            (s for s in data if s["integration_type"] == "notion"), None
        )
        assert notion_status is not None
        assert notion_status["status"] == "connected"

    @pytest.mark.asyncio
    async def test_set_manual_token_overwrite(self, client):
        """Setting a manual token twice should overwrite (not create duplicate)."""
        from unittest.mock import patch, AsyncMock

        mock_validate = AsyncMock(return_value={"valid": True, "details": {"user": "test"}})

        with patch("src.integrations.encryption.encrypt_token", return_value="first"), \
             patch("src.api.routes.integrations._validate_token", mock_validate):
            await client.post(
                "/api/integrations/manual-token",
                json={"integration_type": "linear", "token": "first-token"},
            )

        with patch("src.integrations.encryption.encrypt_token", return_value="second"), \
             patch("src.api.routes.integrations._validate_token", mock_validate):
            response = await client.post(
                "/api/integrations/manual-token",
                json={"integration_type": "linear", "token": "second-token"},
            )

        assert response.status_code == 200

        # Check only 1 linear entry exists
        status_response = await client.get("/api/integrations/status")
        data = status_response.json()
        linear_entries = [s for s in data if s["integration_type"] == "linear"]
        assert len(linear_entries) == 1
        assert linear_entries[0]["status"] == "connected"

    @pytest.mark.asyncio
    async def test_set_manual_token_missing_fields_returns_422(self, client):
        """Missing required fields should return validation error."""
        response = await client.post(
            "/api/integrations/manual-token",
            json={"integration_type": "linear"},
        )
        assert response.status_code == 422

        response2 = await client.post(
            "/api/integrations/manual-token",
            json={"token": "some-token"},
        )
        assert response2.status_code == 422
