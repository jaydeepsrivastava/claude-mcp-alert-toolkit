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

### 3.1 chexma/vibeMK (external) — REJECTED
- **URL:** https://github.com/chexma/vibeMK
- **Language:** Python (raw JSON-RPC stdin/stdout — no FastMCP)
- **Scope:** Full CRUD — 60+ tools covering hosts, services, users, rules, rulesets, downtimes, acknowledgements, discovery, metrics, passwords
- **API client:** `api/client.py` — auto URL detection, SSL context, retry with exponential backoff
- **Why rejected:** Creator explicitly marks it alpha and states "Do not use in production." Forum thread (https://forum.checkmk.com/t/vibemk-connect-checkmk-to-ai-llms/55364) confirms community consensus: "It cannot be used" — unpredictable LLM behavior, risk of accidental destructive actions on live monitoring. **No code borrowed from vibeMK.**
- **Decision:** Build from scratch. Our GET-only scope eliminates the accidental-write risk that makes vibeMK dangerous.

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
- Takes full base URL from `CHECKMK_BASE_URL` env var (already includes site path)
- Auth: Bearer token — `Authorization: Bearer <CHECKMK_TOKEN>` (CheckMK automation token format)
- HTTP (not HTTPS) — no SSL context needed for this instance
- Timeout: `CHECKMK_TIMEOUT` (default 30s)
- Method: single `get(endpoint, params)` — no write methods
- Error handling: maps 401/403/404/5xx to descriptive strings (not exceptions) so Claude gets readable output

**`server.py` — FastMCP tools**
- Each tool calls `client.get(...)` and formats the response as a readable string or JSON
- Tool descriptions written for Claude — explain what the output means in incident context
- No authentication logic in server.py — all in client.py

---

## 6. Environment Variables

| Variable | Value | Notes |
|---|---|---|
| `CHECKMK_BASE_URL` | `http://us2mastermon.us2.whitepj.net/vccmaster/check_mk/api/1.0` | Full API base URL — confirmed working |
| `CHECKMK_TOKEN` | `automation <uuid>` | Bearer token — `Authorization: Bearer <token>` |
| `CHECKMK_TIMEOUT` | `30` | Optional, default 30s |

**CheckMK instance confirmed:**
- Version: `2.2.0p11.cee` (Enterprise Edition)
- Site: `vccmaster`
- Host: `us2mastermon.us2.whitepj.net` (US2 master monitor)
- Protocol: HTTP (no SSL)
- Auth: Bearer token (automation user secret format)

> **Security note:** Store `CHECKMK_TOKEN` in `.env` only — never in code or committed files.

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

## 9. Pre-Build Checklist — ALL CONFIRMED

| Item | Status | Detail |
|---|---|---|
| CheckMK base URL | ✅ Confirmed | `http://us2mastermon.us2.whitepj.net/vccmaster/check_mk/api/1.0` |
| CheckMK version | ✅ Confirmed | `2.2.0p11.cee` — REST API v1 endpoints valid |
| Auth method | ✅ Confirmed | Bearer token, `Authorization: Bearer automation <uuid>` |
| SSL | ✅ Not needed | HTTP only |
| Connection test | ✅ Passed | `/version` returns 200; service list query returns live data |
| Automation user | ✅ Active | Token accepted, data returned |

**Ready to build.** No blockers.

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
