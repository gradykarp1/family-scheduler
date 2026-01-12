"""
Unit tests for API response builder.

Tests transformation of orchestrator state to API responses.
"""

import pytest

from src.api.response_builder import (
    build_response,
    extract_result,
    extract_steps,
    build_explanation,
)
from src.agents.state import FamilySchedulerState


class TestBuildResponse:
    """Test build_response function."""

    def test_completed_event_response(self):
        """Test response for completed event creation."""
        state: FamilySchedulerState = {
            "conversation_id": "conv_123",
            "workflow_status": "completed",
            "proposed_event": {
                "id": "evt_1",
                "title": "Meeting",
                "status": "confirmed",
            },
            "detected_conflicts": {"has_conflicts": False, "conflicts": []},
            "agent_outputs": {
                "nl_parser": {"confidence": 0.95},
            },
            "audit_log": [
                {"step": "nl_parsing", "explanation": "Parsed request"},
            ],
        }

        response = build_response(state)

        assert response.workflow_id == "conv_123"
        assert response.status == "completed"
        assert response.result.event is not None
        assert response.result.auto_confirmed is True

    def test_awaiting_user_with_conflicts(self):
        """Test response for conflicts awaiting resolution."""
        state: FamilySchedulerState = {
            "conversation_id": "conv_456",
            "workflow_status": "awaiting_user",
            "proposed_event": {"id": "evt_1", "status": "proposed"},
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1", "type": "time_conflict"}],
            },
            "agent_outputs": {
                "resolution": {
                    "data": {
                        "proposed_resolutions": [{"resolution_id": "r1"}],
                    }
                }
            },
            "audit_log": [],
        }

        response = build_response(state)

        assert response.status == "awaiting_user"
        assert response.result.auto_confirmed is False
        assert len(response.result.conflicts) == 1

    def test_failed_response(self):
        """Test response for failed workflow."""
        state: FamilySchedulerState = {
            "conversation_id": "conv_789",
            "workflow_status": "failed",
            "errors": [{"message": "Agent crashed"}],
            "agent_outputs": {},
            "audit_log": [],
        }

        response = build_response(state)

        assert response.status == "failed"
        assert response.errors is not None
        assert len(response.errors) == 1


class TestExtractResult:
    """Test extract_result function."""

    def test_event_result(self):
        """Test extraction with event."""
        state: FamilySchedulerState = {
            "proposed_event": {"id": "evt_1", "title": "Test"},
            "detected_conflicts": {"has_conflicts": False, "conflicts": []},
            "agent_outputs": {},
        }

        result = extract_result(state)

        assert result.event is not None
        assert result.auto_confirmed is True

    def test_conflict_result(self):
        """Test extraction with conflicts."""
        state: FamilySchedulerState = {
            "proposed_event": {"id": "evt_1"},
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1"}],
            },
            "agent_outputs": {
                "resolution": {
                    "data": {"proposed_resolutions": [{"resolution_id": "r1"}]}
                }
            },
        }

        result = extract_result(state)

        assert result.auto_confirmed is False
        assert len(result.conflicts) == 1
        assert len(result.proposed_resolutions) == 1

    def test_query_result(self):
        """Test extraction for query response."""
        state: FamilySchedulerState = {
            "detected_conflicts": {},
            "agent_outputs": {
                "query": {
                    "data": {
                        "results": {"response": "You have 3 events tomorrow."}
                    }
                }
            },
        }

        result = extract_result(state)

        assert result.query_response == "You have 3 events tomorrow."

    def test_clarification_result(self):
        """Test extraction for clarification."""
        state: FamilySchedulerState = {
            "detected_conflicts": {},
            "agent_outputs": {
                "clarification": {
                    "data": {
                        "message": "What time did you mean?",
                    }
                }
            },
        }

        result = extract_result(state)

        assert result.clarification_needed is True
        assert result.clarification_message == "What time did you mean?"


class TestExtractSteps:
    """Test extract_steps function."""

    def test_extract_steps(self):
        """Test step extraction from audit log."""
        audit_log = [
            {"step": "nl_parsing"},
            {"step": "scheduling"},
            {"step": "conflict_detection"},
        ]

        steps = extract_steps(audit_log)

        assert steps == ["nl_parsing", "scheduling", "conflict_detection"]

    def test_deduplication(self):
        """Test duplicate steps are removed."""
        audit_log = [
            {"step": "nl_parsing"},
            {"step": "nl_parsing"},
            {"step": "scheduling"},
        ]

        steps = extract_steps(audit_log)

        assert steps == ["nl_parsing", "scheduling"]

    def test_empty_audit_log(self):
        """Test empty audit log."""
        steps = extract_steps([])
        assert steps == []


class TestBuildExplanation:
    """Test build_explanation function."""

    def test_completed_explanation(self):
        """Test explanation for completed workflow."""
        state: FamilySchedulerState = {
            "workflow_status": "completed",
            "proposed_event": {"title": "Meeting"},
            "detected_conflicts": {},
            "agent_outputs": {},
            "audit_log": [
                {"explanation": "Parsed request"},
                {"explanation": "Found time slot"},
            ],
        }

        explanation = build_explanation(state)

        assert "Parsed request" in explanation
        assert "Found time slot" in explanation
        assert "Meeting" in explanation

    def test_conflict_explanation(self):
        """Test explanation for conflicts."""
        state: FamilySchedulerState = {
            "workflow_status": "awaiting_user",
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [{"id": "c1"}, {"id": "c2"}],
            },
            "agent_outputs": {},
            "audit_log": [],
        }

        explanation = build_explanation(state)

        assert "2 conflict" in explanation

    def test_failed_explanation(self):
        """Test explanation for failed workflow."""
        state: FamilySchedulerState = {
            "workflow_status": "failed",
            "errors": [{"message": "LLM timeout"}],
            "detected_conflicts": {},
            "agent_outputs": {},
            "audit_log": [],
        }

        explanation = build_explanation(state)

        assert "LLM timeout" in explanation
