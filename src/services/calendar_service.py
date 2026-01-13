"""
Calendar service - synchronous wrapper for calendar operations.

Provides a unified interface for calendar operations in orchestrator nodes,
abstracting away the async nature of GoogleCalendarRepository and supporting
both Google Calendar and local database backends.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional, Sequence

from src.config import get_settings
from src.integrations.base import (
    CalendarEvent,
    CreateEventRequest,
    FreeBusySlot,
)

logger = logging.getLogger(__name__)

# Singleton instance
_calendar_service: Optional["CalendarService"] = None


class CalendarService:
    """
    Synchronous calendar service for use in orchestrator nodes.

    Wraps the async GoogleCalendarRepository with sync methods using asyncio.run().
    Falls back to local database when CALENDAR_PROVIDER=local.
    """

    def __init__(self):
        """Initialize calendar service based on configuration."""
        self._settings = get_settings()
        self._repository = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of repository."""
        if self._initialized:
            return

        if self._settings.uses_google_calendar:
            self._init_google_calendar()
        else:
            logger.info("Using local calendar provider (database)")
            # Local provider doesn't need special initialization
            # Operations will use database queries directly

        self._initialized = True

    def _init_google_calendar(self):
        """Initialize Google Calendar repository."""
        from src.integrations.google_calendar import (
            GoogleAuthManager,
            GoogleCalendarRepository,
        )

        try:
            # Validate configuration
            self._settings.validate_google_calendar_config()

            # Create auth manager
            if self._settings.google_service_account_json:
                import json
                service_account_info = json.loads(
                    self._settings.google_service_account_json
                )
                auth_manager = GoogleAuthManager(
                    service_account_info=service_account_info
                )
            else:
                auth_manager = GoogleAuthManager(
                    service_account_file=self._settings.google_service_account_file
                )

            # Create repository
            self._repository = GoogleCalendarRepository(auth_manager)
            logger.info(
                f"Google Calendar initialized for calendar: "
                f"{self._settings.google_calendar_id}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            raise

    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.run(coro)

    @property
    def calendar_id(self) -> str:
        """Get the configured calendar ID."""
        return self._settings.google_calendar_id

    @property
    def is_google_calendar(self) -> bool:
        """Check if using Google Calendar backend."""
        return self._settings.uses_google_calendar

    def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        calendar_id: Optional[str] = None,
        include_recurring: bool = True,
    ) -> Sequence[CalendarEvent]:
        """
        Get events within a time range.

        Args:
            start: Range start (inclusive)
            end: Range end (exclusive)
            calendar_id: Calendar to query (uses default if None)
            include_recurring: Whether to expand recurring events

        Returns:
            Sequence of events in the range
        """
        self._ensure_initialized()
        cal_id = calendar_id or self.calendar_id

        if self._repository:
            return self._run_async(
                self._repository.get_events_in_range(
                    calendar_id=cal_id,
                    start=start,
                    end=end,
                    include_recurring=include_recurring,
                )
            )
        else:
            # Local provider - use database queries
            return self._get_events_from_database(start, end)

    def _get_events_from_database(
        self,
        start: datetime,
        end: datetime,
    ) -> Sequence[CalendarEvent]:
        """Get events from local database."""
        from src.database import get_db_context
        from src.models import Event
        from sqlalchemy.orm import joinedload

        with get_db_context() as db:
            # Query events directly, filtering by time range
            query = (
                db.query(Event)
                .filter(
                    Event.start_time < end,
                    Event.end_time > start,
                    Event.status != "cancelled",
                )
                .options(joinedload(Event.participants))
                .order_by(Event.start_time)
            )

            db_events = query.all()

            # Convert to CalendarEvent format
            events = []
            for event in db_events:
                attendees = []
                for p in event.participants:
                    if p.member and hasattr(p.member, 'email') and p.member.email:
                        attendees.append(p.member.email)

                cal_event = CalendarEvent(
                    id=str(event.id),
                    calendar_id=str(event.calendar_id),
                    title=event.title,
                    description=event.description,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    all_day=event.all_day,
                    location=event.location,
                    attendees=attendees,
                    recurrence_rule=event.recurrence_rule,
                    status=event.status,
                    metadata={
                        "priority": event.priority,
                        "flexibility": event.flexibility,
                    },
                )
                events.append(cal_event)

            return events

    def get_event_by_id(
        self,
        event_id: str,
        calendar_id: Optional[str] = None,
    ) -> Optional[CalendarEvent]:
        """
        Get a single event by ID.

        Args:
            event_id: Event ID
            calendar_id: Calendar containing the event

        Returns:
            Event or None if not found
        """
        self._ensure_initialized()
        cal_id = calendar_id or self.calendar_id

        if self._repository:
            return self._run_async(
                self._repository.get_event_by_id(
                    calendar_id=cal_id,
                    event_id=event_id,
                )
            )
        else:
            # Local provider
            from src.database import get_db_context
            from src.services.queries import get_event_by_id as db_get_event

            with get_db_context() as db:
                event = db_get_event(db, event_id)
                if not event:
                    return None

                return CalendarEvent(
                    id=str(event.id),
                    calendar_id=str(event.calendar_id),
                    title=event.title,
                    description=event.description,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    all_day=event.all_day,
                    location=event.location,
                    attendees=[p.member.email for p in event.participants if p.member],
                    recurrence_rule=event.recurrence_rule,
                    status=event.status,
                )

    def create_event(
        self,
        event: CreateEventRequest,
        calendar_id: Optional[str] = None,
    ) -> CalendarEvent:
        """
        Create a new event.

        Args:
            event: Event data
            calendar_id: Calendar to create event in

        Returns:
            Created event with assigned ID
        """
        self._ensure_initialized()
        cal_id = calendar_id or self.calendar_id

        if self._repository:
            created = self._run_async(
                self._repository.create_event(
                    calendar_id=cal_id,
                    event=event,
                )
            )
            logger.info(f"Created event '{event.title}' in Google Calendar")
            return created
        else:
            # Local provider - create in database
            return self._create_event_in_database(event, cal_id)

    def _create_event_in_database(
        self,
        event: CreateEventRequest,
        calendar_id: str,
    ) -> CalendarEvent:
        """Create event in local database."""
        from src.database import get_db_context
        from src.models import Event, Calendar
        import uuid as uuid_module

        with get_db_context() as db:
            # Get or create a default calendar if none specified
            if calendar_id:
                try:
                    cal_uuid = uuid_module.UUID(calendar_id)
                except ValueError:
                    cal_uuid = None
            else:
                cal_uuid = None

            if not cal_uuid:
                # Find or create a default calendar
                default_calendar = db.query(Calendar).filter(
                    Calendar.calendar_type == "family"
                ).first()

                if not default_calendar:
                    default_calendar = db.query(Calendar).first()

                if default_calendar:
                    cal_uuid = default_calendar.id
                else:
                    # Create a default calendar
                    default_calendar = Calendar(
                        id=uuid_module.uuid4(),
                        name="Family Calendar",
                        calendar_type="family",
                        visibility="family",
                    )
                    db.add(default_calendar)
                    db.flush()
                    cal_uuid = default_calendar.id

            # Get or create a default creator if not specified
            creator_id = None
            if event.created_by:
                try:
                    creator_id = uuid_module.UUID(event.created_by)
                except ValueError:
                    pass

            if not creator_id:
                # Find any family member to use as creator
                from src.models import FamilyMember
                default_member = db.query(FamilyMember).first()
                if default_member:
                    creator_id = default_member.id
                else:
                    # Create a default family member
                    default_member = FamilyMember(
                        id=uuid_module.uuid4(),
                        name="System",
                        email="system@family.local",
                        role="parent",
                    )
                    db.add(default_member)
                    db.flush()
                    creator_id = default_member.id

            db_event = Event(
                id=uuid_module.uuid4(),
                calendar_id=cal_uuid,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                all_day=event.all_day,
                location=event.location,
                recurrence_rule=event.recurrence_rule,
                priority=event.priority,
                flexibility=event.flexibility,
                status="confirmed",
                created_by=creator_id,
            )
            db.add(db_event)
            db.commit()
            db.refresh(db_event)

            logger.info(f"Created event '{event.title}' in local database")

            return CalendarEvent(
                id=str(db_event.id),
                calendar_id=str(db_event.calendar_id),
                title=db_event.title,
                description=db_event.description,
                start_time=db_event.start_time,
                end_time=db_event.end_time,
                all_day=db_event.all_day,
                location=db_event.location,
                attendees=event.attendees,
                recurrence_rule=db_event.recurrence_rule,
                status=db_event.status,
            )

    def update_event(
        self,
        event_id: str,
        updates: dict,
        calendar_id: Optional[str] = None,
    ) -> CalendarEvent:
        """
        Update an existing event.

        Args:
            event_id: Event to update
            updates: Fields to update
            calendar_id: Calendar containing the event

        Returns:
            Updated event
        """
        self._ensure_initialized()
        cal_id = calendar_id or self.calendar_id

        if self._repository:
            return self._run_async(
                self._repository.update_event(
                    calendar_id=cal_id,
                    event_id=event_id,
                    updates=updates,
                )
            )
        else:
            # Local provider
            from src.database import get_db_context
            from src.models import Event

            with get_db_context() as db:
                event = db.query(Event).filter(Event.id == event_id).first()
                if not event:
                    raise ValueError(f"Event {event_id} not found")

                for key, value in updates.items():
                    if hasattr(event, key):
                        setattr(event, key, value)

                db.commit()
                db.refresh(event)

                return CalendarEvent(
                    id=str(event.id),
                    calendar_id=str(event.calendar_id),
                    title=event.title,
                    description=event.description,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    all_day=event.all_day,
                    location=event.location,
                    recurrence_rule=event.recurrence_rule,
                    status=event.status,
                )

    def delete_event(
        self,
        event_id: str,
        calendar_id: Optional[str] = None,
    ) -> bool:
        """
        Delete an event.

        Args:
            event_id: Event to delete
            calendar_id: Calendar containing the event

        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()
        cal_id = calendar_id or self.calendar_id

        if self._repository:
            return self._run_async(
                self._repository.delete_event(
                    calendar_id=cal_id,
                    event_id=event_id,
                )
            )
        else:
            # Local provider
            from src.database import get_db_context
            from src.models import Event

            with get_db_context() as db:
                event = db.query(Event).filter(Event.id == event_id).first()
                if not event:
                    return False

                db.delete(event)
                db.commit()
                return True

    def find_free_busy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, list[FreeBusySlot]]:
        """
        Query free/busy information for calendars.

        Args:
            calendar_ids: Calendars to query
            start: Range start
            end: Range end

        Returns:
            Dict mapping calendar_id to list of busy slots
        """
        self._ensure_initialized()

        if self._repository:
            return self._run_async(
                self._repository.find_free_busy(
                    calendar_ids=calendar_ids,
                    start=start,
                    end=end,
                )
            )
        else:
            # Local provider - derive from events
            result = {}
            for cal_id in calendar_ids:
                events = self.get_events_in_range(start, end, calendar_id=cal_id)
                busy_slots = [
                    FreeBusySlot(start=e.start_time, end=e.end_time)
                    for e in events
                    if e.status != "cancelled"
                ]
                result[cal_id] = busy_slots
            return result

    def find_available_slots(
        self,
        start: datetime,
        end: datetime,
        duration_minutes: int,
        calendar_ids: Optional[list[str]] = None,
        working_hours_start: int = 8,
        working_hours_end: int = 20,
    ) -> list[dict]:
        """
        Find available time slots within a range.

        Args:
            start: Search range start
            end: Search range end
            duration_minutes: Required slot duration
            calendar_ids: Calendars to check (uses default if None)
            working_hours_start: Start of working hours (hour, 0-23)
            working_hours_end: End of working hours (hour, 0-23)

        Returns:
            List of available slot dicts with start_time, end_time, score
        """
        self._ensure_initialized()
        cal_ids = calendar_ids or [self.calendar_id]

        # Get all busy periods
        busy_slots = self.find_free_busy(cal_ids, start, end)

        # Merge all busy slots
        all_busy = []
        for slots in busy_slots.values():
            all_busy.extend(slots)

        # Sort by start time
        all_busy.sort(key=lambda s: s.start)

        # Find gaps
        available = []
        current = start
        duration = timedelta(minutes=duration_minutes)

        # Ensure current has timezone
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        for busy in all_busy:
            # Ensure busy slot times have timezone
            busy_start = busy.start
            busy_end = busy.end
            if busy_start.tzinfo is None:
                busy_start = busy_start.replace(tzinfo=timezone.utc)
            if busy_end.tzinfo is None:
                busy_end = busy_end.replace(tzinfo=timezone.utc)

            # Check if there's a gap before this busy period
            if busy_start > current:
                gap_start = current
                gap_end = busy_start

                # Check if gap is long enough and within working hours
                slots_in_gap = self._find_slots_in_range(
                    gap_start,
                    gap_end,
                    duration,
                    working_hours_start,
                    working_hours_end,
                )
                available.extend(slots_in_gap)

            # Move current pointer past busy period
            if busy_end > current:
                current = busy_end

        # Check remaining time after last busy period
        # Ensure end has timezone
        end_tz = end
        if end_tz.tzinfo is None:
            end_tz = end_tz.replace(tzinfo=timezone.utc)

        if current < end_tz:
            slots_in_gap = self._find_slots_in_range(
                current,
                end,
                duration,
                working_hours_start,
                working_hours_end,
            )
            available.extend(slots_in_gap)

        # Score slots (prefer earlier times, mid-day)
        for slot in available:
            slot["score"] = self._score_slot(slot["start_time"])

        # Sort by score (highest first)
        available.sort(key=lambda s: s["score"], reverse=True)

        return available[:10]  # Return top 10 candidates

    def _find_slots_in_range(
        self,
        start: datetime,
        end: datetime,
        duration: timedelta,
        working_hours_start: int,
        working_hours_end: int,
    ) -> list[dict]:
        """Find slots within a specific range respecting working hours."""
        slots = []
        current = start

        while current + duration <= end:
            # Check if within working hours
            if working_hours_start <= current.hour < working_hours_end:
                slot_end = current + duration
                if slot_end.hour <= working_hours_end:
                    slots.append({
                        "start_time": current.isoformat(),
                        "end_time": slot_end.isoformat(),
                        "available_participants": [],
                        "constraint_violations": [],
                    })

            # Move to next slot (30 min increments)
            current += timedelta(minutes=30)

        return slots

    def _score_slot(self, start_time_str: str) -> float:
        """Score a time slot (higher is better)."""
        from dateutil.parser import parse
        start = parse(start_time_str)

        score = 0.5

        # Prefer mid-day (10am-2pm)
        if 10 <= start.hour <= 14:
            score += 0.3
        elif 8 <= start.hour <= 10 or 14 <= start.hour <= 17:
            score += 0.2

        # Prefer weekdays
        if start.weekday() < 5:
            score += 0.1

        # Prefer earlier in the week
        score += (5 - start.weekday()) * 0.02

        return min(score, 1.0)


def get_calendar_service() -> CalendarService:
    """
    Get the calendar service singleton.

    Returns:
        CalendarService instance configured based on settings
    """
    global _calendar_service

    if _calendar_service is None:
        _calendar_service = CalendarService()
        logger.info("Calendar service initialized")

    return _calendar_service


def reset_calendar_service():
    """Reset the calendar service singleton (useful for testing)."""
    global _calendar_service
    _calendar_service = None
