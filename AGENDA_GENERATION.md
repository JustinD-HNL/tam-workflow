# Agenda Generation — Data Sources & Flow

## Overview

When an agenda is generated (either triggered by the scheduler 2 days before a meeting, or manually via the web console), the system gathers context from multiple sources and passes it all to Claude to produce a customer-ready agenda.

Each data source is **resilient** — if any source fails (API down, no data, etc.), it's skipped and the agenda is generated with whatever context is available.

## Data Sources

| # | Source | What's Pulled | Limit | Notes |
|---|--------|--------------|-------|-------|
| 1 | **Linear Issues** | Open/in-progress issues from the customer's Linear project | 20 issues | Requires `linear_project_id` on the customer. Shows identifier, title, and state. |
| 2 | **Last Meeting Notes** | Most recent published meeting notes for the customer | 1 (latest), truncated to 5,000 chars | Pulled from the approval queue (published notes). Falls back to the meeting documents table if no approved notes exist. |
| 3 | **Open Action Items** | Unfinished action items from previous meetings | 20 items | Items in draft, in_review, or approved status. Includes title and description. |
| 4 | **Slack Mentions** | Recent mentions of the TAM in customer Slack channels | 10 mentions | Includes user name and message text (truncated to 200 chars each). |
| 5 | **Agenda Template** | The structural template the agenda should follow | Full document | Fetched from a Google Doc if configured in Settings → Template Links. Falls back to a built-in default template. |
| 6 | **Web Content** | Pre-fetched content from URLs referenced in the template | All URLs found | If the template references URLs (e.g., a changelog URL), those pages are fetched so Claude can incorporate their content (e.g., recent product updates). |

## Flow

```
Trigger (scheduler or manual)
    │
    ├─ 1. Fetch Linear issues (GraphQL API)
    ├─ 2. Query last meeting notes (database)
    ├─ 3. Query open action items (database)
    ├─ 4. Query recent Slack mentions (database)
    ├─ 5. Fetch agenda template (Google Docs API or default)
    ├─ 6. Pre-fetch any URLs in the template (HTTP)
    │
    ▼
Claude generates agenda using all available context
    │
    ▼
Approval item created (status: DRAFT)
    │
    ▼
TAM reviews/edits in web console
    │
    ├─ Approve & Publish → posts to Slack, creates Linear ticket
    ├─ Approve & Copy → copies to clipboard
    └─ Reject → back to draft for re-editing
```

## Key Files

| File | Role |
|------|------|
| `src/orchestrator/workflows.py` → `_execute_agenda_generation()` | Orchestrates data gathering from all sources |
| `src/content/generator.py` → `generate_agenda()` | Builds the Claude prompt and generates the agenda |
| `src/integrations/linear/client.py` → `list_project_issues()` | Fetches Linear issues |
| `src/integrations/google/docs.py` | Fetches Google Doc templates |

## Prompt Behavior

- Claude follows the template structure exactly
- Template meta-instructions (e.g., `*(Note: Verify and update...)*`) are treated as instructions to Claude, not text to include in the output
- The final agenda should be polished and customer-ready with no AI directives visible

## Future Considerations

- Add calendar event details (attendees, Zoom link) as context
- Pull in customer health status/summary from Notion
- Include recent support tickets or escalations
- Configurable per-customer source selection (e.g., skip Slack for some customers)
- Summarize longer note histories instead of just the last meeting
