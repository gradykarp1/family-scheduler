"""
Integration tests for orchestrator workflows.

Tests complete workflow execution through the LangGraph orchestrator
with mocked LLM and calendar services but real graph execution.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.orchestrator import invoke_orchestrator, build_orchestrator_graph
from src.orchestrator.checkpointing import reset_checkpointer
from src.agents.state import NLParserOutput


pytestmark = pytest.mark.integration


class TestEventCreationHappyPath:
    """
    Test event creation workflow without conflicts.

    Flow: NL Parser -> Scheduling -> Resource -> Conflict Detection -> Auto Confirm
    """

    def test_complete_event_creation_workflow(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """
        Test full event creation from natural language to confirmation.

        Given: User requests "Schedule soccer practice tomorrow at 2pm"
        When: Orchestrator processes the request with no existing conflicts
        Then: Event is created and auto-confirmed
        """
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule soccer practice tomorrow at 2pm for Charlie",
                user_id="parent_1",
                conversation_id="test_conv_001",
            )

            # Verify workflow completed successfully
            assert result["workflow_status"] == "completed"
            assert result["proposed_event"] is not None
            assert result["proposed_event"]["status"] == "confirmed"
            assert result["proposed_event"]["title"] == "Soccer Practice"

            # Verify workflow steps executed
            steps = [entry["step"] for entry in result["audit_log"]]
            assert "nl_parsing" in steps
            assert "scheduling" in steps
            assert "resource_check" in steps
            assert "conflict_detection" in steps
            assert "auto_confirm" in steps

            # Verify no conflicts were detected
            detected_conflicts = result.get("detected_conflicts", {})
            assert detected_conflicts.get("has_conflicts") is False

    def test_event_creation_generates_event_id(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test that created event has a valid ID."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting tomorrow",
                user_id="user_1",
            )

            assert result["workflow_status"] == "completed"
            assert result["proposed_event"]["event_id"] is not None
            assert len(result["proposed_event"]["event_id"]) > 0

    def test_event_creation_with_participants(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test event creation includes participant information."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule soccer for Charlie",
                user_id="parent_1",
            )

            assert result["workflow_status"] == "completed"
            participants = result["proposed_event"].get("participants", [])
            assert "Charlie" in participants


class TestEventWithConflicts:
    """
    Test event creation workflow with conflicts.

    Flow: NL Parser -> Scheduling -> Resource -> Conflict Detection -> Resolution -> awaiting_user
    """

    def test_conflict_detection_triggers_resolution(
        self, mock_llm_factory, mock_calendar_with_conflict, fresh_orchestrator
    ):
        """
        Test that conflicting events trigger resolution workflow.

        Given: User requests event at time that conflicts with existing event
        When: Orchestrator processes the request
        Then: Conflicts detected and resolutions proposed, status is awaiting_user
        """
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_with_conflict

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule soccer practice tomorrow at 2pm for Charlie",
                user_id="parent_1",
            )

            # Verify workflow awaits user decision
            assert result["workflow_status"] == "awaiting_user"

            # Verify conflicts were detected
            detected_conflicts = result.get("detected_conflicts", {})
            assert detected_conflicts.get("has_conflicts") is True
            assert len(detected_conflicts.get("conflicts", [])) > 0

            # Verify resolution options were generated
            resolution_output = result["agent_outputs"].get("resolution", {})
            resolutions = resolution_output.get("data", {}).get("proposed_resolutions", [])
            assert len(resolutions) >= 1

            # Verify resolution has required fields
            first_resolution = resolutions[0]
            assert "resolution_id" in first_resolution
            assert "strategy" in first_resolution
            assert "description" in first_resolution

    def test_conflict_includes_conflicting_event_info(
        self, mock_llm_factory, mock_calendar_with_conflict, fresh_orchestrator
    ):
        """Test that conflict includes information about the conflicting event."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_with_conflict

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule something at 2pm tomorrow",
                user_id="parent_1",
            )

            assert result["workflow_status"] == "awaiting_user"
            conflicts = result["detected_conflicts"]["conflicts"]
            assert len(conflicts) > 0

            # Conflict should reference the existing Team Meeting
            first_conflict = conflicts[0]
            assert "type" in first_conflict


