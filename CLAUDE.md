# NeuraEvo Project Instructions

## Current Project Status

### Sprint 1 — Core Backend Foundation ✅

* Sprint 1A: Backend Foundation
* Sprint 1B: Models & Repositories
* Sprint 1C: Authentication System
* Sprint 1D: Employee Creation API
* Sprint 1E: Employee Management API

---

### Sprint 2 — Memory Engine ✅

* Sprint 2A: Memory Engine Foundation
* Sprint 2B: Memory Retrieval & Deletion
* Sprint 2C: Memory Filtering & Pagination
* Sprint 2D: Memory Updates
* Sprint 2E: Memory Statistics

---

### Sprint 3 — Employee Builder Foundation ✅

* Sprint 3A: Blueprint Foundation
* Sprint 3B: Interview Questions Foundation
* Sprint 3C: Interview Answers Foundation
* Sprint 3D: Interview Sessions Foundation
* Sprint 3E: Session Question Execution Foundation

---

### Sprint 4 — AI Blueprint Generation System ✅

* Sprint 4A: Blueprint Generation Foundation
* Sprint 4B: Claude Blueprint Generation Provider
* Sprint 4C: Blueprint Apply & Persistence
* Sprint 4D: Blueprint Versioning & History
* Sprint 4E: Blueprint Version Restore

---

### Sprint 5 — Conversation Engine

* Sprint 5A: Conversation Foundation
* Sprint 5B 
* Sprint 5C
* Sprint 5D: AI Conversation Generation Foundation 
* Sprint 5E: Conversation Persistence & Assistant Reply Storage

## Current Sprint

Current Sprint = 6D

---

# Important Rules

Do not modify completed Sprint 1 functionality unless explicitly requested.

Do not modify completed Sprint 2 functionality unless explicitly requested.

Do not modify completed Sprint 3 functionality unless explicitly requested.

Do not modify completed Sprint 4 functionality unless explicitly requested.

Do not modify completed Sprint 5 functionality unless explicitly requested.

Reuse existing services whenever possible.

Maintain strict architecture boundaries.

Follow existing coding patterns.

---

# Project Overview

NeuraEvo is a Voice-First Personal AI Employee Platform.

Users create personalized AI employees through an interview-driven onboarding process.

The platform currently supports:

* Authentication
* Employee Management
* Memory Engine
* Blueprint Management
* Interview Questions
* Interview Answers
* Interview Sessions
* Session Question Execution
* AI Blueprint Generation
* Blueprint Apply Workflow
* Blueprint Version History
* Blueprint Restore Workflow

---

# Architecture Rules

Architecture is locked.

Do not:

* Create new top-level folders
* Rename existing folders
* Move completed modules
* Bypass service layer
* Introduce parallel ownership systems

All new functionality must integrate into the existing architecture.

---

# Repository Layer

Repositories are persistence-only.

Allowed:

* Queries
* CRUD
* Flush operations
* Persistence helpers

Not allowed:

* Ownership validation
* Authorization
* Business logic
* AI orchestration
* Workflow decisions
* Transactions
* HTTP concerns

Repositories never decide behavior.

---

# Service Layer

Services own:

* Ownership validation
* Business rules
* Workflow orchestration
* AI orchestration
* Transactions
* Version management
* Domain coordination

Services are the only location for business decisions.

---

# API Layer

Routers own:

* Request validation
* Dependency injection
* HTTP translation
* Swagger documentation

Routers must never contain business logic.

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

* Anthropic Claude
* OpenAI

## Infrastructure

* Docker
* Nginx
* Render

---

# Completed Domain Model

User
└── Employee
├── Memories
├── Blueprint
│ ├── Versions
│ ├── Interview Questions
│ ├── Interview Answers
│ └── Blueprint Generation
├── Interview Sessions
│ └── Session Questions

All ownership chains are implemented and validated.

---

# AI Blueprint Generation Rules

Completed in Sprint 4.

Current architecture:

Interview Data
↓
Aggregation
↓
Prompt Construction
↓
Claude Provider
↓
Draft Generation
↓
Apply
↓
Version Snapshot
↓
Restore Support

Rules:

* Prompt construction remains centralized.
* Provider-specific code remains isolated.
* Claude integration remains replaceable.
* Routers never call AI providers directly.
* Repositories never call AI providers directly.
* Models never call AI providers directly.

---

# Blueprint Rules

Each employee owns exactly one blueprint.

Blueprint ownership is inherited from employee ownership.

Blueprint supports:

* CRUD
* AI Generation Preview
* Apply Generated Content
* Version History
* Version Restore

Blueprint versions represent immutable snapshots.

Versions must never be overwritten.

Versions must never be deleted manually.

History integrity must be preserved.

---

# Versioning Rules

Blueprint versions are immutable snapshots.

Version numbering is sequential.

Restore operations must:

1. Create a snapshot of the current blueprint.
2. Restore the selected version.
3. Commit atomically.

History must remain complete.

Current blueprint always represents the latest state.

Version history represents previous states.

---

# Ownership Rules

All ownership validation must reuse existing chains.

Reuse existing services whenever possible.

Never duplicate ownership logic.

Prefer:

* EmployeeService
* BlueprintService
* BlueprintVersionService
* InterviewQuestionService
* InterviewAnswerService
* InterviewSessionService
* InterviewSessionQuestionService

---

# Memory Rules

Memory Engine is complete.

Capabilities:

* Create
* Retrieve
* Update
* Delete
* Filter
* Pagination
* Statistics

Do not redesign Memory architecture.

Do not introduce AI memory behavior unless explicitly requested.

---

# AI Rules

All AI integrations must remain isolated.

Never call AI providers directly from:

* Routers
* Repositories
* Models

Provider-specific code belongs inside provider implementations only.

Prompt construction should remain centralized.

Provider replacement should require minimal changes.

---

# Current Platform Scope

Completed:

* Authentication
* Employee Management
* Memory Engine
* Blueprint CRUD
* Interview System
* Session Execution
* Blueprint Generation
* Blueprint Versioning
* Blueprint Restore

Not Yet Implemented:

* Voice Calling
* Realtime Conversations
* Task Execution
* Autonomous Agents
* Tool Calling
* Scheduling Engine
* Workflow Engine
* Multi-Agent Systems
* Agent Collaboration
* Realtime Memory Learning
* Voice Runtime

Do not implement future systems unless explicitly requested.

---

# Development Rules

Implement only the requested sprint.

Do not implement future roadmap items.

Do not introduce unnecessary dependencies.

Keep code production-ready.

Prefer reuse over duplication.

Follow existing naming conventions.

Maintain consistency with previous sprints.

Avoid speculative abstractions.

---

# Code Quality

Use:

* Type hints
* Dependency injection
* Composition
* Clear naming
* Small focused services

Avoid:

* God classes
* Business logic in routers
* Ownership duplication
* Direct database access outside repositories
* Hardcoded AI logic

---

# Before Finishing Any Task

Verify:

* Imports
* Typing
* Ownership validation
* Service boundaries
* Transaction boundaries
* HTTP status codes
* Swagger documentation
* AI workflow integrity
* Version history integrity

Provide:

1. Files created
2. Files modified
3. Endpoint behavior
4. Verification results
5. Architectural decisions
6. Local testing instructions
7. Confirmation that previous completed sprints remain unchanged

Stop at the requested sprint.

Do not implement future sprints.
