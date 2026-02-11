# Project: Automated TAM Workflow

## Role & Context
You are an engineering manager building this project from start to finish.
You must be able to build autonomously without user interaction on the command line.
You have permissions to run and install any Python packages or tools needed.
You can edit and create any files or folders and run any commands in the project folder.
Use `./tmp` for temporary files.
Create sub-agents as needed for parallel workstreams.
Do deep internet research for any integration questions.
If you have questions about the project, ask before proceeding with assumptions.

## Planning & Tracking
- Create a detailed plan document (`PLAN.md`) first — detailed enough to resume in another session
- Maintain a task tracker (`TASKS.md`) with status for all tasks as you start and finish them
- Use a `DECISIONS.md` log for architectural decisions and tradeoffs

## Environment
- Conda is installed — create a conda environment for this project
- Python 3.11+ preferred
- Install all required packages in the conda environment
- Use `pyproject.toml` for dependency management
- Pin all dependency versions

---

## Project Goal

Build an automated workflow system for a Buildkite Technical Account Manager (TAM) that:
1. Captures and processes meeting notes from call transcripts (manual upload/paste)
2. Generates and manages meeting agendas on a schedule
3. Updates customer health tracking in Notion
4. Generates and tracks tasks/tickets in Linear
5. Coordinates across Slack (two separate workspaces), Google Calendar, Google Docs, and Notion
6. Provides a web console for configuration, approval workflows, and publishing

Claude Code will be the orchestration layer — generating content, coordinating automations,
and driving the workflow. The web console handles human-in-the-loop approvals and configuration.

---

## Deployment & Runtime

### Local Deployment (Docker Recommended)
This runs locally on the TAM's Buildkite laptop. Use Docker Compose for deployment:
- **Why Docker:** Clean isolation from the laptop's environment, single `docker-compose up` to start
  everything, easy to tear down, portable if the TAM switches laptops, consistent Python/Node versions
- **Services in Docker Compose:**
  1. `backend` — FastAPI app (orchestrator + API)
  2. `web` — React frontend (served via nginx or dev server)
  3. `scheduler` — APScheduler process (can be part of backend or separate)
  4. `db` — PostgreSQL (even locally, prefer Postgres over SQLite for consistency)
- **Networking:** All services on a Docker bridge network. Backend exposed on `localhost:8000`,
  frontend on `localhost:3000`
- **Volumes:** Mount `.env` and a `data/` directory for persistence
- **For Slack webhooks/OAuth callbacks:** Use `ngrok` or `cloudflared` tunnel to expose
  localhost to the internet for OAuth redirects and Slack Events API
- Also provide a `docker-compose.dev.yml` for development with hot-reload and debug ports
- Include a non-Docker local dev setup as fallback (conda env + manual process startup)

### Single User
This is a single-TAM tool. No multi-tenancy, no user auth on the web console (or simple
local-only auth). If other TAMs want to use it, they clone the repo and set up their own instance.

---

## Architecture Overview

### Core Components
1. **Orchestration Engine** — Python service that coordinates triggers, schedules, and workflow execution
2. **Integration Layer** — MCP servers + API clients for each external service
3. **Web Console** — Frontend for configuration, approvals, and manual overrides
4. **Data Store** — PostgreSQL (via Docker) for customer config, workflow state, approval queues
5. **Scheduler** — APScheduler for time-based triggers (agenda generation 2 days before calls)
6. **Content Engine** — Claude Code / Claude API for generating agendas, notes, health summaries
7. **Tunnel** — ngrok or cloudflared for Slack webhooks and OAuth callbacks to localhost

### MCP Servers (Critical)
Claude Code can connect to external services via MCP (Model Context Protocol) servers.
Research and configure MCP servers for:
- **Google Calendar** — read calendar events, extract meeting details
- **Google Docs** — create/edit documents from templates
- **Slack** — post messages, read channels, monitor mentions (both workspaces)
- **Linear** — create/update issues, manage projects
- **Notion** — update databases, read/write pages

