"""
Bidirectional mapping between internal Event format and Google Calendar API format.

Handles:
- DateTime formatting (RFC 3339 for Google API)
- All-day event handling
- Recurrence rule mapping
- Extended properties for custom fields
- Attendee mapping
"""

from datetime import datetime, timezone
from typing import Optional

from dateutil.parser import parse as parse_datetime

from src.integrations.base import CalendarEvent, CreateEventRequest, FreeBusySlot


# Status mapping between internal and Google Calendar formats
STATUS_TO_GOOGLE = {
    "proposed": "tentative",
    "confirmed": "confirmed",
    "cancelled": "cancelled",
}

STATUS_FROM_GOOGLE = {
    "tentative": "proposed",
    "confirmed": "confirmed",
    "cancelled": "cancelled",
}


class GoogleCalendarAdapter:
    """Maps between internal Event format and Google Calendar API format."""

    @staticmethod
    def to_google_event(event: CreateEventRequest, internal_id: Optional[str] = None) -> dict:
        """
        Convert internal event request to Google Calendar API format.

        Args:
            event: Internal event request
            internal_id: Optional internal ID to store in extended properties

        Returns:
            Dict suitable for Google Calendar API insert/update
        """
        google_event: dict = {
            "summary": event.title,
        }

        # Optional fields
        if event.description:
            google_event["description"] = event.description

        if event.location:
            google_event["location"] = event.location

        # Date/time handling
        if event.all_day:
            # All-day events use date instead of dateTime
            google_event["start"] = {
                "date": event.start_time.strftime("%Y-%m-%d"),
            }
            google_event["end"] = {
                "date": event.end_time.strftime("%Y-%m-%d"),
            }
        else:
            # Timed events use dateTime with timezone
            google_event["start"] = {
                "dateTime": _format_datetime(event.start_time),
                "timeZone": "UTC",
            }
            google_event["end"] = {
                "dateTime": _format_datetime(event.end_time),
                "timeZone": "UTC",
            }

        # Attendees
        if event.attendees:
            google_event["attendees"] = [
                {"email": email} for email in event.attendees
            ]

        # Recurrence
        if event.recurrence_rule:
            # Google Calendar expects RRULE: prefix
            rrule = event.recurrence_rule
            if not rrule.startswith("RRULE:"):
                rrule = f"RRULE:{rrule}"
            google_event["recurrence"] = [rrule]

        # Extended properties for custom fields
        private_props = {}

        if internal_id:
            private_props["family_scheduler_id"] = internal_id

        if event.priority:
            private_props["priority"] = event.priority

        if event.flexibility:
            private_props["flexibility"] = event.flexibility

        if event.created_by:
            private_props["created_by"] = str(event.created_by)

        # Store any extra metadata
        for key, value in event.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                private_props[key] = str(value)

        if private_props:
            google_event["extendedProperties"] = {
                "private": private_props,
            }

        return google_event

    @staticmethod
    def from_google_event(google_event: dict, calendar_id: str) -> CalendarEvent:
        """
        Convert Google Calendar event to internal format.

        Args:
            google_event: Event from Google Calendar API
            calendar_id: Calendar ID the event belongs to

        Returns:
            CalendarEvent in internal format
        """
        # Parse start/end times
        start_data = google_event.get("start", {})
        end_data = google_event.get("end", {})

        if "dateTime" in start_data:
            start_time = _parse_datetime(start_data["dateTime"])
            end_time = _parse_datetime(end_data["dateTime"])
            all_day = False
        elif "date" in start_data:
            # All-day event
            start_time = _parse_date(start_data["date"])
            end_time = _parse_date(end_data["date"])
            all_day = True
        else:
            # Fallback
            start_time = datetime.now(timezone.utc)
            end_time = datetime.now(timezone.utc)
            all_day = False

        # Parse attendees
        attendees = []
        for attendee in google_event.get("attendees", []):
            email = attendee.get("email")
            if email:
                attendees.append(email)

        # Parse recurrence
        recurrence_rule = None
        recurrence_list = google_event.get("recurrence", [])
        for rule in recurrence_list:
            if rule.startswith("RRULE:"):
                recurrence_rule = rule[6:]  # Strip "RRULE:" prefix
                break

        # Parse status
        google_status = google_event.get("status", "confirmed")
        status = STATUS_FROM_GOOGLE.get(google_status, "confirmed")

        # Extract extended properties
        ext_props = google_event.get("extendedProperties", {})
        private_props = ext_props.get("private", {})

        metadata = {
            "google_id": google_event.get("id"),
            "etag": google_event.get("etag"),
            "html_link": google_event.get("htmlLink"),
            **private_props,
        }

        return CalendarEvent(
            id=google_event.get("id", ""),
            calendar_id=calendar_id,
            title=google_event.get("summary", "Untitled"),
            description=google_event.get("description"),
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            location=google_event.get("location"),
            attendees=attendees,
            recurrence_rule=recurrence_rule,
            status=status,
            metadata=metadata,
        )

    @staticmethod
    def to_update_body(updates: dict) -> dict:
        """
        Convert update dict to Google Calendar API format.

        Args:
            updates: Dict of field updates

        Returns:
            Dict suitable for Google Calendar API patch
        """
        google_updates: dict = {}

        # Direct mappings
        if "title" in updates:
            google_updates["summary"] = updates["title"]

        if "description" in updates:
            google_updates["description"] = updates["description"]

        if "location" in updates:
            google_updates["location"] = updates["location"]

        # Status mapping
        if "status" in updates:
            google_updates["status"] = STATUS_TO_GOOGLE.get(
                updates["status"], updates["status"]
            )

        # Time updates
        if "start_time" in updates or "end_time" in updates or "all_day" in updates:
            all_day = updates.get("all_day", False)

            if "start_time" in updates:
                start = updates["start_time"]
                if all_day:
                    google_updates["start"] = {"date": start.strftime("%Y-%m-%d")}
                else:
                    google_updates["start"] = {
                        "dateTime": _format_datetime(start),
                        "timeZone": "UTC",
                    }

            if "end_time" in updates:
                end = updates["end_time"]
                if all_day:
                    google_updates["end"] = {"date": end.strftime("%Y-%m-%d")}
                else:
                    google_updates["end"] = {
                        "dateTime": _format_datetime(end),
                        "timeZone": "UTC",
                    }

        # Attendee updates
        if "attendees" in updates:
            google_updates["attendees"] = [
                {"email": email} for email in updates["attendees"]
            ]

        # Recurrence updates
        if "recurrence_rule" in updates:
            rule = updates["recurrence_rule"]
            if rule:
                if not rule.startswith("RRULE:"):
                    rule = f"RRULE:{rule}"
                google_updates["recurrence"] = [rule]
            else:
                google_updates["recurrence"] = []

        return google_updates

    @staticmethod
    def parse_freebusy_response(
        response: dict,
    ) -> dict[str, list[FreeBusySlot]]:
        """
        Parse Google Calendar freebusy response.

        Args:
            response: Response from freebusy.query API

        Returns:
            Dict mapping calendar_id to list of busy slots
        """
        result: dict[str, list[FreeBusySlot]] = {}

        calendars = response.get("calendars", {})
        for calendar_id, calendar_data in calendars.items():
            busy_slots = []
            for busy in calendar_data.get("busy", []):
                start = _parse_datetime(busy["start"])
                end = _parse_datetime(busy["end"])
                busy_slots.append(FreeBusySlot(start=start, end=end))
            result[calendar_id] = busy_slots

        return result


def _format_datetime(dt: datetime) -> str:
    """
    Format datetime to RFC 3339 format for Google API.

    Args:
        dt: Datetime to format

    Returns:
        RFC 3339 formatted string
    """
    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)

    return dt.isoformat()


def _parse_datetime(dt_str: str) -> datetime:
    """
    Parse datetime string from Google API.

    Args:
        dt_str: RFC 3339 datetime string

    Returns:
        Parsed datetime (UTC)
    """
    dt = parse_datetime(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_date(date_str: str) -> datetime:
    """
    Parse date string from Google API (for all-day events).

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Datetime at midnight UTC
    """
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
