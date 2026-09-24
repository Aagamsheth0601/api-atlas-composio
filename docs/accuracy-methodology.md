# Accuracy and verification methodology

API Atlas does not treat model confidence as accuracy. Accuracy is measured
against retrieved sources and independent checks.

## First-pass controls

1. Gemini 2.5 Flash performs the research; Flash-Lite is not used because it
   failed to complete the tested multi-step MCP research loop.
2. Search snippets are discovery aids. Decisive claims should cite fetched
   official developer, help, pricing, partner, or first-party repository pages.
3. Evidence is attached to claims rather than supplied as one generic app URL.
4. Unknown and human-review states are valid outputs. The agent must not convert
   missing evidence into a confident conclusion.
5. JSON Schema and consistency rules reject malformed or internally conflicting
   records before they enter the dataset.

## Verification sample

The final audit will include:

- 20 stratified apps: two from each supplied category;
- every record with low confidence, contradictory evidence, or missing decisive
  fields, even when this increases the sample beyond 20;
- a mix of build-now, constrained, outreach, blocked, and unclear verdicts;
- both well-known apps and obscure/adversarial apps.

For each sampled app, a verifier and a human/browser check will independently
assess five decisive fields:

1. authentication method;
2. credential access/gating;
3. API type and breadth;
4. MCP availability;
5. buildability and primary blocker.

With 20 sampled apps, this yields at least 100 field-level decisions. The case
study will report first-pass correct/incorrect/unclear counts, the error types,
the corrections made, post-correction accuracy, and unresolved claims. No
accuracy percentage will be claimed before this audit exists.

## Billing and production scaling

This take-home uses the available Gemini free tier and a resumable pipeline.
Enabling billing would raise throughput limits and make it practical to run more
independent verifier passes in parallel. It is a production scaling improvement,
not a substitute for evidence or human verification, and it was not used for the
reported take-home results.

