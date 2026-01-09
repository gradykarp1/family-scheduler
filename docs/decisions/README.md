# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting key architectural decisions made during the development of the Family Scheduler project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## Format

Each ADR follows this structure:

```markdown
# ADR-XXX: Title

## Status
[Proposed | Accepted | Implemented | Superseded]

**Implementation Status**: [Not yet implemented | Implemented | Partially implemented]
**Implementation Date**: [YYYY-MM-DD or TBD]

_If status is Superseded, reference the superseding ADR: "Superseded by ADR-XXX"_

## Context
What is the issue we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?

## Alternatives Considered
What other options were evaluated?

## Implementation
_This section documents the actual implementation of this decision and is added when the decision is implemented._

**Implemented**: [YYYY-MM-DD]
**Deviations from Plan**: [Any differences between the planned decision and actual implementation]
**Lessons Learned**: [What we discovered during implementation]
**Related Commits/PRs**: [References to relevant code changes]

_Note: This section is optional for Accepted decisions and required for Implemented decisions._
```

## Status Definitions

- **Proposed**: ADR drafted but not yet accepted/decided
- **Accepted**: Decision documented and agreed upon, but not yet implemented
- **Implemented**: Decision has been coded/deployed and is in use
- **Superseded**: Replaced by a newer ADR (reference the superseding ADR)

## Index

### [ADR-001: Agent Framework Selection](./adr-001-agent-framework-selection.md)
**Status:** Accepted
**Summary:** Chose LangChain/LangGraph for agent orchestration
**Date:** 2026-01-08

### [ADR-002: Hub-and-Spoke Agent Architecture](./adr-002-hub-and-spoke-agent-architecture.md)
**Status:** Accepted
**Summary:** Use central orchestrator with specialized agents returning to hub
**Date:** 2026-01-08

### [ADR-003: Proposal Flow for Event Creation](./adr-003-proposal-flow-for-event-creation.md)
**Status:** Accepted
**Summary:** Events validated through pipeline before confirmation
**Date:** 2026-01-08

### [ADR-004: Hybrid Agent Output Format](./adr-004-hybrid-agent-output-format.md)
**Status:** Accepted
**Summary:** Agents return structured data + natural language explanations
**Date:** 2026-01-08

### [ADR-005: Event-Triggered Conflict Detection](./adr-005-event-triggered-conflict-detection.md)
**Status:** Accepted
**Summary:** Synchronous validation during proposal flow + event-triggered scanning
**Date:** 2026-01-08

### [ADR-006: Phased Infrastructure Deployment](./adr-006-phased-infrastructure-deployment.md)
**Status:** Accepted
**Summary:** Start local (SQLite), evolve to GCP with agent scaling
**Date:** 2026-01-08

### [ADR-007: Hybrid Recurrence Model](./adr-007-hybrid-recurrence-model.md)
**Status:** Accepted
**Summary:** Store RRULE, generate instances on-the-fly, create records only for exceptions
**Date:** 2026-01-08

### [ADR-008: Resource Capacity Model](./adr-008-resource-capacity-model.md)
**Status:** Accepted
**Summary:** Resources support concurrent usage via capacity field
**Date:** 2026-01-08

### [ADR-009: Hard vs Soft Constraints](./adr-009-hard-vs-soft-constraints.md)
**Status:** Accepted
**Summary:** Constraints have levels (hard=blocking, soft=preference) with priority scoring
**Date:** 2026-01-08

### [ADR-010: Python Environment & Package Management](./adr-010-python-environment-package-management.md)
**Status:** Implemented ✅
**Implementation:** 2026-01-08
**Summary:** Use Poetry for package management, Python 3.11, and .env files for configuration
**Date:** 2026-01-08

### [ADR-011: LLM Provider Selection](./adr-011-llm-provider-selection.md)
**Status:** Implemented ✅
**Implementation:** 2026-01-08
**Summary:** Use Anthropic Claude as LLM provider with Claude Sonnet 4 as primary model
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
