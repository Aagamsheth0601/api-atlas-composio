"""Gemini reasoning loop with all external research executed through MCP."""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types
from mcp import ClientSession


def extract_json(text: str) -> dict[str, Any]:
    """Parse one JSON object, tolerating a Markdown JSON fence."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Research output must be one JSON object")
    return value


def tool_declarations(listed_tools: Any) -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "Composio MCP research tool",
            parameters_json_schema=tool.inputSchema,
        )
        for tool in listed_tools.tools
    ]


async def research_with_mcp(
    client: genai.Client,
    mcp_session: ClientSession,
    listed_tools: Any,
    prompt: str,
    max_turns: int = 8,
) -> tuple[str, list[str]]:
    """Let Gemini select tools while executing every tool through MCP."""

    config = types.GenerateContentConfig(
        temperature=0,
        tools=[types.Tool(function_declarations=tool_declarations(listed_tools))],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]
    trace: list[str] = []

    for _ in range(max_turns):
        response = await client.aio.models.generate_content(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            contents=contents,
            config=config,
        )
        calls = response.function_calls or []
        if not calls:
            if not response.text:
                raise RuntimeError("Gemini returned neither tool calls nor text")
            return response.text, trace

        contents.append(response.candidates[0].content)
        result_parts: list[types.Part] = []
        for call in calls:
            if not call.name:
                raise RuntimeError("Gemini emitted an unnamed tool call")
            trace.append(call.name)
            result = await mcp_session.call_tool(
                call.name, arguments=dict(call.args or {})
            )
            result_parts.append(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result.model_dump(mode="json")},
                )
            )
        contents.append(types.Content(role="tool", parts=result_parts))

    raise RuntimeError(f"Research exceeded the {max_turns}-turn limit")


def build_prompt(app: dict[str, Any], schema: dict[str, Any]) -> str:
    """Create an evidence-first brief whose output must match our schema."""

    return f"""
You are the research agent in API Atlas, an integration-intelligence pipeline.

Research this app:
- id: {app['id']}
- app: {app['app']}
- category: {app['category']}
- website hint: {app['website_hint']}

Determine what it does, auth methods, whether credentials are self-serve or
gated, API type and breadth, existing MCP availability, Composio toolkit
availability, and whether an agent toolkit is buildable today.

Rules:
1. Prefer official developer, help, pricing, partner, and first-party repository
   sources. Search snippets are leads, not evidence: fetch decisive pages.
2. Attach evidence to claims. Never guess when evidence is absent.
3. "API docs exist" does not prove credentials are self-serve.
4. Distinguish official MCP, community MCP, and no MCP found.
5. Set human_review_required=true for ambiguity, missing decisive evidence,
   contradictions, or confidence below 0.75.
6. Return ONLY one JSON object. No Markdown fence or commentary.
7. The JSON must validate against this exact JSON Schema:

{json.dumps(schema, separators=(',', ':'))}
""".strip()

