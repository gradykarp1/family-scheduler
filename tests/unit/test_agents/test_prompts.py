"""Unit tests for prompt templates."""

import pytest

from src.agents.prompts.nl_parser_prompts import (
    NL_PARSER_SYSTEM_PROMPT,
    NL_PARSER_FEW_SHOT_EXAMPLES,
    build_nl_parser_prompt,
)
from src.agents.prompts.resolution_prompts import (
    RESOLUTION_SYSTEM_PROMPT,
    RESOLUTION_FEW_SHOT_EXAMPLES,
    build_resolution_prompt,
)


class TestNLParserPrompts:
    """Test NL Parser prompt construction."""

    def test_build_prompt_includes_few_shot_examples(self):
        """Verify few-shot examples are included in prompt."""
        prompt = build_nl_parser_prompt(
            user_input="Schedule a meeting",
            today="2026-01-13",
            family_members=["Alice", "Bob"],
            resources=["car", "van"],
        )

        assert "Example 1:" in prompt
        assert "Soccer practice" in prompt  # From first example

    def test_build_prompt_includes_user_input(self):
        """Verify user input is included in prompt."""
        prompt = build_nl_parser_prompt(
            user_input="Schedule soccer for Emma Saturday at 2pm",
            today="2026-01-13",
        )

        assert "Schedule soccer for Emma Saturday at 2pm" in prompt

    def test_build_prompt_includes_today_date(self):
        """Verify today's date is included for relative time parsing."""
        prompt = build_nl_parser_prompt(
            user_input="Book something tomorrow",
            today="2026-01-15",
        )

        assert "2026-01-15" in prompt

    def test_build_prompt_includes_family_members(self):
        """Verify family members are included in context."""
        prompt = build_nl_parser_prompt(
            user_input="Book the car",
            today="2026-01-13",
            family_members=["Emma", "Jake", "Sophie"],
            resources=["car", "van"],
        )

        assert "Emma" in prompt
        assert "Jake" in prompt
        assert "Sophie" in prompt

    def test_build_prompt_includes_resources(self):
        """Verify resources are included in context."""
        prompt = build_nl_parser_prompt(
            user_input="Book the car",
            today="2026-01-13",
            family_members=[],
            resources=["car", "van", "kitchen"],
        )

        assert "car" in prompt
        assert "van" in prompt

    def test_build_prompt_handles_empty_context(self):
        """Verify prompt works with no family context."""
        prompt = build_nl_parser_prompt(
            user_input="Schedule something",
            today="2026-01-13",
            family_members=[],
            resources=[],
        )

        # Should still build a valid prompt
        assert "Schedule something" in prompt
        assert "Example 1:" in prompt

    def test_build_prompt_includes_conversation_context(self):
        """Verify conversation context is included when provided."""
        conversation = [
            {"role": "user", "content": "I want to schedule something"},
            {"role": "assistant", "content": "What would you like to schedule?"},
        ]
        prompt = build_nl_parser_prompt(
            user_input="A meeting with Bob",
            today="2026-01-13",
            conversation_context=conversation,
        )

        assert "Recent conversation context" in prompt
        assert "schedule something" in prompt

    def test_few_shot_examples_cover_all_event_types(self):
        """Verify examples cover create, modify, cancel, query."""
        event_types = {ex["output"]["event_type"] for ex in NL_PARSER_FEW_SHOT_EXAMPLES}

        assert "create" in event_types
        assert "modify" in event_types
        assert "cancel" in event_types
        assert "query" in event_types

    def test_few_shot_examples_have_required_fields(self):
        """Verify all examples have proper structure."""
        for i, example in enumerate(NL_PARSER_FEW_SHOT_EXAMPLES):
            assert "input" in example, f"Example {i} missing 'input'"
            assert "output" in example, f"Example {i} missing 'output'"
            assert "event_type" in example["output"], f"Example {i} missing 'event_type'"

    def test_system_prompt_has_guidelines(self):
        """Verify system prompt contains key guidelines."""
        assert "Event Type Detection" in NL_PARSER_SYSTEM_PROMPT
        assert "Time Parsing" in NL_PARSER_SYSTEM_PROMPT
        assert "Participant Inference" in NL_PARSER_SYSTEM_PROMPT


