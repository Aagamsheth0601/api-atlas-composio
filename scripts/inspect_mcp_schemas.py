"""Print enabled Composio MCP tool schemas without exposing credentials."""

from __future__ import annotations

import asyncio
import argparse
import json
import os
from pathlib import Path

from composio import Composio, SESSION_PRESET_DIRECT_TOOLS
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client


ROOT = Path(__file__).resolve().parents[1]


async def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY is missing or empty in .env")

    session = Composio(api_key=api_key).sessions.create(
        user_id="api-atlas-schema-inspection",
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
    async with create_mcp_http_client(headers=session.mcp.headers) as http_client:
        async with streamable_http_client(
            session.mcp.url, http_client=http_client
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as mcp_session:
                await mcp_session.initialize()
                tools = await mcp_session.list_tools()
                for tool in tools.tools:
                    print(tool.name)
                    print(json.dumps(tool.inputSchema, indent=2))
                if args.probe:
                    result = await mcp_session.call_tool(
                        "COMPOSIO_SEARCH_TAVILY",
                        arguments={
                            "query": "site:developers.hubspot.com API authentication OAuth private app",
                            "max_results": 3,
                            "search_depth": "basic",
                            "include_answer": False,
                            "include_raw_content": False,
                        },
                    )
                    print("PROBE_RESULT")
                    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(run())
