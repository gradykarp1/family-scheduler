"""
Service layer for the Family Scheduler.

Provides business logic and data access patterns for:
- Recurrence expansion (RRULE handling)
- Family configuration queries (members, calendars, resources, constraints)
- Resource availability checking

Note: Events are stored in Google Calendar. Use CalendarService for event operations.
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
    # Family member queries
    get_all_family_members,
    get_family_member_by_id,
    get_family_member_by_email,
    get_family_members_by_role,
    # Calendar queries
    get_all_calendars,
    get_calendars_by_owner,
    get_calendar_by_id,
    get_calendar_by_google_id,
    get_calendars_by_type,
    # Resource queries
    get_all_resources,
    get_resource_by_id,
    get_resources_by_type,
    # Constraint queries
    get_all_constraints,
    get_constraints_for_member,
    get_constraints_by_type,
)

from src.services.resources import (
    AvailabilitySlot,
    ResourceAvailability,
    get_resource_by_id as get_resource,
    get_all_resources as get_active_resources,
    get_resources_by_type as get_resources_filtered_by_type,
    find_resources_with_calendar,
    check_resource_availability,
    check_multiple_resources,
    find_available_resources,
    find_available_slots,
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
    # Family member queries
    "get_all_family_members",
    "get_family_member_by_id",
    "get_family_member_by_email",
    "get_family_members_by_role",
    # Calendar queries
    "get_all_calendars",
    "get_calendars_by_owner",
    "get_calendar_by_id",
    "get_calendar_by_google_id",
    "get_calendars_by_type",
    # Resource queries
    "get_all_resources",
    "get_resource_by_id",
    "get_resources_by_type",
    # Constraint queries
    "get_all_constraints",
    "get_constraints_for_member",
    "get_constraints_by_type",
    # Resource availability
    "AvailabilitySlot",
    "ResourceAvailability",
    "get_resource",
    "get_active_resources",
    "get_resources_filtered_by_type",
    "find_resources_with_calendar",
    "check_resource_availability",
    "check_multiple_resources",
    "find_available_resources",
    "find_available_slots",
    # Calendar Service (Google Calendar)
    "CalendarService",
    "get_calendar_service",
    "reset_calendar_service",
]
