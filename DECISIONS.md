# Architectural Decisions Log

## ADR-001: Direct API Clients over MCP Servers
**Date:** 2025-02-11
**Status:** Accepted
**Context:** CLAUDE.md suggests using MCP servers for integrations where available.
**Decision:** Use direct API clients (Python libraries) for all integrations. MCP servers are designed for Claude Code's own tool use, not for a standalone application's backend. Our FastAPI backend needs programmatic API access, which is better served by standard Python HTTP clients.
**Integrations:**
- Google Calendar/Docs/Drive → `google-api-python-client` + `google-auth-oauthlib`
- Slack → `slack-sdk` (includes Socket Mode support)
- Linear → `httpx` with GraphQL queries
- Notion → `httpx` with Notion REST API
**Consequence:** Simpler architecture, easier to test, no MCP server process management.

## ADR-002: SQLAlchemy 2.0 + Alembic for Database
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need ORM for PostgreSQL with migration support.
**Decision:** SQLAlchemy 2.0 (async) with Alembic for migrations. Use asyncpg as the async PostgreSQL driver.
**Consequence:** Full async support matches FastAPI's async nature. Alembic handles schema evolution.

## ADR-003: Fernet Encryption for Token Storage
**Date:** 2025-02-11
**Status:** Accepted
**Context:** OAuth tokens must be stored encrypted in the database.
**Decision:** Use `cryptography.fernet` for symmetric encryption. Encryption key stored in .env as ENCRYPTION_KEY.
**Consequence:** Tokens are encrypted at rest. Key rotation would require re-encrypting all tokens.

## ADR-004: APScheduler In-Process with FastAPI
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need a scheduler for periodic tasks (calendar scan, template refresh, health checks).
**Decision:** Run APScheduler within the FastAPI process using AsyncIOScheduler with PostgreSQL job store.
**Consequence:** No separate scheduler service needed. Jobs survive restarts via DB persistence. Simplifies Docker Compose.

## ADR-005: Socket Mode for Slack Events
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need real-time Slack events. Options: Events API (requires public URL) vs Socket Mode (WebSocket, no public URL).
**Decision:** Use Slack Socket Mode for both workspaces. No ngrok/tunnel needed for event delivery.
**Consequence:** Simpler local setup. Two persistent WebSocket connections (one per workspace). Tunnel only needed for OAuth callbacks if required.

## ADR-006: Vite + React for Frontend
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need a React + TypeScript frontend.
**Decision:** Use Vite as the build tool with React 18, TypeScript, React Router, and TailwindCSS for styling.
**Consequence:** Fast dev server with HMR, modern tooling, minimal config.

## ADR-007: Claude API via Anthropic Python SDK
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need Claude for content generation (agendas, notes, health assessments).
**Decision:** Use the `anthropic` Python SDK with Claude claude-sonnet-4-5-20250929 for content generation. Structured prompts with templates.
**Consequence:** Direct API calls from the backend. Cost per generation is minimal for this use case.

## ADR-008: httpx for HTTP Clients
**Date:** 2025-02-11
**Status:** Accepted
**Context:** Need an HTTP client for Linear GraphQL API and Notion REST API.
**Decision:** Use `httpx` with async support for all direct HTTP calls. Use tenacity for retry logic.
**Consequence:** Consistent async HTTP across all integrations. tenacity provides flexible retry with exponential backoff.

## ADR-009: OAuth App Credentials in DB (Not Just .env)
**Date:** 2026-02-11
**Status:** Accepted
**Context:** The original design stored OAuth client IDs/secrets only in `.env`. This requires restarting Docker to change credentials and is less user-friendly.
**Decision:** Allow OAuth app credentials to be stored encrypted in the database via the Settings UI (`oauth_app_configs` table). The system checks DB first, falls back to `.env` values. This lets the TAM configure OAuth apps through the web console without editing files.
**Consequence:** More flexible setup. Added `OAuthAppConfig` model and migration 002. Settings page has forms to enter client ID/secret per integration.

## ADR-010: Friendly Name/URL Resolution for Customer Fields
**Date:** 2026-02-11
**Status:** Accepted
**Context:** Customer form required raw IDs (Slack channel IDs, Linear project UUIDs, Notion page IDs) which are not user-friendly. TAMs work with channel names, URLs, and @mentions.
**Decision:** Build a resolution layer:
1. Pure URL/name parsing functions (`url_parsers.py`) — extract IDs from URLs, normalize names
2. Integration client search methods — validate IDs against live APIs
3. Resolution API endpoints (`/api/integrations/resolve/*`) — 7 endpoints with consistent `{valid, id, name, error}` response
4. `ResolvableField` React component — input with resolve-on-blur, success/error indicators
**Consequence:** TAMs enter `#aurora-team`, `@justin.downer`, Linear project URLs, Notion page URLs, etc. The system resolves and validates them, storing the resulting IDs. Backward compatible — raw IDs still work.

## ADR-011: redirect_slashes=False in FastAPI
**Date:** 2026-02-11
**Status:** Accepted
**Context:** FastAPI's default `redirect_slashes=True` caused 307 redirects from `/api/customers` to `/api/customers/`. When behind nginx reverse proxy, the redirect `Location` header used `http://localhost/` (port 80) instead of `http://localhost:3001/`, causing browser `ERR_NETWORK` errors.
**Decision:** Set `redirect_slashes=False` on the FastAPI app. All routes use empty string paths (`""`) meaning they match the prefix exactly (e.g., `/api/customers`). Test URLs updated to match.
**Consequence:** No ambiguity between `/path` and `/path/`. Frontend and tests all use consistent paths without trailing slashes.

## ADR-012: Standard OAuth over gcloud ADC for Google
**Date:** 2026-02-11
**Status:** Accepted
**Context:** Attempted to use `gcloud auth application-default login` as an alternative Google auth method since it avoids needing a GCP OAuth app. However, the Google Auth Library client (ID 764086051850) used by ADC is blocked by Buildkite's Google Workspace admin.
**Decision:** Revert to standard OAuth 2.0 with a custom GCP project. The Settings page provides an admin request email template to help the TAM request the necessary permissions from their Google Workspace admin.
**Consequence:** Google setup requires admin approval for the OAuth consent screen. The Settings UI guides the TAM through the process with copy-pasteable admin request templates.
