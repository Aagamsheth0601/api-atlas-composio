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

### PowerShell interpolated variable followed by a colon

- **Symptom:** The safe environment-key presence check failed with
  `Variable reference is not valid` before it could report status.
- **Root cause:** PowerShell interpreted `"$name: ..."` as a scoped variable
  reference because the colon immediately followed the variable name.
- **Fix:** Delimit the interpolated name as `"${name}: ..."`. The failed command
  did not print or modify either secret.

### Documented Composio SDK patch is absent from PyPI

- **Symptom:** Pip could not satisfy `composio>=0.22.1,<0.23` even though the
  current MCP-session documentation says Python `composio` 0.22.1+ is required.
- **Root cause:** PyPI publishes 0.22.0 and then 0.23.0; there is no 0.22.1
  release available from the configured package index.
- **Fix:** Pin `composio==0.23.0`, the smallest published version above the
  documented minimum, and verify the MCP behavior with a live smoke test.

### Windows saved the secrets file as `.env.txt`

- **Symptom:** The application reported that `.env` was missing even though the
  credentials had been saved from a text editor.
- **Root cause:** Windows appended `.txt` to the requested filename, likely while
  known file extensions were hidden. `.env.txt` did not match the `.env` ignore
  rule and could have been committed accidentally.
- **Fix:** Rename the exact file to `.env`, confirm `git check-ignore` matches it,
  and verify only key presence and length without printing values.

### Scoped project key could authenticate but not create sessions

- **Symptom:** The first live SDK call returned HTTP 403 for
  `POST /api/v3.1/tool_router/session`.
- **Root cause:** The project key had read-only `session_management` permission.
  Creating the MCP-backed research session requires write access, and executing
  its research tools also requires `session_tool_execution` write access.
- **Fix:** Grant the scoped key **Session management: Write** and **Session tool
  execution: Write**, or create a full project key for this isolated take-home
  project. Keep all unrelated permissions disabled when using a scoped key.

### Valid OpenAI API key had no credit balance

- **Symptom:** After the Composio session and authenticated MCP endpoint were
  created successfully, the OpenAI Responses request returned HTTP 429 with
  `credit_balance_exhausted`.
- **Root cause:** ChatGPT Plus and OpenAI API billing are separate. The API
  organization attached to the key had no remaining credits.
- **Fix:** Add API credits to that organization or switch the model layer to a
  funded provider. Keep the completed Composio SDK/MCP integration unchanged.

### Buffered phase logs hid where a long MCP call stalled

- **Symptom:** The Gemini remote-MCP smoke test produced no terminal output for
  more than 90 seconds even though status messages preceded the model request.
- **Root cause:** Python buffered stdout in the non-interactive process, so phase
  messages were not visible while the network call remained active.
- **Fix:** Flush phase messages immediately and test the Gemini model and MCP
  endpoint independently before retrying the combined request.

### Gemini Interactions API hung while Generate Content succeeded

- **Symptom:** Both remote-MCP and plain-text calls through Gemini's preview
  Interactions API remained silent until manually stopped, while a text-only
  `gemini-2.5-flash` Generate Content call returned `OK` immediately.
- **Root cause:** The failure is isolated to the preview Interactions path for
  this key/environment, not to the Gemini credential or Composio.
- **Fix:** Use Google's supported Python MCP `ClientSession` integration with
  Generate Content. The client maintains the authenticated Streamable HTTP MCP
  connection and passes the live session to Gemini for automatic tool calling.

### MCP 1.30 removed the direct `headers` argument

- **Symptom:** `streamable_http_client(..., headers=...)` raised an unexpected
  keyword argument error before opening the Composio connection.
- **Root cause:** MCP 1.30 accepts a configured `http_client` instead of headers
  directly on `streamable_http_client`.
- **Fix:** Build the client with `create_mcp_http_client(headers=...)` and pass
  that authenticated client into `streamable_http_client`.

### Gemini `generate_content` could not deep-copy a live MCP session

- **Symptom:** After MCP initialization and successful tool listing, Google's
  SDK raised `TypeError: cannot pickle '_asyncio.Future' object` before calling
  the model.
- **Root cause:** `models.generate_content()` deep-copied its configuration; the
  active MCP `ClientSession` contains non-copyable asyncio state.
- **Fix:** Convert the live MCP tool schemas into serializable Gemini function
  declarations and run an explicit loop: Gemini selects a tool, the client calls
  it through MCP, and the result is returned to Gemini. This avoids copying live
  asyncio state and keeps all actual tool execution on the MCP protocol.

### Sandbox could not create Git's index lock

- **Symptom:** The milestone commit failed before staging with permission denied
  for `.git/index.lock`.
- **Root cause:** This task's sandbox could edit the workspace but had read-only
  access to Git's internal metadata directory during that command.
- **Fix:** Re-run only the reviewed `git add` and `git commit` operations with
  repository metadata permission, then verify the branch and pushed commit.
