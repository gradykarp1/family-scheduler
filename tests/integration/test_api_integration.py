"""
Integration tests for API endpoints.

Tests HTTP request -> orchestrator -> response flow
with mocked LLM and calendar services but real orchestrator execution.
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import init_orchestrator
from src.orchestrator.checkpointing import reset_checkpointer


pytestmark = pytest.mark.integration


class TestCreateEventAPI:
    """Test POST /events endpoint with real orchestrator."""

    def test_create_event_success(self, integration_api_client):
        """
        Test successful event creation via API.

        Given: Valid event creation request
        When: POST /events is called
        Then: Returns 200 with completed workflow
        """
        client = integration_api_client["client"]

        response = client.post(
            "/events",
            json={
                "message": "Schedule soccer practice tomorrow at 2pm for Charlie",
                "user_id": "parent_1",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "workflow_id" in data
        assert data["status"] == "completed"
        assert data["result"]["auto_confirmed"] is True
        assert data["result"]["event"] is not None

        # Verify event details
        event = data["result"]["event"]
        assert event["title"] == "Soccer Practice"
        assert event["status"] == "confirmed"

        # Verify workflow steps tracked
        assert len(data["workflow_steps"]) > 0
        assert "nl_parsing" in data["workflow_steps"]

    def test_create_event_with_conflicts(
        self, mock_llm_factory, mock_calendar_with_conflict
    ):
        """Test event creation with conflicts returns awaiting_user status."""
        import src.api.dependencies as deps

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_with_conflict

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            deps._orchestrator = None
            init_orchestrator()

            with TestClient(app) as client:
                response = client.post(
                    "/events",
                    json={
                        "message": "Schedule soccer practice tomorrow at 2pm",
                        "user_id": "parent_1",
                    },
                )

                assert response.status_code == 200
                data = response.json()

                # Verify conflict response
                assert data["status"] == "awaiting_user"
                assert data["result"]["auto_confirmed"] is False
                assert len(data["result"]["conflicts"]) > 0
                assert len(data["result"]["proposed_resolutions"]) > 0

    def test_create_event_validation_error(self, integration_api_client):
        """Test API validation for short message."""
        client = integration_api_client["client"]

        response = client.post(
            "/events",
            json={"message": "Hi"},
        )

        assert response.status_code == 422

    def test_create_event_includes_request_id(self, integration_api_client):
        """Test that response includes X-Request-ID header."""
        client = integration_api_client["client"]

        response = client.post(
            "/events",
            json={
                "message": "Schedule meeting tomorrow at 3pm",
            },
        )

        assert response.status_code == 200
        assert "x-request-id" in response.headers


class TestQueryAPI:
    """Test POST /query endpoint with real orchestrator."""

    def test_query_success(self, mock_llm_factory, mock_calendar_with_events):
        """Test query endpoint returns schedule information."""
        import src.api.dependencies as deps

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("query")
            patched_calendar.return_value = mock_calendar_with_events

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            deps._orchestrator = None
            init_orchestrator()

            with TestClient(app) as client:
                response = client.post(
                    "/query",
                    json={"message": "What's on my calendar tomorrow?"},
                )

                assert response.status_code == 200
                data = response.json()

                assert data["status"] == "completed"
                assert data["result"]["query_response"] is not None

    def test_query_validation_error(self, integration_api_client):
        """Test query validation for short message."""
        client = integration_api_client["client"]

        response = client.post(
            "/query",
            json={"message": "?"},
        )

        assert response.status_code == 422


class TestClarifyAPI:
    """Test POST /events/clarify endpoint."""

    def test_clarify_event(self, integration_api_client):
        """Test clarification endpoint."""
        client = integration_api_client["client"]

        response = client.post(
            "/events/clarify",
            json={
                "event_id": "evt_123",
                "clarification": "I meant tomorrow at 2pm, not today",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Clarification should re-invoke orchestrator
        assert "status" in data
        assert "workflow_id" in data


class TestHealthAPI:
    """Test GET /health endpoint in integration context."""

    def test_health_with_initialized_orchestrator(self, integration_api_client):
        """Test health check with fully initialized system."""
        client = integration_api_client["client"]

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["orchestrator_ready"] is True


class TestAPIWorkflowSteps:
    """Test that API responses include proper workflow tracking."""

    def test_response_includes_agent_outputs(self, integration_api_client):
        """Test that response includes agent outputs for debugging."""
        client = integration_api_client["client"]

        response = client.post(
            "/events",
            json={
                "message": "Schedule meeting tomorrow at 10am",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Agent outputs should be included
        assert "agent_outputs" in data
        assert "nl_parser" in data["agent_outputs"]

    def test_response_includes_explanation(self, integration_api_client):
        """Test that response includes human-readable explanation."""
        client = integration_api_client["client"]

        response = client.post(
            "/events",
            json={
                "message": "Schedule doctor appointment Friday at 3pm",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "explanation" in data
        assert len(data["explanation"]) > 0
