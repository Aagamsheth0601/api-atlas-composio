# API Atlas

API Atlas is an evidence-first research agent for deciding whether requested
apps can become agent toolkits today. It gathers claim-level evidence, measures
credential friction and API breadth, queues uncertain findings for review, and
tracks how verification changes accuracy.

## Current checkpoint

The live feasibility test passes end to end:

1. The Composio Python SDK creates a session restricted to two read-only
   `composio_search` tools.
2. An authenticated Streamable HTTP MCP client discovers those tools.
3. Gemini chooses search, then fetches an official page instead of trusting a
   search snippet.
4. The ignored run artifact contains a grounded Salesforce answer and official
   documentation URLs.

The next checkpoint expands this proven path to the deliberately varied
three-app feasibility set before scaling to all 100 apps.

## Secret setup

Copy `.env.example` to `.env` and populate it locally. `.env` is gitignored.
Use a Composio **project API key** from Settings -> Project Settings -> API
Keys, not a `ck_...` consumer MCP key.

## Run the smoke test

```powershell
.\.venv\Scripts\python.exe .\scripts\smoke_mcp.py
```

Generated run artifacts are written beneath `data/runs/` and remain ignored
until they have passed validation and are intentionally promoted.
