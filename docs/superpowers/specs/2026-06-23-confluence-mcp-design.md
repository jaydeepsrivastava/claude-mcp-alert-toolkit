# Confluence MCP Server — Design Spec

**Date:** 2026-06-23  
**Status:** Approved  
**Scope:** Read-only FastMCP server for Confluence, replacing the broken `mcp-atlassian` entry

---

## Problem

`https://confluence.8x8.com` is behind Cloudflare Access. `WebFetch` redirects to a login page. The existing `.mcp.json` entry uses `mcp-atlassian`, which has no support for CF-Access service token headers and will fail identically. During live investigations, Claude must manually construct curl commands to fetch runbooks — error-prone and slow.

---

## Goal

A custom FastMCP server that encapsulates CF-Access + Bearer auth once, exposes three clean tools, and returns Confluence page content as Markdown so runbooks are directly usable during incident investigation.

---

## Architecture

```
mcp-servers/confluence/
├── client.py          # ConfluenceClient — auth, HTTP, error mapping
├── server.py          # FastMCP — tool definitions
├── requirements.txt   # mcp, requests, markdownify
├── tests/
│   ├── __init__.py
│   ├── test_client.py
│   └── test_server.py
└── README.md
```

Follows the same structure as `mcp-servers/checkmk/` exactly.

---

## Authentication

`ConfluenceClient.__init__` reads three env vars. All must be present — missing any raises `ValueError` at startup.

| Env Var | HTTP Header |
|---|---|
| `CONFLUENCE_CLIENT_ID` | `CF-Access-Client-Id` |
| `CONFLUENCE_CLIENT_SECRET` | `CF-Access-Client-Secret` |
| `CONFLUENCE_TOKEN` | `Authorization: Bearer <token>` |

All three are already exported in the user's shell environment.

---

## Tools

### `confluence_test_connection()`
Hits `GET /rest/api/space?limit=1`. Confirms all three auth headers are accepted by Cloudflare Access and the Confluence API. Returns `✅ Connected — X spaces accessible` or a specific error string.

Call first in any investigation to confirm credentials before using other tools.

### `confluence_search(query: str, limit: int = 10)`
Executes CQL `text ~ "<query>"` with no space filter (all spaces). Returns up to `limit` results, each containing:
- Page title
- Space key and space name
- Direct URL (`https://confluence.8x8.com/pages/<id>`)
- Excerpt — first ~200 chars of body text (plain text, for quick scanning)

### `confluence_get_page(page_id: str)`
Fetches `GET /rest/api/content/<id>?expand=body.storage,version,space`. Returns:
- Title, space key, last-modified timestamp, last author
- Full page body converted from Confluence storage XML to **Markdown** via `markdownify`
- Page URL

Page ID is the numeric segment from the page URL: `.../pages/9967739/Title` → `9967739`.

---

## Data Flow

```
Claude tool call
    └─▶ server.py tool function
            └─▶ ConfluenceClient.get(endpoint, params)
                    ├─▶ requests.get() with CF-Access + Bearer headers
                    │       ├─▶ dict  (success)
                    │       └─▶ str   (error message)
                    └─▶ server tool checks _is_error()
                            ├─▶ return error string as-is
                            └─▶ format + return result string
```

For `confluence_get_page`: raw `body.storage.value` (Confluence XML) is passed through `markdownify.markdownify()` before returning.

---

## Error Handling

`ConfluenceClient.get()` returns `dict | str`. A `str` return is always an error. Server tools use `_is_error(result)` before processing — identical to checkmk pattern.

| Condition | Return |
|---|---|
| HTTP 401 | `❌ Auth failed — check CONFLUENCE_TOKEN` |
| HTTP 403 | `❌ CF-Access rejected — check CONFLUENCE_CLIENT_ID/SECRET` |
| HTTP 404 | `❌ Page not found: <page_id>` |
| HTTP 5xx | `❌ Server error <code>: <first 200 chars>` |
| Connection error | `❌ Connection failed: <reason>` |
| Timeout (30s default) | `❌ Request timed out after 30s` |
| Missing env var | `ValueError` raised at `__init__` — fails fast at server startup |

---

## Dependencies

```
mcp==1.26.0
requests==2.32.3
markdownify>=0.11.6
pytest==8.3.5
pytest-mock==3.14.0
```

`markdownify` converts Confluence storage format (XHTML-like) to clean Markdown. Handles tables, code blocks, headers, lists — critical for runbooks.

---

## Testing Strategy

### `test_client.py`
Mocks `requests.get` directly. Verifies:
- All three auth headers present in every request
- Each HTTP error code (401, 403, 404, 5xx) returns correct error string
- Timeout returns correct error string
- Connection error returns correct error string
- Missing env var raises `ValueError`

### `test_server.py`
`autouse` fixture patches `ConfluenceClient` at the server module level (same pattern as checkmk).
- `confluence_test_connection`: success path, error passthrough
- `confluence_search`: results formatted correctly, empty results, error passthrough
- `confluence_get_page`: markdown conversion present in output, missing page, error passthrough

---

## Registration

Replace the existing broken `confluence` entry in `.mcp.json`:

```json
"confluence": {
  "type": "stdio",
  "command": "/home/jaydeep/jaydeep_claude/mcp-servers/confluence/.venv/bin/python",
  "args": ["/home/jaydeep/jaydeep_claude/mcp-servers/confluence/server.py"]
}
```

No additional env vars needed in `.mcp.json` — all three Confluence env vars are already exported in the shell environment at Claude Code startup.

---

## Out of Scope (this iteration)

- Write operations (create page, update page) — to be added later, creation space will be VCCOPS
- Page hierarchy / child page listing
- Attachment fetching
- Space-level browsing