Where MCP servers are not available or insufficient, fall back to direct API integration.
Document which integrations use MCP vs direct API in `DECISIONS.md`.

### Authentication & Credentials

**Primary method: Browser-based OAuth via the web console setup wizard.**
The TAM clicks "Connect [Service]" in the Settings page, authenticates in the browser, and
the system stores the tokens automatically. No manual token hunting required.

**OAuth Flows (preferred):**
- **Google (Calendar, Docs, Drive):** OAuth 2.0. TAM clicks "Connect Google" → redirected to
  Google sign-in → grants Calendar, Docs, and Drive scopes → callback stores refresh token.
  Requires a GCP project with Calendar API, Docs API, and Drive API enabled, plus an OAuth
  consent screen configured. Document the one-time GCP setup steps in `AUTH.md`.
- **Slack (Internal Workspace):** OAuth 2.0. Create a Slack App for the Buildkite workspace.
  TAM clicks "Connect Internal Slack" → "Add to Slack" flow → grants bot scopes
  (channels:read, channels:history, chat:write, users:read, app_mentions:read).
- **Slack (External Workspace):** Same OAuth flow but for the external customer-facing workspace.
  Separate Slack App installation. TAM clicks "Connect External Slack" → same "Add to Slack" flow.
- **Notion:** OAuth 2.0. TAM clicks "Connect Notion" → Notion auth screen → grants access
  to the customer health database/pages.
- **Linear:** OAuth 2.0. TAM clicks "Connect Linear" → Linear auth screen → grants access.

**Manual Token Fallback:**
If OAuth doesn't cooperate for any service, the Settings page also has a "Paste Token Manually"
option for each integration:
- Linear: Personal API key from Settings → API → Personal API Keys
- Notion: Internal integration token from Notion Settings → Integrations
- Slack: Bot token from the Slack App admin page
- Google: Service account JSON key (less ideal but works)

**Token Storage:**
- All OAuth tokens (access + refresh) stored encrypted in the database, NOT in `.env`
- `.env` holds only the OAuth client IDs/secrets for each service (needed to initiate flows)
- `.env` is gitignored; provide `.env.example` with placeholder values
- Refresh tokens are used to auto-renew access tokens — TAM should rarely need to re-auth
- Never hardcode credentials

**Setup Wizard Flow:**
The web console Settings page shows connection status for each service with:
- 🟢 Connected (last verified: timestamp)
- 🔴 Not Connected — "Connect" button
- 🟡 Token Expired — "Reconnect" button
The wizard guides the TAM through each service one by one on first setup.
Document all required OAuth scopes per integration in `AUTH.md`.

---

## Customer Data Model

Each customer record contains:
```
Customer:
  - name: string (e.g., "Anthropic", "Dropbox", "Reddit")
  - slug: string (e.g., "anthropic") — used for file paths, channel naming
  - linear_project_id: string — Linear project for this customer's TAM work
  - slack_internal_channel_id: string — Buildkite internal Slack channel
  - slack_external_channel_id: string — Customer-facing Slack Connect channel (external workspace)
  - notion_page_id: string — Notion page/database entry for customer health
  - google_calendar_event_pattern: string — how to match calendar events for this customer
  - google_docs_folder_id: string — Google Drive folder for this customer's docs
  - tam_slack_user_id: string — the TAM's Slack user ID (for @mention detection)
  - primary_contacts: list — key customer contacts
  - cadence: string — meeting cadence (weekly, biweekly, monthly)
  - health_status: enum (green, yellow, red)
  - last_health_update: datetime
  - linear_task_defaults:
      - team_id: string
      - assignee_id: string
      - labels: list
      - priority: enum
```

---

## Integration Details

