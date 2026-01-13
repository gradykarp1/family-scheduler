"""
Service layer for the Family Scheduler.

Provides business logic and data access patterns for:
- Recurrence expansion (RRULE handling)
- Event and calendar queries
- Resource availability checking
"""

from src.services.recurrence import (
    RecurrenceInstance,
    parse_rrule,
    expand_recurrence,
    format_recurrence_id,
    parse_recurrence_id,
    get_next_occurrence,
    validate_rrule,
    count_instances_in_range,
)

from src.services.queries import (
    get_events_in_range,
    get_events_for_member,
    get_event_by_id,
    find_overlapping_events,
    get_upcoming_events,
    get_member_schedule,
    find_busy_members,
    find_available_members,
    get_unresolved_conflicts,
    get_calendars_by_owner,
    get_calendar_by_id,
)

from src.services.resources import (
    AvailabilitySlot,
    ResourceAvailability,
    check_resource_availability,
    check_multiple_resources,
    find_available_resources,
    get_resource_schedule,
    find_available_slots,
    get_resource_utilization,
    get_resources_by_type,
)

from src.services.calendar_service import (
    CalendarService,
    get_calendar_service,
    reset_calendar_service,
)

__all__ = [
    # Recurrence
    "RecurrenceInstance",
    "parse_rrule",
    "expand_recurrence",
    "format_recurrence_id",
    "parse_recurrence_id",
    "get_next_occurrence",
    "validate_rrule",
    "count_instances_in_range",
    # Queries
    "get_events_in_range",
    "get_events_for_member",
    "get_event_by_id",
    "find_overlapping_events",
    "get_upcoming_events",
    "get_member_schedule",
    "find_busy_members",
    "find_available_members",
    "get_unresolved_conflicts",
    "get_calendars_by_owner",
    "get_calendar_by_id",
    # Resources
    "AvailabilitySlot",
    "ResourceAvailability",
    "check_resource_availability",
    "check_multiple_resources",
    "find_available_resources",
    "get_resource_schedule",
    "find_available_slots",
    "get_resource_utilization",
    "get_resources_by_type",
    # Calendar Service
    "CalendarService",
    "get_calendar_service",
    "reset_calendar_service",
]
