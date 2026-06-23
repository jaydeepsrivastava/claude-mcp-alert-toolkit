# Confluence MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only FastMCP server for Confluence with CF-Access + Bearer auth, exposing three tools: `confluence_test_connection`, `confluence_search`, `confluence_get_page`.

**Architecture:** `client.py` owns all HTTP and auth logic, returning `dict | str` (error string on failure). `server.py` registers three FastMCP tools that call the client and format results as strings. Mirrors `mcp-servers/checkmk/` exactly.

**Tech Stack:** Python 3, FastMCP (`mcp==1.26.0`), `requests==2.32.3`, `markdownify>=0.11.6`, `pytest==8.3.5`, `pytest-mock==3.14.0`

## Global Constraints

- Python: follow `from __future__ import annotations` at top of every file
- Confluence base URL is hardcoded: `https://confluence.8x8.com` — not configurable via env var
- Three env vars required at `ConfluenceClient.__init__`: `CONFLUENCE_CLIENT_ID`, `CONFLUENCE_CLIENT_SECRET`, `CONFLUENCE_TOKEN` — raise `ValueError` if any missing
- All tools return `str` — errors returned as-is, never raised as exceptions
- `_is_error(result)` pattern: `isinstance(result, str)` — mirrors checkmk exactly
- No write operations in scope
- Page URL format: `https://confluence.8x8.com/pages/<page_id>`
- Register in `.mcp.json` replacing the existing broken `mcp-atlassian` entry

---

### Task 1: Scaffold + ConfluenceClient

**Files:**
- Create: `mcp-servers/confluence/requirements.txt`
- Create: `mcp-servers/confluence/tests/__init__.py`
- Create: `mcp-servers/confluence/tests/test_client.py`
- Create: `mcp-servers/confluence/client.py`

**Interfaces:**
- Produces: `ConfluenceClient` class with `__init__(self)` and `get(self, endpoint: str, params: dict | None = None) -> dict | str`

---

- [ ] **Step 1: Create requirements.txt**

```
mcp==1.26.0
requests==2.32.3
markdownify>=0.11.6
pytest==8.3.5
pytest-mock==3.14.0
```

Save to `mcp-servers/confluence/requirements.txt`.

- [ ] **Step 2: Create venv and install dependencies**

```bash
cd mcp-servers/confluence
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: packages install cleanly, `.venv/` directory created.

- [ ] **Step 3: Create tests/__init__.py**

Create empty file `mcp-servers/confluence/tests/__init__.py`.

- [ ] **Step 4: Write failing tests for ConfluenceClient**

Create `mcp-servers/confluence/tests/test_client.py`:

```python
from __future__ import annotations

import os
import sys
import pytest
import requests
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("CONFLUENCE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CONFLUENCE_TOKEN", "test-bearer-token")
    import importlib
    import client as c
    importlib.reload(c)


def test_client_sends_cf_access_headers():
    import client as c
    cl = c.ConfluenceClient()
    assert cl.headers["CF-Access-Client-Id"] == "test-client-id"
    assert cl.headers["CF-Access-Client-Secret"] == "test-client-secret"


def test_client_sends_bearer_auth():
    import client as c
    cl = c.ConfluenceClient()
    assert cl.headers["Authorization"] == "Bearer test-bearer-token"


def test_client_get_returns_json_on_200():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [], "size": 0}
    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = cl.get("rest/api/space", params={"limit": 1})
    assert result == {"results": [], "size": 0}
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://confluence.8x8.com/rest/api/space"


def test_client_get_returns_error_on_401():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result == "❌ Auth failed — check CONFLUENCE_TOKEN"


def test_client_get_returns_error_on_403():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result == "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"


def test_client_get_returns_error_on_404():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/content/9999999")
    assert result == "❌ Page not found: rest/api/content/9999999"