### Avoma — Manual Transcript Input (Phase 1)
- Avoma records calls and generates transcripts, but we are NOT integrating with the Avoma API
- Instead, the TAM will either:
  1. **Upload** a transcript file (txt, pdf, or docx) via the web console, OR
  2. **Copy-paste** the transcript text directly into the web console
- The web console must provide a clean upload/paste interface tied to a specific customer and meeting date
- The system matches the transcript to the correct customer and calendar event
- Future enhancement: Avoma API or webhook integration can replace manual input later
- Keep the transcript ingestion interface abstracted so swapping to automated input is easy

### Google Calendar
- All customer calls are scheduled here with Zoom links
- Used to: detect upcoming meetings, trigger agenda generation, match transcripts to meetings
- Trigger: 2 days before a scheduled customer call → generate agenda
- Need: Read access to calendar events, ability to parse recurring meetings
- Google Workspace is already in use; need GCP project with Calendar API enabled

### Google Docs
- Generate drafts of agendas and notes from templates
- **Templates are Google Docs** — the TAM provides a Google Doc URL for each template type:
  1. **Agenda Template** — linked via web console settings
  2. **Meeting Notes Template** — linked via web console settings
- At startup/config time, Claude Code fetches the template doc content and uses it as the
  structural guide for all generated content
- The system should periodically re-fetch templates in case they're updated
- Generated agendas and notes are created as new Google Docs in the customer's Drive folder
- Docs are editable in the web console (via embedded editor or link to Google Doc) before publishing

### Linear
- Track all TAM work and tasks per customer project
- Each customer has a dedicated Linear project
- Task creation triggers:
  1. Action items extracted from meeting notes
  2. New threads in internal Slack customer channels
  3. @mentions of TAM in external Slack customer channels
  4. Manual creation from web console
- Configurable defaults per customer (team, assignee, labels, priority)
- Use Linear's GraphQL API (well-documented, preferred over REST)

### Slack (Two Separate Workspaces)
- **Internal Workspace (Buildkite):** One channel per customer for internal discussion
  - Monitor: New threads → create Linear ticket under customer project
  - Publish: Approved agendas and meeting notes posted here
- **External Workspace (Customer-facing with Slack Connect):** Channels with customers via Slack Connect
  - Monitor: @mentions of the TAM → create Linear ticket under customer project
  - Publish: Approved agendas posted here (notes are internal only)
- **Auth:** Two separate Slack apps / bot tokens — one installed in each workspace
  - Internal workspace bot: needs channels:read, channels:history, chat:write, users:read
  - External workspace bot: needs the same scopes
  - Both need Socket Mode or Events API subscriptions for real-time monitoring
- **Socket Mode recommended for local dev** — no public URL needed for event delivery
  (simpler than Events API which requires an internet-accessible endpoint)
- For production/reliability, consider Slack Events API with ngrok/cloudflared tunnel

### Notion
- Customer health database with status tracking
- After each customer call: update health status, add notes, update last-contact date
- Health updates go through approval workflow before publishing
- Fields to update: health status (RAG), summary, key risks, opportunities, last meeting date
- Notion API rate limit: 3 requests/second — implement throttling

---

## Workflow Definitions

### Workflow 1: Agenda Generation
```
Trigger: 2 days before scheduled customer call (scheduler checks Google Calendar daily)
Steps:
  1. Identify upcoming customer call from Google Calendar
  2. Pull context: recent Linear tickets, last meeting notes, open action items, Slack activity
  3. Claude generates agenda following the Agenda Template (fetched from linked Google Doc)
  4. Create Google Doc with generated agenda in customer's Drive folder
  5. Queue for approval in web console (status: DRAFT)
  6. TAM reviews/edits in web console
  7. On approval (status: APPROVED):
     a. Post agenda to internal Slack channel
     b. Post agenda to external Slack channel (Slack Connect)
     c. Create Linear ticket: "Agenda prepared for [Customer] [Date]"
     d. Status → PUBLISHED
```

