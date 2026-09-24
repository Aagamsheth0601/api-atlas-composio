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

The three-app feasibility pipeline also passes schema validation:

| App | Verdict | Confidence | Human review | Evidence |
| --- | --- | ---: | --- | ---: |
| Salesforce | Build now | 0.95 | No | 7 |
| fanbasis | Build now | 0.80 | Yes | 7 |
| PitchBook | Constrained | 0.80 | Yes | 7 |

The pipeline checkpoints after every app, resumes validated records, retries
provider rate limits, limits research turns and duration, and refuses to promote
records that fail the JSON Schema. Generated feasibility results remain ignored
until a human review promotes them.

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

Run the three-app feasibility pipeline:

```powershell
.\.venv\Scripts\python.exe -m scripts.research_apps
```
