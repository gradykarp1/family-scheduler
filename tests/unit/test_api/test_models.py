"""
Unit tests for API Pydantic models.

Tests request validation and response serialization.
"""

import pytest
from pydantic import ValidationError

from src.api.models import (
    CreateEventRequest,
    ConfirmEventRequest,
    ClarifyEventRequest,
    QueryRequest,
    WorkflowResponse,
    WorkflowResult,
    HealthResponse,
    EventListResponse,
)


class TestCreateEventRequest:
    """Test CreateEventRequest validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = CreateEventRequest(message="Schedule meeting at 2pm")
        assert request.message == "Schedule meeting at 2pm"
        assert request.user_id is None
        assert request.family_id is None

    def test_with_all_fields(self):
        """Test request with all optional fields."""
        request = CreateEventRequest(
            message="Schedule meeting",
            user_id="user_123",
            family_id="family_456",
            conversation_id="conv_789",
        )
        assert request.user_id == "user_123"
        assert request.family_id == "family_456"
        assert request.conversation_id == "conv_789"

    def test_message_too_short(self):
        """Test validation rejects too short message."""
        with pytest.raises(ValidationError) as exc_info:
            CreateEventRequest(message="Hi")

        assert "min_length" in str(exc_info.value).lower() or "at least 3" in str(exc_info.value)

    def test_message_empty_after_strip(self):
        """Test validation rejects empty message after stripping."""
        with pytest.raises(ValidationError):
            CreateEventRequest(message="   ")

    def test_message_stripped(self):
        """Test message is stripped of whitespace."""
        request = CreateEventRequest(message="  Schedule meeting  ")
        assert request.message == "Schedule meeting"

    def test_message_too_long(self):
        """Test validation rejects too long message."""
        long_message = "a" * 501
        with pytest.raises(ValidationError):
            CreateEventRequest(message=long_message)

    def test_max_length_message(self):
        """Test max length message is accepted."""
        max_message = "a" * 500
        request = CreateEventRequest(message=max_message)
        assert len(request.message) == 500


class TestConfirmEventRequest:
    """Test ConfirmEventRequest validation."""

    def test_empty_request(self):
        """Test empty request is valid."""
        request = ConfirmEventRequest()
        assert request.resolution_id is None
        assert request.user_notes is None

    def test_with_resolution_id(self):
        """Test request with resolution ID."""
        request = ConfirmEventRequest(resolution_id="res_1")
        assert request.resolution_id == "res_1"

    def test_with_user_notes(self):
        """Test request with user notes."""
        request = ConfirmEventRequest(user_notes="Confirmed after discussion")
        assert request.user_notes == "Confirmed after discussion"

    def test_user_notes_too_long(self):
        """Test validation rejects too long user notes."""
        long_notes = "a" * 501
        with pytest.raises(ValidationError):
            ConfirmEventRequest(user_notes=long_notes)


class TestClarifyEventRequest:
    """Test ClarifyEventRequest validation."""

    def test_valid_request(self):
        """Test valid clarification request."""
        request = ClarifyEventRequest(
            event_id="event_123",
            clarification="I meant 2pm not 2am",
        )
        assert request.event_id == "event_123"
        assert request.clarification == "I meant 2pm not 2am"

    def test_missing_event_id(self):
        """Test validation requires event_id."""
        with pytest.raises(ValidationError):
            ClarifyEventRequest(clarification="I meant 2pm")

    def test_missing_clarification(self):
        """Test validation requires clarification."""
        with pytest.raises(ValidationError):
            ClarifyEventRequest(event_id="event_123")

    def test_clarification_too_short(self):
        """Test validation rejects too short clarification."""
        with pytest.raises(ValidationError):
            ClarifyEventRequest(event_id="event_123", clarification="ok")


class TestQueryRequest:
    """Test QueryRequest validation."""

    def test_valid_request(self):
        """Test valid query request."""
        request = QueryRequest(message="When is everyone free?")
        assert request.message == "When is everyone free?"

    def test_message_too_short(self):
        """Test validation rejects too short message."""
        with pytest.raises(ValidationError):
            QueryRequest(message="Hi")

    def test_message_stripped(self):
        """Test message is stripped of whitespace."""
        request = QueryRequest(message="  What events?  ")
        assert request.message == "What events?"


class TestWorkflowResponse:
    """Test WorkflowResponse model."""

    def test_minimal_response(self):
        """Test minimal valid response."""
        response = WorkflowResponse(
            workflow_id="conv_123",
            status="completed",
            result=WorkflowResult(),
            explanation="Done",
        )
        assert response.workflow_id == "conv_123"
        assert response.status == "completed"
        assert response.explanation == "Done"
        assert response.agent_outputs == {}
        assert response.workflow_steps == []
        assert response.errors is None

    def test_full_response(self):
        """Test response with all fields."""
        response = WorkflowResponse(
            workflow_id="conv_123",
            status="awaiting_user",
            result=WorkflowResult(
                event={"id": "evt_1", "title": "Meeting"},
                conflicts=[{"id": "c1", "type": "time_conflict"}],
                auto_confirmed=False,
            ),
            explanation="Conflicts detected",
            agent_outputs={"nl_parser": {"confidence": 0.9}},
            workflow_steps=["nl_parsing", "scheduling"],
            errors=None,
        )
        assert response.result.event["id"] == "evt_1"
        assert len(response.result.conflicts) == 1
        assert response.result.auto_confirmed is False

    def test_failed_response(self):
        """Test failed response with errors."""
        response = WorkflowResponse(
            workflow_id="conv_123",
            status="failed",
            result=WorkflowResult(),
            explanation="Error occurred",
            errors=[{"error_type": "agent_failure", "message": "Test error"}],
        )
        assert response.status == "failed"
        assert len(response.errors) == 1

    def test_serialization(self):
        """Test JSON serialization."""
        response = WorkflowResponse(
            workflow_id="conv_123",
            status="completed",
            result=WorkflowResult(auto_confirmed=True),
            explanation="Done",
        )
        json_str = response.model_dump_json()
        assert "conv_123" in json_str
        assert "completed" in json_str


class TestWorkflowResult:
    """Test WorkflowResult model."""

    def test_default_values(self):
        """Test default values."""
        result = WorkflowResult()
        assert result.event is None
        assert result.conflicts == []
        assert result.proposed_resolutions == []
        assert result.auto_confirmed is False
        assert result.query_response is None
        assert result.clarification_needed is False

    def test_with_event(self):
        """Test result with event."""
        result = WorkflowResult(
            event={"id": "evt_1", "title": "Meeting"},
            auto_confirmed=True,
        )
        assert result.event["title"] == "Meeting"
        assert result.auto_confirmed is True

    def test_with_conflicts(self):
        """Test result with conflicts."""
        result = WorkflowResult(
            conflicts=[{"id": "c1"}, {"id": "c2"}],
            proposed_resolutions=[{"resolution_id": "r1"}],
            auto_confirmed=False,
        )
        assert len(result.conflicts) == 2
        assert len(result.proposed_resolutions) == 1

    def test_clarification_result(self):
        """Test clarification result."""
        result = WorkflowResult(
            clarification_needed=True,
            clarification_message="What time did you mean?",
        )
        assert result.clarification_needed is True
        assert result.clarification_message is not None


class TestHealthResponse:
    """Test HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy status response."""
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            orchestrator_ready=True,
            database_connected=True,
        )
        assert response.status == "healthy"
        assert response.orchestrator_ready is True

    def test_unhealthy_response(self):
        """Test unhealthy status response."""
        response = HealthResponse(
            status="unhealthy",
            version="0.1.0",
            orchestrator_ready=False,
            database_connected=True,
        )
        assert response.status == "unhealthy"
        assert response.orchestrator_ready is False


class TestEventListResponse:
    """Test EventListResponse model."""

    def test_empty_list(self):
        """Test empty event list."""
        response = EventListResponse(
            events=[],
            total=0,
            limit=50,
            offset=0,
        )
        assert len(response.events) == 0
        assert response.total == 0

    def test_with_events(self):
        """Test response with events."""
        response = EventListResponse(
            events=[{"id": "evt_1"}, {"id": "evt_2"}],
            total=10,
            limit=2,
            offset=0,
        )
        assert len(response.events) == 2
        assert response.total == 10
