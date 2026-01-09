# ADR-009: Hard vs Soft Constraints

## Status
Accepted

## Context

Family members have various rules and preferences about scheduling:
- **Rules**: "No events before 8am" (absolute requirement)
- **Preferences**: "Prefer morning events" (preference but flexible)
- **Limits**: "Maximum 3 events per day" (boundary constraint)
- **Time Windows**: "Available 9am-5pm on weekdays" (availability)

We need to decide how to model and enforce these constraints in the scheduling system. Key questions:

- Should all constraints be treated equally (blocking vs preferences)?
- How should agents handle constraint violations?
- How should scoring work when multiple constraints apply?
- How should users express different constraint strengths?

Several approaches exist:

1. **Binary (Hard Only)**: All constraints block scheduling, no preferences
2. **Priority Levels**: Constraints have priority 1-10, higher priority more important
3. **Hard vs Soft**: Two types - hard constraints block, soft constraints influence scoring
4. **Weighted Scoring**: All constraints have weights, combined into score
5. **Declarative Rules**: Complex rule engine with IF/THEN logic

Considerations:
- **User Experience**: Users need simple way to express "must have" vs "nice to have"
- **Agent Logic**: Agents need clear guidance on when to block vs optimize
- **Conflict Resolution**: Resolution Agent needs to know what can be compromised
- **Flexibility**: System should handle both strict rules and flexible preferences

## Decision

We will use a **hard vs soft constraint model** where constraints are categorized as either:

1. **Hard Constraints**: Blocking rules that prevent scheduling entirely
2. **Soft Constraints**: Preferences that influence scoring but don't block

**Additional features:**
- Soft constraints have priority (1-10) for relative importance
- Scheduling Agent combines soft constraint scores
- Hard constraints checked first, soft constraints optimize within valid space

### Model Structure

```python
class Constraint(Base):
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
    family_member_id = Column(UUID, ForeignKey("family_members.id"), nullable=True)
    type = Column(String, nullable=False)
    constraint_level = Column(String, nullable=False)  # "hard" or "soft"
    priority = Column(Integer, default=5)  # 1-10, for soft constraints only
    rule = Column(JSONB, nullable=False)
    active = Column(Boolean, default=True)
```

### Constraint Levels

**Hard Constraint (constraint_level = "hard"):**
- **Blocks** scheduling entirely if violated
- Examples: "No events before 8am", "Required gap between events", "Resource unavailable"
- Scheduling Agent: Excludes time slots that violate hard constraints
- Conflict Detection: Hard constraint violations are high-severity conflicts

**Soft Constraint (constraint_level = "soft"):**
- **Influences** scoring but doesn't block
- Has priority 1-10 indicating importance
- Examples: "Prefer morning events", "Minimize travel time", "Limit daily events"
- Scheduling Agent: Adjusts scores for candidate times based on soft constraint compliance
- Conflict Detection: Soft constraint violations are low-severity, informational

### Scoring Logic

```python
def score_candidate_time(candidate, soft_constraints):
    """
    Score candidate time based on soft constraint compliance.
    Returns score 0.0 (worst) to 1.0 (best)
    """
    base_score = 1.0
    total_priority = sum(c.priority for c in soft_constraints)

    for constraint in soft_constraints:
        if violates_constraint(candidate, constraint.rule):
            # Penalty proportional to priority
            penalty = (constraint.priority / total_priority) * 0.5
            base_score -= penalty

    return max(0.0, base_score)
```

## Consequences

### Positive

1. **Clear Semantics**: Hard = blocking, soft = preference (intuitive for users)
2. **Flexible Scheduling**: Soft constraints allow optimization without over-constraining
3. **Agent Logic Simplified**: Clear rules for when to block vs when to optimize
4. **User Control**: Users can express both "must have" and "nice to have" requirements
5. **Conflict Resolution**: Resolution Agent knows which constraints can be relaxed
6. **Graceful Degradation**: System finds valid times even if soft constraints violated
7. **Transparent Scoring**: Priority system makes relative importance explicit
8. **Balanced Approach**: Combines strict enforcement with flexible optimization

### Negative

