# NeuraEvo Systems — Architecture Decisions

This document records the major architectural decisions made during development.

These decisions should not be changed without strong technical justification.

---

# ADR-001

Planning and Runtime are separate systems.

Reason

Planning reasons.

Runtime executes.

Benefits

- Clean boundaries
- Easier testing
- Better scalability
- No circular logic

Status

Accepted

---

# ADR-002

Planning never executes.

Planning only creates execution artifacts.

Runtime consumes those artifacts.

Status

Accepted

---

# ADR-003

Runtime never performs planning.

Runtime executes only.

Status

Accepted

---

# ADR-004

Every capability implements ExecutionCapability.

No special-case capabilities.

Benefits

- Uniform execution
- Easy orchestration
- Replaceable implementations

Status

Accepted

---

# ADR-005

Provider Independence

SDK objects must never leave provider layers.

Examples

Browser

Playwright

↓

BrowserDriver

↓

Browser Capability

Python

Safe Executor

↓

Python Capability

Benefits

- Replaceability
- Better testing
- Cleaner DTOs

Status

Accepted

---

# ADR-006

Frozen DTOs

Every public DTO must be immutable.

Reason

Determinism

Thread safety

Safer Runtime

Status

Accepted

---

# ADR-007

Dependency Injection

All capabilities are constructed through the composition root.

No direct instantiation inside Runtime.

Benefits

- Testing
- Swappable providers
- Cleaner architecture

Status

Accepted

---

# ADR-008

Deterministic Behaviour

No clocks.

No UUIDs.

No randomness.

Stable identifiers only.

Benefits

- Repeatable execution
- Stable tests
- Easier debugging

Status

Accepted

---

# ADR-009

Stateless Services

Services never store execution state.

Execution state belongs in DTOs.

Benefits

- Thread safety
- Horizontal scaling
- Easier testing

Status

Accepted

---

# ADR-010

Browser Architecture

Browser Capability

↓

Browser DOM

↓

Browser Element

↓

Browser Interaction

↓

Browser Workspace

↓

Browser Driver

↓

Playwright

Reason

Provider independence.

SDK isolation.

Status

Accepted

---

# ADR-011

Python Architecture

Python Capability

↓

Workspace

↓

Safe Executor

↓

Artifact Manager

↓

Execution Result

Reason

Safe execution.

Clear separation.

Future scalability.

Status

Accepted

---

# ADR-012

Capability Registry

Every capability must be

Registered

↓

Resolved

↓

Discovered

↓

Validated

before execution.

Reason

Supports future dynamic capability loading.

Status

Accepted

---

# ADR-013

Architecture Growth Policy

Architecture grows additively.

Completed sprints are frozen.

Breaking changes require explicit architectural review.

Status

Accepted

---

# ADR-014

Testing Policy

Every sprint must include

- Unit Tests
- Regression Tests
- Deterministic Tests

No sprint is considered complete without passing tests.

Status

Accepted

---

# ADR-015

Manager Review Policy

Every sprint must be reviewed before commit.

Review includes

- Architecture
- Scalability
- Maintainability
- Security
- Determinism
- Testing
- Roadmap impact

Only approved sprints are committed.

Status

Accepted

---

# Guiding Principles

Enterprise architecture over shortcuts.

Long-term maintainability over short-term speed.

Provider independence.

Deterministic systems.

Single responsibility.

Clean dependency flow.

Test-driven engineering.

Capability reuse.

Incremental evolution without architectural debt.