def test_client_get_returns_error_on_500():
    import client as c
    cl = c.ConfluenceClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    with patch("requests.get", return_value=mock_resp):
        result = cl.get("rest/api/space")
    assert result.startswith("❌ Server error 500:")


def test_client_get_returns_error_on_connection_error():
    import client as c
    cl = c.ConfluenceClient()
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        result = cl.get("rest/api/space")
    assert result.startswith("❌ Connection failed:")


def test_client_get_returns_error_on_timeout():
    import client as c
    cl = c.ConfluenceClient()
    with patch("requests.get", side_effect=requests.exceptions.Timeout()):
        result = cl.get("rest/api/space")
    assert result == "❌ Request timed out after 30s"


def test_client_raises_on_missing_client_id(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_CLIENT_ID")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_CLIENT_ID"):
        c.ConfluenceClient()


def test_client_raises_on_missing_client_secret(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_CLIENT_SECRET")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_CLIENT_SECRET"):
        c.ConfluenceClient()


def test_client_raises_on_missing_token(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_TOKEN")
    import importlib
    import client as c
    importlib.reload(c)
    with pytest.raises(ValueError, match="CONFLUENCE_TOKEN"):
        c.ConfluenceClient()
```

- [ ] **Step 5: Run tests to confirm they all fail**

```bash
cd mcp-servers/confluence
.venv/bin/pytest tests/test_client.py -v
```

Expected: `ERROR` or `ModuleNotFoundError: No module named 'client'` — file doesn't exist yet.

- [ ] **Step 6: Implement ConfluenceClient**

Create `mcp-servers/confluence/client.py`:

```python
from __future__ import annotations

import os
import requests

_BASE_URL = "https://confluence.8x8.com"
_CLIENT_ID = os.environ.get("CONFLUENCE_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("CONFLUENCE_CLIENT_SECRET", "")
_TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")
_TIMEOUT = int(os.environ.get("CONFLUENCE_TIMEOUT", "30"))


class ConfluenceClient:
    def __init__(self) -> None:
        if not _CLIENT_ID:
            raise ValueError("CONFLUENCE_CLIENT_ID env var is not set")
        if not _CLIENT_SECRET:
            raise ValueError("CONFLUENCE_CLIENT_SECRET env var is not set")
        if not _TOKEN:
            raise ValueError("CONFLUENCE_TOKEN env var is not set")
        self.base_url = _BASE_URL.rstrip("/")
        self.headers = {
            "CF-Access-Client-Id": _CLIENT_ID,
            "CF-Access-Client-Secret": _CLIENT_SECRET,
            "Authorization": f"Bearer {_TOKEN}",
            "Accept": "application/json",
        }
        self.timeout = _TIMEOUT

    def get(self, endpoint: str, params: dict | None = None) -> dict | str:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
        except requests.exceptions.ConnectionError as e:
            return f"❌ Connection failed: {e}"
        except requests.exceptions.Timeout:
            return f"❌ Request timed out after {self.timeout}s"

        if resp.status_code == 401:
            return "❌ Auth failed — check CONFLUENCE_TOKEN"
        if resp.status_code == 403:
            return "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"
        if resp.status_code == 404:
            return f"❌ Page not found: {endpoint}"
        if resp.status_code >= 500:
            return f"❌ Server error {resp.status_code}: {resp.text[:200]}"

        try:
            return resp.json()
        except ValueError:
            return resp.text
```

- [ ] **Step 7: Run tests to confirm they all pass**

```bash
cd mcp-servers/confluence
.venv/bin/pytest tests/test_client.py -v
```

Expected: `13 passed` — all green.

- [ ] **Step 8: Commit**

```bash
git add mcp-servers/confluence/requirements.txt \
        mcp-servers/confluence/client.py \
        mcp-servers/confluence/tests/__init__.py \
        mcp-servers/confluence/tests/test_client.py
git commit -m "feat(confluence-mcp): add ConfluenceClient with CF-Access + Bearer auth"
```

---

### Task 2: FastMCP Server Tools

**Files:**
- Create: `mcp-servers/confluence/tests/test_server.py`
- Create: `mcp-servers/confluence/server.py`

**Interfaces:**
- Consumes: `ConfluenceClient` from `client.py` — `get(endpoint, params) -> dict | str`
- Produces: three MCP tools: `confluence_test_connection()`, `confluence_search(query, limit)`, `confluence_get_page(page_id)`

---

- [ ] **Step 1: Write failing tests for server tools**

Create `mcp-servers/confluence/tests/test_server.py`:

```python
from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("CONFLUENCE_CLIENT_ID", "test-client-id")
os.environ.setdefault("CONFLUENCE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("CONFLUENCE_TOKEN", "test-bearer-token")


@pytest.fixture(autouse=True)
def mock_client_cls():
    with patch("server.ConfluenceClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


# ── confluence_test_connection ───────────────────────────────────────────────

def test_test_connection_success(mock_client_cls):
    from server import confluence_test_connection
    mock_client_cls.get.return_value = {
        "results": [{"name": "VCC Operations"}],
        "size": 1,
    }
    result = confluence_test_connection()
    assert "✅" in result
    assert "VCC Operations" in result
    mock_client_cls.get.assert_called_once_with("rest/api/space", params={"limit": 1})


def test_test_connection_error(mock_client_cls):
    from server import confluence_test_connection
    mock_client_cls.get.return_value = "❌ Auth failed — check CONFLUENCE_TOKEN"
    result = confluence_test_connection()
    assert result == "❌ Auth failed — check CONFLUENCE_TOKEN"


# ── confluence_search ────────────────────────────────────────────────────────

def test_search_returns_results(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {
        "results": [
            {
                "id": "9967739",
                "title": "Clear a Stuck Call",
                "space": {"key": "VCCOPS", "name": "VCC Operations"},
                "excerpt": "<p>This page describes how to clear a stuck call.</p>",
            }
        ],
        "totalSize": 1,
    }
    result = confluence_search("stuck call")
    assert "Clear a Stuck Call" in result
    assert "VCCOPS" in result
    assert "https://confluence.8x8.com/pages/9967739" in result
    assert "stuck call" in result.lower() or "Clear" in result


def test_search_empty_results(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {"results": [], "totalSize": 0}
    result = confluence_search("xyzzy nonexistent")
    assert "⚠️" in result
    assert "xyzzy nonexistent" in result


def test_search_error_passthrough(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"
    result = confluence_search("runbook")
    assert result == "❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET"


def test_search_passes_cql_and_limit(mock_client_cls):
    from server import confluence_search
    mock_client_cls.get.return_value = {"results": [], "totalSize": 0}
    confluence_search("stuck call", limit=5)
    call_params = mock_client_cls.get.call_args[1]["params"]
    assert "stuck call" in call_params["cql"]
    assert call_params["limit"] == 5


# ── confluence_get_page ──────────────────────────────────────────────────────

def test_get_page_returns_markdown(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = {
        "id": "9967739",
        "title": "Clear a Stuck Call",
        "space": {"key": "VCCOPS"},
        "version": {
            "when": "2026-01-15T10:00:00.000Z",
            "by": {"displayName": "Jane Doe"},
        },
        "body": {
            "storage": {
                "value": "<h2>Steps</h2><p>Step 1: Restart the service.</p>"
            }
        },
    }
    result = confluence_get_page("9967739")
    assert "Clear a Stuck Call" in result
    assert "VCCOPS" in result
    assert "Jane Doe" in result
    assert "https://confluence.8x8.com/pages/9967739" in result
    assert "Steps" in result
    assert "Restart the service" in result


def test_get_page_error_passthrough(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = "❌ Page not found: rest/api/content/9999999"
    result = confluence_get_page("9999999")
    assert result == "❌ Page not found: rest/api/content/9999999"


def test_get_page_calls_correct_endpoint(mock_client_cls):
    from server import confluence_get_page
    mock_client_cls.get.return_value = "❌ Page not found: rest/api/content/1234"
    confluence_get_page("1234")
    called_endpoint = mock_client_cls.get.call_args[0][0]
    assert "1234" in called_endpoint
    called_params = mock_client_cls.get.call_args[1]["params"]
    assert "body.storage" in called_params["expand"]
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd mcp-servers/confluence
.venv/bin/pytest tests/test_server.py -v
```

Expected: `ERROR` or `ModuleNotFoundError: No module named 'server'` — file doesn't exist yet.

- [ ] **Step 3: Implement server.py**

Create `mcp-servers/confluence/server.py`:

```python
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
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
cd mcp-servers/confluence
.venv/bin/pytest tests/ -v
```

Expected: `21 passed` — all green (12 client + 9 server tests).

- [ ] **Step 5: Commit**

```bash
git add mcp-servers/confluence/server.py \
        mcp-servers/confluence/tests/test_server.py
git commit -m "feat(confluence-mcp): implement 3 FastMCP tools with unit tests"
```

---

### Task 3: README + MCP Registration

**Files:**
- Create: `mcp-servers/confluence/README.md`
- Modify: `.mcp.json` — replace broken `confluence` entry

**Interfaces:**
- Consumes: all tools from Task 2

---

- [ ] **Step 1: Write README.md**

Create `mcp-servers/confluence/README.md`:

````markdown
# Confluence MCP Server

Read-only MCP server for Confluence. Encapsulates Cloudflare Access (CF-Access) + Bearer token authentication so Claude can search and fetch Confluence pages without constructing curl commands manually.

## Architecture

```
client.py   — ConfluenceClient: CF-Access headers, HTTP requests, error mapping
server.py   — FastMCP: three tool definitions that call ConfluenceClient
tests/      — Unit tests (mocked client and HTTP layer)
```

Mirrors `mcp-servers/checkmk/` structure exactly.

## Prerequisites

Three env vars must be exported in the shell before starting Claude Code:

| Env Var | Purpose | HTTP Header |
|---|---|---|
| `CONFLUENCE_CLIENT_ID` | Cloudflare Access service token ID | `CF-Access-Client-Id` |
| `CONFLUENCE_CLIENT_SECRET` | Cloudflare Access service token secret | `CF-Access-Client-Secret` |
| `CONFLUENCE_TOKEN` | Confluence Personal Access Token | `Authorization: Bearer` |

Add to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
export CONFLUENCE_CLIENT_ID="your-client-id"
export CONFLUENCE_CLIENT_SECRET="your-client-secret"
export CONFLUENCE_TOKEN="your-personal-access-token"
```

## Installation

```bash
cd mcp-servers/confluence
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Tools

### `confluence_test_connection()`
Tests that CF-Access and Confluence credentials are valid. Call this first in any investigation session to confirm auth works before using other tools.

```
✅ Connected to Confluence (sample space: VCC Operations)
```

### `confluence_search(query, limit=10)`
Searches all Confluence spaces using CQL `text ~ "<query>"`. Returns titles, URLs, space names, and excerpts.

```
confluence_search("stuck call", limit=5)
```

```
Found 12 result(s) (showing 5):

[VCCOPS] Clear a Stuck Call
  URL: https://confluence.8x8.com/pages/9967739
  Space: VCC Operations
  Excerpt: This page describes how to clear a stuck call in the IR system...
```

### `confluence_get_page(page_id)`
Fetches a page by its numeric ID and returns the full content as Markdown. Tables, code blocks, and headers are preserved.

Extract the page ID from the URL: `https://confluence.8x8.com/spaces/VCCOPS/pages/9967739/Title` → `9967739`

```
confluence_get_page("9967739")
```

```markdown
# Clear a Stuck Call

**Space:** VCCOPS
**Last modified:** 2026-01-15T10:00:00.000Z
**Author:** Jane Doe
**URL:** https://confluence.8x8.com/pages/9967739

---

## Steps

1. SSH to the IR host...
```

## Development

Run the full test suite:

```bash
cd mcp-servers/confluence
.venv/bin/pytest tests/ -v
```

Expected: 21 tests passing.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ValueError: CONFLUENCE_CLIENT_ID env var is not set` | Env var not exported | Add to shell profile and restart Claude Code |
| `❌ Auth failed — check CONFLUENCE_TOKEN` | Token expired or invalid | Regenerate PAT in Confluence → Profile → Personal Access Tokens |
| `❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET` | CF-Access service token invalid or expired | Rotate token in Cloudflare Access dashboard |
| `❌ Page not found: rest/api/content/<id>` | Wrong page ID | Extract numeric ID from URL segment `.../pages/<ID>/` |
| `❌ Connection failed: ...` | Network or DNS issue | Check VPN / network connectivity to `confluence.8x8.com` |

## Out of Scope (this version)

Write operations (create/update pages) are not implemented. When added, creation space will be `VCCOPS`.
````

- [ ] **Step 2: Update .mcp.json — replace the broken confluence entry**

Read the current `.mcp.json` first, then replace the `"confluence"` block:

```json
"confluence": {
  "type": "stdio",
  "command": "/home/jaydeep/jaydeep_claude/mcp-servers/confluence/.venv/bin/python",
  "args": ["/home/jaydeep/jaydeep_claude/mcp-servers/confluence/server.py"]
}
```

The old entry used `uvx mcp-atlassian` with `--confluence-spaces-filter CCE` and no CF-Access env vars — remove it entirely and replace with the entry above.

- [ ] **Step 3: Smoke-test the server starts cleanly**

```bash
cd mcp-servers/confluence
CONFLUENCE_CLIENT_ID=x CONFLUENCE_CLIENT_SECRET=y CONFLUENCE_TOKEN=z \
  .venv/bin/python server.py &
sleep 2 && kill %1
```

Expected: server starts without import errors. Output may show FastMCP startup message. No `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 4: Commit**

```bash
git add mcp-servers/confluence/README.md .mcp.json
git commit -m "feat(confluence-mcp): register MCP server and add README"
```

---

### Task 4: Live Connection Verification

**Files:** None — verification only.

---

- [ ] **Step 1: Restart Claude Code to pick up the new MCP server**

Close and reopen Claude Code (or reload MCP servers via `/mcp`). The `confluence` server should appear in the connected MCP list.

- [ ] **Step 2: Test connection**

In Claude Code, ask:
```
call confluence_test_connection
```

Expected: `✅ Connected to Confluence (sample space: <name>)`

If `❌ Auth failed` → check `CONFLUENCE_TOKEN` is exported in your shell.
If `❌ CF-Access rejected` → check `CONFLUENCE_CLIENT_ID` and `CONFLUENCE_CLIENT_SECRET`.
If server not listed → check `.mcp.json` path is correct and `.venv` exists.

- [ ] **Step 3: Test search**

```
call confluence_search with query "stuck call"
```

Expected: at least one result with title, URL, space, and excerpt.

- [ ] **Step 4: Test page fetch**

Pick a page ID from search results and call:
```
call confluence_get_page with page_id "<id from search>"
```

Expected: Markdown output with title, metadata header, and page body with headers/tables preserved.

- [ ] **Step 5: Update CLAUDE.md Confluence reference**

In `/home/jaydeep/jaydeep_claude/CLAUDE.md`, under `## MCP Tools`, update the Confluence reference to note the MCP is now available:

Change the existing Confluence curl pattern reference to:
```
- **Confluence**: MCP `confluence` (preferred) | tools: `confluence_test_connection`, `confluence_search`, `confluence_get_page` | curl fallback: `memory/reference_confluence_access.md`
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(confluence-mcp): update CLAUDE.md to reference confluence MCP tools"
```
