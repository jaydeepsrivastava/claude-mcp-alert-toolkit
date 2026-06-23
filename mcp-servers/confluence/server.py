from __future__ import annotations

import re
from mcp.server.fastmcp import FastMCP
from markdownify import markdownify
from client import ConfluenceClient

mcp = FastMCP("confluence")

_BASE_URL = "https://confluence.8x8.com"


def _client() -> ConfluenceClient:
    return ConfluenceClient()


def _is_error(result: object) -> bool:
    return isinstance(result, str)


@mcp.tool()
def confluence_test_connection() -> str:
    """Test connectivity and credentials. Call first to confirm Confluence is reachable before using other tools."""
    client = _client()
    result = client.get("rest/api/space", params={"limit": 1})
    if _is_error(result):
        return result
    assert isinstance(result, dict)
    results = result.get("results", [])
    sample = results[0].get("name", "unknown") if results else "none"
    return f"✅ Connected to Confluence (sample space: {sample})"


@mcp.tool()
def confluence_search(query: str, limit: int = 10) -> str:
    """Search Confluence pages across all spaces by keyword.
    query: search term or phrase
    limit: max results to return (default 10)"""
    client = _client()
    result = client.get(
        "rest/api/content/search",
        params={
            "cql": f'text ~ "{query}" AND type = "page"',
            "limit": limit,
            "expand": "space,excerpt",
        },
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    results = result.get("results", [])
    if not results:
        return f"⚠️ No pages found for: {query}"

    total = result.get("totalSize", len(results))
    lines = [f"Found {total} result(s) (showing {len(results)}):"]
    for page in results:
        page_id = page.get("id", "")
        title = page.get("title", "Untitled")
        space = page.get("space", {})
        space_key = space.get("key", "?")
        space_name = space.get("name", "?")
        excerpt = re.sub(r"<[^>]+>", "", page.get("excerpt", ""))[:200]
        url = f"{_BASE_URL}/pages/{page_id}"
        lines.append(
            f"\n[{space_key}] {title}\n"
            f"  URL: {url}\n"
            f"  Space: {space_name}\n"
            f"  Excerpt: {excerpt}"
        )
    return "\n".join(lines)


@mcp.tool()
def confluence_get_page(page_id: str) -> str:
    """Fetch a Confluence page by ID and return its content as Markdown.
    page_id: numeric ID from the page URL (e.g. from .../pages/9967739/Title, use 9967739)"""
    client = _client()
    result = client.get(
        f"rest/api/content/{page_id}",
        params={"expand": "body.storage,version,space"},
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    title = result.get("title", "Untitled")
    space_key = result.get("space", {}).get("key", "?")
    version = result.get("version", {})
    last_modified = version.get("when", "?")
    author = version.get("by", {}).get("displayName", "?")
    url = f"{_BASE_URL}/pages/{page_id}"
    html = result.get("body", {}).get("storage", {}).get("value", "")
    body_md = markdownify(html, heading_style="ATX")

    return (
        f"# {title}\n\n"
        f"**Space:** {space_key}  \n"
        f"**Last modified:** {last_modified}  \n"
        f"**Author:** {author}  \n"
        f"**URL:** {url}\n\n"
        f"---\n\n"
        f"{body_md}"
    )


if __name__ == "__main__":
    mcp.run()
