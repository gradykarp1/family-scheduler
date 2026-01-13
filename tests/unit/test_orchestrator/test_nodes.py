"""
Unit tests for orchestrator node implementations.

Tests individual nodes in isolation with mocked dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from src.agents.state import FamilySchedulerState
from src.orchestrator.nodes import (
    nl_parser_node,
    scheduling_node,
    resource_manager_node,
    conflict_detection_node,
    resolution_node,
    query_node,
    auto_confirm_node,
    request_clarification_node,
    _calculate_nl_confidence,
    _create_audit_entry,
    _create_error,
)


class TestHelperFunctions:
    """Test helper functions used by nodes."""

    def test_create_audit_entry(self):
        """Test audit entry creation."""
        entry = _create_audit_entry(
            step="test_step",
            agent="test_agent",
            confidence=0.85,
            explanation="Test explanation",
        )

        assert entry["step"] == "test_step"
        assert entry["agent"] == "test_agent"
        assert entry["confidence"] == 0.85
        assert entry["explanation"] == "Test explanation"
        assert "timestamp" in entry

    def test_create_error(self):
        """Test error entry creation."""
        error = _create_error(
            error_type="test_error",
            agent="test_agent",
            message="Test message",
            details={"key": "value"},
            retryable=True,
        )

        assert error["error_type"] == "test_error"
        assert error["agent"] == "test_agent"
        assert error["message"] == "Test message"
        assert error["details"]["key"] == "value"
        assert error["retryable"] is True
        assert "timestamp" in error

    def test_calculate_nl_confidence_complete_data(self):
        """Test confidence calculation with complete data."""
        parsed_data = {
            "event_type": "create",
            "title": "Team Meeting",
            "start_time": "2026-01-15T14:00:00Z",
            "participants": ["Alice", "Bob"],
        }

        confidence = _calculate_nl_confidence(parsed_data, "Schedule team meeting at 2pm with Alice and Bob")
        assert confidence >= 0.8  # Should be high with all fields

    def test_calculate_nl_confidence_minimal_data(self):
        """Test confidence calculation with minimal data."""
        parsed_data = {
            "event_type": "create",
        }

        confidence = _calculate_nl_confidence(parsed_data, "do something")
        assert confidence < 0.7  # Should be low with missing fields

    def test_calculate_nl_confidence_short_input(self):
        """Test confidence penalty for short inputs."""
        parsed_data = {
            "event_type": "create",
            "title": "Event",
        }

        confidence = _calculate_nl_confidence(parsed_data, "hi")
        assert confidence < 0.5  # Penalized for short input


class TestNLParserNode:
    """Test NL Parser node."""

    @patch("src.orchestrator.nodes.get_llm")
    def test_successful_parsing(self, mock_get_llm):
        """Test successful NL parsing."""
        # Mock LLM response
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '{"event_type": "create", "title": "Meeting", "start_time": "2026-01-15T14:00:00Z"}'
        mock_get_llm.return_value = mock_llm

        state: FamilySchedulerState = {
            "user_input": "Schedule a meeting at 2pm tomorrow",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = nl_parser_node(state)

        assert "agent_outputs" in result
        assert "nl_parser" in result["agent_outputs"]
        assert result["agent_outputs"]["nl_parser"]["data"]["event_type"] == "create"
        assert "parsed_event_data" in result
        assert len(result["audit_log"]) == 1
        assert result["workflow_status"] == "in_progress"

    @patch("src.orchestrator.nodes.get_llm")
    def test_llm_failure_returns_error_state(self, mock_get_llm):
        """Test LLM failure returns error state."""
        mock_get_llm.side_effect = Exception("API error")

        state: FamilySchedulerState = {
            "user_input": "Schedule a meeting",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "agent_outputs": {},
            "audit_log": [],
            "errors": [],
            "workflow_status": "in_progress",
        }

        result = nl_parser_node(state)

        assert result["workflow_status"] == "failed"
        assert len(result["errors"]) == 1
        assert result["errors"][0]["agent"] == "nl_parser"


class TestSchedulingNode:
    """Test Scheduling node."""

    def test_with_specified_time(self):
        """Test scheduling with user-specified time."""
        state: FamilySchedulerState = {
            "user_input": "Schedule meeting at 2pm",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "event_type": "create",
                "start_time": "2026-01-15T14:00:00Z",
                "end_time": "2026-01-15T15:00:00Z",
                "participants": ["Alice"],
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = scheduling_node(state)

        assert "agent_outputs" in result
        assert "scheduling" in result["agent_outputs"]
        assert len(result["agent_outputs"]["scheduling"]["data"]["candidate_times"]) == 1
        assert result["selected_time_slot"] is not None
        assert result["agent_outputs"]["scheduling"]["confidence"] == 0.95

    def test_without_specified_time(self):
        """Test scheduling without user-specified time."""
        state: FamilySchedulerState = {
            "user_input": "Schedule a meeting",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "event_type": "create",
                "title": "Meeting",
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = scheduling_node(state)

        # Now the scheduling node finds available slots when no time is specified
        candidate_times = result["agent_outputs"]["scheduling"]["data"]["candidate_times"]
        assert isinstance(candidate_times, list)
        # If slots are found, confidence should be 0.8; if not found, 0.3
        confidence = result["agent_outputs"]["scheduling"]["confidence"]
        if len(candidate_times) > 0:
            assert confidence == 0.8
            assert result["selected_time_slot"] is not None
        else:
            assert confidence == 0.3
            assert result["selected_time_slot"] is None


class TestResourceManagerNode:
    """Test Resource Manager node."""

    def test_with_resources(self):
        """Test resource checking with requested resources."""
        state: FamilySchedulerState = {
            "user_input": "Schedule meeting in conference room",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "resources": ["conference room"],
            },
            "selected_time_slot": {
                "start_time": "2026-01-15T14:00:00Z",
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = resource_manager_node(state)

        assert "agent_outputs" in result
        assert "resource_manager" in result["agent_outputs"]
        assert result["agent_outputs"]["resource_manager"]["data"]["all_resources_available"] is True

    def test_without_resources(self):
        """Test resource checking without requested resources."""
        state: FamilySchedulerState = {
            "user_input": "Schedule meeting",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {},
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = resource_manager_node(state)

        assert result["agent_outputs"]["resource_manager"]["data"]["all_resources_available"] is True


class TestConflictDetectionNode:
    """Test Conflict Detection node."""

    def test_no_conflicts(self):
        """Test conflict detection with no conflicts."""
        state: FamilySchedulerState = {
            "user_input": "Schedule meeting",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "participants": ["Alice"],
            },
            "selected_time_slot": {
                "start_time": "2026-01-15T14:00:00Z",
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = conflict_detection_node(state)

        assert "detected_conflicts" in result
        assert result["detected_conflicts"]["has_conflicts"] is False
        assert result["detected_conflicts"]["conflicts"] == []
        assert result["agent_outputs"]["conflict_detection"]["confidence"] == 1.0


class TestResolutionNode:
    """Test Resolution node."""

    @patch("src.orchestrator.nodes.get_llm")
    def test_generates_resolutions(self, mock_get_llm):
        """Test resolution generation."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = '''
        {
            "proposed_resolutions": [
                {
                    "resolution_id": "res_1",
                    "strategy": "move_event",
                    "score": 0.9,
                    "description": "Move to 3pm"
                }
            ],
            "recommended_resolution": "res_1"
        }
        '''
        mock_get_llm.return_value = mock_llm

        state: FamilySchedulerState = {
            "user_input": "Schedule meeting",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {"title": "Meeting"},
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1", "type": "time_conflict"}],
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = resolution_node(state)

        assert "agent_outputs" in result
        assert "resolution" in result["agent_outputs"]
        assert result["workflow_status"] == "awaiting_user"


class TestQueryNode:
    """Test Query node."""

    @patch("src.orchestrator.nodes.get_llm")
    def test_answers_query(self, mock_get_llm):
        """Test query answering."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value.content = "You have a meeting at 2pm tomorrow."
        mock_get_llm.return_value = mock_llm

        state: FamilySchedulerState = {
            "user_input": "What's on my calendar tomorrow?",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {"event_type": "query"},
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = query_node(state)

        assert "agent_outputs" in result
        assert "query" in result["agent_outputs"]
        assert result["workflow_status"] == "completed"


class TestAutoConfirmNode:
    """Test Auto Confirm node."""

    def test_creates_confirmed_event(self):
        """Test auto confirmation creates event."""
        state: FamilySchedulerState = {
            "user_input": "Schedule meeting at 2pm",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "title": "Team Meeting",
                "participants": ["Alice", "Bob"],
                "resources": [],
            },
            "selected_time_slot": {
                "start_time": "2026-01-15T14:00:00Z",
                "end_time": "2026-01-15T15:00:00Z",
            },
            "agent_outputs": {},
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = auto_confirm_node(state)

        assert "proposed_event" in result
        assert result["proposed_event"]["title"] == "Team Meeting"
        assert result["proposed_event"]["status"] == "confirmed"
        assert result["workflow_status"] == "completed"


class TestRequestClarificationNode:
    """Test Request Clarification node."""

    def test_identifies_missing_fields(self):
        """Test clarification identifies missing fields."""
        state: FamilySchedulerState = {
            "user_input": "schedule something",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {},
            "agent_outputs": {
                "nl_parser": {"confidence": 0.4},
            },
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = request_clarification_node(state)

        assert "agent_outputs" in result
        assert "clarification" in result["agent_outputs"]
        assert result["workflow_status"] == "awaiting_user"
        assert "missing_fields" in result["agent_outputs"]["clarification"]["data"]

    def test_low_confidence_clarification(self):
        """Test clarification for low confidence."""
        state: FamilySchedulerState = {
            "user_input": "do that thing",
            "user_id": "user_1",
            "conversation_id": "conv_1",
            "parsed_event_data": {
                "title": "Event",
                "start_time": "2026-01-15T14:00:00Z",
                "participants": ["Alice"],
            },
            "agent_outputs": {
                "nl_parser": {"confidence": 0.5},
            },
            "audit_log": [],
            "workflow_status": "in_progress",
        }

        result = request_clarification_node(state)

        assert result["workflow_status"] == "awaiting_user"
        clarification_data = result["agent_outputs"]["clarification"]["data"]
        assert "message" in clarification_data