### Workflow 2: Meeting Notes Generation
```
Trigger: TAM uploads or pastes transcript in web console
Steps:
  1. TAM uploads transcript file or pastes transcript text in web console
  2. TAM selects the customer and meeting date (system suggests match from recent calendar events)
  3. Claude generates meeting notes following the Notes Template (fetched from linked Google Doc)
  4. Extract action items from notes
  5. Create Google Doc with generated notes in customer's Drive folder
  6. Queue for approval in web console (status: DRAFT)
  7. TAM reviews/edits notes and action items in web console
  8. On approval (status: APPROVED):
     a. Post notes to internal Slack channel ONLY (not external)
     b. Create Linear tickets for each action item
     c. Update Notion customer health (queued for separate approval)
     d. Status → PUBLISHED
```

### Workflow 3: Customer Health Update
```
Trigger: After meeting notes are approved/published
Steps:
  1. Claude generates health assessment based on: meeting notes, recent Slack activity,
     open Linear tickets, previous health status
  2. Queue health update for approval in web console
  3. TAM reviews/edits health summary and RAG status
  4. On approval: Update Notion customer page
```

### Workflow 4: Slack Monitoring
```
Trigger: Real-time via Slack Socket Mode (both workspaces)
Events:
  A. New thread in internal customer channel:
     → Create Linear ticket in customer project with thread context
  B. @mention of TAM in external customer channel (Slack Connect):
     → Create Linear ticket in customer project
     → Surface in web console "Mentions" view
```

### Approval State Machine
```
States: DRAFT → IN_REVIEW → APPROVED → PUBLISHED → ARCHIVED
         ↓                    ↑
       REJECTED ──(edit)──────┘

All content (agendas, notes, health updates, Linear tickets) passes through this flow.
The web console is the approval interface.
"Approve and Publish" = auto-push to all configured channels
"Approve and Copy" = copy to clipboard for manual posting (fallback for any integration gaps)
```

---

## Web Console Requirements

### Tech Stack
- **Frontend:** React + TypeScript
- **Backend:** FastAPI (Python) — shares codebase with orchestration engine
- **Database:** PostgreSQL (via Docker Compose)
- **Auth:** No login required (single-user, localhost only). Optional: simple token auth if exposed via tunnel.

### Pages / Views

#### 1. Dashboard
- Overview of upcoming meetings, pending approvals, recent activity
- Quick-action buttons for common tasks

#### 2. Customer Management
- List all customers with health status indicators
- Per-customer config page to link:
  - Linear project
  - Slack channels (internal channel ID + external Slack Connect channel ID)
  - Notion page
  - Google Calendar pattern/filter
  - Google Docs folder
  - Meeting cadence
  - Linear task defaults (team, assignee, labels, priority)

#### 3. Transcript Upload
- Select customer and meeting date (auto-suggest from recent calendar events)
- Upload transcript file (txt, pdf, docx) OR paste transcript text
- Preview and submit to trigger notes generation workflow
- This replaces Avoma API integration for Phase 1

#### 4. Approval Queue
- List of pending items: agendas, notes, health updates, Linear tickets
- Each item has: preview, edit (inline or modal), approve+publish, approve+copy, reject
- Filter by customer, type, status

#### 5. Agendas & Notes
- Browse all generated agendas and notes by customer
- Edit in rich text editor (synced with Google Doc)
- Publish controls

#### 6. Linear Tickets
- View generated/pending tickets before they're created
- Edit title, description, priority, labels, assignee
- Approve individually or in bulk
- View existing tickets per customer

#### 7. Slack Mentions
- View all @mentions of the TAM across external customer Slack Connect channels
- Filter by customer
- One-click "Create Linear Ticket" from a mention
- Mark as handled/ignored

#### 8. Health Dashboard
- All customers with current RAG status
- Pending health updates awaiting approval
- History of health changes per customer

