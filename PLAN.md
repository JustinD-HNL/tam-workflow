# TAM Workflow — Implementation Plan

## Overview
Build an automated workflow system for a Buildkite TAM. Local Docker deployment, single user, FastAPI backend, React frontend, PostgreSQL database.

---

## Phase 1: Foundation (Tasks 1-4)
**Goal:** Project scaffolding, database, and basic backend running in Docker.

### 1.1 Project Setup
- [x] Create planning documents (PLAN.md, TASKS.md, DECISIONS.md, AUTH.md)
- [x] Create conda environment (tam-workflow, Python 3.11+)
- [x] Set up pyproject.toml with pinned dependencies
- [x] Create full directory structure per CLAUDE.md
- [x] Create .env.example with all required variables
- [x] Initialize git repository

### 1.2 Docker Infrastructure
- [x] Dockerfile for FastAPI backend
- [x] docker-compose.yml (backend, web, db, scheduler)
- [x] docker-compose.dev.yml for development
- [x] PostgreSQL service with volume persistence

### 1.3 Database Models & Migrations
- [x] SQLAlchemy models: Customer, Workflow, ApprovalItem, IntegrationCredential, ActionItem, SlackMention, MeetingDocument
- [x] Alembic setup with initial migration
- [x] Database connection pooling and session management

### 1.4 Core FastAPI App
- [x] FastAPI application scaffold with CORS, middleware
- [x] Health check endpoint
- [x] Database session dependency injection
- [x] Basic error handling middleware

---

## Phase 2: Authentication & Integration Layer (Tasks 5-6)
**Goal:** All OAuth flows working, integration clients operational.

### 2.1 OAuth Infrastructure
- [ ] Encryption utility for token storage (Fernet)
- [ ] OAuth callback handlers for all 5 integrations
- [ ] Token refresh middleware/utility
- [ ] Settings API to check connection status

### 2.2 Google Integration (Calendar, Docs, Drive)
- [ ] OAuth 2.0 flow with Calendar, Docs, Drive scopes
- [ ] Calendar client: list events, get event details, recurring event handling
- [ ] Docs client: create doc, read doc content (template fetcher), update doc
- [ ] Drive client: create file in folder, list folder contents
- [ ] Template caching and periodic re-fetch

### 2.3 Slack Integration (Two Workspaces)
- [ ] OAuth 2.0 flow for internal workspace
- [ ] OAuth 2.0 flow for external workspace
- [ ] Slack client: post message, read channel history, get user info
- [ ] Socket Mode event listener for internal workspace (new threads)
- [ ] Socket Mode event listener for external workspace (@mentions)
- [ ] Message formatting (Slack Block Kit)

### 2.4 Linear Integration
- [ ] OAuth 2.0 flow
- [ ] GraphQL client: create issue, update issue, list project issues
- [ ] Issue template with customer defaults (team, assignee, labels, priority)

### 2.5 Notion Integration
- [ ] OAuth 2.0 flow
- [ ] API client with rate limiting (3 req/s)
- [ ] Update page properties (health status, summary, dates)
- [ ] Read page content

---

## Phase 3: Orchestration Engine (Task 7)
**Goal:** Workflow engine, scheduler, content generation working.

### 3.1 Workflow Engine
- [ ] Approval state machine: DRAFT → IN_REVIEW → APPROVED → PUBLISHED → ARCHIVED (+ REJECTED)
- [ ] Workflow executor with step tracking
- [ ] Compensation logic for partial failures
- [ ] Retry with idempotency (don't re-post on retry)

### 3.2 Content Generation
- [ ] Claude API integration for content generation
- [ ] Agenda generation from context (tickets, past notes, Slack activity)
- [ ] Meeting notes generation from transcript
- [ ] Action item extraction
- [ ] Health assessment generation
- [ ] Template-aware generation (fetches Google Doc templates)

### 3.3 Transcript Processing
- [ ] Text paste ingestion
- [ ] File upload parsing (txt, pdf, docx)
- [ ] Calendar event matching for transcript → meeting linkage

### 3.4 Scheduler
- [ ] APScheduler with PostgreSQL job store
- [ ] Daily calendar scan job (T-2 agenda trigger)
- [ ] Template re-fetch job
- [ ] Integration health check job

---

## Phase 4: React Frontend (Task 8)
**Goal:** Full web console with all pages functional.

### 4.1 App Shell
- [ ] React + TypeScript + Vite setup
- [ ] Routing (React Router)
- [ ] Layout with sidebar navigation
- [ ] API client with error handling
- [ ] Toast notifications

### 4.2 Pages
- [ ] Dashboard (upcoming meetings, pending approvals, activity feed)
- [ ] Customer Management (CRUD, per-customer config)
- [ ] Transcript Upload (file upload + paste, customer/date selection)
- [ ] Approval Queue (list, preview, edit, approve/reject)
- [ ] Agendas & Notes (browse, edit, publish)
- [ ] Linear Tickets (view, edit, approve, bulk actions)
- [ ] Slack Mentions (list, create ticket, mark handled)
- [ ] Health Dashboard (RAG status grid, pending updates, history)
- [ ] Settings (OAuth wizard, template links, scheduler controls)

---

## Phase 5: End-to-End Integration & Testing
**Goal:** Single customer workflow working end-to-end.

### 5.1 Integration Testing
- [ ] Test customer setup (calendar, Slack channels, Linear project, Notion page)
- [ ] Agenda generation → approval → publish flow
- [ ] Transcript upload → notes generation → approval → publish flow
- [ ] Health update → approval → Notion update flow
- [ ] Slack monitoring → Linear ticket creation flow

### 5.2 Testing
- [ ] Unit tests for integration clients (mocked)
- [ ] Unit tests for workflow engine
- [ ] API endpoint tests
- [ ] Frontend component tests (basic)

---

## Implementation Order (Critical Path)
1. **Foundation** — can't build anything without DB and FastAPI scaffold
2. **OAuth & Auth** — every integration depends on tokens working
3. **Integration Clients** — workflows depend on being able to talk to services
4. **Workflow Engine** — orchestration ties integrations together
5. **Content Generation** — Claude API for the "smart" parts
6. **Frontend** — the TAM-facing approval and config interface
7. **Scheduler** — automated triggers once manual flows work
8. **End-to-End Testing** — validate the complete loop

---

## Key Technical Decisions
See DECISIONS.md for detailed rationale on each choice.