1. **Binary Categories**: Only two levels; no fine-grained gradations
2. **Priority Ambiguity**: How to set priorities? Users may find it confusing
3. **Scoring Complexity**: Combining multiple soft constraints requires careful tuning
4. **Edge Cases**: What if all soft constraints violated? Score could be misleading
5. **Learning Curve**: Users need to understand hard vs soft distinction

### Mitigation Strategies

- Provide clear documentation and examples of hard vs soft
- Default to sensible priorities (e.g., 5) if user unsure
- UI helpers to guide constraint level selection ("Will this PREVENT scheduling or just PREFER?")
- Scheduling Agent explains which soft constraints were violated
- Show users the impact of soft constraint violations in proposals
- Consider adding "medium" level in Phase 2 if binary proves insufficient

## Implementation Examples

### Hard Constraint: No Early Morning Events

```python
{
    "name": "No early morning events",
    "family_member_id": "child_1",
    "type": "time_window",
    "constraint_level": "hard",
    "priority": None,  # Not used for hard constraints
    "rule": {
        "type": "no_events_before",
        "time": "08:00"
    }
}
```

**Enforcement:**
```python
def check_hard_constraints(event, constraints):
    violations = []
    for constraint in constraints:
        if constraint.constraint_level == "hard":
            if violates_constraint(event, constraint.rule):
                violations.append({
                    "constraint_id": constraint.id,
                    "name": constraint.name,
                    "blocking": True
                })
    return violations

# In Scheduling Agent
violations = check_hard_constraints(proposed_event, hard_constraints)
if violations:
    return {
        "data": {"candidate_times": [], "blocking_constraints": violations},
        "explanation": "Cannot schedule: violates hard constraint 'No early morning events'",
        "confidence": 1.0
    }
```

### Soft Constraint: Prefer Morning Events

```python
{
    "name": "Prefer morning events",
    "family_member_id": "parent_1",
    "type": "time_window",
    "constraint_level": "soft",
    "priority": 7,  # High priority preference
    "rule": {
        "type": "preferred_window",
        "start": "09:00",
        "end": "12:00"
    }
}
```

**Scoring:**
```python
def score_candidate_with_soft_constraints(candidate, soft_constraints):
    score = 1.0

    for constraint in soft_constraints:
        if violates_constraint(candidate, constraint.rule):
            # Deduct based on priority
            penalty = constraint.priority / 10 * 0.3  # Priority 7 → 0.21 penalty
            score -= penalty

    return max(0.0, score)

# In Scheduling Agent
candidates = [
    {"start": "2026-01-11T10:00:00", "end": "2026-01-11T11:00:00"},  # Morning
    {"start": "2026-01-11T14:00:00", "end": "2026-01-11T15:00:00"}   # Afternoon
]

for candidate in candidates:
    candidate["score"] = score_candidate_with_soft_constraints(
        candidate, soft_constraints
    )

# Results:
# Morning: score 1.0 (no violation)
# Afternoon: score 0.79 (violates priority-7 preference, penalty -0.21)
```

### Hard Constraint: Minimum Gap Between Events

```python
{
    "name": "Buffer time between events",
    "family_member_id": "parent_1",
    "type": "min_gap",
    "constraint_level": "hard",
    "rule": {
        "type": "min_gap_minutes",
        "minutes": 30
    }
}
```

**Enforcement:**
```python
def check_min_gap(new_event, existing_events, min_gap_minutes):
    for existing in existing_events:
        # Check gap before new event
        gap_before = (new_event.start_time - existing.end_time).total_seconds() / 60
        if 0 < gap_before < min_gap_minutes:
            return False

        # Check gap after new event
        gap_after = (existing.start_time - new_event.end_time).total_seconds() / 60
        if 0 < gap_after < min_gap_minutes:
            return False

    return True
```

### Soft Constraint: Limit Daily Events

```python
{
    "name": "Limit daily events",
    "family_member_id": "child_1",
    "type": "max_events_per_day",
    "constraint_level": "soft",
    "priority": 8,  # High priority
    "rule": {
        "type": "max_events_per_day",
        "count": 3
    }
}
```

