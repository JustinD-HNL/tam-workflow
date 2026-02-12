# TAM Workflow — Architecture Document

## Overview

The TAM Workflow system is an automated workflow platform for a Buildkite Technical Account Manager. It captures meeting transcripts, generates agendas and notes using AI, updates customer health tracking, manages tasks in Linear, and coordinates across Slack, Google Calendar, Google Docs, and Notion — all with a human-in-the-loop approval workflow.

It runs locally on the TAM's laptop via Docker Compose. Single-user, no multi-tenancy.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Docker Compose Network                             │
│                                                                             │
│  ┌──────────────┐     ┌──────────────────────────────┐    ┌──────────────┐ │
│  │              │     │         Backend (FastAPI)     │    │              │ │
│  │   Frontend   │     │                              │    │  PostgreSQL  │ │
│  │   (React)    │────▶│  ┌────────┐  ┌───────────┐  │───▶│    16        │ │
│  │              │     │  │  API   │  │ Scheduler  │  │    │              │ │
│  │  nginx:80    │     │  │ Routes │  │(APScheduler│  │    │  :5432       │ │
│  │  :3001       │     │  └────────┘  └───────────┘  │    │  :5433       │ │
│  │              │     │  ┌────────┐  ┌───────────┐  │    └──────────────┘ │
│  └──────────────┘     │  │Orchestr│  │Integration│  │                     │
│                       │  │ ator   │  │  Clients  │  │                     │
│                       │  └────────┘  └───────────┘  │                     │
│                       │  ┌────────┐                  │                     │
│                       │  │Content │  uvicorn:8000    │                     │
│                       │  │  Gen   │  :8001           │                     │
│                       │  └────────┘                  │                     │
│                       └──────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────────┐
                    ▼               ▼                   ▼
           ┌──────────────┐ ┌─────────────┐   ┌──────────────┐
           │   External   │ │  External   │   │   External   │
           │   Services   │ │  Services   │   │   Services   │
           │              │ │             │   │              │
           │ Google APIs  │ │ Slack APIs  │   │ Linear API   │
           │ - Calendar   │ │ - Internal  │   │ (GraphQL)    │
           │ - Docs       │ │ - External  │   │              │
           │ - Drive      │ │ - Socket    │   │ Notion API   │
           │              │ │   Mode      │   │ (REST)       │
           └──────────────┘ └─────────────┘   └──────────────┘
                                                      │
                                                      ▼
                                              ┌──────────────┐
                                              │  Claude API   │
                                              │  (Anthropic)  │
                                              │  Content Gen  │
                                              └──────────────┘
```

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Primary language |
| FastAPI | 0.115.6 | Web framework (async) |
| SQLAlchemy | 2.0.36 | ORM (async mode) |
| Alembic | 1.14.1 | Database migrations |
| asyncpg | — | Async PostgreSQL driver |
| Pydantic | 2.x | Data validation, settings |
| APScheduler | 3.10.4 | Task scheduling (PostgreSQL-backed) |
| Anthropic SDK | 0.42.0 | Claude AI content generation |
| httpx | 0.28.1 | Async HTTP client (Linear, Notion) |
| slack-sdk | 3.34.0 | Slack Web API + Socket Mode |
| google-api-python-client | 2.160.0 | Google Calendar/Docs/Drive |
| google-auth-oauthlib | 1.2.1 | Google OAuth 2.0 |
| cryptography | 44.0.0 | Fernet encryption for tokens |
| tenacity | 9.0.0 | Retry with exponential backoff |
| structlog | 24.4.0 | Structured logging |
| python-docx | — | DOCX transcript parsing |
| PyPDF2 | — | PDF transcript parsing |
| uvicorn | 0.34.0 | ASGI server |

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| TypeScript | ~5.9.3 | Primary language |
| React | 19.2 | UI framework |
| Vite | 7.3.1 | Build tool / dev server |
| Tailwind CSS | 4.1.18 | Utility-first styling |
| React Router | 6.30.3 | Client-side routing |
| Axios | 1.13.5 | HTTP client |
| Headless UI | 2.2.9 | Accessible UI primitives |
| Heroicons | 2.2.0 | Icon library |
| date-fns | 4.1.0 | Date formatting |
| ESLint | 9.39.1 | Linting |

### Infrastructure

| Technology | Version | Purpose |
|-----------|---------|---------|
| Docker | — | Containerization |
| Docker Compose | — | Multi-service orchestration |
| PostgreSQL | 16 (Alpine) | Primary database |
| nginx | — | Frontend web server + reverse proxy |
| ngrok/cloudflared | — | Tunnel for OAuth callbacks (optional) |

### Testing

| Technology | Purpose |
|-----------|---------|
| pytest + pytest-asyncio | Backend test runner |
| SQLite + aiosqlite | In-memory test database |
| httpx AsyncClient | API endpoint testing |
| ruff | Python linting |
| mypy | Type checking |

---

## Component Architecture

### Request Flow Diagram

```
Browser (localhost:3001)
    │
    ▼
┌─────────┐     ┌──────────────────────────────────────────┐
│  nginx   │     │              FastAPI Backend              │
│          │     │                                          │
│ /api/* ──┼────▶│  API Routes ──▶ Service Layer            │
│ /auth/*──┼────▶│     │              │                     │
│ /* ──────┼──┐  │     ▼              ▼                     │
└─────────┘  │  │  Pydantic      SQLAlchemy                │
             │  │  Schemas       Models                     │
             │  │     │              │                      │
             │  │     ▼              ▼                      │
             │  │  Response      PostgreSQL                 │
             │  └──────────────────────────────────────────┘
             │
             ▼
        React SPA
     (static files)
```

### Backend Module Structure

```
src/
├── api/                        # HTTP layer
│   ├── main.py                 # FastAPI app, CORS, lifespan, router registration
│   ├── schemas.py              # Pydantic request/response models
│   └── routes/                 # 11 route modules
│       ├── auth.py             # OAuth flows (Google, Slack x2, Linear, Notion)
│       ├── customers.py        # Customer CRUD
│       ├── approvals.py        # Approval queue + state transitions
│       ├── transcripts.py      # Upload/paste transcripts
│       ├── workflows.py        # Workflow management
│       ├── integrations.py     # Integration config, status, tokens
│       ├── resolve.py          # Name/URL → ID resolution
│       ├── health.py           # Customer health updates
│       ├── slack.py            # Slack mention management
│       ├── linear.py           # Linear ticket approval items
│       └── dashboard.py        # Dashboard aggregation
│
├── models/                     # Data layer
│   ├── base.py                 # SQLAlchemy base, UUID + timestamp mixins
│   ├── database.py             # Async engine, session factory, get_db()
│   ├── customer.py             # Customer model (integrations, health, cadence)
│   ├── workflow.py             # Workflow, ApprovalItem, ActionItem models
│   ├── integration.py          # IntegrationCredential, MeetingDocument, SlackMention
│   └── oauth_config.py         # OAuthAppConfig (UI-managed credentials)
│
├── integrations/               # External service clients
│   ├── base.py                 # IntegrationClient base class (token retrieval)
│   ├── encryption.py           # Fernet encrypt/decrypt for token storage
│   ├── oauth_helpers.py        # Credential resolution (DB → .env fallback)
│   ├── url_parsers.py          # URL/name parsing for resolution endpoints
│   ├── google/
│   │   ├── calendar.py         # Google Calendar client (event listing, matching)
│   │   ├── docs.py             # Google Docs client (create, read, templates)
│   │   └── drive.py            # Google Drive client (folder operations)
│   ├── slack/
│   │   ├── client.py           # Slack Web API (dual workspace, Block Kit)
│   │   └── socket_handler.py   # Socket Mode for real-time events
│   ├── linear/
│   │   └── client.py           # Linear GraphQL API (issues, projects, teams)
│   └── notion/
│       └── client.py           # Notion REST API (rate-limited, health updates)
│
├── orchestrator/               # Workflow engine
│   ├── state_machine.py        # Approval state transitions
│   ├── workflows.py            # Workflow executors + publish side effects
│   └── scheduler.py            # APScheduler jobs (calendar scan, processing)
│
├── content/                    # AI content generation
│   └── generator.py            # Claude API (agendas, notes, health assessments)
│
├── transcript/                 # File parsing
│   └── parser.py               # PDF and DOCX transcript parsing
│
└── config/                     # App configuration
    ├── settings.py             # Pydantic Settings (from .env)
    └── logging.py              # Structlog configuration
```

### Frontend Module Structure

```
web/src/
├── main.tsx                    # React entry point
├── App.tsx                     # Router with 11 routes
├── index.css                   # Tailwind CSS imports
│
├── layouts/
│   └── AppLayout.tsx           # Sidebar navigation, mobile menu, <Outlet />
│
├── pages/                      # 10 page components
│   ├── Dashboard.tsx           # Stats, upcoming meetings, recent activity
│   ├── Customers.tsx           # Customer table with health + integration dots
│   ├── CustomerForm.tsx        # Create/edit with ResolvableField components
│   ├── TranscriptUpload.tsx    # File upload + paste, customer/date selection
│   ├── ApprovalQueue.tsx       # Filter, preview, approve/reject/publish
│   ├── Documents.tsx           # Agendas and meeting notes browser
│   ├── LinearTickets.tsx       # Ticket table with bulk approve
│   ├── SlackMentions.tsx       # Mention list with create-ticket action
│   ├── HealthDashboard.tsx     # RAG status grid, health history
│   └── Settings.tsx            # Integration wizard, templates, scheduler
│
├── components/                 # Shared components
│   ├── ResolvableField.tsx     # Input with live API validation/resolution
│   ├── LoadingSpinner.tsx      # Loading states
│   ├── ErrorAlert.tsx          # Error display with retry
│   ├── EmptyState.tsx          # Empty list placeholder
│   └── ConfirmDialog.tsx       # Modal confirmation (Headless UI)
│
├── hooks/
│   └── useApi.ts               # useApi<T> + usePolling<T> data fetching hooks
│
├── services/
│   └── api.ts                  # Axios API client (all backend endpoints)
│
├── types/
│   └── index.ts                # TypeScript interfaces and enums
│
└── utils/
    └── index.ts                # Formatting, color helpers, classNames
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────┐      ┌───────────────────────┐
│     customers       │      │      workflows         │
├─────────────────────┤      ├───────────────────────┤
│ id (UUID PK)        │◄──┐  │ id (UUID PK)          │
│ name                │   │  │ workflow_type (enum)   │
│ slug (unique)       │   │  │ status (enum)          │
│ linear_project_id   │   ├──│ customer_id (FK)       │
│ slack_internal_ch   │   │  │ context (JSONB)        │
│ slack_external_ch   │   │  │ steps_completed (JSONB)│
│ notion_page_id      │   │  │ error_message          │
│ google_cal_pattern  │   │  │ started_at, finished_at│
│ google_docs_folder  │   │  └───────────────────────┘
│ tam_slack_user_id   │   │
│ primary_contacts    │   │  ┌───────────────────────┐
│   (JSONB)           │   │  │   approval_items       │
│ cadence (enum)      │   │  ├───────────────────────┤
│ health_status (enum)│   │  │ id (UUID PK)          │
│ last_health_update  │   ├──│ customer_id (FK)       │
│ linear_task_defaults│   │  │ workflow_id (FK) ──────┼──▶ workflows
│   (JSONB)           │   │  │ item_type (enum)       │
│ created_at          │   │  │ status (enum)          │
│ updated_at          │   │  │ title                  │
└─────────────────────┘   │  │ content (Text)         │
                          │  │ metadata_json (JSONB)  │
┌─────────────────────┐   │  │ google_doc_id/url      │
│  meeting_documents  │   │  │ linear_issue_id        │
├─────────────────────┤   │  │ published_* (booleans) │
│ id (UUID PK)        │   │  │ meeting_date           │
│ customer_id (FK) ───┼───┤  └───────────────────────┘
│ document_type       │   │           │
│ title               │   │           ▼
│ content (Text)      │   │  ┌───────────────────────┐
│ meeting_date        │   │  │    action_items        │
│ calendar_event_id   │   │  ├───────────────────────┤
│ google_doc_id/url   │   │  │ id (UUID PK)          │
└─────────────────────┘   │  │ approval_item_id (FK)  │
                          │  │ title, description     │
┌─────────────────────┐   │  │ assignee, priority     │
│   slack_mentions    │   │  │ status                 │
├─────────────────────┤   │  │ linear_issue_id/url    │
│ id (UUID PK)        │   │  └───────────────────────┘
│ customer_id (FK) ───┼───┘
│ workspace           │      ┌───────────────────────┐
│ channel_id/name     │      │integration_credentials│
│ message_ts/thread   │      ├───────────────────────┤
│ user_id/name        │      │ id (UUID PK)          │
│ message_text        │      │ integration_type (enum)│ unique
│ permalink           │      │ status (enum)          │
│ handled (bool)      │      │ access_token (encrypted│
│ linear_issue_id     │      │ refresh_token (encrypt)│
└─────────────────────┘      │ token_type, scopes     │
                             │ expires_at             │
┌─────────────────────┐      │ last_verified          │
│  oauth_app_configs  │      └───────────────────────┘
├─────────────────────┤
│ integration_type PK │
│ client_id (encrypted│
│ client_secret (encr)│
│ extra_config (encr) │
└─────────────────────┘
```

### Database Enums

| Enum | Values |
|------|--------|
| `cadence` | weekly, biweekly, monthly |
| `health_status` | green, yellow, red |
| `workflow_type` | agenda_generation, meeting_notes, health_update, slack_monitoring |
| `workflow_status` | pending, running, completed, failed |
| `approval_item_type` | agenda, meeting_notes, health_update, linear_ticket |
| `approval_status` | draft, in_review, approved, published, archived, rejected |
| `integration_type` | google, slack_internal, slack_external, linear, notion |
| `integration_status` | connected, disconnected, expired |

---

## Workflow Engine

### Approval State Machine

```
                    ┌──────────┐
          ┌────────▶│  DRAFT   │◄────────────────────┐
          │         └──────────┘                      │
          │           │      │                        │
          │    submit │      │ approve                │
          │           ▼      ▼                        │
          │     ┌──────────┐  ┌──────────┐            │
          │     │IN_REVIEW │  │          │            │
          │     └──────────┘  │          │            │
          │       │      │    │          │            │
          │approve│ reject│   │          │            │
          │       ▼      │    │          │            │
          │  ┌──────────┐│   │          │            │
          │  │ APPROVED ││   │          │  (edit +   │
          │  └──────────┘│   │          │  resubmit) │
          │       │      │    │          │            │
          │publish│      │    │          │            │
          │       ▼      ▼    ▼          │            │
          │  ┌──────────┐  ┌──────────┐  │            │
          │  │PUBLISHED │  │ REJECTED │──┘            │
          │  └──────────┘  └──────────┘               │
          │       │                  │                 │
          │archive│           approve│                 │
          │       ▼                  └─────────────────┘
          │  ┌──────────┐
          └──│ ARCHIVED │ (terminal)
             └──────────┘
```

### Workflow Types and Triggers

```
┌─────────────────┐    T-2 days     ┌─────────────────────────┐
│ Google Calendar  │───before call──▶│ Agenda Generation       │
│ (daily scan)    │                 │ 1. Fetch context         │
└─────────────────┘                 │ 2. Claude generates      │
                                    │ 3. Create DRAFT item     │
                                    │ 4. TAM reviews/approves  │
                                    │ 5. Post to Slack (both)  │
                                    └─────────────────────────┘

┌─────────────────┐   TAM uploads   ┌─────────────────────────┐
│ Transcript      │────or pastes───▶│ Meeting Notes Generation │
│ (web console)   │                 │ 1. Parse transcript      │
└─────────────────┘                 │ 2. Claude generates notes│
                                    │ 3. Extract action items  │
                                    │ 4. Create DRAFT item     │
                                    │ 5. TAM reviews/approves  │
                                    │ 6. Post to Slack (int)   │
                                    │ 7. Create Linear tickets │
                                    │ 8. Trigger health update │
                                    └─────────────────────────┘

┌─────────────────┐   after notes   ┌─────────────────────────┐
│ Notes Published  │───published────▶│ Health Update            │
│                  │                 │ 1. Gather context        │
└─────────────────┘                 │ 2. Claude assesses health│
                                    │ 3. Create DRAFT item     │
                                    │ 4. TAM reviews/approves  │
                                    │ 5. Update Notion page    │
                                    └─────────────────────────┘

┌─────────────────┐   real-time     ┌─────────────────────────┐
│ Slack Events    │───Socket Mode──▶│ Slack Monitoring         │
│ (both workspaces│                 │ - New thread → Linear    │
└─────────────────┘                 │ - @mention → Linear +    │
                                    │   surface in web console │
                                    └─────────────────────────┘
```

### Publishing Side Effects

| Content Type | On Publish |
|-------------|------------|
| **Agenda** | Post to internal Slack channel + external Slack channel |
| **Meeting Notes** | Post to internal Slack channel only + create Linear tickets for action items |
| **Health Update** | Update Notion customer page (status, summary, risks, opportunities) + update customer model |
| **Linear Ticket** | Create issue in Linear with customer defaults (team, assignee, labels, priority) |

---

## Integration Architecture

### Authentication Flow

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐
│  Browser  │     │   Backend    │     │  OAuth Provider  │
│ (Settings │     │  /auth/*     │     │ (Google, Slack,  │
│   page)   │     │              │     │  Linear, Notion) │
└──────────┘     └──────────────┘     └─────────────────┘
     │                  │                      │
     │  Click Connect   │                      │
     ├─────────────────▶│                      │
     │                  │  Redirect to OAuth    │
     │◀─────────────────├─────────────────────▶│
     │  OAuth Login     │                      │
     ├──────────────────┼─────────────────────▶│
     │                  │   Callback + code     │
     │                  │◀─────────────────────┤
     │                  │   Exchange for tokens  │
     │                  ├─────────────────────▶│
     │                  │   access + refresh    │
     │                  │◀─────────────────────┤
     │                  │                      │
     │                  │  Encrypt + store in DB│
     │                  │  ┌────────────┐      │
     │  Redirect back   │  │ PostgreSQL │      │
     │◀─────────────────┤  └────────────┘      │
     │  (Connected!)    │                      │
```

### Integration Client Pattern

All clients extend `IntegrationClient` base class:

```
IntegrationClient (base.py)
├── get_access_token()     ── reads encrypted token from DB
├── get_refresh_token()    ── for token renewal
│
├── GoogleCalendarClient   ── google-api-python-client + asyncio.to_thread
├── GoogleDocsClient       ── google-api-python-client + asyncio.to_thread
├── GoogleDriveClient      ── google-api-python-client + asyncio.to_thread
├── SlackClient            ── slack-sdk AsyncWebClient (per workspace)
├── LinearClient           ── httpx + GraphQL
└── NotionClient           ── httpx + REST (3 req/s rate limit)

All clients use tenacity retry with exponential backoff.
```

### Resolution Pipeline

For user-friendly input on the customer form:

```
User Input                  Parser                  API Validation
─────────────────          ──────────────          ────────────────
#aurora-team          ──▶  normalize name     ──▶  Slack conversations.list
@justin.downer        ──▶  normalize @name    ──▶  Slack users.list
linear.app/proj/...   ──▶  parse URL → ID     ──▶  Linear GraphQL get_project
notion.so/page/...    ──▶  parse URL → UUID   ──▶  Notion get_page
docs.google.com/d/... ──▶  parse URL → ID     ──▶  Google Docs get_document
Team Name             ──▶  passthrough        ──▶  Linear find_team_by_name
Person Name           ──▶  passthrough        ──▶  Linear find_user
```

---

## API Endpoint Map

### Authentication (`/auth`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/google/connect` | Initiate Google OAuth |
| GET | `/auth/google/callback` | Google OAuth callback |
| GET | `/auth/slack/internal/connect` | Initiate internal Slack OAuth |
| GET | `/auth/slack/internal/callback` | Internal Slack callback |
| GET | `/auth/slack/external/connect` | Initiate external Slack OAuth |
| GET | `/auth/slack/external/callback` | External Slack callback |
| GET | `/auth/linear/connect` | Initiate Linear OAuth |
| GET | `/auth/linear/callback` | Linear OAuth callback |
| GET | `/auth/notion/connect` | Initiate Notion OAuth |
| GET | `/auth/notion/callback` | Notion OAuth callback |

### Customers (`/api/customers`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/customers` | List all customers |
| POST | `/api/customers` | Create customer |
| GET | `/api/customers/{id}` | Get customer |
| PATCH | `/api/customers/{id}` | Update customer |
| DELETE | `/api/customers/{id}` | Delete customer |

### Approvals (`/api/approvals`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/approvals` | List (filterable by status/type/customer) |
| GET | `/api/approvals/{id}` | Get single item |
| PATCH | `/api/approvals/{id}` | Edit content/title |
| POST | `/api/approvals/{id}/action` | Generic state transition |
| POST | `/api/approvals/{id}/approve` | Approve |
| POST | `/api/approvals/{id}/publish` | Auto-approve + publish |
| POST | `/api/approvals/{id}/reject` | Reject |
| POST | `/api/approvals/{id}/copy` | Get content for clipboard |

### Transcripts (`/api/transcripts`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/transcripts/upload` | Multipart upload (.txt/.pdf/.docx) |
| POST | `/api/transcripts/paste` | JSON body paste |

### Workflows (`/api/workflows`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows` | List workflows |
| GET | `/api/workflows/{id}` | Get workflow details |
| POST | `/api/workflows/{id}/retry` | Retry failed workflow |
| POST | `/api/workflows/agenda` | Trigger agenda generation |

### Integrations (`/api/integrations`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/integrations/status` | All connection statuses |
| POST | `/api/integrations/verify/{type}` | Validate stored token |
| POST | `/api/integrations/manual-token` | Save manually pasted token |
| DELETE | `/api/integrations/{type}` | Disconnect |
| GET | `/api/integrations/oauth-config` | Check configured credentials |
| POST | `/api/integrations/oauth-app-config` | Save OAuth client credentials |
| GET | `/api/integrations/slack-manifest/{ws}` | Slack App manifest |
| POST | `/api/integrations/import-gcloud` | Import gcloud credentials |
| GET | `/api/integrations/gcloud-status` | Check gcloud availability |
| GET | `/api/integrations/settings/templates` | Get template config |
| PUT | `/api/integrations/settings/templates` | Update templates |

### Resolution (`/api/integrations/resolve`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/integrations/resolve/slack-channel` | Channel name → ID |
| POST | `/api/integrations/resolve/slack-user` | @name → user ID |
| POST | `/api/integrations/resolve/linear-project` | Project URL → ID |
| POST | `/api/integrations/resolve/linear-team` | Team name → ID |
| POST | `/api/integrations/resolve/linear-assignee` | Name/email → user ID |
| POST | `/api/integrations/resolve/notion-page` | Page URL → ID |
| POST | `/api/integrations/resolve/google-doc` | Doc URL → ID |

### Health (`/api/health`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | List health update items |
| GET | `/api/health/history/{customer_id}` | Health history |
| GET | `/api/health/dashboard` | All customers health status |
| POST | `/api/health/update` | Create health update |

### Slack (`/api/slack`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/slack/mentions` | List mentions |
| POST | `/api/slack/mentions/{id}/create-ticket` | Create Linear ticket |
| POST | `/api/slack/mentions/{id}/handled` | Mark handled |

### Linear (`/api/linear`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/linear/tickets` | List ticket items |
| POST | `/api/linear/tickets` | Create ticket as DRAFT |

### Dashboard (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard` | Aggregated stats |
| GET | `/health` | Health check |

---

## Scheduler Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `scan_calendar_for_upcoming_meetings` | Daily at 8:00 AM | Scans Google Calendar for meetings in T-2 days, creates agenda_generation workflows |
| `process_pending_workflows` | Every 30 seconds | Picks up pending workflows and executes them |
| `check_integration_health` | Every hour | Checks token expiry for all integrations |

Jobs are stored in PostgreSQL via `SQLAlchemyJobStore`, surviving container restarts.

---

## Infrastructure Details

### Docker Compose Services

```yaml
services:
  db:        PostgreSQL 16 Alpine, port 5433:5432, persistent volume
  backend:   Python 3.11, port 8001:8000, runs alembic + uvicorn
  web:       Multi-stage build (Node → nginx), port 3001:80
```

### nginx Reverse Proxy

```
localhost:3001
├── /api/*   ──▶  proxy_pass http://backend:8000  (FastAPI)
├── /auth/*  ──▶  proxy_pass http://backend:8000  (OAuth flows)
├── /health  ──▶  proxy_pass http://backend:8000  (health check)
└── /*       ──▶  try_files → /index.html         (React SPA)
```

### Environment Variables

All secrets stored in `.env` (gitignored). See `.env.example` for full list:
- Database: `DATABASE_URL`, `ENCRYPTION_KEY`
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Slack: `SLACK_{INTERNAL,EXTERNAL}_{CLIENT_ID,CLIENT_SECRET,APP_TOKEN}`
- Linear: `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`
- Notion: `NOTION_CLIENT_ID`, `NOTION_CLIENT_SECRET`
- AI: `ANTHROPIC_API_KEY`
- URLs: `OAUTH_REDIRECT_BASE_URL`, `FRONTEND_URL`

---

## Security Model

- **Single-user, localhost-only** — no multi-tenancy or user authentication
- **Token encryption** — all OAuth tokens encrypted with Fernet (AES-128-CBC) before DB storage
- **Encryption key** — stored in `.env`, not in the database
- **OAuth credentials** — can be stored in DB (via Settings UI) or `.env` (fallback)
- **No exposed ports** — only localhost bindings in Docker Compose
- **Tunnel only for OAuth** — ngrok/cloudflared used temporarily during setup if providers require HTTPS callbacks

---

## Test Architecture

```
tests/
├── conftest.py               # SQLite in-memory DB, PostgreSQL type shims,
│                              # FastAPI app with DB override, httpx client
├── test_api_customers.py     # Customer CRUD (17 tests)
├── test_api_approvals.py     # Approval lifecycle (27 tests)
├── test_api_dashboard.py     # Dashboard aggregation (7 tests)
├── test_api_integrations.py  # Integration status + tokens (10 tests)
├── test_state_machine.py     # State transitions (28 tests)
├── test_encryption.py        # Fernet encrypt/decrypt (11 tests)
└── test_transcript_parser.py # PDF + DOCX parsing (10 tests)

Total: 130 tests, all passing
```

Testing approach:
- Uses SQLite + aiosqlite as a fast in-memory substitute for PostgreSQL
- Custom SQLAlchemy type compilers translate `UUID → CHAR(36)`, `JSONB → JSON`, `ARRAY → JSON`
- FastAPI dependency injection overridden to use test database sessions
- Integration clients are not tested in unit tests (would require service mocking)
