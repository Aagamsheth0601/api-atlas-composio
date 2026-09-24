# API Atlas project guidance

## Goal

Build an evidence-first integration-intelligence pipeline that Composio could
rerun for new app requests. The 100-app take-home dataset is the first run, not
the entire product.

## Working rules

- Prefer official developer, help, pricing, and partner documentation.
- Attach evidence to individual claims, not only to an app record.
- Preserve unknowns. Never turn missing evidence into a confident answer.
- Test each milestone before expanding scope.
- Never commit API keys or raw secrets.

## Bug log / gotchas

### Consumer MCP key is not a project SDK key

- **Symptom:** The Composio Sessions & API Key page supplies a `ck_...` key and
  instructs clients to send it as `x-consumer-api-key`.
- **Root cause:** That credential belongs to the consumer-facing MCP flow. The
  Python SDK research pipeline authenticates with a project API key using
  `COMPOSIO_API_KEY` / `x-api-key`.
- **Fix:** Obtain the project key from Settings -> Project Settings -> API Keys.
  Keep both key types out of source control.

### TypeScript SDK does not match the local Node version

- **Symptom:** Current Composio TypeScript documentation requires Node 22.22.3+
  while this machine uses Node 20.11.1.
- **Root cause:** The current SDK is ESM-only and targets a newer Node runtime.
- **Fix:** Use the Python SDK for the timed take-home instead of changing the
  machine's Node installation.

