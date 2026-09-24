# API Atlas

API Atlas is an evidence-first research agent for deciding whether requested
apps can become agent toolkits today. It gathers claim-level evidence, measures
credential friction and API breadth, queues uncertain findings for review, and
tracks how verification changes accuracy.

## Current checkpoint

The repository contains the frozen record schema and a deliberately varied
three-app feasibility set. The next checkpoint is one live Composio SDK + MCP
research run before scaling to all 100 apps.

## Secret setup

Copy `.env.example` to `.env` and populate it locally. `.env` is gitignored.
Use a Composio **project API key** from Settings -> Project Settings -> API
Keys, not a `ck_...` consumer MCP key.

