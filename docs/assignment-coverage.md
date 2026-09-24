# Assignment coverage

This checklist prevents presentation work from hiding missing evidence or
verification work.

## Per-app research

- [x] Category and one-line description fields
- [x] OAuth2, API key, Basic, token, other, and unknown auth values
- [x] Free/trial/paid self-serve, admin-gated, partner-gated, and unknown access
- [x] REST, GraphQL, SOAP, SDK, CLI, webhook, other, and unknown API types
- [x] API breadth and public-documentation fields
- [x] Official/community/no-MCP distinction
- [x] Composio toolkit availability
- [x] Buildability verdict, rationale, and primary blocker
- [x] Claim-level evidence URLs and retrieval timestamps
- [x] Confidence, missing fields, contradictions, and human-review flags
- [ ] Research and validate all 100 apps

## Patterns and Product Ops decisions

- [x] Preserve the supplied ten market categories
- [x] Cross-category integration archetypes
- [x] Readiness cohorts for build, constraints, outreach, review, and blockers
- [x] Auth-burden clustering
- [ ] Calculate auth distribution across all 100
- [ ] Compare self-serve/gating patterns by category and archetype
- [ ] Rank common blockers and identify easy wins versus outreach
- [ ] Write evidence-backed headline findings

## Agent and proof

- [x] Live Composio Python SDK session creation
- [x] Authenticated Composio MCP tool discovery and execution
- [x] Gemini research/tool-selection loop
- [x] Search followed by fetched-source inspection
- [x] Schema rejection, visible failures, retries, timeout, and resume behavior
- [ ] Runnable single-app trigger suitable for the case-study proof section
- [ ] Final run instructions and architecture in README

## Verification

- [x] Automated schema and manifest checks
- [x] Human-review queue based on uncertainty
- [ ] Stratified verification sample across all ten categories
- [ ] Independent source/browser cross-checks
- [ ] Field-level accuracy score for first pass
- [ ] Correct sampled mistakes and rerun validators
- [ ] Report final accuracy and remaining unresolved cases

## Submission

- [ ] Two-minute self-explanatory HTML case study
- [ ] Headline patterns above the fold
- [ ] Searchable/filterable 100-app matrix
- [ ] Agent workflow and honest human-intervention section
- [ ] Verification hits, misses, and accuracy movement
- [ ] Live deployment
- [x] Private source repository during development
- [ ] Reviewer-accessible repository decision and final secret scan

