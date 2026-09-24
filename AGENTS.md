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

### PowerShell consumed Markdown backticks in an inline Python test

- **Symptom:** A one-line parser test failed with an unterminated Python string
  even though both source modules compiled.
- **Root cause:** PowerShell treated the Markdown fence backticks inside the
  `python -c` argument as escape characters before Python received the text.
- **Fix:** Keep fenced-parser cases in Python test files and avoid embedding
  backticks in PowerShell command strings.

### First feasibility batch exposed taxonomy and quota gaps

- **Symptom:** Salesforce was rejected because the schema did not allow SOAP;
  fanbasis hit Gemini's five-requests-per-minute free-tier limit; PitchBook
  validated after five MCP calls.
- **Root cause:** The API taxonomy was incomplete, and the first pipeline version
  surfaced rate limits but did not retry or resume completed records.
- **Fix:** Add `soap`, checkpoint by app, reuse validated records, apply bounded
  rate-limit retries, and enforce a three-minute per-app timeout.

### Flash-Lite stopped after its first MCP result

- **Symptom:** `gemini-2.5-flash-lite` selected Tavily but then returned neither
  another tool call nor final text after receiving the search result.
- **Root cause:** The smaller model did not reliably complete this multi-step
  research loop under the same prompt and tool schemas.
- **Fix:** Keep `gemini-2.5-flash` for evidence research. Do not treat a cheaper
  model as equivalent without a measured quality comparison.

### PowerShell cleanup masked a failed process exit code

- **Symptom:** The combined command reported exit code zero even though the
  Python smoke test raised a runtime error.
- **Root cause:** A later `Remove-Item Env:GOOGLE_MODEL` command succeeded and
  became the PowerShell process's final exit status.
- **Fix:** Inspect the Python trace, never use a cleanup command as proof of test
  success, and run behavioral verification as the final command or explicitly
  preserve its exit code.

### Direct script execution could not import the local package

- **Symptom:** `python scripts/research_apps.py --help` failed with
  `ModuleNotFoundError: No module named 'api_atlas'`.
- **Root cause:** Python placed the `scripts` directory, rather than the repository
  root, at the front of `sys.path` for direct file execution.
- **Fix:** Bootstrap the resolved repository root before importing the local
  package, and keep the documented direct command covered by a subprocess test.

### Temporary Gemini 503s were recorded as app failures

- **Symptom:** HubSpot failed immediately with `503 UNAVAILABLE` during the full
  run even though the message identified a temporary high-demand spike.
- **Root cause:** The retry policy covered quota `429` responses but not transient
  provider outages.
- **Fix:** Retry both 429 rate limits and 503 unavailable responses with bounded
  delays. Checkpointing keeps completed apps and failed apps are retried on resume.

### Gemini Flash daily quota interrupted batched synthesis

- **Symptom:** The optimized runner collected evidence for five apps, then Gemini
  rejected the single synthesis call with the free-tier limit of 20 requests per
  day for `gemini-2.5-flash`.
- **Root cause:** Earlier feasibility calls consumed the daily model allowance,
  and the runner only checkpointed after synthesis rather than after retrieval.
- **Fix:** Cache each MCP evidence packet immediately, allow an explicit synthesis
  model, and resume without repeating retrieval. Do not silently downgrade to
  Flash-Lite.

### Listed Gemini 2.5 Pro model was retired for new users

- **Symptom:** The model-list API returned `gemini-2.5-pro`, but generation failed
  with 404 and directed new users to Gemini 3.1 Pro Preview. Gemini 3.1 Pro then
  reported a free-tier quota of zero.
- **Root cause:** Model discovery describes catalog entries, not entitlement or
  usable free-tier quota.
- **Fix:** Treat an actual bounded generation as the capability check. Use the
  accessible Gemini 3 Flash Preview for the pilot and measure its output against
  the deep baseline; document that billed Pro synthesis remains an upgrade path.

### Fast-path synthesis did not retry temporary model outages

- **Symptom:** Cached five-app evidence reached Gemini 3 Flash synthesis, which
  returned a temporary 503 high-demand response.
- **Root cause:** Transient retry handling existed only in the original deep
  runner, not the new batched runner.
- **Fix:** Add bounded 503 and per-minute 429 retries to batch synthesis while
  failing immediately for daily or zero-quota billing gates.

### PowerShell parsed a formatting pipe inside inline Python

- **Symptom:** A model-catalog inspection command failed because the `|` used as
  display punctuation inside an inline Python f-string was treated as a
  PowerShell pipeline operator.
- **Root cause:** Nested shell quoting made the pipe visible to PowerShell before
  Python received the command.
- **Fix:** Avoid shell-sensitive punctuation in inline Python commands and move
  reusable network logic into tested project modules.

### Antigravity's 12k budget ended before a final answer

- **Symptom:** The first managed-agent smoke test completed quickly but returned
  `status: incomplete`, no `output_text`, and about 15k total tokens used.
- **Root cause:** Agent planning and two grounded searches consumed more than the
  12k best-effort budget before it could synthesize the requested JSON.
- **Fix:** Reject incomplete interactions explicitly and use a measured 30k cap
  for the single-app pilot before choosing a safe multi-app batch size.

### Antigravity MCP configuration errors lacked provider details

- **Symptom:** The three-app MCP pilot returned HTTP 400 for every app while the
  runner displayed only a generic `HTTPStatusError` link.
- **Root cause:** `raise_for_status()` discarded the useful validation body in
  user-facing logs, and the pilot lacked a one-app configuration mode.
- **Fix:** Surface a bounded response body and add `--limit` so configuration is
  proven on one app before spending requests across a batch.

### Full runner skipped batches during the Antigravity TPM window

- **Symptom:** Immediately after a successful deep batch, the resumed runner
  received a 429 with an explicit retry delay and rapidly marked subsequent
  batches failed instead of waiting.
- **Root cause:** The runner checkpointed content failures but lacked quota-aware
  transport retry handling.
- **Fix:** Parse Google's stated TPM retry delay, wait once with a small buffer,
  and retry the same batch up to three times. Failed records remain resumable.

### Seven-app fast synthesis omitted one record

- **Symptom:** Flash-Lite returned six records for the seven-app batch covering
  IDs 58–64.
- **Root cause:** The batch was too large for reliable constrained extraction;
  accepting it would have risked mapping records to the wrong apps.
- **Fix:** Reject the batch atomically, retain its cached MCP evidence, and resume
  the remaining dataset in five-app batches on the available Gemini 3.8 Flash
  quota.
