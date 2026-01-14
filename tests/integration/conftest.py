"""
Integration test fixtures for Family Scheduler.

Provides mocked LLM, mock calendar service, and orchestrator setup
for testing complete workflows with real graph execution.
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from src.agents.state import (
    NLParserOutput,
    ResolutionOutput,
    ProposedResolutionOutput,
)
from src.integrations.base import CalendarEvent, CreateEventRequest, FreeBusySlot
from src.orchestrator import build_orchestrator_graph
from src.orchestrator.checkpointing import reset_checkpointer


# =============================================================================
# Pytest Markers Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


# =============================================================================
# Mock LLM Responses
# =============================================================================


class MockLLMResponses:
    """
    Predefined LLM responses for predictable integration testing.

    Each response simulates what the real LLM would return for specific inputs.
    """

    @staticmethod
    def create_event_high_confidence() -> NLParserOutput:
        """Response for clear event creation request."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        return NLParserOutput(
            event_type="create",
            title="Soccer Practice",
            start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0).isoformat(),
            end_time=tomorrow.replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
            participants=["Charlie"],
            resources=[],
            priority="medium",
            flexibility="fixed",
            recurrence_rule=None,
        )

    @staticmethod
    def create_event_low_confidence() -> NLParserOutput:
        """Response for ambiguous input requiring clarification."""
        return NLParserOutput(
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

    @staticmethod
    def query_intent() -> NLParserOutput:
        """Response for query request."""
        return NLParserOutput(
            event_type="query",
            title="schedule check",
            start_time=None,
            end_time=None,
            participants=[],
            resources=[],
            priority=None,
            flexibility=None,
            recurrence_rule=None,
        )

    @staticmethod
    def resolution_for_conflict() -> ResolutionOutput:
        """Resolution response for conflict scenario."""
        return ResolutionOutput(
            proposed_resolutions=[
                ProposedResolutionOutput(
                    resolution_id="res_move_later",
                    strategy="move_event",
                    score=0.9,
                    description="Move event to 4pm to avoid conflict",
                    changes=[],
                    conflicts_resolved=["conflict_1"],
                    side_effects=[],
                ),
                ProposedResolutionOutput(
                    resolution_id="res_shorten",
                    strategy="shorten_event",
                    score=0.7,
                    description="Shorten event to 1 hour",
                    changes=[],
                    conflicts_resolved=["conflict_1"],
                    side_effects=["Reduced activity time"],
                ),
            ],
            recommended_resolution="res_move_later",
            analysis_summary="Conflict with existing meeting can be resolved by rescheduling",
        )

    @staticmethod
    def query_response_text() -> str:
        """Query agent response text."""
        return "You have 2 events tomorrow: a Team Meeting at 10am and Doctor Appointment at 2pm."


@pytest.fixture
def mock_llm_responses():
    """Provide access to mock LLM response generators."""
    return MockLLMResponses()


# =============================================================================
# Mock LLM Fixture
# =============================================================================


@pytest.fixture
def mock_llm_factory(mock_llm_responses) -> Callable[[str], MagicMock]:
    """
    Factory that creates mock LLM instances for different scenarios.

    Usage:
        mock_llm = mock_llm_factory("create_high_confidence")

    Args:
        response_type: One of "create_high_confidence", "create_low_confidence", "query"

    Returns:
        Configured MagicMock LLM with with_structured_output() support
    """
    def create_mock_llm(response_type: str = "create_high_confidence") -> MagicMock:
        mock_llm_instance = MagicMock()

        def with_structured_output(schema):
            structured_mock = MagicMock()

            if schema == NLParserOutput:
                if response_type == "create_high_confidence":
                    structured_mock.invoke.return_value = mock_llm_responses.create_event_high_confidence()
                elif response_type == "create_low_confidence":
                    structured_mock.invoke.return_value = mock_llm_responses.create_event_low_confidence()
                elif response_type == "query":
                    structured_mock.invoke.return_value = mock_llm_responses.query_intent()
            elif schema == ResolutionOutput:
                structured_mock.invoke.return_value = mock_llm_responses.resolution_for_conflict()

            return structured_mock

        mock_llm_instance.with_structured_output = with_structured_output

        # For direct invoke (query node uses this)
        mock_response = MagicMock()
        mock_response.content = mock_llm_responses.query_response_text()
        mock_llm_instance.invoke.return_value = mock_response

        return mock_llm_instance

    return create_mock_llm


# =============================================================================
# Mock Calendar Service
# =============================================================================


class MockCalendarService:
    """
    Mock calendar service for predictable testing.

    Supports configurable scenarios:
    - Empty calendar (no conflicts)
    - Calendar with conflicting events
    """

    def __init__(self, events: list[CalendarEvent] | None = None):
        self.events = events or []
        self.created_events: list[CalendarEvent] = []

    def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str | None = None
    ) -> list[CalendarEvent]:
        """Return events that overlap with the given range."""
        result = []
        for event in self.events:
            if event.start_time < end and event.end_time > start:
                result.append(event)
        return result

    def create_event(self, event: CreateEventRequest, calendar_id: str | None = None) -> CalendarEvent:
        """Create an event and return it."""
        created = CalendarEvent(
            id=str(uuid.uuid4()),
            calendar_id=calendar_id or "default-calendar",
            title=event.title,
            description=event.description,
            start_time=event.start_time,
            end_time=event.end_time,
            all_day=event.all_day,
            location=event.location,
            attendees=event.attendees,
            recurrence_rule=event.recurrence_rule,
            status="confirmed",
        )
        self.created_events.append(created)
        return created

    def find_free_busy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime
    ) -> dict[str, list[FreeBusySlot]]:
        """Return busy slots from events."""
        busy_slots = [
            FreeBusySlot(start=e.start_time, end=e.end_time)
            for e in self.events
            if e.start_time < end and e.end_time > start
        ]
        return {cal_id: busy_slots for cal_id in calendar_ids}

    def find_available_slots(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int,
        calendar_id: str | None = None
    ) -> list[dict]:
        """Find available time slots."""
        slots = []
        current = start
        duration = timedelta(minutes=duration_minutes)

        while current + duration <= end:
            is_free = True
            for event in self.events:
                if current < event.end_time and (current + duration) > event.start_time:
                    is_free = False
                    break

            if is_free:
                slots.append({
                    "start_time": current.isoformat(),
                    "end_time": (current + duration).isoformat(),
                    "score": 0.8,
                    "available_participants": [],
                    "constraint_violations": [],
                })

            current += timedelta(minutes=30)

        return slots[:10]


