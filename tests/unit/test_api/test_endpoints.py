"""
Unit tests for API endpoints.

Tests endpoint behavior using FastAPI TestClient.
"""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import init_orchestrator


# Reset orchestrator for testing
@pytest.fixture(autouse=True)
def reset_orchestrator():
    """Reset orchestrator before each test."""
    import src.api.dependencies as deps
    deps._orchestrator = None


@pytest.fixture
def client():
    """Create test client with mocked orchestrator."""
    with patch("src.api.dependencies.get_orchestrator_graph") as mock_get_graph:
        # Create mock orchestrator
        mock_orchestrator = MagicMock()
        mock_get_graph.return_value = mock_orchestrator

        # Initialize
        init_orchestrator()

        with TestClient(app) as client:
            yield client


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check(self, client):
        """Test health check returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "orchestrator_ready" in data

    def test_health_check_has_request_id(self, client):
        """Test health check includes request ID header."""
        response = client.get("/health")

        assert "X-Request-ID" in response.headers


class TestCreateEventEndpoint:
    """Test POST /events endpoint."""

    @patch("src.api.main.invoke_orchestrator")
    def test_create_event_success(self, mock_invoke, client):
        """Test successful event creation."""
        mock_invoke.return_value = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "proposed_event": {
                "id": "evt_1",
                "title": "Meeting",
                "status": "confirmed",
            },
            "detected_conflicts": {"has_conflicts": False, "conflicts": []},
            "agent_outputs": {},
            "audit_log": [],
        }

        response = client.post(
            "/events",
            json={"message": "Schedule meeting at 2pm"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"]["auto_confirmed"] is True

    @patch("src.api.main.invoke_orchestrator")
    def test_create_event_with_conflicts(self, mock_invoke, client):
        """Test event creation with conflicts."""
        mock_invoke.return_value = {
            "conversation_id": "conv_456",
            "workflow_status": "awaiting_user",
            "proposed_event": {"id": "evt_1", "status": "proposed"},
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1", "type": "time_conflict"}],
            },
            "agent_outputs": {
                "resolution": {
                    "data": {"proposed_resolutions": [{"resolution_id": "r1"}]}
                }
            },
            "audit_log": [],
        }

        response = client.post(
            "/events",
            json={"message": "Schedule soccer at 2pm"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_user"
        assert data["result"]["auto_confirmed"] is False

    def test_create_event_validation_error(self, client):
        """Test validation error for too short message."""
        response = client.post(
            "/events",
            json={"message": "Hi"},
        )

        assert response.status_code == 422

    def test_create_event_empty_message(self, client):
        """Test validation error for empty message."""
        response = client.post(
            "/events",
            json={"message": "   "},
        )

        assert response.status_code == 422

    @patch("src.api.main.invoke_orchestrator")
    def test_create_event_with_user_id(self, mock_invoke, client):
        """Test event creation with user ID."""
        mock_invoke.return_value = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "proposed_event": {"id": "evt_1"},
            "detected_conflicts": {"has_conflicts": False},
            "agent_outputs": {},
            "audit_log": [],
        }

        response = client.post(
            "/events",
            json={"message": "Schedule meeting", "user_id": "user_123"},
        )

        assert response.status_code == 200
        # Verify user_id was passed to orchestrator
        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs["user_id"] == "user_123"

    @patch("src.api.main.invoke_orchestrator")
    def test_create_event_with_header_user_id(self, mock_invoke, client):
        """Test event creation with X-User-ID header."""
        mock_invoke.return_value = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "proposed_event": {"id": "evt_1"},
            "detected_conflicts": {"has_conflicts": False},
            "agent_outputs": {},
            "audit_log": [],
        }

        response = client.post(
            "/events",
            json={"message": "Schedule meeting"},
            headers={"X-User-ID": "header_user"},
        )

        assert response.status_code == 200
        call_kwargs = mock_invoke.call_args[1]
        assert call_kwargs["user_id"] == "header_user"


class TestQueryEndpoint:
    """Test POST /query endpoint."""

    @patch("src.api.main.invoke_orchestrator")
    def test_query_success(self, mock_invoke, client):
        """Test successful query."""
        mock_invoke.return_value = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "detected_conflicts": {},
            "agent_outputs": {
                "query": {
                    "data": {
                        "results": {"response": "You have 3 events tomorrow."}
                    }
                }
            },
            "audit_log": [],
        }

        response = client.post(
            "/query",
            json={"message": "What's on my calendar tomorrow?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "3 events" in data["result"]["query_response"]

    def test_query_validation_error(self, client):
        """Test validation error for short query."""
        response = client.post(
            "/query",
            json={"message": "Hi"},
        )

        assert response.status_code == 422


class TestListEventsEndpoint:
    """Test GET /events endpoint."""

    def test_list_events_empty(self, client):
        """Test listing events returns empty list."""
        response = client.get("/events")

        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0

    def test_list_events_with_pagination(self, client):
        """Test listing events with pagination params."""
        response = client.get("/events?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5


class TestConfirmEventEndpoint:
    """Test POST /events/{event_id}/confirm endpoint."""

    def test_confirm_event(self, client):
        """Test event confirmation."""
        response = client.post(
            "/events/evt_123/confirm",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_confirm_with_resolution(self, client):
        """Test confirmation with resolution ID."""
        response = client.post(
            "/events/evt_123/confirm",
            json={"resolution_id": "res_1"},
        )

        assert response.status_code == 200


class TestGetEventEndpoint:
    """Test GET /events/{event_id} endpoint."""

    def test_get_event_not_found(self, client):
        """Test getting non-existent event returns 404."""
        response = client.get("/events/nonexistent_id")

        assert response.status_code == 404


class TestDeleteEventEndpoint:
    """Test DELETE /events/{event_id} endpoint."""

    def test_delete_event_not_found(self, client):
        """Test deleting non-existent event returns 404."""
        response = client.delete("/events/nonexistent_id")

        assert response.status_code == 404


class TestClarifyEventEndpoint:
    """Test POST /events/clarify endpoint."""

    @patch("src.api.main.invoke_orchestrator")
    def test_clarify_event(self, mock_invoke, client):
        """Test event clarification."""
        mock_invoke.return_value = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "proposed_event": {"id": "evt_1"},
            "detected_conflicts": {"has_conflicts": False},
            "agent_outputs": {},
            "audit_log": [],
        }

        response = client.post(
            "/events/clarify",
            json={
                "event_id": "evt_123",
                "clarification": "I meant 2pm not 2am",
            },
        )

        assert response.status_code == 200

    def test_clarify_missing_fields(self, client):
        """Test clarification with missing fields."""
        response = client.post(
            "/events/clarify",
            json={"clarification": "I meant 2pm"},
        )

        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling."""

    @patch("src.api.main.invoke_orchestrator")
    def test_orchestrator_failure(self, mock_invoke, client):
        """Test handling of orchestrator failure."""
        mock_invoke.side_effect = Exception("Orchestrator crashed")

        response = client.post(
            "/events",
            json={"message": "Schedule meeting"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "error_type" in data or "detail" in data
