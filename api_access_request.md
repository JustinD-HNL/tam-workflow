I'm building a local automation tool (TAM Workflow) to manage customer meetings, and follow up tasks.  The goal is to automate as much as possible from agendas, notes, to followup tracking in linear, and notion.  While having human aproval and editing capabil This runs entirely locally on my laptop — no external servers or data leaving my system other than our sas tool access. 


It needs Google API access for:

- Reading my Google Calendar events (to detect upcoming customer calls)
- Creating/editing Google Docs (for meeting agendas and notes)
- Managing files in a Google Drive folder (storing generated docs)

**What I need:**
1. Access to a GCP project (or permission to create one) with these APIs enabled:
   - Google Calendar API
   - Google Docs API
   - Google Drive API
2. An OAuth 2.0 Client ID (type: Web application) created in that project with:
   - Authorized redirect URI: http://localhost:3001/auth/google/callback
3. The OAuth consent screen configured (can be "Internal" for our org)

If it's easier, I just need the **Client ID** and **Client Secret** from the OAuth client. I can handle the rest.


It needs a Slack App installed in our internal workspace to:

- Read customer channel messages (to track new threads)
- Post agendas and meeting notes to customer channels
- Detect @mentions

**What I need:**
1. Permission to create and install a Slack App in our internal workspace, OR
2. Someone to create the app and share the Bot User OAuth Token (xoxb-...) with me

The app needs these bot scopes: channels:read, channels:history, chat:write, users:read, app_mentions:read

I have a pre-built app manifest that auto-configures everything — it takes about 2 minutes. Happy to walk through it together.


----------internal slack manifest--------------
{
  "display_information": {
    "name": "TAM Workflow (Internal)",
    "description": "Automated TAM workflow for internal Buildkite channels",
    "background_color": "#1a1a2e"
  },
  "features": {
    "bot_user": {
      "display_name": "TAM Workflow",
      "always_online": true
    }
  },
  "oauth_config": {
    "redirect_urls": [
      "http://localhost:3001/auth/slack/internal/callback"
    ],
    "scopes": {
      "bot": [
        "channels:read",
        "channels:history",
        "chat:write",
        "users:read",
        "app_mentions:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "message.channels",
        "app_mention"
      ]
    },
    "socket_mode_enabled": true,
    "org_deploy_enabled": false,
    "token_rotation_enabled": false
  }
}
-------------------------------------


It needs a Slack App installed in our external/customer-facing workspace to:

- Detect @mentions of me in customer Slack Connect channels
- Read channel messages for context
- Post approved agendas to customer channels

**What I need:**
1. Permission to create and install a Slack App in the external workspace, OR
2. Someone to create the app and share the Bot User OAuth Token (xoxb-...) with me

Required bot scopes: channels:read, channels:history, chat:write, users:read, app_mentions:read

I have a pre-built app manifest that auto-configures everything.

---------------------external slack manifest----------------------
{
  "display_information": {
    "name": "TAM Workflow (External)",
    "description": "Automated TAM workflow for customer-facing Slack Connect channels",
    "background_color": "#16213e"
  },
  "features": {
    "bot_user": {
      "display_name": "TAM Workflow",
      "always_online": true
    }
  },
  "oauth_config": {
    "redirect_urls": [
      "http://localhost:3001/auth/slack/external/callback"
    ],
    "scopes": {
      "bot": [
        "channels:read",
        "channels:history",
        "chat:write",
        "users:read",
        "app_mentions:read"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "bot_events": [
        "app_mention"
      ]
    },
    "socket_mode_enabled": true,
    "org_deploy_enabled": false,
    "token_rotation_enabled": false
  }
}
------------------------------------------------------------------------


It needs a Notion integration to:

- Read customer health pages
- Update health status (RAG), summary, and notes after customer calls
- Add new entries

**What I need:**
1. Permission to create an internal integration at notion.so/my-integrations (it looks to be restricted by workspace settings), OR
2. Someone to create an integration named "TAM Workflow" with Read/Update/Insert capabilities and share the Internal Integration Token with me

It needs Linear api key but I'm able to generate one for myself. 
