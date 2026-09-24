"""Deterministic evidence collection for the low-call research path."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession


def mcp_text(result: Any) -> str:
    """Join text blocks from an MCP tool result."""

    blocks = result.model_dump(mode="json").get("content", [])
    return "\n".join(
        block.get("text", "") for block in blocks if block.get("type") == "text"
    )


def search_payload(result: Any) -> dict[str, Any]:
    """Unwrap Composio Search's JSON-in-an-MCP-text response."""

    envelope = json.loads(mcp_text(result))
    if not envelope.get("successful") or envelope.get("error"):
        raise RuntimeError(f"Composio search failed: {envelope.get('error')}")
    return envelope["data"]


def result_urls(payload: dict[str, Any]) -> list[str]:
    return [
        item["url"]
        for item in payload.get("results", [])
        if isinstance(item, dict) and item.get("url")
    ]


def same_domain(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    expected = domain.casefold().removeprefix("www.")
    return host == expected or host.endswith(f".{expected}")


async def collect_evidence(
    session: ClientSession, app: dict[str, Any]
) -> dict[str, Any]:
    """Search predictably, then fetch a bounded set of first-party pages."""

    domain = app["website_hint"]
    official = await session.call_tool(
        "COMPOSIO_SEARCH_TAVILY",
        arguments={
            "query": (
                f"site:{domain} {app['app']} developer API authentication OAuth "
                "API key credentials pricing plan access public REST GraphQL"
            ),
            "max_results": 6,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    access = await session.call_tool(
        "COMPOSIO_SEARCH_TAVILY",
        arguments={
            "query": (
                f"site:{domain} {app['app']} developer account API credentials "
                "free trial paid plan admin approval partner contact sales"
            ),
            "max_results": 6,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    ecosystem = await session.call_tool(
        "COMPOSIO_SEARCH_TAVILY",
        arguments={
            "query": (
                f'"{app["app"]}" official MCP server GitHub '
                f'site:composio.dev/toolkits OR site:github.com'
            ),
            "max_results": 6,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    official_payload = search_payload(official)
    access_payload = search_payload(access)
    ecosystem_payload = search_payload(ecosystem)
    urls = []
    for payload in (official_payload, access_payload):
        for url in result_urls(payload):
            if same_domain(url, domain) and url not in urls:
                urls.append(url)
    urls = urls[:6]
    fetched_text = ""
    if urls:
        fetched = await session.call_tool(
            "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
            arguments={
                "urls": urls,
                "text": True,
                "summary": False,
                "max_characters": 3500,
            },
        )
        fetched_text = mcp_text(fetched)

    return {
        "evidence_version": 2,
        "app": app,
        "official_search": official_payload,
        "access_search": access_payload,
        "ecosystem_search": ecosystem_payload,
        "fetched_official_pages": fetched_text,
        "fetched_urls": urls,
    }


def batch_prompt(
    packets: list[dict[str, Any]], schema: dict[str, Any]
) -> str:
    """Ask Gemini to extract records only from the supplied evidence packets."""

    return f"""
You are the extraction stage of API Atlas. Convert the supplied evidence packets
into one JSON array in the same order. Every array item must validate against the
provided per-item schema.

Accuracy rules:
1. Use only the supplied evidence. Search snippets are weaker than fetched pages.
2. Prefer first-party documentation. A search result is not proof that credentials
   are self-serve or that an MCP server is official.
3. Attach evidence to individual claims with precise URLs and source types.
4. Preserve unknowns. Set human_review_required=true for missing decisive proof,
   contradictions, confidence below 0.75, or a verdict based only on snippets.
5. "No MCP found" means the supplied searches found no credible MCP; do not turn it
   into proof that none exists.
6. Return only the JSON array, without a Markdown fence or commentary.

PER-ITEM JSON SCHEMA:
{json.dumps(schema, separators=(',', ':'))}

EVIDENCE PACKETS:
{json.dumps(packets, separators=(',', ':'))}
""".strip()


def extract_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
    value = json.loads(cleaned)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("Batch output must be a JSON array of objects")
    return value
