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
| 1.2 | Create conda environment + pyproject.toml | ✅ | Python 3.11, all deps installed |
| 1.3 | Create project directory structure | ✅ | Per CLAUDE.md spec |
| 1.4 | Create .env.example | ✅ | |
| 1.5 | Docker Compose (prod + dev) | ✅ | |
| 1.6 | Dockerfile for backend | ✅ | |
| 1.7 | SQLAlchemy models | ✅ | 8 tables, async engine |
| 1.8 | Alembic migrations setup | ✅ | 2 migrations (initial + oauth_app_configs) |
| 1.9 | FastAPI app scaffold | ✅ | 11 route modules, CORS, lifespan |
| 1.10 | Database session management | ✅ | Async sessions with commit/rollback |

## Phase 2: Auth & Integration Layer

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Token encryption utility (Fernet) | ✅ | |
| 2.2 | Google OAuth flow + callback | ✅ | |
| 2.3 | Google Calendar client | ✅ | With retry logic |
| 2.4 | Google Docs client | ✅ | Template fetching included |
| 2.5 | Google Drive client | ✅ | Folder operations |
| 2.6 | Slack OAuth flow (internal) | ✅ | |
| 2.7 | Slack OAuth flow (external) | ✅ | |
| 2.8 | Slack client (messages, channels) | ✅ | Block Kit formatting, channel/user search |
| 2.9 | Slack Socket Mode listeners | ✅ | Both workspaces |
| 2.10 | Linear OAuth flow | ✅ | |
| 2.11 | Linear GraphQL client | ✅ | Full CRUD + project/team/user queries |
| 2.12 | Notion OAuth flow | ✅ | |
| 2.13 | Notion API client (rate-limited) | ✅ | 3 req/s throttling, health updates |
| 2.14 | Integration status API | ✅ | Manual token fallback included |
| 2.15 | OAuth app config via Settings UI | ✅ | Store client ID/secret in DB |
| 2.16 | Slack App manifest generation | ✅ | For both workspaces |
| 2.17 | Integration verify endpoint | ✅ | Validates stored tokens against live APIs |

## Phase 3: Orchestration

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Approval state machine | ✅ | DRAFT→IN_REVIEW→APPROVED→PUBLISHED→ARCHIVED |
| 3.2 | Workflow executor | ✅ | With step tracking and error handling |
| 3.3 | Claude content generation | ✅ | Agendas, notes, health assessments |
| 3.4 | Transcript parser (txt, pdf, docx) | ✅ | |
| 3.5 | Agenda generation workflow | ✅ | |
| 3.6 | Meeting notes generation workflow | ✅ | With action item extraction |
| 3.7 | Health update workflow | ✅ | |
| 3.8 | Slack monitoring workflow | ✅ | Socket Mode handlers |
| 3.9 | APScheduler setup | ✅ | Daily calendar scan, workflow processing, health checks |

## Phase 4: Frontend

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | React + Vite + TypeScript setup | ✅ | TailwindCSS, React Router |
| 4.2 | App shell + routing + layout | ✅ | Sidebar navigation, mobile responsive |
| 4.3 | Dashboard page | ✅ | Stats, upcoming meetings, recent activity |
| 4.4 | Customer Management page | ✅ | CRUD + config form |
| 4.5 | Transcript Upload page | ✅ | File upload + paste, drag-and-drop |
| 4.6 | Approval Queue page | ✅ | Filters, approve/reject/publish, copy |
| 4.7 | Agendas & Notes page | ✅ | Browse and preview |
| 4.8 | Linear Tickets page | ✅ | Table with bulk approve |
| 4.9 | Slack Mentions page | ✅ | Create ticket, mark handled |
| 4.10 | Health Dashboard page | ✅ | RAG status grid, history |
| 4.11 | Settings page (OAuth wizard) | ✅ | Connection status + manual tokens + admin templates |

## Phase 5: Polish & Usability

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Friendly name/URL resolution for customer form | ✅ | ResolvableField component, 7 resolve endpoints |
| 5.2 | URL parsing utilities | ✅ | Linear, Notion, Google Docs, Slack name normalization |
| 5.3 | Integration client search methods | ✅ | Slack channel/user search, Linear project/team/user search |
| 5.4 | Google Doc template validation | ✅ | ResolvableField on Settings template URLs |
| 5.5 | Clean error messages for disconnected integrations | ✅ | RetryError unwrapping |
| 5.6 | Google OAuth admin request template | ✅ | Setup instructions in Settings page |

## Phase 6: Testing

| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Unit tests — encryption | ✅ | 11 tests |
| 6.2 | Unit tests — transcript parser | ✅ | 10 tests |
| 6.3 | Unit tests — state machine | ✅ | 28 tests |
| 6.4 | API tests — customers | ✅ | 17 tests |
| 6.5 | API tests — approvals | ✅ | 27 tests |
| 6.6 | API tests — dashboard | ✅ | 7 tests |
| 6.7 | API tests — integrations | ✅ | 10 tests |
| 6.8 | URL parser unit tests | ✅ | Inline verification (all parsers) |
| 6.9 | Docker deployment verification | ✅ | All 3 services healthy, all endpoints tested |
| 6.10 | End-to-end workflow tests | ⬜ | |
| 6.11 | Frontend smoke tests (Playwright) | ⬜ | |
| 6.12 | Integration client tests (mocked) | ⬜ | |

## Phase 7: Documentation

| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | ARCHITECTURE.md (system design, diagrams) | ✅ | Full architecture with ASCII diagrams |
| 7.2 | AUTH.md (OAuth setup guide) | ✅ | All 5 integrations + Claude |
| 7.3 | DECISIONS.md (architectural decisions) | ✅ | 10 ADRs |
| 7.4 | PLAN.md (implementation plan) | ✅ | |
| 7.5 | TASKS.md (this file) | ✅ | |

---

## Current Status Summary

**130 backend tests passing. All Docker services healthy. Core functionality complete.**

### What's Working
- Full Docker Compose deployment (backend, frontend, PostgreSQL)
- Customer CRUD with friendly name/URL resolution
- All 5 integration OAuth flows (Google, Slack x2, Linear, Notion)
- Integration setup wizard with status indicators
- Manual token fallback for all integrations
- Approval state machine and workflow engine
- Claude-powered content generation (agendas, notes, health)
- Transcript upload/paste with PDF and DOCX support
- APScheduler with PostgreSQL-backed job store
- Frontend with 10 pages and sidebar navigation
- Linear integration connected and resolving projects

### What's Not Yet Connected (awaiting OAuth setup)
- Google (Calendar, Docs, Drive) — needs admin approval for OAuth app
- Slack Internal — needs Slack App created and installed
- Slack External — needs Slack App created and installed
- Notion — needs integration created and connected

---

## Next Steps

### Immediate (Integration Setup)
| # | Task | Status | Notes |
|---|------|--------|-------|
| N.1 | Request Google OAuth app approval from Buildkite admin | ⬜ | Admin template provided in Settings |
| N.2 | Create Slack App for internal workspace | ⬜ | Manifest available in Settings |
| N.3 | Create Slack App for external workspace | ⬜ | Manifest available in Settings |
| N.4 | Create Notion integration and connect | ⬜ | |
| N.5 | Connect Google and verify Calendar/Docs/Drive access | ⬜ | Blocked by N.1 |
| N.6 | Set up first customer (e.g., "Aurora") end-to-end | ⬜ | Blocked by N.1–N.4 |

### Short-Term (Feature Completion)
| # | Task | Status | Notes |
|---|------|--------|-------|
| N.7 | Test full agenda generation workflow end-to-end | ⬜ | Needs calendar + docs connected |
| N.8 | Test full meeting notes workflow end-to-end | ⬜ | Needs all integrations |
| N.9 | Test health update → Notion publish flow | ⬜ | Needs Notion connected |
| N.10 | Test Slack monitoring (Socket Mode) both workspaces | ⬜ | Needs Slack apps |
| N.11 | Rich text editor for approval items | ⬜ | Currently plain text preview |
| N.12 | Google Doc creation on agenda/notes publish | ⬜ | Needs Drive connected |

### Medium-Term (Hardening)
| # | Task | Status | Notes |
|---|------|--------|-------|
| N.13 | End-to-end workflow tests (automated) | ⬜ | |
| N.14 | Frontend smoke tests (Playwright/Cypress) | ⬜ | |
| N.15 | Integration client unit tests with mocks | ⬜ | |
| N.16 | Token refresh/renewal testing | ⬜ | |
| N.17 | Error recovery and retry UX improvements | ⬜ | |
| N.18 | Notification/toast system in frontend | ⬜ | |

### Long-Term (Enhancements)
| # | Task | Status | Notes |
|---|------|--------|-------|
| N.19 | Avoma API integration (replace manual transcript) | ⬜ | |
| N.20 | Google Docs embedded editor in approval view | ⬜ | |
| N.21 | Bulk customer import | ⬜ | |
| N.22 | Slack Events API (alternative to Socket Mode) | ⬜ | For reliability |
| N.23 | Dashboard charts/graphs | ⬜ | |
| N.24 | Export/reporting features | ⬜ | |
