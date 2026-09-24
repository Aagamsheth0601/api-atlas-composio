"""Milestone 1: prove the Composio SDK -> MCP -> Gemini path works.

This script intentionally researches one narrow claim before the project scales
to three apps and then 100. It never prints API keys or MCP header values.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "data" / "runs"


def require_secret(name: str) -> str:
    """Return a required secret without logging its value."""

    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is missing or empty in .env")
    return value


async def run_gemini_tool_loop(
    client: genai.Client,
    mcp_session: ClientSession,
    listed_tools: Any,
    prompt: str,
) -> str:
    """Run an explicit Gemini function-calling loop backed by MCP execution."""

    declarations = [
        types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "Composio MCP research tool",
            parameters_json_schema=tool.inputSchema,
        )
        for tool in listed_tools.tools
    ]
    config = types.GenerateContentConfig(
        temperature=0,
        tools=[types.Tool(function_declarations=declarations)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    )
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]

    for turn in range(1, 7):
        response = await client.aio.models.generate_content(
            model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            contents=contents,
            config=config,
        )
        function_calls = response.function_calls or []
        if not function_calls:
            if not response.text:
                raise RuntimeError("Gemini returned neither tool calls nor text")
            return response.text

        print(
            f"Tool turn {turn}: "
            + ", ".join(call.name or "unnamed" for call in function_calls),
            flush=True,
        )
        contents.append(response.candidates[0].content)
        result_parts: list[types.Part] = []
        for call in function_calls:
            if not call.name:
                raise RuntimeError("Gemini emitted a tool call without a name")
            result = await mcp_session.call_tool(
                call.name,
                arguments=dict(call.args or {}),
            )
            result_parts.append(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result.model_dump(mode="json")},
                )
            )
        contents.append(types.Content(role="tool", parts=result_parts))

    raise RuntimeError("Gemini exceeded the six-turn research limit")


async def run() -> None:
    load_dotenv(ROOT / ".env")
    composio_key = require_secret("COMPOSIO_API_KEY")
    google_key = require_secret("GOOGLE_API_KEY")

    # Catch the consumer-key/project-key mix-up before sending a request.
    if not composio_key.startswith("ak_"):
        raise RuntimeError(
            "COMPOSIO_API_KEY is not a project key (expected an ak_ prefix). "
            "Use Settings -> Project Settings -> API Keys."
        )

    composio = Composio(api_key=composio_key)
    session = composio.sessions.create(
        user_id="api-atlas-smoke-test",
        toolkits=["composio_search"],
        tools={
            "composio_search": {
                "enable": [
                    "COMPOSIO_SEARCH_TAVILY",
                    "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
                ]
            }
        },
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
        mcp=True,
    )

    print(f"Composio session: {session.session_id}", flush=True)
    print(f"MCP host: {urlparse(session.mcp.url).netloc}", flush=True)
    print(
        f"MCP auth headers: {sorted(session.mcp.headers.keys())}", flush=True
    )
    print("Connecting local MCP client to Composio...", flush=True)

    client = genai.Client(api_key=google_key)
    async with create_mcp_http_client(
        headers=session.mcp.headers
    ) as http_client:
        async with streamable_http_client(
            session.mcp.url,
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as mcp_session:
                await mcp_session.initialize()
                listed_tools = await mcp_session.list_tools()
                print(
                    "MCP tools: "
                    + ", ".join(tool.name for tool in listed_tools.tools),
                    flush=True,
                )
                print("Starting Gemini + MCP research call...", flush=True)
                result_text = await run_gemini_tool_loop(
                    client,
                    mcp_session,
                    listed_tools,
                    "Use the Composio research tools to find official Salesforce "
                    "documentation establishing the authentication methods "
                    "available for its REST API. Return compact JSON with keys "
                    "summary and official_urls. Do not rely on search snippets "
                    "when a source page can be fetched."
                )
    await client.aio.aclose()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RUNS_DIR / "salesforce-smoke.json"
    output_path.write_text(
        json.dumps(
            {
                "session_id": session.session_id,
                "result": result_text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Research result:")
    print(result_text)
    print(f"Saved ignored run artifact: {output_path.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(run())
