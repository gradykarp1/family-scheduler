"""
Unit tests for LangGraph state schema and utilities.

Tests Pydantic model validation, state initialization, updates, transitions,
validation, and optimization defined in ADR-012.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.agents.state import (
    FamilySchedulerState,
    AgentOutput,
    NLParserData,
    TimeSlot,
    SchedulingData,
    ResourceAvailability,
    ResourceManagerData,
    Conflict,
    ConflictDetectionData,
    ResolutionChange,
    ProposedResolution,
    ResolutionData,
    QueryData,
    ProposedEvent,
    ValidationResult,
    ErrorInfo,
    Message,
)
from src.agents.state_utils import (
    initialize_state,
    update_state_with_agent_output,
    transition_workflow_step,
    validate_state_transition,
    prune_state,
    get_agent_output,
    get_agent_confidence,
    has_blocking_conflicts,
    is_workflow_complete,
    add_error,
    should_retry,
)


# ============================================================================
# Pydantic Model Validation Tests
# ============================================================================

class TestAgentOutput:
    """Test AgentOutput model validation."""

    def test_valid_agent_output(self):
        """Test creating valid AgentOutput."""
        output = AgentOutput(
            data={"test": "data"},
            explanation="Test explanation",
            confidence=0.95,
            reasoning="Test reasoning",
            timestamp=datetime.utcnow().isoformat(),
        )
        assert output.confidence == 0.95
        assert output.explanation == "Test explanation"

    def test_confidence_validation(self):
        """Test confidence must be between 0.0 and 1.0."""
        # Valid confidence
        AgentOutput(
            data={},
            explanation="Test",
            confidence=0.5,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )

        # Invalid: confidence > 1.0
        with pytest.raises(ValidationError):
            AgentOutput(
                data={},
                explanation="Test",
                confidence=1.5,
                reasoning="Test",
                timestamp=datetime.utcnow().isoformat(),
            )

        # Invalid: confidence < 0.0
        with pytest.raises(ValidationError):
            AgentOutput(
                data={},
                explanation="Test",
                confidence=-0.1,
                reasoning="Test",
                timestamp=datetime.utcnow().isoformat(),
            )


class TestNLParserData:
    """Test NLParserData model validation."""

    def test_valid_nl_parser_data(self):
        """Test creating valid NLParserData."""
        data = NLParserData(
            event_type="create",
            title="Soccer practice",
            start_time="2026-01-11T14:00:00Z",
            end_time="2026-01-11T16:00:00Z",
            participants=["user_123", "user_456"],
            resources=["field_1"],
        )
        assert data.event_type == "create"
        assert data.title == "Soccer practice"
        assert len(data.participants) == 2

    def test_event_type_validation(self):
        """Test event_type must be valid literal."""
        # Valid types
        for event_type in ["create", "modify", "cancel", "query"]:
            NLParserData(event_type=event_type)

        # Invalid type
        with pytest.raises(ValidationError):
            NLParserData(event_type="invalid")


class TestConflict:
    """Test Conflict model validation."""

    def test_valid_conflict(self):
        """Test creating valid Conflict."""
        conflict = Conflict(
            id="conflict_1",
            type="time_conflict",
            severity="high",
            details="Overlaps with existing event",
        )
        assert conflict.type == "time_conflict"
        assert conflict.severity == "high"

    def test_type_and_severity_validation(self):
        """Test type and severity must be valid literals."""
        # Valid types
        for conflict_type in ["time_conflict", "resource_conflict", "constraint_violation"]:
            Conflict(
                id="test",
                type=conflict_type,
                severity="low",
                details="Test",
            )

        # Valid severities
        for severity in ["low", "medium", "high", "critical"]:
            Conflict(
                id="test",
                type="time_conflict",
                severity=severity,
                details="Test",
            )


# ============================================================================
# State Initialization Tests
# ============================================================================

class TestStateInitialization:
    """Test state initialization."""

    def test_initialize_state(self):
        """Test initialize_state creates valid state."""
        state = initialize_state(
            user_input="Schedule soccer Saturday at 2pm", user_id="user_123"
        )

        assert state["user_input"] == "Schedule soccer Saturday at 2pm"
        assert state["user_id"] == "user_123"
        assert state["current_step"] == "start"
        assert state["workflow_status"] == "in_progress"
        assert state["retry_count"] == 0
        assert isinstance(state["conversation_id"], str)
        assert state["conversation_id"].startswith("conv_")
        assert len(state["agent_outputs"]) == 0
        assert len(state["validation_results"]) == 0
        assert len(state["errors"]) == 0

    def test_initialize_state_generates_unique_conversation_ids(self):
        """Test that multiple initializations generate unique conversation IDs."""
        state1 = initialize_state("Test 1", "user_1")
        state2 = initialize_state("Test 2", "user_2")

        assert state1["conversation_id"] != state2["conversation_id"]


# ============================================================================
# State Update Tests
# ============================================================================

class TestStateUpdates:
    """Test state update operations."""

    def test_update_state_with_agent_output(self):
        """Test update_state_with_agent_output adds agent output."""
        state = initialize_state("Test input", "user_123")

        output = AgentOutput(
            data={"event_type": "create", "title": "Soccer"},
            explanation="Parsed as event creation",
            confidence=0.95,
            reasoning="Clear intent",
            timestamp=datetime.utcnow().isoformat(),
        )

        state = update_state_with_agent_output(state, "nl_parser", output)

        assert "nl_parser" in state["agent_outputs"]
        assert state["agent_outputs"]["nl_parser"]["confidence"] == 0.95
        assert state["agent_outputs"]["nl_parser"]["explanation"] == "Parsed as event creation"
        assert len(state["audit_log"]) == 1
        assert state["audit_log"][0]["step"] == "nl_parser"

    def test_update_multiple_agents(self):
        """Test updating state with multiple agent outputs."""
        state = initialize_state("Test input", "user_123")

        # Add NL Parser output
        nl_output = AgentOutput(
            data={"event_type": "create"},
            explanation="NL Parser ran",
            confidence=0.9,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", nl_output)

        # Add Scheduling output
        scheduling_output = AgentOutput(
            data={"candidate_times": []},
            explanation="Scheduling ran",
            confidence=0.85,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "scheduling", scheduling_output)

        assert len(state["agent_outputs"]) == 2
        assert "nl_parser" in state["agent_outputs"]
        assert "scheduling" in state["agent_outputs"]
        assert len(state["audit_log"]) == 2


# ============================================================================
# State Transition Tests
# ============================================================================

class TestStateTransitions:
    """Test workflow step transitions."""

    def test_transition_workflow_step(self):
        """Test transition_workflow_step updates current step."""
        state = initialize_state("Test input", "user_123")
        state["current_step"] = "nl_parsing"

        state = transition_workflow_step(state, "nl_parsing", "scheduling")

        assert state["current_step"] == "scheduling"
        # Find transition in audit log
        transitions = [
            log for log in state["audit_log"] if log.get("action") == "transition"
        ]
        assert len(transitions) == 1
        assert transitions[0]["from"] == "nl_parsing"
        assert transitions[0]["to"] == "scheduling"


# ============================================================================
# State Validation Tests
# ============================================================================

class TestStateValidation:
    """Test state transition validation."""

    def test_validate_transition_to_scheduling_success(self):
        """Test successful validation when NL Parser output exists."""
        state = initialize_state("Test input", "user_123")

        # Add NL Parser output
        nl_output = AgentOutput(
            data={"event_type": "create"},
            explanation="Test",
            confidence=0.95,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", nl_output)

        valid, error = validate_state_transition(state, "scheduling")
        assert valid is True
        assert error is None

    def test_validate_transition_to_scheduling_failure_missing_nl_parser(self):
        """Test validation fails when NL Parser output missing."""
        state = initialize_state("Test input", "user_123")

        valid, error = validate_state_transition(state, "scheduling")
        assert valid is False
        assert "NL Parser output required" in error

    def test_validate_transition_to_scheduling_failure_low_confidence(self):
        """Test validation fails when NL Parser confidence too low."""
        state = initialize_state("Test input", "user_123")

        # Add NL Parser output with low confidence
        nl_output = AgentOutput(
            data={"event_type": "create"},
            explanation="Test",
            confidence=0.3,  # Too low
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", nl_output)

        valid, error = validate_state_transition(state, "scheduling")
        assert valid is False
        assert "confidence too low" in error


# ============================================================================
# State Pruning Tests
# ============================================================================

class TestStatePruning:
    """Test state pruning operations."""

    def test_prune_messages(self):
        """Test pruning keeps only recent messages."""
        state = initialize_state("Test input", "user_123")

        # Add 15 messages
        state["messages"] = [{"content": f"Message {i}"} for i in range(15)]

        state = prune_state(state, keep_messages=10)

        assert len(state["messages"]) == 10
        # Should keep most recent
        assert state["messages"][-1]["content"] == "Message 14"

    def test_prune_nl_parser_data(self):
        """Test pruning clears NL Parser data after extraction."""
        state = initialize_state("Test input", "user_123")

        # Add NL Parser output with data
        nl_output = AgentOutput(
            data={"event_type": "create", "title": "Large data structure"},
            explanation="Test",
            confidence=0.9,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", nl_output)

        # Mark as extracted to convenience field
        state["parsed_event_data"] = {"event_type": "create"}

        state = prune_state(state)

        # Data should be cleared but metadata retained
        assert state["agent_outputs"]["nl_parser"]["data"] == {}
        assert state["agent_outputs"]["nl_parser"]["explanation"] == "Test"
        assert state["agent_outputs"]["nl_parser"]["confidence"] == 0.9


# ============================================================================
# State Accessor Tests
# ============================================================================

class TestStateAccessors:
    """Test state accessor helper functions."""

    def test_get_agent_output_exists(self):
        """Test getting existing agent output."""
        state = initialize_state("Test input", "user_123")

        output = AgentOutput(
            data={"test": "data"},
            explanation="Test",
            confidence=0.9,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", output)

        result = get_agent_output(state, "nl_parser")
        assert result is not None
        assert result["confidence"] == 0.9

    def test_get_agent_output_missing(self):
        """Test getting non-existent agent output returns None."""
        state = initialize_state("Test input", "user_123")

        result = get_agent_output(state, "nl_parser")
        assert result is None

    def test_get_agent_confidence(self):
        """Test getting agent confidence score."""
        state = initialize_state("Test input", "user_123")

        output = AgentOutput(
            data={},
            explanation="Test",
            confidence=0.85,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )
        state = update_state_with_agent_output(state, "nl_parser", output)

        confidence = get_agent_confidence(state, "nl_parser")
        assert confidence == 0.85

    def test_get_agent_confidence_missing(self):
        """Test getting confidence for missing agent returns None."""
        state = initialize_state("Test input", "user_123")

        confidence = get_agent_confidence(state, "nl_parser")
        assert confidence is None


# ============================================================================
# Conflict and Error Tests
# ============================================================================

class TestConflictsAndErrors:
    """Test conflict and error handling functions."""

    def test_has_blocking_conflicts_true(self):
        """Test has_blocking_conflicts returns True when conflicts exist."""
        state = initialize_state("Test input", "user_123")
        state["detected_conflicts"] = {
            "has_conflicts": True,
            "blocking_conflicts": ["conflict_1"],
        }

        assert has_blocking_conflicts(state) is True

    def test_has_blocking_conflicts_false(self):
        """Test has_blocking_conflicts returns False when no conflicts."""
        state = initialize_state("Test input", "user_123")
        state["detected_conflicts"] = {
            "has_conflicts": False,
            "blocking_conflicts": [],
        }

        assert has_blocking_conflicts(state) is False

    def test_is_workflow_complete(self):
        """Test is_workflow_complete detects terminal states."""
        state = initialize_state("Test input", "user_123")

        # In progress - not complete
        assert is_workflow_complete(state) is False

        # Completed - is complete
        state["workflow_status"] = "completed"
        assert is_workflow_complete(state) is True

        # Failed - is complete
        state["workflow_status"] = "failed"
        assert is_workflow_complete(state) is True

        # Awaiting user - is complete
        state["workflow_status"] = "awaiting_user"
        assert is_workflow_complete(state) is True

    def test_add_error(self):
        """Test add_error adds error to state."""
        state = initialize_state("Test input", "user_123")

        state = add_error(
            state,
            step="nl_parser",
            error_type="parsing_error",
            message="Could not parse time",
            retryable=True,
        )

        assert len(state["errors"]) == 1
        assert state["errors"][0]["step"] == "nl_parser"
        assert state["errors"][0]["error_type"] == "parsing_error"
        assert state["errors"][0]["retryable"] is True

    def test_should_retry_true(self):
        """Test should_retry returns True when retryable and under limit."""
        state = initialize_state("Test input", "user_123")
        state = add_error(
            state,
            step="test",
            error_type="test_error",
            message="Test",
            retryable=True,
        )
        state["retry_count"] = 1

        assert should_retry(state, max_retries=3) is True

    def test_should_retry_false_not_retryable(self):
        """Test should_retry returns False for non-retryable error."""
        state = initialize_state("Test input", "user_123")
        state = add_error(
            state,
            step="test",
            error_type="fatal_error",
            message="Test",
            retryable=False,
        )

        assert should_retry(state, max_retries=3) is False

    def test_should_retry_false_max_retries_reached(self):
        """Test should_retry returns False when max retries reached."""
        state = initialize_state("Test input", "user_123")
        state = add_error(
            state,
            step="test",
            error_type="test_error",
            message="Test",
            retryable=True,
        )
        state["retry_count"] = 3

        assert should_retry(state, max_retries=3) is False


# ============================================================================
# JSON Serialization Tests
# ============================================================================

class TestSerialization:
    """Test JSON serialization of state and models."""

    def test_agent_output_serialization(self):
        """Test AgentOutput serializes to JSON correctly."""
        import json

        output = AgentOutput(
            data={"test": "data"},
            explanation="Test",
            confidence=0.9,
            reasoning="Test",
            timestamp=datetime.utcnow().isoformat(),
        )

        # Convert to dict
        output_dict = output.model_dump()

        # Serialize to JSON
        json_str = json.dumps(output_dict)

        # Deserialize
        deserialized = json.loads(json_str)

        assert deserialized["confidence"] == 0.9
        assert deserialized["explanation"] == "Test"

    def test_state_serialization(self):
        """Test FamilySchedulerState serializes to JSON correctly."""
        import json

        state = initialize_state("Test input", "user_123")

        # Convert TypedDict to dict
        state_dict = dict(state)

        # Serialize to JSON
        json_str = json.dumps(state_dict)

        # Deserialize
        deserialized = json.loads(json_str)

        assert deserialized["user_input"] == "Test input"
        assert deserialized["user_id"] == "user_123"
        assert deserialized["current_step"] == "start"
