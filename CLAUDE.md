# NeuraEvo Project Instructions

## Current Project Status

### Sprint 1 — Core Backend Foundation ✅

* Sprint 1A: Backend Foundation
* Sprint 1B: Models & Repositories
* Sprint 1C: Authentication System
* Sprint 1D: Employee Creation API
* Sprint 1E: Employee Management API

### Sprint 2 — Memory Engine ✅

* Sprint 2A: Memory Engine Foundation
* Sprint 2B: Memory Retrieval & Deletion
* Sprint 2C: Memory Filtering & Pagination
* Sprint 2D: Memory Updates
* Sprint 2E: Memory Statistics

### Sprint 3 — Employee Builder Foundation ✅

* Sprint 3A: Blueprint Foundation
* Sprint 3B: Interview Questions Foundation
* Sprint 3C: Interview Answers Foundation
* Sprint 3D: Interview Sessions Foundation
* Sprint 3E: Session Question Execution Foundation
* Sprint 4A: Blueprint Generation Foundation

---

## Current Sprint

 * Current Sprint = 4C

 Blueprint Apply/Persist Generation

---

## Important Rules

Do not modify completed Sprint 1 functionality unless explicitly requested.

Do not modify completed Sprint 2 functionality unless explicitly requested.

Do not modify completed Sprint 3 functionality unless explicitly requested.

Follow existing architecture and patterns.

Reuse existing services whenever possible.

Maintain strict layer separation.

---

# Project Overview

NeuraEvo is a Voice-First Personal AI Employee Platform.

Users create personalized AI employees through an interview-driven onboarding process.

The platform stores:

* Employee profile
* Memories
* Blueprint
* Interview questions
* Interview answers
* Interview sessions

Sprint 4 introduces AI-assisted blueprint generation from collected interview data.

---

# Architecture Rules

Architecture is locked.

Do not:

* Create new top-level folders
* Rename existing folders
* Move completed modules
* Bypass service layer

---

## Repository Layer

Repositories are persistence-only.

Allowed:

* Database queries
* CRUD operations

Not allowed:

* Authorization
* Business rules
* AI logic
* Validation

---

## Service Layer

Services own:

* Ownership validation
* Business rules
* AI orchestration
* Transactions
* Domain workflows

All generation logic belongs here.

---

## API Layer

API owns:

* Request validation
* Dependency injection
* HTTP translation

API must never contain business logic.

---

# Technology Stack

## Frontend

* React Native
* TypeScript

## Backend

* FastAPI
* Python 3.11+

## Database

* PostgreSQL
* pgvector

## Storage

* Supabase Storage

## AI

* Claude
* OpenAI

## Infrastructure

* Docker
* Nginx
* Render

---

# Completed Data Model

User
└── Employee
├── Memories
├── Blueprint
│ ├── Interview Questions
│ └── Interview Answers
└── Interview Sessions
└── Session Questions

All CRUD and ownership validation are complete.

---

# Sprint 4 Scope

## Blueprint Generation

Allowed:

* Interview aggregation
* Blueprint generation workflows
* Prompt construction
* AI provider abstraction
* Generation services
* Blueprint regeneration

Not allowed:

* Voice systems
* Realtime conversations
* Autonomous agents
* Task execution
* Scheduling
* Workflow engines
* Tool calling
* Agent-to-agent communication

---

# AI Rules

All AI integrations must be isolated behind services.

Never call AI providers directly from:

* Routers
* Repositories
* Database models

Generation should be deterministic where possible.

Prompt construction must be centralized.

Provider-specific code should remain replaceable.

---

# Ownership Rules

Every operation must validate ownership through existing chains.

Reuse:

* EmployeeService
* BlueprintService
* InterviewQuestionService
* InterviewAnswerService
* InterviewSessionService
* InterviewSessionQuestionService

Never duplicate ownership logic.

---

# Memory Rules

Memory Engine is complete.

Current capabilities:

* Create memory
* Retrieve memory
* Update memory
* Delete memory
* Search/filter memory
* Pagination
* Statistics

Do not redesign memory architecture.

---

# Blueprint Rules

Each employee owns exactly one blueprint.

Blueprint ownership is inherited from employee ownership.

Sprint 4 may update blueprint content through generation services.

Generated content must be persisted through existing blueprint services.

---

# Development Rules

Implement only the requested sprint objective.

Do not implement future roadmap items.

Do not introduce unnecessary dependencies.

Keep code typed and production-ready.

Prefer reuse over duplication.

Follow existing naming conventions.

Maintain consistency with previous sprints.

---

# Code Quality

Use:

* Type hints
* Clear naming
* Small focused classes
* Dependency injection
* Composition over inheritance

Avoid:

* God classes
* Duplicate ownership checks
* Business logic in routers
* Direct database access outside repositories

---

# Before Finishing Any Task

Verify:

* Imports
* Typing
* Ownership validation
* Service boundaries
* HTTP status codes
* Swagger documentation
* AI workflow correctness

Provide:

1. Files created
2. Files modified
3. Endpoint behavior
4. Verification results
5. Architectural decisions
6. Local testing instructions