class TestQueryWorkflow:
    """
    Test query workflow.

    Flow: NL Parser -> Query -> completed
    """

    def test_query_workflow_returns_schedule_info(
        self, mock_llm_factory, mock_calendar_with_events, fresh_orchestrator
    ):
        """
        Test query workflow for schedule questions.

        Given: User asks "What's on my calendar tomorrow?"
        When: Orchestrator processes the query
        Then: Query is answered and workflow completes
        """
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("query")
            patched_calendar.return_value = mock_calendar_with_events

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="What's on my calendar tomorrow?",
                user_id="parent_1",
            )

            # Verify workflow completed
            assert result["workflow_status"] == "completed"

            # Verify query agent was invoked
            assert "query" in result["agent_outputs"]
            query_output = result["agent_outputs"]["query"]
            assert "data" in query_output

            # Verify response contains query results
            results = query_output["data"].get("results", {})
            assert "response" in results

    def test_query_workflow_includes_events_found(
        self, mock_llm_factory, mock_calendar_with_events, fresh_orchestrator
    ):
        """Test query returns event count."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("query")
            patched_calendar.return_value = mock_calendar_with_events

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="What events do I have tomorrow?",
                user_id="parent_1",
            )

            assert result["workflow_status"] == "completed"
            query_data = result["agent_outputs"]["query"]["data"]
            assert query_data["events_found"] >= 0


class TestLowConfidenceClarification:
    """
    Test low confidence clarification workflow.

    Flow: NL Parser -> Clarification -> awaiting_user
    """

    def test_low_confidence_triggers_clarification(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """
        Test that ambiguous input triggers clarification request.

        Given: User provides vague input "schedule something"
        When: Orchestrator processes the request
        Then: Clarification is requested, status is awaiting_user
        """
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_low_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="schedule something",
                user_id="parent_1",
            )

            # Verify workflow awaits clarification
            assert result["workflow_status"] == "awaiting_user"

            # Verify clarification was generated
            assert "clarification" in result["agent_outputs"]
            clarification_data = result["agent_outputs"]["clarification"]["data"]
            assert "message" in clarification_data
            assert "missing_fields" in clarification_data

            # Verify missing fields identified
            missing = clarification_data["missing_fields"]
            assert len(missing) > 0

    def test_clarification_identifies_specific_missing_fields(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test that clarification correctly identifies what information is missing."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_low_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="do that thing",
                user_id="parent_1",
            )

            assert result["workflow_status"] == "awaiting_user"
            missing_fields = result["agent_outputs"]["clarification"]["data"]["missing_fields"]

            # Should identify title and time as missing
            assert any("title" in f.lower() for f in missing_fields) or \
                   any("time" in f.lower() for f in missing_fields) or \
                   any("what" in f.lower() for f in missing_fields) or \
                   any("when" in f.lower() for f in missing_fields)


class TestAuditLogTracking:
    """Test that audit logs correctly track workflow execution."""

    def test_audit_log_includes_all_executed_steps(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test that audit log tracks all workflow steps."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting tomorrow at 3pm",
                user_id="user_1",
            )

            audit_log = result["audit_log"]
            assert len(audit_log) > 0

            # Each entry should have required fields
            for entry in audit_log:
                assert "step" in entry
                assert "timestamp" in entry
                assert "agent" in entry

    def test_audit_log_includes_confidence_scores(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test that audit log includes confidence scores."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting tomorrow",
                user_id="user_1",
            )

            # NL parser entry should have confidence
            nl_entry = next(
                (e for e in result["audit_log"] if e["step"] == "nl_parsing"),
                None
            )
            assert nl_entry is not None
            assert "confidence" in nl_entry
            assert 0 <= nl_entry["confidence"] <= 1


class TestErrorHandling:
    """Test error handling in orchestrator workflows."""

    def test_orchestrator_handles_empty_input_gracefully(
        self, mock_llm_factory, mock_calendar_empty, fresh_orchestrator
    ):
        """Test that empty input is handled without crashing."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            # Configure LLM to return low confidence for empty input
            patched_llm.return_value = mock_llm_factory("create_low_confidence")
            patched_calendar.return_value = mock_calendar_empty

            graph = fresh_orchestrator()

            result = invoke_orchestrator(
                graph=graph,
                user_input="",
                user_id="user_1",
            )

            # Should either fail gracefully or request clarification
            assert result["workflow_status"] in ["awaiting_user", "failed"]
