# API Atlas

API Atlas is an evidence-first research agent for deciding whether requested
apps can become agent toolkits today. It gathers claim-level evidence, measures
credential friction and API breadth, queues uncertain findings for review, and
tracks how verification changes accuracy.

## Current checkpoint

The submitted quota-bounded run contains **48 validated apps from the supplied
100-app manifest**, backed by 249 claim-level citations. The remaining 52 apps
are explicitly shown as queued rather than silently inferred or fabricated.

The live pipeline passes end to end:

1. The Composio Python SDK creates a session restricted to two read-only
   `composio_search` tools.
2. An authenticated Streamable HTTP MCP client discovers those tools.
3. Gemini chooses search, then fetches an official page instead of trusting a
   search snippet.
4. Gemini extracts structured records in batches of up to five.
5. JSON Schema and identity checks reject malformed or incomplete batches.
6. Validated results and raw evidence are checkpointed separately for resume.

An independent deep path completed 21 apps. Comparing those with the fast path
showed 17/21 exact agreement on buildability verdict, but materially lower
agreement on access tiers and MCP labels. An eight-app official-document audit
therefore corrected high-impact authentication and access claims while keeping
the raw model outputs unchanged.

The self-contained submission page is committed at
`case-study/dist/index.html`. Regenerate it from checkpointed research with:

```powershell
.\.venv\Scripts\python.exe .\case-study\generate.py
```

The page deliberately reports 48/100 coverage. Finishing the full manifest only
requires rerunning the resumable pipeline with available model quota; no
retrieval already cached needs to be repeated.

## Two-layer clustering

API Atlas preserves the assignment's ten market categories, then derives three
stable operational views from validated facts:

- **Integration archetype:** record systems, communication channels, transaction
  rails, growth channels, data providers, control planes, or content processors.
- **Readiness cohort:** build now, build with constraints, partnership outreach,
  human verification, or blocked/unclear.
- **Auth burden:** low, moderate, high, or unknown.

The research agent gathers evidence; deterministic rules assign these portfolio
clusters. This prevents a model rerun from silently changing what “build now”
means and produces chart-ready counts for the case-study page.

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

Run or resume the complete assignment dataset:

```powershell
.\.venv\Scripts\python.exe .\scripts\research_apps.py --full
```

Every app is checkpointed to the ignored `data/runs/full-results.json` file.
An interrupted run can use the same command: validated records are reused and
failed records are retried. ID ranges and `--limit` are available for bounded
tests without changing the source manifest.

## Full research manifest

`data/seed/apps.json` is reproducibly imported from the assignment and guarded
by tests requiring IDs 1–100, 100 unique names, non-empty website hints, and ten
categories containing ten apps each.

Preview a quota-aware run without spending model requests:

```powershell
.\.venv\Scripts\python.exe -m scripts.plan_run --start-id 1 --end-id 10
```

The planner uses observed MCP calls from validated runs and the active account's
RPM limit. This makes the time/cost decision explicit before a large run begins.

Accuracy is measured through a predeclared field-level audit, not inferred from
model confidence. See `docs/accuracy-methodology.md` for the stratified sample,
browser checks, correction loop, and the limited role of paid quota in scaling.

Run the bounded, lower-call CRM pilot with deterministic MCP retrieval and
batched synthesis:

```powershell
.\.venv\Scripts\python.exe .\scripts\research_fast.py --start-id 1 --end-id 10 --model gemini-3-flash-preview
```

This path checkpoints evidence after each app and results after each synthesis
batch. It escalates uncertain records to the deeper agent instead of treating
speed as proof of correctness.
