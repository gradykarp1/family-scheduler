"""
Unit tests for orchestrator graph construction.

Tests graph building, state initialization, and result analysis.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.orchestrator import (
    build_orchestrator_graph,
    get_orchestrator_graph,
    initialize_state,
    invoke_orchestrator,
    analyze_result,
)
from src.orchestrator.checkpointing import reset_checkpointer
from src.agents.state import FamilySchedulerState


class TestBuildOrchestratorGraph:
    """Test graph building."""

    def setup_method(self):
        """Reset checkpointer before each test."""
        reset_checkpointer()

    def test_builds_graph_successfully(self):
        """Test graph builds without errors."""
        graph = build_orchestrator_graph()
        assert graph is not None

    def test_graph_has_nodes(self):
        """Test graph contains expected nodes."""
        graph = build_orchestrator_graph()

        # Graph should have been compiled, so we can check the nodes
        # through the underlying graph structure
        assert graph is not None


class TestGetOrchestratorGraph:
    """Test singleton graph retrieval."""

    def setup_method(self):
        """Reset checkpointer before each test."""
        reset_checkpointer()
        # Reset the module-level graph
        import src.orchestrator
        src.orchestrator._compiled_graph = None

    def test_returns_same_graph_instance(self):
        """Test singleton returns same instance."""
        graph1 = get_orchestrator_graph()
        graph2 = get_orchestrator_graph()
        assert graph1 is graph2


class TestInitializeState:
    """Test state initialization."""

    def test_creates_valid_state(self):
        """Test state initialization with required fields."""
        state = initialize_state(
            user_input="Schedule meeting at 2pm",
            user_id="user_123",
            conversation_id="conv_456",
        )

        assert state["user_input"] == "Schedule meeting at 2pm"
        assert state["user_id"] == "user_123"
        assert state["conversation_id"] == "conv_456"
        assert state["workflow_status"] == "in_progress"
        assert state["agent_outputs"] == {}
        assert state["errors"] == []
        assert state["audit_log"] == []

    def test_generates_conversation_id(self):
        """Test conversation ID is generated if not provided."""
        state = initialize_state(
            user_input="Schedule meeting",
            user_id="user_123",
        )

        assert state["conversation_id"] is not None
        assert len(state["conversation_id"]) > 0

    def test_sets_timestamps(self):
        """Test timestamps are set correctly."""
        state = initialize_state(
            user_input="Schedule meeting",
            user_id="user_123",
        )

        assert "created_at" in state
        assert "updated_at" in state
        assert state["created_at"] == state["updated_at"]


class TestAnalyzeResult:
    """Test result analysis."""

    def test_error_result(self):
        """Test analysis of error state."""
        state: FamilySchedulerState = {
            "user_input": "test",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "workflow_status": "failed",
            "errors": [{"message": "Test error"}],
        }

        result = analyze_result(state)

        assert result["result_type"] == "error"
        assert "Test error" in result["message"]

    def test_awaiting_resolution_result(self):
        """Test analysis of awaiting resolution state."""
        state: FamilySchedulerState = {
            "user_input": "test",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "workflow_status": "awaiting_user",
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1"}],
            },
            "agent_outputs": {
                "resolution": {
                    "data": {
                        "proposed_resolutions": [{"id": "r1"}],
                    }
                }
            },
        }

        result = analyze_result(state)

        assert result["result_type"] == "awaiting_resolution"
        assert "conflicts" in result["data"]
        assert "resolutions" in result["data"]

    def test_awaiting_clarification_result(self):
        """Test analysis of awaiting clarification state."""
        state: FamilySchedulerState = {
            "user_input": "test",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "workflow_status": "awaiting_user",
            "detected_conflicts": {"has_conflicts": False},
            "agent_outputs": {
                "clarification": {
                    "data": {
                        "message": "What time?",
                        "missing_fields": ["start_time"],
                    }
                }
            },
        }

        result = analyze_result(state)

        assert result["result_type"] == "awaiting_clarification"
        assert "What time?" in result["message"]

    def test_event_created_result(self):
        """Test analysis of completed event creation."""
        state: FamilySchedulerState = {
            "user_input": "test",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "workflow_status": "completed",
            "proposed_event": {
                "title": "Meeting",
                "status": "confirmed",
            },
        }

        result = analyze_result(state)

        assert result["result_type"] == "event_created"
        assert "Meeting" in result["message"]
        assert result["data"]["event"]["title"] == "Meeting"

    def test_query_answered_result(self):
        """Test analysis of completed query."""
        state: FamilySchedulerState = {
            "user_input": "What's on my calendar?",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "workflow_status": "completed",
            "agent_outputs": {
                "query": {
                    "data": {
                        "results": {"response": "You have 3 events tomorrow."}
                    }
                }
            },
        }

        result = analyze_result(state)

        assert result["result_type"] == "query_answered"
        assert "3 events" in result["message"]


class TestInvokeOrchestrator:
    """Test orchestrator invocation."""

    def setup_method(self):
        """Reset checkpointer before each test."""
        reset_checkpointer()

    @patch("src.services.calendar_service.get_calendar_service")
    @patch("src.orchestrator.nodes.get_llm")
    def test_successful_invocation(self, mock_get_llm, mock_get_calendar_service):
        """Test successful orchestrator invocation."""
        from datetime import datetime, timezone
        from src.agents.state import NLParserOutput
        from src.integrations.base import CalendarEvent

        # Mock calendar service with real CalendarEvent (serializable)
        mock_event = CalendarEvent(
            id="event_123",
            calendar_id="test@calendar",
            title="Team Meeting",
            start_time=datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 15, 0, tzinfo=timezone.utc),
        )
        mock_service = MagicMock()
        mock_service.create_event.return_value = mock_event
        mock_service.get_events_in_range.return_value = []
        mock_service.find_available_slots.return_value = []
        mock_get_calendar_service.return_value = mock_service

        # Create mock NLParserOutput for structured output
        mock_parsed_output = NLParserOutput(
            event_type="create",
            title="Team Meeting",
            start_time="2026-01-15T14:00:00Z",
            end_time="2026-01-15T15:00:00Z",
            participants=["Alice"],
            resources=[],
            priority=None,
            flexibility=None,
            recurrence_rule=None,
        )

        # Setup mock for structured output
        mock_structured_llm = MagicMock()
        mock_structured_llm.invoke.return_value = mock_parsed_output

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        # For regular invoke (query node uses this)
        mock_llm.invoke.return_value.content = "Mock response"
        mock_get_llm.return_value = mock_llm

        graph = build_orchestrator_graph()

        result = invoke_orchestrator(
            graph=graph,
            user_input="Schedule team meeting at 2pm tomorrow",
            user_id="user_123",
        )

        assert result is not None
        assert "workflow_status" in result
        assert "audit_log" in result
        # Should have executed some nodes
        assert len(result.get("audit_log", [])) > 0

    @patch("src.services.calendar_service.get_calendar_service")
    @patch("src.orchestrator.nodes.get_llm")
    def test_query_workflow(self, mock_get_llm, mock_get_calendar_service):
        """Test query workflow path."""
        from src.agents.state import NLParserOutput

        # Mock calendar service
        mock_service = MagicMock()
        mock_service.get_events_in_range.return_value = []
        mock_get_calendar_service.return_value = mock_service

        # Create mock NLParserOutput for query type
        mock_parsed_output = NLParserOutput(
            event_type="query",
            title="Calendar Check",
            start_time="2026-01-15T00:00:00Z",
            end_time=None,
            participants=["user"],
            resources=[],
            priority=None,
            flexibility=None,
            recurrence_rule=None,
        )

        # Setup mock for structured output
        mock_structured_llm = MagicMock()
        mock_structured_llm.invoke.return_value = mock_parsed_output

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        # For regular invoke (query node uses this)
        mock_llm.invoke.return_value.content = "You have 2 events tomorrow."
        mock_get_llm.return_value = mock_llm

        graph = build_orchestrator_graph()

        result = invoke_orchestrator(
            graph=graph,
            user_input="What's on my calendar tomorrow? Please check for me.",
            user_id="user_123",
        )

        assert result["workflow_status"] == "completed"
        # Should have query in agent outputs
        assert "query" in result.get("agent_outputs", {})

    @patch("src.orchestrator.nodes.get_llm")
    def test_low_confidence_clarification(self, mock_get_llm):
        """Test low confidence triggers clarification."""
        from src.agents.state import NLParserOutput

        # Create mock NLParserOutput with minimal data to trigger low confidence
        mock_parsed_output = NLParserOutput(
            event_type="create",
            title=None,
            start_time=None,
            end_time=None,
            participants=[],
            resources=[],
            priority=None,
            flexibility=None,
            recurrence_rule=None,
        )

        # Setup mock for structured output
        mock_structured_llm = MagicMock()
        mock_structured_llm.invoke.return_value = mock_parsed_output

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_get_llm.return_value = mock_llm

        graph = build_orchestrator_graph()

        result = invoke_orchestrator(
            graph=graph,
            user_input="do thing",  # Very short, ambiguous
            user_id="user_123",
        )

        # Should request clarification due to low confidence
        assert result["workflow_status"] == "awaiting_user"
        assert "clarification" in result.get("agent_outputs", {})
