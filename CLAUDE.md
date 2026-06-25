# NeuraEvo Project Instructions

## Current Project Status

Completed:

* Sprint 1A: Backend Foundation

* Sprint 1B: Models & Repositories

* Sprint 1C: Authentication System

* Sprint 1D: Employee Creation API

* Sprint 1E: Employee Management API

* Sprint 2A: Memory Engine Foundation

* Sprint 2B: Memory Retrieval & Deletion

* Sprint 2C: Memory Filtering & Pagination

* Sprint 2D: Memory Updates

* Sprint 2E: Memory Statistics

* Sprint 3A: Blueprint Foundation

*  Sprint 3B: Blueprint Interview Questions Foundation

*  Sprint 3C - Interview Answer Foundation

*  Sprint 3D - Interview Session Foundation

Current Sprint: 3E

Important:

* Do not modify completed Sprint 1 functionality unless explicitly requested.
* Do not modify completed Sprint 2 functionality unless explicitly requested.
* Follow existing architecture and coding patterns.
* Keep business logic inside services.
* Keep repositories persistence-only.
* Maintain clean separation between API, Service, Repository, and Database layers.

## Project Overview

NeuraEvo is a Voice-First Personal AI Employee Platform.

Users create personalized AI employees through a guided interview process.

The platform creates AI employees that can learn preferences, execute tasks, remember important information, and improve through feedback.

Current development phase is Sprint 3.

---

## Architecture Rules

Do not modify project architecture without explicit approval.

Follow the existing folder structure exactly.

Do not create new top-level folders.

Do not rename existing folders.

Repositories:

* Database access only
* No authorization
* No validation
* No business rules

Services:

* Ownership validation
* Business logic
* Domain orchestration
* Transaction boundaries

API:

* Request validation
* Dependency injection
* HTTP translation only

---

## Technology Stack

Frontend:

* React Native
* TypeScript

Backend:

* FastAPI
* Python 3.11+

Database:

* PostgreSQL
* pgvector

Storage:

* Supabase Storage

AI:

* Claude
* OpenAI Realtime

Infrastructure:

* Docker
* Nginx
* Render

---

## Development Rules

Implement only the task requested.

Do not implement future features.

Do not add unnecessary dependencies.

Keep code modular and production-ready.

Write clean, typed, maintainable code.

Do not introduce shortcuts that bypass the service layer.

Reuse existing ownership validation chains whenever possible.

---

## Current Scope

Completed Foundation:


* Authentication
* Employee Management
* Memory Engine

Current Objective:

* Employee Blueprint System
* Interview Foundation
* Blueprint Generation Foundation

Do not implement:

* Voice calls
* Realtime conversations
* Task execution
* AI autonomy
* Agent orchestration
* Workflow execution
* Embedding generation
* Semantic search
* Memory retrieval AI
* LLM decision making

These belong to future phases.

---

## Blueprint Rules

Blueprints are structured employee profiles.

Each employee may have only one blueprint.

Blueprint ownership is inherited through employee ownership.

Do not implement blueprint generation logic unless explicitly requested.

Do not implement AI-written blueprints unless explicitly requested.

---

## Memory Rules

Memory system is complete for current phase.

Existing functionality:

* Create memory
* List memories
* Filter memories
* Pagination
* Retrieve memory
* Update memory
* Delete memory
* Memory statistics

Do not redesign memory architecture without approval.

---

## Code Quality

Use clear naming.

Add docstrings where useful.

Follow SOLID principles.

Keep files focused and small.

Prefer composition over large classes.

Favor reuse over duplication.

---

## Before Finishing Any Task

Check imports.

Check typing.

Check project structure.

Check ownership validation.

Check HTTP response codes.

Check Swagger documentation.

Do not leave TODO code unless requested.

Provide:

1. Files created
2. Files modified
3. Endpoint behavior
4. Verification results
5. Architectural decisions
6. Local testing instructions