#### 9. Settings
- **Integration Setup Wizard:** Step-by-step "Connect" buttons for each service:
  - Connect Google (Calendar, Docs, Drive) — OAuth flow
  - Connect Internal Slack — OAuth "Add to Slack" flow
  - Connect External Slack — OAuth "Add to Slack" flow
  - Connect Linear — OAuth flow
  - Connect Notion — OAuth flow
- Each shows connection status: 🟢 Connected / 🔴 Not Connected / 🟡 Token Expired
- "Reconnect" button for expired tokens
- "Paste Token Manually" fallback for each integration
- **Template Links:** Fields to paste Google Doc URLs for Agenda Template and Notes Template
- Scheduler status and manual trigger buttons
- ngrok/tunnel status indicator

---

## Error Handling & Resilience
- All API calls must have retry logic with exponential backoff
- If one step in a workflow fails, mark the workflow as FAILED with error context
  (don't roll back successful steps — use compensation/manual resolution)
- Log all API interactions for debugging
- Web console should surface errors clearly with "Retry" buttons
- If Slack post succeeds but Linear ticket fails, don't re-post to Slack on retry
- Graceful degradation: if an integration is down, the "Approve and Copy" button always works

## Scheduling
- Use APScheduler with a database-backed job store (PostgreSQL) for:
  - Daily scan of Google Calendar for meetings in T-2 days
  - Periodic re-fetch of Google Doc templates
  - Health check on all integration connections
- Scheduler runs as part of the FastAPI backend process
- Scheduler state survives Docker restarts via database persistence

## Testing Strategy
- Unit tests for each integration client (mock API responses)
- Integration tests with sandbox/test accounts where possible
- End-to-end workflow tests using a test customer
- Web console: basic Playwright or Cypress tests for approval flows

## Project Structure
```
tam-workflow/
├── PLAN.md
├── TASKS.md
├── DECISIONS.md
├── AUTH.md
├── .env.example
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── pyproject.toml
├── conda-env.yml              # Fallback for non-Docker local dev
├── src/
│   ├── orchestrator/          # Workflow engine, scheduler, state machine
│   ├── integrations/          # API clients: google, slack, linear, notion
│   ├── mcp/                   # MCP server configs and wrappers
│   ├── transcript/            # Transcript upload, parsing, and matching
│   ├── content/               # Claude-powered content generation (agendas, notes, health)
│   ├── models/                # Database models, schemas
│   ├── api/                   # FastAPI backend for web console
│   └── config/                # Customer configs, template references
├── web/                       # React frontend
├── tests/
├── scripts/                   # Setup, migration, utility scripts
└── tmp/                       # Temporary files
```

---

## Notes for Claude Code
- Prioritize getting a single customer end-to-end workflow working before expanding
- Start with the integration layer — if APIs don't work, nothing else matters
- Avoma is NOT integrated — build the manual transcript upload/paste interface instead
- Two separate Slack bot tokens needed — one per workspace. Test both independently.
- Socket Mode is preferred for Slack in local dev (no public URL needed for events)
- Google APIs require a GCP project — document the exact setup steps in AUTH.md
  (enable Calendar API, Docs API, Drive API; configure OAuth consent screen; create OAuth client ID)
- Build the OAuth callback handlers EARLY — all integrations depend on auth working first
- OAuth redirect URI will be localhost (e.g., http://localhost:8000/auth/google/callback)
  — ngrok/cloudflared tunnel needed only if Google requires HTTPS redirect URIs
- Store refresh tokens in the database, not .env — auto-renew access tokens transparently
- Templates are Google Docs — build a fetcher that pulls doc content from a URL and caches it
- Linear's GraphQL API is well-documented — prefer it over REST
- Notion API has rate limits (3 requests/second) — implement throttling
- All generated content must be editable — never publish without approval
- The "Approve and Copy" fallback is critical — it's the escape hatch when integrations break
- Docker Compose is the primary run method; conda env is the dev/debug fallback
- Use ngrok or cloudflared for OAuth callback URLs during setup (document this clearly)
