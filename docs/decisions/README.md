# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting key architectural decisions made during the development of the Family Scheduler project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## Format

Each ADR follows this structure:

```markdown
# ADR-XXX: Title

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
What is the issue we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?

## Alternatives Considered
What other options were evaluated?
```

## Index

### ADR-001: Agent Framework Selection
**Status:** Accepted
**Summary:** Chose LangChain/LangGraph for agent orchestration
**Date:** 2026-01-08

### ADR-002: Hub-and-Spoke Agent Architecture
**Status:** Accepted
**Summary:** Use central orchestrator with specialized agents returning to hub
**Date:** 2026-01-08

### ADR-003: Proposal Flow for Event Creation
**Status:** Accepted
**Summary:** Events validated through pipeline before confirmation
**Date:** 2026-01-08

### ADR-004: Hybrid Agent Output Format
**Status:** Accepted
**Summary:** Agents return structured data + natural language explanations
**Date:** 2026-01-08

### ADR-005: Event-Triggered Conflict Detection
**Status:** Accepted
**Summary:** Synchronous validation during proposal flow + event-triggered scanning
**Date:** 2026-01-08

### ADR-006: Phased Infrastructure Deployment
**Status:** Accepted
**Summary:** Start local (SQLite), evolve to GCP with agent scaling
**Date:** 2026-01-08

### ADR-007: Hybrid Recurrence Model
**Status:** Accepted
**Summary:** Store RRULE, generate instances on-the-fly, create records only for exceptions
**Date:** 2026-01-08

### ADR-008: Resource Capacity Model
**Status:** Accepted
**Summary:** Resources support concurrent usage via capacity field
**Date:** 2026-01-08

### ADR-009: Hard vs Soft Constraints
**Status:** Accepted
**Summary:** Constraints have levels (hard=blocking, soft=preference) with priority scoring
**Date:** 2026-01-08

---

## Creating a New ADR

To create a new ADR:

1. Determine the next ADR number
2. Create a new file: `adr-XXX-short-title.md`
3. Use the template above
4. Update this README index

---

*Last Updated: 2026-01-08*