**Scoring:**
```python
def check_daily_event_count(date, family_member_id):
    count = db.query(Event).join(EventParticipant).filter(
        EventParticipant.family_member_id == family_member_id,
        Event.status == "confirmed",
        func.date(Event.start_time) == date
    ).count()
    return count

# In Scheduling Agent
current_count = check_daily_event_count(candidate_date, family_member_id)
max_count = constraint.rule["count"]

if current_count >= max_count:
    # Soft constraint: Penalize but don't block
    penalty = constraint.priority / 10 * 0.4  # Priority 8 → 0.32 penalty
    candidate["score"] -= penalty
    candidate["violations"].append({
        "constraint": "Limit daily events",
        "level": "soft",
        "message": f"This would be event {current_count + 1} of preferred max {max_count}"
    })
```

## Scheduling Agent Integration

```python
def scheduling_agent(event_details, constraints):
    family_member_id = event_details["participant_id"]

    # Separate hard and soft constraints
    hard_constraints = [c for c in constraints if c.constraint_level == "hard"]
    soft_constraints = [c for c in constraints if c.constraint_level == "soft"]

    # Generate candidate times
    candidates = generate_candidate_times(event_details)

    # Filter by hard constraints (blocking)
    valid_candidates = [
        c for c in candidates
        if not violates_any_hard_constraint(c, hard_constraints)
    ]

    if not valid_candidates:
        return {
            "data": {"candidate_times": [], "blocking_constraints": hard_constraints},
            "explanation": "No valid times found - all candidates violate hard constraints",
            "confidence": 1.0
        }

    # Score by soft constraints (optimization)
    for candidate in valid_candidates:
        candidate["score"] = score_candidate_with_soft_constraints(
            candidate, soft_constraints
        )

    # Sort by score
    valid_candidates.sort(key=lambda c: c["score"], reverse=True)

    return {
        "data": {
            "candidate_times": valid_candidates[:5],  # Top 5
            "recommended_time": valid_candidates[0],
            "soft_violations": get_soft_violations(valid_candidates[0], soft_constraints)
        },
        "explanation": format_explanation(valid_candidates[0]),
        "confidence": 0.90
    }
```

## User Experience

**Constraint Creation UI:**
```
Constraint: No events before 8am
Type: [ ] Requirement (blocks scheduling) ← Hard
      [x] Preference (influences suggestions) ← Soft

If preference, how important?
[=========|=] Priority: 7/10
Low  ←  Medium  →  High
```

**Scheduling Results:**
```
✓ Best option: Saturday 10am-12pm (Score: 95%)
  • All requirements met
  • Matches preference: Morning events (Priority: High)

⚠ Alternative: Saturday 2pm-4pm (Score: 78%)
  • All requirements met
  • Doesn't match preference: Morning events (Priority: High)
  • This would be 4th event today (preferred max: 3)
```

## Alternatives Considered

### Binary (Hard Only)
**Pros**: Simplest possible, clear enforcement
**Cons**: No flexibility, over-constrains, can't express preferences
**Why not chosen**: Too rigid; users need to express preferences without blocking

### Priority Levels (1-10 scale)
**Pros**: Fine-grained control, no arbitrary binary split
**Cons**: Unclear where "blocking" threshold is, harder for users to understand
**Why not chosen**: Lacks clear semantic distinction between blocking and optimizing

### Weighted Scoring Only
**Pros**: Smooth scoring, no binary categories
**Cons**: Nothing truly blocks scheduling, even critical constraints could be violated
**Why not chosen**: Need hard guarantees for some constraints (safety, availability)

### Complex Rule Engine
**Pros**: Maximum expressiveness, can handle any logic
**Cons**: Complexity explosion, hard for agents to reason about, poor UX
**Why not chosen**: Over-engineered; 90% of use cases covered by hard/soft distinction

## Future Enhancements

**Phase 2+ Possibilities:**
- Add "medium" constraint level if binary proves insufficient
- Machine learning to suggest priority levels based on user behavior
- Constraint templates for common patterns
- Conditional constraints ("No events before 8am on weekends only")
- Constraint violations tracking and analytics

## References

- [Data Model - Constraint Entity](../architecture/data-model.md#8-constraint)
- [Agent Architecture - Scheduling Agent](../architecture/agents.md#2-scheduling-agent)
- [Agent Architecture - Conflict Detection](../architecture/agents.md#4-conflict-detection-agent)

---

*Date: 2026-01-08*
*Supersedes: None*