class TestResolutionPrompts:
    """Test Resolution prompt construction."""

    def test_build_prompt_includes_conflict_details(self):
        """Verify conflict details are included."""
        conflicts = [
            {
                "type": "time_overlap",
                "description": "Events overlap by 30 minutes",
                "conflicting_event": {
                    "title": "Team Meeting",
                    "start_time": "2026-01-15T14:00:00",
                    "end_time": "2026-01-15T15:00:00",
                },
            }
        ]

        prompt = build_resolution_prompt(
            conflicts=conflicts,
            event_request={"title": "New Event"},
        )

        assert "time_overlap" in prompt
        assert "Team Meeting" in prompt

    def test_build_prompt_includes_event_request(self):
        """Verify event request details are included."""
        prompt = build_resolution_prompt(
            conflicts=[{"type": "conflict", "description": "test"}],
            event_request={
                "title": "Soccer Practice",
                "start_time": "2026-01-15T14:00:00",
                "participants": ["Emma", "Jake"],
                "priority": "high",
            },
        )

        assert "Soccer Practice" in prompt
        assert "Emma" in prompt
        assert "high" in prompt

    def test_build_prompt_includes_strategies(self):
        """Verify resolution strategies are listed."""
        prompt = build_resolution_prompt(
            conflicts=[{"type": "conflict", "description": "test"}],
            event_request={"title": "Test"},
        )

        assert "move_event" in prompt
        assert "shorten_event" in prompt
        assert "alternative_resource" in prompt
        assert "swap_participants" in prompt

    def test_build_prompt_includes_examples(self):
        """Verify few-shot examples are included."""
        prompt = build_resolution_prompt(
            conflicts=[{"type": "conflict", "description": "test"}],
            event_request={"title": "Test"},
        )

        assert "EXAMPLES" in prompt
        assert "score:" in prompt

    def test_build_prompt_handles_multiple_conflicts(self):
        """Verify multiple conflicts are all included."""
        conflicts = [
            {"type": "time_overlap", "description": "Conflict 1"},
            {"type": "resource_conflict", "description": "Conflict 2"},
            {"type": "participant_conflict", "description": "Conflict 3"},
        ]

        prompt = build_resolution_prompt(
            conflicts=conflicts,
            event_request={"title": "Test"},
        )

        assert "Conflict 1" in prompt
        assert "Conflict 2" in prompt
        assert "Conflict 3" in prompt

    def test_build_prompt_includes_existing_events(self):
        """Verify existing events are included when provided."""
        existing_events = [
            {"title": "Existing Event 1", "start_time": "2026-01-15T10:00:00"},
            {"title": "Existing Event 2", "start_time": "2026-01-15T14:00:00"},
        ]

        prompt = build_resolution_prompt(
            conflicts=[{"type": "conflict", "description": "test"}],
            event_request={"title": "Test"},
            existing_events=existing_events,
        )

        assert "Existing Event 1" in prompt
        assert "Existing Event 2" in prompt

    def test_system_prompt_has_strategies(self):
        """Verify system prompt contains all strategies."""
        assert "move_event" in RESOLUTION_SYSTEM_PROMPT
        assert "shorten_event" in RESOLUTION_SYSTEM_PROMPT
        assert "split_event" in RESOLUTION_SYSTEM_PROMPT
        assert "cancel_event" in RESOLUTION_SYSTEM_PROMPT
        assert "override_constraint" in RESOLUTION_SYSTEM_PROMPT
        assert "alternative_resource" in RESOLUTION_SYSTEM_PROMPT
        assert "swap_participants" in RESOLUTION_SYSTEM_PROMPT
        assert "suggest_virtual" in RESOLUTION_SYSTEM_PROMPT

    def test_few_shot_examples_have_valid_structure(self):
        """Verify all resolution examples have proper structure."""
        for i, example in enumerate(RESOLUTION_FEW_SHOT_EXAMPLES):
            assert "conflict" in example, f"Example {i} missing 'conflict'"
            assert "resolutions" in example, f"Example {i} missing 'resolutions'"
            assert len(example["resolutions"]) >= 1, f"Example {i} has no resolutions"

            for j, res in enumerate(example["resolutions"]):
                assert "resolution_id" in res, f"Example {i} resolution {j} missing 'resolution_id'"
                assert "strategy" in res, f"Example {i} resolution {j} missing 'strategy'"
                assert "score" in res, f"Example {i} resolution {j} missing 'score'"
                assert "description" in res, f"Example {i} resolution {j} missing 'description'"
