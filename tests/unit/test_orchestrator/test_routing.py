"""
Unit tests for orchestrator routing functions.

Tests the routing decision logic that determines workflow paths.
"""

import pytest

from src.orchestrator.routing import (
    route_after_nl_parser,
    route_after_conflict_detection,
    route_on_error,
    route_scheduling_result,
    route_resource_result,
    CONFIDENCE_THRESHOLD,
)
from src.agents.state import FamilySchedulerState


class TestRouteAfterNLParser:
    """Test routing decisions after NL Parser node."""

    def test_high_confidence_event_routes_to_scheduling(self):
        """Test high confidence event intent routes to scheduling."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "Schedule meeting at 2pm",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "create", "title": "meeting"},
                    "confidence": 0.9,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "scheduling"

    def test_high_confidence_query_routes_to_query(self):
        """Test high confidence query intent routes to query agent."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "What's on my calendar tomorrow?",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "query"},
                    "confidence": 0.85,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "query"

    def test_low_confidence_routes_to_clarification(self):
        """Test low confidence routes to clarification."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "do that thing",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "create"},
                    "confidence": 0.5,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "clarification"

    def test_boundary_confidence_routes_to_clarification(self):
        """Test confidence at threshold boundary."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule something",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "create"},
                    "confidence": CONFIDENCE_THRESHOLD - 0.01,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "clarification"

    def test_exact_threshold_routes_to_scheduling(self):
        """Test confidence exactly at threshold routes to scheduling."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "create"},
                    "confidence": CONFIDENCE_THRESHOLD,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "scheduling"

    def test_modify_event_routes_to_scheduling(self):
        """Test modify event intent routes to scheduling."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "move the meeting to 3pm",
            "user_id": "user_1",
            "agent_outputs": {
                "nl_parser": {
                    "data": {"event_type": "modify"},
                    "confidence": 0.8,
                }
            },
            "workflow_status": "in_progress",
        }

        result = route_after_nl_parser(state)
        assert result == "scheduling"


class TestRouteAfterConflictDetection:
    """Test routing decisions after Conflict Detection node."""

    def test_conflicts_detected_routes_to_resolution(self):
        """Test conflicts detected routes to resolution agent."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "detected_conflicts": {
                "has_conflicts": True,
                "conflicts": [
                    {"id": "conflict_1", "type": "time_conflict"}
                ],
            },
            "workflow_status": "in_progress",
        }

        result = route_after_conflict_detection(state)
        assert result == "resolution"

    def test_no_conflicts_routes_to_auto_confirm(self):
        """Test no conflicts routes to auto confirm."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "detected_conflicts": {
                "has_conflicts": False,
                "conflicts": [],
            },
            "workflow_status": "in_progress",
        }

        result = route_after_conflict_detection(state)
        assert result == "auto_confirm"

    def test_empty_conflicts_routes_to_auto_confirm(self):
        """Test empty detected_conflicts routes to auto confirm."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "detected_conflicts": {},
            "workflow_status": "in_progress",
        }

        result = route_after_conflict_detection(state)
        assert result == "auto_confirm"

    def test_missing_conflicts_routes_to_auto_confirm(self):
        """Test missing detected_conflicts key routes to auto confirm."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
        }

        result = route_after_conflict_detection(state)
        assert result == "auto_confirm"


class TestRouteOnError:
    """Test error routing function."""

    def test_failed_status_routes_to_end(self):
        """Test failed workflow status routes to end."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "failed",
            "errors": [{"message": "test error"}],
        }

        result = route_on_error(state)
        assert result == "end"

    def test_in_progress_routes_to_continue(self):
        """Test in-progress status routes to continue."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
        }

        result = route_on_error(state)
        assert result == "continue"

    def test_completed_routes_to_continue(self):
        """Test completed status routes to continue."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "completed",
        }

        result = route_on_error(state)
        assert result == "continue"


class TestRouteSchedulingResult:
    """Test routing after scheduling node."""

    def test_candidates_found_routes_to_resource_manager(self):
        """Test successful scheduling routes to resource manager."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
            "agent_outputs": {
                "scheduling": {
                    "data": {
                        "candidate_times": [
                            {"start_time": "2026-01-15T14:00:00Z", "score": 0.9}
                        ]
                    }
                }
            },
        }

        result = route_scheduling_result(state)
        assert result == "resource_manager"

    def test_no_candidates_routes_to_clarification(self):
        """Test no candidate times routes to clarification."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
            "agent_outputs": {
                "scheduling": {
                    "data": {
                        "candidate_times": []
                    }
                }
            },
        }

        result = route_scheduling_result(state)
        assert result == "clarification"

    def test_failed_status_routes_to_end(self):
        """Test failed status routes to end."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "failed",
            "agent_outputs": {},
        }

        result = route_scheduling_result(state)
        assert result == "end"


class TestRouteResourceResult:
    """Test routing after resource manager node."""

    def test_resources_available_routes_to_conflict_detection(self):
        """Test all resources available routes to conflict detection."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
            "agent_outputs": {
                "resource_manager": {
                    "data": {
                        "all_resources_available": True
                    }
                }
            },
        }

        result = route_resource_result(state)
        assert result == "conflict_detection"

    def test_resources_unavailable_routes_to_clarification(self):
        """Test unavailable resources routes to clarification."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "in_progress",
            "agent_outputs": {
                "resource_manager": {
                    "data": {
                        "all_resources_available": False
                    }
                }
            },
        }

        result = route_resource_result(state)
        assert result == "clarification"

    def test_failed_status_routes_to_end(self):
        """Test failed status routes to end."""
        state: FamilySchedulerState = {
            "conversation_id": "test_conv",
            "user_input": "schedule meeting",
            "user_id": "user_1",
            "workflow_status": "failed",
            "agent_outputs": {},
        }

        result = route_resource_result(state)
        assert result == "end"
