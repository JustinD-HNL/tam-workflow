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
