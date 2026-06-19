# CheckMK MCP Server — Technical Design Spec

**Date:** 2026-06-19  
**Author:** Jaydeep Srivastava (via Claude)  
**Status:** Draft — pending implementation

---

## 1. Purpose

Create a lightweight, read-only MCP server that exposes CheckMK monitoring data to Claude Code for use in the alert investigation workflow. Claude should be able to look up host status, failing services, and current problems without switching context to the CheckMK UI or writing curl commands manually.

---

## 2. Scope — GET Only

This server exposes **read-only** operations only. No writes, no acknowledges, no downtimes (those can be done via curl from CLAUDE.md if needed).

---

## 3. Reference Repos Reviewed

### 3.1 chexma/vibeMK (external)
- **URL:** https://github.com/chexma/vibeMK
- **Language:** Python (raw JSON-RPC stdin/stdout — no FastMCP)
- **Scope:** Full CRUD — 60+ tools covering hosts, services, users, rules, rulesets, downtimes, acknowledgements, discovery, metrics, passwords
- **API client:** `api/client.py` — well-structured, handles auto URL detection (5 URL patterns tried), SSL context, retry with exponential backoff, all HTTP methods
- **Config vars:** `CHECKMK_SERVER_URL`, `CHECKMK_SITE`, `CHECKMK_USERNAME`, `CHECKMK_PASSWORD`, `CHECKMK_VERIFY_SSL`, `CHECKMK_TIMEOUT`, `CHECKMK_MAX_RETRIES`
- **Decision:** Too large for our needs. We borrow the **API client pattern** (URL detection, SSL, retry) but not the full server. We use FastMCP instead of raw JSON-RPC.

### 3.2 8x8/contact-center-tools (internal)
- **URL:** https://github.com/8x8/contact-center-tools (cloned at `/home/jaydeep/jaydeep_claude/contact-center-tools/`)
- **Language:** Python/FastAPI
- **Purpose:** Web ops platform for 8x8 CC infrastructure — media nodes, load balancers, cluster balancing, analytics
- **CheckMK relevance:** None — no CheckMK client code found. Good reference for 8x8 site names and infrastructure context.
- **Decision:** Not used as a code reference for this MCP. Confirms our 9 production sites.

---

## 4. Tools (GET Only — 6 Tools)

| Tool | CheckMK Endpoint | Use in Alert Workflow |
|---|---|---|
| `checkmk_list_problems` | `GET /domain-types/service/collections/all` + filter state≥1 | List all CRIT/WARN services — first step in MINIMAL context |
| `checkmk_get_service_status` | `GET /objects/service/{host}~{svc}` | Look up a specific service during FULL context investigation |
| `checkmk_get_host_status` | `GET /objects/host/{hostname}` | Check if host is up/down — confirm host-level failure |
| `checkmk_list_hosts` | `GET /domain-types/host/collections/all` | Enumerate monitored hosts — useful for finding correct hostname |
| `checkmk_get_host_services` | `GET /objects/host/{hostname}/collections/services` | All services on a host — confirm blast radius of host issue |
| `checkmk_test_connection` | `GET /version` | Connectivity check / debug — confirm server reachable |

---

## 5. Architecture

### Language / Framework
**Python + FastMCP** — consistent with `mcp-devops-demo/server.py` already in this repo. Simpler than raw JSON-RPC. FastMCP handles the MCP protocol layer; we write only tool functions.

### File Structure
```
mcp-servers/
  checkmk/
    server.py          # Main FastMCP server — all 6 tools
    client.py          # CheckMK REST API client (HTTP + auth + retry)
    requirements.txt   # mcp[cli], requests (or httpx)
```

### Component Breakdown

**`client.py` — CheckMKClient**
- Takes `url`, `site`, `user`, `secret` from env vars
- Builds base URL: `{CHECKMK_URL}/{CHECKMK_SITE}/check_mk/api/1.0`
- Auth: HTTP Basic (`CHECKMK_USER:CHECKMK_SECRET`) — matches existing env vars
- SSL: configurable via `CHECKMK_VERIFY_SSL` (default `true`; set `false` for self-signed certs)
- Timeout: `CHECKMK_TIMEOUT` (default 30s)
- Method: single `get(endpoint, params)` — no write methods
- Error handling: maps 401/403/404/5xx to descriptive strings (not exceptions) so Claude gets readable output

