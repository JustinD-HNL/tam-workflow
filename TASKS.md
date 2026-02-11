# Task Tracker

## Legend
- ⬜ Not Started
- 🔄 In Progress
- ✅ Complete
- ❌ Blocked

---

## Phase 1: Foundation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Create planning docs (PLAN, TASKS, DECISIONS, AUTH) | ✅ | |
| 1.2 | Create conda environment + pyproject.toml | 🔄 | Python 3.11+ |
| 1.3 | Create project directory structure | 🔄 | Per CLAUDE.md spec |
| 1.4 | Create .env.example | 🔄 | |
| 1.5 | Docker Compose (prod + dev) | 🔄 | |
| 1.6 | Dockerfile for backend | 🔄 | |
| 1.7 | SQLAlchemy models | 🔄 | |
| 1.8 | Alembic migrations setup | ⬜ | |
| 1.9 | FastAPI app scaffold | 🔄 | |
| 1.10 | Database session management | ⬜ | |

## Phase 2: Auth & Integration Layer

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Token encryption utility (Fernet) | ⬜ | |
| 2.2 | Google OAuth flow + callback | ⬜ | |
| 2.3 | Google Calendar client | ⬜ | |
| 2.4 | Google Docs client | ⬜ | |
| 2.5 | Google Drive client | ⬜ | |
| 2.6 | Slack OAuth flow (internal) | ⬜ | |
| 2.7 | Slack OAuth flow (external) | ⬜ | |
| 2.8 | Slack client (messages, channels) | ⬜ | |
| 2.9 | Slack Socket Mode listeners | ⬜ | |
| 2.10 | Linear OAuth flow | ⬜ | |
| 2.11 | Linear GraphQL client | ⬜ | |
| 2.12 | Notion OAuth flow | ⬜ | |
| 2.13 | Notion API client (rate-limited) | ⬜ | |
| 2.14 | Integration status API | ⬜ | |

## Phase 3: Orchestration

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Approval state machine | ⬜ | |
| 3.2 | Workflow executor | ⬜ | |
| 3.3 | Claude content generation | ⬜ | |
| 3.4 | Transcript parser (txt, pdf, docx) | ⬜ | |
| 3.5 | Agenda generation workflow | ⬜ | |
| 3.6 | Meeting notes generation workflow | ⬜ | |
| 3.7 | Health update workflow | ⬜ | |
| 3.8 | Slack monitoring workflow | ⬜ | |
| 3.9 | APScheduler setup | ⬜ | |

## Phase 4: Frontend

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | React + Vite + TypeScript setup | ⬜ | |
| 4.2 | App shell + routing + layout | ⬜ | |
| 4.3 | Dashboard page | ⬜ | |
| 4.4 | Customer Management page | ⬜ | |
| 4.5 | Transcript Upload page | ⬜ | |
| 4.6 | Approval Queue page | ⬜ | |
| 4.7 | Agendas & Notes page | ⬜ | |
| 4.8 | Linear Tickets page | ⬜ | |
| 4.9 | Slack Mentions page | ⬜ | |
| 4.10 | Health Dashboard page | ⬜ | |
| 4.11 | Settings page (OAuth wizard) | ⬜ | |

## Phase 5: Testing & Polish

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Unit tests — integration clients | ⬜ | |
| 5.2 | Unit tests — workflow engine | ⬜ | |
| 5.3 | API endpoint tests | ⬜ | |
| 5.4 | End-to-end workflow test | ⬜ | |
| 5.5 | Frontend smoke tests | ⬜ | |
