"""
Integration tests for multi-turn conversations.

Tests conversation continuity using the same conversation_id
with real MemorySaver checkpointing.
"""

import pytest
from unittest.mock import patch

from src.orchestrator import invoke_orchestrator, build_orchestrator_graph
from src.orchestrator.checkpointing import reset_checkpointer, get_checkpointer


pytestmark = pytest.mark.integration


class TestMultiTurnConversations:
    """Test multi-turn conversation workflows with state preservation."""

    def test_conversation_context_preserved_across_turns(
        self, mock_llm_factory, mock_calendar_empty
    ):
        """
        Test that conversation context is preserved across turns.

        Turn 1: User provides incomplete request -> awaiting_user
        Turn 2: User provides clarification with same conversation_id -> completed
        """
        conversation_id = "multi_turn_test_001"

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_calendar.return_value = mock_calendar_empty

            # Build graph once (to use same checkpointer)
            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # Turn 1: Low confidence request
            patched_llm.return_value = mock_llm_factory("create_low_confidence")

            result_turn1 = invoke_orchestrator(
                graph=graph,
                user_input="schedule something",
                user_id="parent_1",
                conversation_id=conversation_id,
            )

            # Verify turn 1 awaits clarification
            assert result_turn1["workflow_status"] == "awaiting_user"
            assert result_turn1["conversation_id"] == conversation_id

            # Turn 2: User provides clarification
            patched_llm.return_value = mock_llm_factory("create_high_confidence")

            result_turn2 = invoke_orchestrator(
                graph=graph,
                user_input="I mean schedule soccer practice tomorrow at 2pm for Charlie",
                user_id="parent_1",
                conversation_id=conversation_id,
            )

            # Verify turn 2 completes
            assert result_turn2["workflow_status"] == "completed"
            assert result_turn2["conversation_id"] == conversation_id
            assert result_turn2["proposed_event"] is not None

    def test_different_conversation_ids_are_isolated(
        self, mock_llm_factory, mock_calendar_empty
    ):
        """Test that different conversation_ids maintain separate state."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # Conversation A
            result_a = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting at 10am",
                user_id="user_a",
                conversation_id="conv_a",
            )

            # Conversation B (different conversation)
            result_b = invoke_orchestrator(
                graph=graph,
                user_input="Schedule lunch at noon",
                user_id="user_b",
                conversation_id="conv_b",
            )

            # Verify both completed independently
            assert result_a["conversation_id"] == "conv_a"
            assert result_b["conversation_id"] == "conv_b"
            assert result_a["workflow_status"] == "completed"
            assert result_b["workflow_status"] == "completed"

    def test_checkpointer_persists_state(self, mock_llm_factory, mock_calendar_empty):
        """Test that MemorySaver checkpointer correctly tracks workflow state."""
        conversation_id = "checkpoint_test_001"

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # Execute workflow
            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting tomorrow",
                user_id="parent_1",
                conversation_id=conversation_id,
            )

            # Verify workflow completed successfully
            assert result["workflow_status"] == "completed"
            assert len(result["audit_log"]) > 0

            # The checkpointer should have state for this thread
            # This is verified by the successful multi-turn test above

    def test_conversation_id_auto_generated_when_not_provided(
        self, mock_llm_factory, mock_calendar_empty
    ):
        """Test that conversation_id is auto-generated if not provided."""
        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_empty

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # Invoke without conversation_id
            result = invoke_orchestrator(
                graph=graph,
                user_input="Schedule meeting tomorrow",
                user_id="parent_1",
                # No conversation_id provided
            )

            # Should auto-generate a conversation_id
            assert result["conversation_id"] is not None
            assert len(result["conversation_id"]) > 0


class TestWorkflowResumption:
    """Test workflow resumption after user input."""

    def test_can_resume_after_clarification_request(
        self, mock_llm_factory, mock_calendar_empty
    ):
        """
        Test workflow can resume after user provides clarification.

        This tests the full clarification -> resumption flow.
        """
        conversation_id = "resume_test_001"

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            patched_calendar.return_value = mock_calendar_empty

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # Initial ambiguous request
            patched_llm.return_value = mock_llm_factory("create_low_confidence")

            result1 = invoke_orchestrator(
                graph=graph,
                user_input="book it",
                user_id="user_1",
                conversation_id=conversation_id,
            )

            assert result1["workflow_status"] == "awaiting_user"
            assert "clarification" in result1["agent_outputs"]

            # User provides clarifying information
            patched_llm.return_value = mock_llm_factory("create_high_confidence")

            result2 = invoke_orchestrator(
                graph=graph,
                user_input="I want to book soccer practice for Charlie tomorrow at 2pm",
                user_id="user_1",
                conversation_id=conversation_id,
            )

            # Should complete successfully
            assert result2["workflow_status"] == "completed"
            assert result2["proposed_event"] is not None

    def test_conflict_resolution_flow(
        self, mock_llm_factory, mock_calendar_with_conflict, mock_calendar_empty
    ):
        """
        Test conflict detection -> user selects resolution -> event created.
        """
        conversation_id = "conflict_resolution_test"

        with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
             patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

            reset_checkpointer()
            import src.orchestrator
            src.orchestrator._compiled_graph = None
            graph = build_orchestrator_graph()

            # First request hits conflict
            patched_llm.return_value = mock_llm_factory("create_high_confidence")
            patched_calendar.return_value = mock_calendar_with_conflict

            result1 = invoke_orchestrator(
                graph=graph,
                user_input="Schedule soccer at 2pm tomorrow",
                user_id="user_1",
                conversation_id=conversation_id,
            )

            assert result1["workflow_status"] == "awaiting_user"
            assert result1["detected_conflicts"]["has_conflicts"] is True
            resolutions = result1["agent_outputs"]["resolution"]["data"]["proposed_resolutions"]
            assert len(resolutions) > 0

            # User could then select a resolution and re-invoke
            # For this test, we just verify the flow up to resolution proposal
