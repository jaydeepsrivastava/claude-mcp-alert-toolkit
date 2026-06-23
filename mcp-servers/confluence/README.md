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
