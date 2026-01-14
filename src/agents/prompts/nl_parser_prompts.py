"""NL Parser prompts with few-shot examples."""

from typing import Optional

NL_PARSER_SYSTEM_PROMPT = """You are an expert natural language parser for a family scheduling application.

Your task: Extract structured event data from the user's input about scheduling events for their family.

IMPORTANT GUIDELINES:

1. Event Type Detection:
   - "create": User wants to schedule/add a new event
   - "modify": User wants to change an existing event (time, participants, etc.)
   - "cancel": User wants to remove/cancel an event
   - "query": User is asking about the schedule (availability, what's planned, etc.)

2. Time Parsing:
   - Convert relative times to ISO 8601 format based on today's date: {today}
   - The user's timezone is: {timezone}
   - IMPORTANT: All times should be interpreted in the user's local timezone and output with the timezone offset
   - For example, if timezone is America/Los_Angeles and user says "6pm", output "2026-01-15T18:00:00-08:00"
   - "tomorrow" = next day, "next Tuesday" = the upcoming Tuesday
   - "morning" typically means 9:00 AM, "afternoon" = 2:00 PM, "evening" = 6:00 PM
   - If only start time given, assume 1-hour duration for meetings, 2 hours for activities

3. Participant Inference:
   - Family members mentioned by name should be included
   - "family dinner" implies all family members
   - "kids' event" implies children only

4. Resource Detection:
   - Look for mentions of: car, van, kitchen, living room, backyard, etc.

5. Recurrence Patterns:
   - "every Monday" = RRULE:FREQ=WEEKLY;BYDAY=MO
   - "daily" = RRULE:FREQ=DAILY
   - "monthly" = RRULE:FREQ=MONTHLY

Be precise and extract only information explicitly stated or clearly implied."""


NL_PARSER_FEW_SHOT_EXAMPLES = [
    # Example 1: Create event with specific time
    {
        "input": "Schedule soccer practice for Emma on Saturday at 2pm",
        "output": {
            "event_type": "create",
            "title": "Soccer practice",
            "start_time": "2026-01-18T14:00:00",
            "end_time": "2026-01-18T16:00:00",
            "participants": ["Emma"],
            "resources": [],
            "priority": "medium",
            "flexibility": "fixed",
            "recurrence_rule": None,
        },
    },
    # Example 2: Create event with relative time and resource
    {
        "input": "I need the car tomorrow morning to take Jake to the dentist",
        "output": {
            "event_type": "create",
            "title": "Dentist appointment - Jake",
            "start_time": "2026-01-14T09:00:00",
            "end_time": "2026-01-14T10:30:00",
            "participants": ["Jake"],
            "resources": ["car"],
            "priority": "high",
            "flexibility": "fixed",
            "recurrence_rule": None,
        },
    },
    # Example 3: Create recurring event
    {
        "input": "Set up weekly piano lessons for Sophie every Wednesday at 4pm",
        "output": {
            "event_type": "create",
            "title": "Piano lessons - Sophie",
            "start_time": "2026-01-15T16:00:00",
            "end_time": "2026-01-15T17:00:00",
            "participants": ["Sophie"],
            "resources": [],
            "priority": "medium",
            "flexibility": "fixed",
            "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=WE",
        },
    },
    # Example 4: Query event type
    {
        "input": "What do we have planned this weekend?",
        "output": {
            "event_type": "query",
            "title": None,
            "start_time": None,
            "end_time": None,
            "participants": [],
            "resources": [],
            "priority": None,
            "flexibility": None,
            "recurrence_rule": None,
        },
    },
    # Example 5: Modify event
    {
        "input": "Move the dentist appointment to Thursday instead",
        "output": {
            "event_type": "modify",
            "title": "Dentist appointment",
            "start_time": None,
            "end_time": None,
            "participants": [],
            "resources": [],
            "priority": None,
            "flexibility": None,
            "recurrence_rule": None,
        },
    },
    # Example 6: Cancel event
    {
        "input": "Cancel the piano lesson this week",
        "output": {
            "event_type": "cancel",
            "title": "Piano lesson",
            "start_time": None,
            "end_time": None,
            "participants": [],
            "resources": [],
            "priority": None,
            "flexibility": None,
            "recurrence_rule": None,
        },
    },
    # Example 7: Flexible timing
    {
        "input": "We need a family meeting sometime this week, flexible on timing",
        "output": {
            "event_type": "create",
            "title": "Family meeting",
            "start_time": None,
            "end_time": None,
            "participants": [],
            "resources": [],
            "priority": "medium",
            "flexibility": "very_flexible",
            "recurrence_rule": None,
        },
    },
    # Example 8: High priority with specific resource
    {
        "input": "Urgent - need to book the van for moving furniture Sunday morning",
        "output": {
            "event_type": "create",
            "title": "Moving furniture",
            "start_time": "2026-01-19T09:00:00",
            "end_time": "2026-01-19T12:00:00",
            "participants": [],
            "resources": ["van"],
            "priority": "high",
            "flexibility": "fixed",
            "recurrence_rule": None,
        },
    },
]


def build_nl_parser_prompt(
    user_input: str,
    today: str,
    timezone: str = "America/Los_Angeles",
    family_members: Optional[list[str]] = None,
    resources: Optional[list[str]] = None,
    conversation_context: Optional[list[dict]] = None,
) -> str:
    """Build the complete NL parser prompt with few-shot examples.

    Args:
        user_input: The natural language input from the user
        today: Today's date in YYYY-MM-DD format
        timezone: User's timezone (IANA name, e.g., America/Los_Angeles)
        family_members: List of known family member names
        resources: List of available resources
        conversation_context: Recent conversation messages for context

    Returns:
        Complete prompt string with system instructions, examples, and user input
    """
    family_members = family_members or []
    resources = resources or []

    # Format few-shot examples
    examples_text = "\n\nHere are examples of how to parse scheduling requests:\n"
    for i, example in enumerate(NL_PARSER_FEW_SHOT_EXAMPLES, 1):
        examples_text += f"\nExample {i}:\n"
        examples_text += f'Input: "{example["input"]}"\n'
        examples_text += f"Output: {example['output']}\n"

    # Format system prompt with context
    system = NL_PARSER_SYSTEM_PROMPT.format(today=today, timezone=timezone)

    # Add family context if available
    context_section = ""
    if family_members:
        context_section += f"\nKnown family members: {', '.join(family_members)}"
    if resources:
        context_section += f"\nAvailable resources: {', '.join(resources)}"

    # Add conversation context if available
    conversation_section = ""
    if conversation_context:
        conversation_section = "\n\nRecent conversation context:\n"
        for msg in conversation_context[-3:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:100]
            conversation_section += f"- {role}: {content}...\n"

    # Compose final prompt
    prompt = f"""{system}
{context_section}
{examples_text}
{conversation_section}
Now parse this request:
Input: "{user_input}"
"""
    return prompt
