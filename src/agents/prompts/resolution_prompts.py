"""Resolution agent prompts with strategy examples."""

from typing import Optional

RESOLUTION_SYSTEM_PROMPT = """You are an expert conflict resolution specialist for family scheduling.

Your task: Analyze scheduling conflicts and propose practical resolution strategies.

AVAILABLE STRATEGIES:
1. move_event: Reschedule to a different time slot
2. shorten_event: Reduce event duration to fit
3. split_event: Break event into multiple shorter sessions
4. cancel_event: Cancel the new or conflicting event
5. override_constraint: Proceed despite soft constraint violation
6. alternative_resource: Use a different resource (e.g., different car)
7. swap_participants: Reassign who attends which event
8. suggest_virtual: Convert to virtual attendance if applicable

RESOLUTION GUIDELINES:
1. Prioritize solutions with minimal disruption to existing events
2. Consider participant preferences and priorities
3. For family events, consider splitting participation
4. Score each resolution from 0.0 to 1.0 based on:
   - Impact on participants (lower impact = higher score)
   - Feasibility (more feasible = higher score)
   - Preservation of original intent (better preservation = higher score)
5. Provide clear, actionable descriptions
6. Identify all side effects of each resolution

Generate 2-4 resolution options, ranked by score."""


RESOLUTION_FEW_SHOT_EXAMPLES = [
    {
        "conflict": "Emma has soccer practice at 2pm and dentist at 2:30pm on Saturday",
        "resolutions": [
            {
                "resolution_id": "res_1",
                "strategy": "move_event",
                "score": 0.9,
                "description": "Move dentist appointment to 10am Saturday - before soccer practice",
                "changes": [
                    {
                        "event_id": "dentist_1",
                        "field": "start_time",
                        "new_value": "2026-01-18T10:00:00",
                    }
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Need to call dentist to reschedule"],
            },
            {
                "resolution_id": "res_2",
                "strategy": "shorten_event",
                "score": 0.7,
                "description": "Leave soccer practice 30 minutes early to make dentist",
                "changes": [
                    {
                        "event_id": "soccer_1",
                        "field": "end_time",
                        "new_value": "2026-01-18T14:00:00",
                    }
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Emma will miss end of practice"],
            },
        ],
    },
    {
        "conflict": "Both parents need the car at 9am Monday - work meeting vs school drop-off",
        "resolutions": [
            {
                "resolution_id": "res_1",
                "strategy": "alternative_resource",
                "score": 0.95,
                "description": "Use rideshare for school drop-off, keep car for work meeting",
                "changes": [
                    {
                        "event_id": "school_dropoff",
                        "field": "resources",
                        "new_value": "rideshare",
                    }
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Additional cost for rideshare (~$15)"],
            },
            {
                "resolution_id": "res_2",
                "strategy": "move_event",
                "score": 0.8,
                "description": "Do drop-off earlier at 8am, then car is free for 9am meeting",
                "changes": [
                    {
                        "event_id": "school_dropoff",
                        "field": "start_time",
                        "new_value": "2026-01-20T08:00:00",
                    }
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Need to adjust morning schedule"],
            },
        ],
    },
    {
        "conflict": "Family dinner at 6pm conflicts with Jake's basketball game at 5:30pm",
        "resolutions": [
            {
                "resolution_id": "res_1",
                "strategy": "move_event",
                "score": 0.85,
                "description": "Move family dinner to 7:30pm after basketball game ends",
                "changes": [
                    {
                        "event_id": "family_dinner",
                        "field": "start_time",
                        "new_value": "2026-01-18T19:30:00",
                    }
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Later dinner time for younger kids"],
            },
            {
                "resolution_id": "res_2",
                "strategy": "swap_participants",
                "score": 0.7,
                "description": "One parent stays for dinner, other takes Jake to game",
                "changes": [
                    {
                        "event_id": "basketball_game",
                        "field": "participants",
                        "new_value": "Parent A, Jake",
                    },
                    {
                        "event_id": "family_dinner",
                        "field": "participants",
                        "new_value": "Parent B, Emma, Sophie",
                    },
                ],
                "conflicts_resolved": ["conflict_1"],
                "side_effects": ["Family not all together for dinner"],
            },
        ],
    },
]


def build_resolution_prompt(
    conflicts: list[dict],
    event_request: dict,
    existing_events: Optional[list[dict]] = None,
) -> str:
    """Build resolution prompt with conflict context.

    Args:
        conflicts: List of detected conflict dictionaries
        event_request: The parsed event data being scheduled
        existing_events: Optional list of relevant existing events

    Returns:
        Complete prompt string for resolution generation
    """
    # Format conflict description
    conflict_desc = "DETECTED CONFLICTS:\n"
    for i, conflict in enumerate(conflicts, 1):
        conflict_desc += f"\n{i}. {conflict.get('type', 'Unknown')} conflict:\n"
        conflict_desc += f"   - ID: {conflict.get('conflict_id', conflict.get('id', 'unknown'))}\n"
        conflict_desc += (
            f"   - Description: {conflict.get('description', 'No description')}\n"
        )
        if conflict.get("conflicting_event"):
            ce = conflict["conflicting_event"]
            conflict_desc += f"   - Conflicting event: {ce.get('title', 'Unknown')} "
            conflict_desc += (
                f"({ce.get('start_time', '?')} - {ce.get('end_time', '?')})\n"
            )
        if conflict.get("overlapping_participants"):
            conflict_desc += f"   - Affected participants: {', '.join(conflict['overlapping_participants'])}\n"
        if conflict.get("is_blocking"):
            conflict_desc += "   - This is a BLOCKING conflict\n"

    # Format event request
    participants = event_request.get("participants", [])
    event_desc = f"""
EVENT BEING SCHEDULED:
- Title: {event_request.get('title', 'Unknown')}
- Time: {event_request.get('start_time', 'Not specified')} - {event_request.get('end_time', 'Not specified')}
- Participants: {', '.join(participants) if participants else 'Not specified'}
- Priority: {event_request.get('priority', 'medium')}
- Flexibility: {event_request.get('flexibility', 'fixed')}
"""

    # Format existing events context if provided
    existing_desc = ""
    if existing_events:
        existing_desc = "\n\nRELEVANT EXISTING EVENTS (can be adjusted if needed):\n"
        for event in existing_events[:5]:
            existing_desc += f"- {event.get('title', 'Unknown')}: "
            existing_desc += f"{event.get('start_time', '?')} - {event.get('end_time', '?')}\n"

    # Format examples
    examples_text = "\n\nEXAMPLES OF GOOD RESOLUTION STRATEGIES:\n"
    for example in RESOLUTION_FEW_SHOT_EXAMPLES:
        examples_text += f"\nConflict: {example['conflict']}\n"
        examples_text += "Proposed resolutions:\n"
        for res in example["resolutions"][:2]:
            examples_text += f"  - {res['strategy']}: {res['description']} (score: {res['score']})\n"
            if res.get("side_effects"):
                examples_text += f"    Side effects: {', '.join(res['side_effects'])}\n"

    return f"""{RESOLUTION_SYSTEM_PROMPT}

{conflict_desc}
{event_desc}
{existing_desc}
{examples_text}

Now analyze the conflicts above and generate 2-4 resolution options.
"""
