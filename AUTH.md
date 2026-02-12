# Authentication Setup Guide

## Overview
The TAM Workflow system uses OAuth 2.0 for all integrations. The web console provides a setup wizard that guides you through connecting each service.

---

## Prerequisites
Before starting, you'll need:
1. A Google Cloud Platform (GCP) project
2. A Slack App for your internal Buildkite workspace
3. A Slack App for your external customer-facing workspace
4. A Linear account with API access
5. A Notion integration

---

## 1. Google (Calendar, Docs, Drive)

### One-Time GCP Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing): "TAM Workflow"
3. Enable the following APIs:
   - **Google Calendar API** — `calendar-json.googleapis.com`
   - **Google Docs API** — `docs.googleapis.com`
   - **Google Drive API** — `drive.googleapis.com`
4. Configure OAuth Consent Screen:
   - Go to APIs & Services → OAuth consent screen
   - User Type: **Internal** (if using Google Workspace) or **External** (for testing)
   - App name: "TAM Workflow"
   - Scopes: Add the following:
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/documents`
     - `https://www.googleapis.com/auth/drive.file`
   - If External: Add your email as a test user
5. Create OAuth Client ID:
   - Go to APIs & Services → Credentials → Create Credentials → OAuth Client ID
   - Application type: **Web application**
   - Name: "TAM Workflow"
   - Authorized redirect URIs: `http://localhost:3001/auth/google/callback`
   - Copy the **Client ID** and **Client Secret**
6. Add to your `.env` file:
   ```
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

### Required OAuth Scopes
| Scope | Purpose |
|-------|---------|
| `calendar.readonly` | Read calendar events to detect upcoming meetings |
| `documents` | Create and read Google Docs (agendas, notes, templates) |
| `drive.file` | Create files in specific Drive folders |

---

## 2. Slack (Internal Workspace — Buildkite)

### Create Slack App
1. Go to [Slack API](https://api.slack.com/apps) → Create New App → From scratch
2. App Name: "TAM Workflow (Internal)"
3. Workspace: Select your Buildkite internal workspace

### Configure Bot Scopes
Go to OAuth & Permissions → Bot Token Scopes. Add:
| Scope | Purpose |
|-------|---------|
| `channels:read` | List and identify customer channels |
| `channels:history` | Read messages to detect new threads |
| `chat:write` | Post agendas and notes to channels |
| `users:read` | Resolve user names and IDs |
| `app_mentions:read` | Detect @mentions of the bot |

### Enable Socket Mode
1. Go to Socket Mode → Enable Socket Mode
2. Generate an App-Level Token with `connections:write` scope
3. Name it "tam-workflow-socket"
4. Copy the token (starts with `xapp-`)

### Enable Events
1. Go to Event Subscriptions → Enable Events
2. Subscribe to bot events:
   - `message.channels` — new messages in channels the bot is in
3. Socket Mode handles delivery (no request URL needed)

### Install to Workspace
1. Go to Install App → Install to Workspace
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### Add to .env
```
SLACK_INTERNAL_CLIENT_ID=your-client-id
SLACK_INTERNAL_CLIENT_SECRET=your-client-secret
SLACK_INTERNAL_BOT_TOKEN=xoxb-...  (fallback for manual setup)
SLACK_INTERNAL_APP_TOKEN=xapp-...  (for Socket Mode)
```

---

## 3. Slack (External Workspace — Customer-Facing)

### Create Separate Slack App
1. Same steps as Internal Slack, but:
   - App Name: "TAM Workflow (External)"
   - Workspace: Select the external/customer-facing workspace
2. Same bot scopes as internal
3. Enable Socket Mode with a separate App-Level Token
4. Subscribe to `app_mentions:read` event (for @mention detection)
5. Install to the external workspace

### Add to .env
```
SLACK_EXTERNAL_CLIENT_ID=your-client-id
SLACK_EXTERNAL_CLIENT_SECRET=your-client-secret
SLACK_EXTERNAL_BOT_TOKEN=xoxb-...
SLACK_EXTERNAL_APP_TOKEN=xapp-...
```

---

## 4. Linear

### OAuth Setup
1. Go to [Linear Settings](https://linear.app/settings) → API → OAuth Applications
2. Create a new OAuth application:
   - Name: "TAM Workflow"
   - Redirect URI: `http://localhost:3001/auth/linear/callback`
3. Copy **Client ID** and **Client Secret**

### Required Scopes
| Scope | Purpose |
|-------|---------|
| `read` | Read issues, projects, teams |
| `write` | Create and update issues |

### Manual Fallback
1. Go to Linear Settings → API → Personal API Keys
2. Create a key, copy it

### Add to .env
```
LINEAR_CLIENT_ID=your-client-id
LINEAR_CLIENT_SECRET=your-client-secret
LINEAR_API_KEY=lin_api_...  (manual fallback)
```

---

## 5. Notion

### Create Integration
1. Go to [Notion Integrations](https://www.notion.so/my-integrations) → New Integration
2. Name: "TAM Workflow"
3. Associated Workspace: Your Notion workspace
4. Capabilities: Read content, Update content, Insert content
5. Copy the **Internal Integration Token**

### OAuth Setup (Alternative)
1. Make the integration public to enable OAuth
2. Redirect URI: `http://localhost:3001/auth/notion/callback`
3. Copy **OAuth Client ID** and **OAuth Client Secret**

### Required Capabilities
| Capability | Purpose |
|-----------|---------|
| Read content | Read customer health pages |
| Update content | Update health status, summary |
| Insert content | Add new entries |

### Share Database with Integration
**Important:** You must share your Notion customer health database with the integration:
1. Open the database in Notion
2. Click ••• → Connections → Add connection → "TAM Workflow"

### Add to .env
```
NOTION_CLIENT_ID=your-client-id  (if using OAuth)
NOTION_CLIENT_SECRET=your-client-secret  (if using OAuth)
NOTION_API_KEY=ntn_...  (manual fallback / internal integration token)
```

---

## 6. Claude API (Anthropic)

### Get API Key
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an API key
3. Add to .env:
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Token Storage & Security
- OAuth tokens (access + refresh) are stored **encrypted** in the PostgreSQL database
- Encryption uses Fernet symmetric encryption
- The encryption key is in `.env` as `ENCRYPTION_KEY`
- Generate one with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `.env` is gitignored — never commit credentials
- Refresh tokens are used to auto-renew access tokens transparently

## Tunnel Setup (for OAuth Callbacks)
Some OAuth providers require HTTPS redirect URIs. If `http://localhost:8000` doesn't work:
1. Install ngrok: `brew install ngrok`
2. Run: `ngrok http 8000`
3. Update OAuth redirect URIs in each provider to use the ngrok HTTPS URL
4. Set `OAUTH_REDIRECT_BASE_URL=https://your-ngrok-url.ngrok.io` in `.env`