@pytest.fixture
def mock_calendar_empty():
    """Calendar service with no existing events."""
    return MockCalendarService(events=[])


@pytest.fixture
def mock_calendar_with_conflict():
    """Calendar service with a conflicting event at 2pm tomorrow."""
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    conflicting_event = CalendarEvent(
        id="existing_event_1",
        calendar_id="default-calendar",
        title="Team Meeting",
        start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
        end_time=tomorrow.replace(hour=15, minute=0, second=0, microsecond=0),
        attendees=["Charlie"],
        status="confirmed",
    )
    return MockCalendarService(events=[conflicting_event])


@pytest.fixture
def mock_calendar_with_events():
    """Calendar service with multiple events for query testing."""
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    events = [
        CalendarEvent(
            id="event_1",
            calendar_id="default-calendar",
            title="Team Meeting",
            start_time=tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
            attendees=["Alice", "Bob"],
            status="confirmed",
        ),
        CalendarEvent(
            id="event_2",
            calendar_id="default-calendar",
            title="Doctor Appointment",
            start_time=tomorrow.replace(hour=14, minute=0, second=0, microsecond=0),
            end_time=tomorrow.replace(hour=15, minute=0, second=0, microsecond=0),
            attendees=["Charlie"],
            status="confirmed",
        ),
    ]
    return MockCalendarService(events=events)


# =============================================================================
# Orchestrator Fixtures
# =============================================================================


@pytest.fixture
def fresh_orchestrator():
    """
    Reset orchestrator state and return a fresh graph builder.

    Clears checkpointer and module-level graph singleton.
    """
    reset_checkpointer()

    # Reset module-level compiled graph
    import src.orchestrator
    src.orchestrator._compiled_graph = None

    return build_orchestrator_graph


# =============================================================================
# API Test Client Fixtures
# =============================================================================


@pytest.fixture
def integration_api_client(mock_llm_factory, mock_calendar_empty):
    """
    FastAPI test client with real orchestrator but mocked LLM and calendar.

    For testing HTTP request -> orchestrator -> response flow.
    """
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.dependencies import init_orchestrator
    import src.api.dependencies as deps

    with patch("src.orchestrator.nodes.get_llm") as patched_llm, \
         patch("src.services.calendar_service.get_calendar_service") as patched_calendar:

        patched_llm.return_value = mock_llm_factory("create_high_confidence")
        patched_calendar.return_value = mock_calendar_empty

        # Reset and build fresh orchestrator
        reset_checkpointer()
        import src.orchestrator
        src.orchestrator._compiled_graph = None

        # Initialize orchestrator dependency
        deps._orchestrator = None
        init_orchestrator()

        with TestClient(app) as client:
            yield {
                "client": client,
                "mock_llm": patched_llm,
                "mock_calendar": patched_calendar,
                "llm_factory": mock_llm_factory,
                "calendar_service": mock_calendar_empty,
            }
