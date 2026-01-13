"""
Recurrence expansion service.

Implements hybrid recurrence model (ADR-007):
- Stores RRULE on master events
- Expands instances on-demand for query windows
- Handles exceptions and modifications

Uses python-dateutil for RRULE parsing and expansion.
"""

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from dateutil.rrule import rrulestr, rrule
from dateutil.parser import parse as parse_datetime


@dataclass
class RecurrenceInstance:
    """Represents a single occurrence of a recurring event."""

    instance_start: datetime
    instance_end: datetime
    recurrence_id: str
    is_exception: bool = False


def parse_rrule(rrule_string: str, dtstart: datetime) -> Optional[rrule]:
    """
    Parse an RRULE string into a dateutil rrule object.

    Args:
        rrule_string: iCalendar RRULE string (e.g., 'FREQ=WEEKLY;BYDAY=MO,WE,FR')
        dtstart: Start datetime for the recurrence

    Returns:
        rrule object or None if parsing fails
    """
    if not rrule_string:
        return None

    try:
        # rrulestr can parse the RRULE format
        # Add DTSTART if not present in the string
        full_rule = rrule_string
        if "DTSTART" not in rrule_string.upper():
            # Format dtstart as iCalendar datetime
            dtstart_str = dtstart.strftime("%Y%m%dT%H%M%S")
            if dtstart.tzinfo:
                dtstart_str += "Z"
            full_rule = f"DTSTART:{dtstart_str}\n{rrule_string}"

        return rrulestr(full_rule)
    except (ValueError, TypeError):
        return None


def expand_recurrence(
    rrule_string: str,
    dtstart: datetime,
    duration: timedelta,
    window_start: datetime,
    window_end: datetime,
    max_instances: int = 100,
) -> list[RecurrenceInstance]:
    """
    Expand a recurring event into instances within a time window.

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Original event start time
        duration: Event duration (end_time - start_time)
        window_start: Start of query window
        window_end: End of query window
        max_instances: Maximum instances to generate (safety limit)

    Returns:
        List of RecurrenceInstance objects within the window
    """
    if not rrule_string:
        return []

    rule = parse_rrule(rrule_string, dtstart)
    if not rule:
        return []

    instances = []

    # Get occurrences within the window
    # Use between() for efficiency - only generates instances in range
    try:
        occurrences = list(rule.between(window_start, window_end, inc=True))
    except (ValueError, OverflowError):
        # Handle edge cases like invalid date ranges
        return []

    # Limit instances for safety
    for occurrence in occurrences[:max_instances]:
        instance_end = occurrence + duration
        recurrence_id = format_recurrence_id(occurrence)

        instances.append(
            RecurrenceInstance(
                instance_start=occurrence,
                instance_end=instance_end,
                recurrence_id=recurrence_id,
                is_exception=False,
            )
        )

    return instances


def format_recurrence_id(dt: datetime) -> str:
    """
    Format a datetime as a recurrence ID (iCalendar RECURRENCE-ID format).

    Args:
        dt: Datetime to format

    Returns:
        String in YYYYMMDDTHHMMSS format
    """
    return dt.strftime("%Y%m%dT%H%M%S")


def parse_recurrence_id(recurrence_id: str) -> Optional[datetime]:
    """
    Parse a recurrence ID back to a datetime.

    Args:
        recurrence_id: String in YYYYMMDDTHHMMSS format

    Returns:
        Datetime or None if parsing fails
    """
    try:
        return parse_datetime(recurrence_id)
    except (ValueError, TypeError):
        return None


def get_next_occurrence(
    rrule_string: str,
    dtstart: datetime,
    after: Optional[datetime] = None,
) -> Optional[datetime]:
    """
    Get the next occurrence of a recurring event.

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Original event start time
        after: Find occurrence after this time (default: now)

    Returns:
        Next occurrence datetime or None
    """
    if not rrule_string:
        return None

    rule = parse_rrule(rrule_string, dtstart)
    if not rule:
        return None

    if after is None:
        after = datetime.utcnow()

    try:
        return rule.after(after, inc=False)
    except (ValueError, OverflowError):
        return None


def validate_rrule(rrule_string: str) -> tuple[bool, Optional[str]]:
    """
    Validate an RRULE string.

    Args:
        rrule_string: iCalendar RRULE string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not rrule_string:
        return False, "RRULE string is empty"

    if not rrule_string.strip():
        return False, "RRULE string is blank"

    # Check for required FREQ component
    if "FREQ=" not in rrule_string.upper():
        return False, "RRULE must contain FREQ component"

    # Try to parse it
    try:
        # Use a dummy start date for validation
        dummy_start = datetime(2020, 1, 1, 12, 0, 0)
        rule = parse_rrule(rrule_string, dummy_start)
        if rule is None:
            return False, "Failed to parse RRULE"

        # Try to generate at least one occurrence
        next_occ = rule.after(dummy_start, inc=True)
        if next_occ is None:
            return False, "RRULE generates no occurrences"

        return True, None
    except Exception as e:
        return False, f"Invalid RRULE: {str(e)}"


def count_instances_in_range(
    rrule_string: str,
    dtstart: datetime,
    window_start: datetime,
    window_end: datetime,
    max_count: int = 1000,
) -> int:
    """
    Count recurrence instances within a time window without fully expanding.

    Useful for checking if expansion would be expensive.

    Args:
        rrule_string: iCalendar RRULE string
        dtstart: Original event start time
        window_start: Start of query window
        window_end: End of query window
        max_count: Stop counting after this many

    Returns:
        Number of instances (capped at max_count)
    """
    if not rrule_string:
        return 0

    rule = parse_rrule(rrule_string, dtstart)
    if not rule:
        return 0

    try:
        count = 0
        for _ in rule.between(window_start, window_end, inc=True):
            count += 1
            if count >= max_count:
                break
        return count
    except (ValueError, OverflowError):
        return 0