**`server.py` — FastMCP tools**
- Each tool calls `client.get(...)` and formats the response as a readable string or JSON
- Tool descriptions written for Claude — explain what the output means in incident context
- No authentication logic in server.py — all in client.py

---

## 6. Environment Variables

| Variable | Maps To | Notes |
|---|---|---|
| `CHECKMK_URL` | CheckMK server base URL | e.g. `https://checkmk.8x8.com` — **already in .env** |
| `CHECKMK_SITE` | CheckMK site name | e.g. `cmk` — **needs to be filled in** |
| `CHECKMK_USER` | Automation user | **already in .env** |
| `CHECKMK_SECRET` | Automation password | **already in .env** |
| `CHECKMK_VERIFY_SSL` | SSL verification | Optional, default `true`; set `false` for self-signed certs |
| `CHECKMK_TIMEOUT` | Request timeout (seconds) | Optional, default `30` |

> **Note:** vibeMK uses `CHECKMK_USERNAME`/`CHECKMK_PASSWORD`. Our server uses `CHECKMK_USER`/`CHECKMK_SECRET` to match existing env vars in `.env`. This is intentional — do not change the env var names.

---

## 7. .mcp.json Registration

```json
"checkmk": {
  "type": "stdio",
  "command": "/home/jaydeep/jaydeep_claude/mcp-servers/checkmk/.venv/bin/python",
  "args": ["/home/jaydeep/jaydeep_claude/mcp-servers/checkmk/server.py"]
}
```

Env vars are loaded from shell (`.env` sourced at startup) — not duplicated in `.mcp.json`.

---

## 8. CLAUDE.md Update

Add `checkmk` MCP section under **MCP Tools**:
```
- **checkmk**: `checkmk_list_problems`, `checkmk_get_service_status`, `checkmk_get_host_status`, 
  `checkmk_list_hosts`, `checkmk_get_host_services`, `checkmk_test_connection`
  Read-only. Use checkmk_list_problems first for MINIMAL context alerts.
```

Update `docs/api-reference.md` — CheckMK section now secondary (MCP preferred).

---

## 9. What's Missing / Needs Confirmation Before Build

| Item | Status | Action Needed |
|---|---|---|
| CheckMK host URL | Unknown | Confirm `CHECKMK_URL` value from `.env` |
| CheckMK site name | Unknown | Confirm the site name (e.g. `cmk`, `monitoring`, `prod`) — needed for URL path |
| CheckMK version | Unknown | REST API v1 (2.x) vs older? Affects endpoint paths |
| SSL cert | Unknown | Is cert self-signed? Set `CHECKMK_VERIFY_SSL=false` if so |
| Automation user exists | Unknown | Confirm automation user is created in CheckMK (Setup → Users) |

---

## 10. Error Handling Strategy

All tools return plain text — never raise exceptions to Claude:

```
✅ <formatted data>          # success
⚠️ No results found for ...  # empty response
❌ Connection failed: <msg>  # network/auth error
❌ Host not found: <host>    # 404
❌ Auth failed — check CHECKMK_USER and CHECKMK_SECRET  # 401
```

---

## 11. Testing Plan

1. `checkmk_test_connection` — verify reachability and credentials before other tests
2. `checkmk_list_problems` — confirm returns CRIT/WARN services
3. `checkmk_get_host_status` — test with a known host
4. `checkmk_get_service_status` — test with a known host~service pair
5. `checkmk_list_hosts` — verify pagination if site has many hosts
6. `checkmk_get_host_services` — verify service list for a known host

---

## 12. Out of Scope

- Write operations (acknowledge, downtime, reschedule) — use curl from `docs/api-reference.md`
- Multi-site CheckMK federation
- Metrics / RRD data (vibeMK has this; we don't need it for alert triage)
- Configuration management (rules, rulesets, users)
