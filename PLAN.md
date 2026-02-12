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
- [x] Encryption utility for token storage (Fernet)
- [x] OAuth callback handlers for all 5 integrations
- [x] Token refresh middleware/utility
- [x] Settings API to check connection status
- [x] OAuth app config via Settings UI (store in DB)
- [x] Manual token fallback for all integrations

### 2.2 Google Integration (Calendar, Docs, Drive)
- [x] OAuth 2.0 flow with Calendar, Docs, Drive scopes
- [x] Calendar client: list events, get event details, recurring event handling
- [x] Docs client: create doc, read doc content (template fetcher), update doc
- [x] Drive client: create file in folder, list folder contents
- [ ] Template caching and periodic re-fetch
- **Note:** Blocked on Buildkite admin approval for Google OAuth app

### 2.3 Slack Integration (Two Workspaces)
- [x] OAuth 2.0 flow for internal workspace
- [x] OAuth 2.0 flow for external workspace
- [x] Slack client: post message, read channel history, get user info
- [x] Channel/user search (find_channel_by_name, find_user_by_name)
- [x] Socket Mode event listener for internal workspace (new threads)
- [x] Socket Mode event listener for external workspace (@mentions)
- [x] Message formatting (Slack Block Kit)
- [x] Slack App manifest generation

### 2.4 Linear Integration
- [x] OAuth 2.0 flow
- [x] GraphQL client: create issue, update issue, list project issues
- [x] Project/team/user queries and search
- [x] Issue template with customer defaults (team, assignee, labels, priority)

### 2.5 Notion Integration
- [x] OAuth 2.0 flow
- [x] API client with rate limiting (3 req/s)
- [x] Update page properties (health status, summary, dates)
- [x] Read page content
- [x] Page title extraction

---

## Phase 3: Orchestration Engine (Task 7)
**Goal:** Workflow engine, scheduler, content generation working.

### 3.1 Workflow Engine
- [x] Approval state machine: DRAFT → IN_REVIEW → APPROVED → PUBLISHED → ARCHIVED (+ REJECTED)
- [x] Workflow executor with step tracking
- [x] Compensation logic for partial failures
- [x] Retry with idempotency (don't re-post on retry)
- [x] Publish side effects (Slack posting, Linear ticket creation, Notion update)

### 3.2 Content Generation
- [x] Claude API integration for content generation (claude-sonnet-4-5-20250929)
- [x] Agenda generation from context (tickets, past notes, Slack activity)
- [x] Meeting notes generation from transcript
- [x] Action item extraction
- [x] Health assessment generation
- [x] Template-aware generation (fetches Google Doc templates)

### 3.3 Transcript Processing
- [x] Text paste ingestion
- [x] File upload parsing (txt, pdf, docx)
- [x] Calendar event matching for transcript → meeting linkage

### 3.4 Scheduler
- [x] APScheduler with PostgreSQL job store
- [x] Daily calendar scan job (T-2 agenda trigger)
- [x] Workflow processing job (every 30s)
- [x] Integration health check job (hourly)

---

## Phase 4: React Frontend (Task 8)
**Goal:** Full web console with all pages functional.

### 4.1 App Shell
- [x] React 19 + TypeScript + Vite setup
- [x] Routing (React Router, 11 routes)
- [x] Layout with sidebar navigation (mobile responsive)
- [x] API client with error handling (Axios, useApi hook)
- [ ] Toast notifications (not yet implemented)

### 4.2 Pages
- [x] Dashboard (stats, upcoming meetings, recent activity)
- [x] Customer Management (CRUD with ResolvableField integration)
- [x] Transcript Upload (file upload + paste, drag-and-drop)
- [x] Approval Queue (filters, preview, approve/reject/publish, copy)
- [x] Agendas & Notes (browse and preview)
- [x] Linear Tickets (table with bulk approve)
- [x] Slack Mentions (list, create ticket, mark handled)
- [x] Health Dashboard (RAG status grid, history timeline)
- [x] Settings (OAuth wizard, admin templates, manual tokens, template config, scheduler)

---

## Phase 5: End-to-End Integration & Testing
**Goal:** Single customer workflow working end-to-end.

### 5.1 Integration Testing
- [ ] Test customer setup (calendar, Slack channels, Linear project, Notion page) — blocked on OAuth setup
- [ ] Agenda generation → approval → publish flow
- [ ] Transcript upload → notes generation → approval → publish flow
- [ ] Health update → approval → Notion update flow
- [ ] Slack monitoring → Linear ticket creation flow

### 5.2 Unit & API Testing
- [x] Unit tests — encryption (11 tests)
- [x] Unit tests — state machine (28 tests)
- [x] Unit tests — transcript parser (10 tests)
- [x] API tests — customers CRUD (17 tests)
- [x] API tests — approvals lifecycle (27 tests)
- [x] API tests — dashboard (7 tests)
- [x] API tests — integrations (10 tests)
- [x] URL parser verification tests
- [ ] Integration client tests (mocked)
- [ ] Frontend component tests

**Total: 130 tests, all passing**

## Phase 6: Usability Improvements (Added)
- [x] Friendly name/URL resolution for customer fields (ResolvableField)
- [x] URL parsing for Linear, Notion, Google Docs
- [x] Slack channel/user search
- [x] Linear project/team/user search
- [x] Google Doc template URL validation
- [x] Clean error messages for disconnected integrations
- [x] Google OAuth admin request template in Settings

## Phase 7: Documentation (Added)
- [x] ARCHITECTURE.md — full system architecture with diagrams
- [x] AUTH.md — OAuth setup guide for all integrations
- [x] DECISIONS.md — 12 architectural decision records
- [x] TASKS.md — comprehensive task tracker with next steps
- [x] PLAN.md — this implementation plan (updated)

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
