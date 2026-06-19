# CheckMK MCP Server

**Read-only MCP server that connects Claude Code to CheckMK monitoring.**  
Claude can query host status, service health, and active problems directly during alert investigation — no manual curl commands, no context switching.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File Locations](#file-locations)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Available Tools](#available-tools)
8. [Usage in Alert Investigation](#usage-in-alert-investigation)
9. [Running Tests](#running-tests)
10. [Security](#security)
11. [Troubleshooting](#troubleshooting)

---

## Overview

### Why This Was Built

The alert investigation workflow required engineers to manually run curl commands against CheckMK to look up host/service status. This MCP server exposes CheckMK data directly to Claude Code so that during a live incident, Claude can:

- Immediately list all CRIT/WARN services across the environment
- Look up a specific host's up/down state
- Enumerate all services on a host to assess blast radius
- Drill into a specific service's detailed status

All operations are **read-only** (GET only). No acknowledges, no downtimes, no configuration changes can be made through this server.

### What It Connects To

- **CheckMK 2.2.x** (tested on 2.2.0p11 Commercial Edition)
- **REST API v1** (`/check_mk/api/1.0`)
- **Authentication**: Bearer token (CheckMK automation user)

---

## Architecture

```
Claude Code
    │
    │  MCP (stdio)
    ▼
server.py  ──── FastMCP  ──── 6 @mcp.tool() functions
    │
    ▼
client.py  ──── CheckMKClient
    │               • Bearer token auth
    │               • GET requests only
    │               • Error → plain string (never exception)
    ▼
CheckMK REST API
http://<host>/<site>/check_mk/api/1.0
```

**Framework:** Python + FastMCP (same as other MCP servers in this repo)  
**Protocol:** MCP stdio — Claude Code spawns the server as a subprocess  
**Error handling:** All failures return `❌ <message>` strings — Claude never receives a Python exception

---

## File Locations

### MCP Server Files

| File | Purpose |
|---|---|
| `mcp-servers/checkmk/server.py` | Main FastMCP server — all 6 tools |
| `mcp-servers/checkmk/client.py` | CheckMK REST API client — HTTP, auth, error mapping |
| `mcp-servers/checkmk/requirements.txt` | Python dependencies |
| `mcp-servers/checkmk/.venv/` | Python 3.11 virtual environment (not committed) |
| `mcp-servers/checkmk/tests/test_client.py` | 10 unit tests for CheckMKClient |
| `mcp-servers/checkmk/tests/test_server.py` | 15 unit tests for all 6 tools |

### Configuration Files

| File | Purpose |
|---|---|
| `.mcp.json` | MCP server registration — tells Claude Code where to find this server |
| `CLAUDE.md` | Workflow instructions — updated to reference checkmk MCP tools |
| `.env` | Credentials — `CHECKMK_BASE_URL` and `CHECKMK_TOKEN` (not committed) |

### Documentation

| File | Purpose |
|---|---|
| `mcp-servers/checkmk/README.md` | This file — setup and usage guide |
| `docs/superpowers/specs/2026-06-19-checkmk-mcp-design.md` | Technical design spec — decisions, rejected alternatives, pre-build validation |
| `docs/api-reference.md` | curl fallback templates for CheckMK (for operations outside MCP scope) |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Check: `python3.11 --version` |
| pip | any | Bundled with Python |
| Claude Code | latest | MCP stdio support required |
| CheckMK | 2.0+ | REST API v1 must be enabled |
| CheckMK automation user | active | Needs read access to hosts and services |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/jaydeepsrivastava/claude-mcp-alert-toolkit.git
cd claude-mcp-alert-toolkit
```

### 2. Create the virtual environment

```bash
cd mcp-servers/checkmk
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Verify:
```bash
.venv/bin/python -c "from mcp.server.fastmcp import FastMCP; import requests; print('OK')"
# Expected: OK
```

### 3. Create your .env file

In the repo root, add these to your `.env` file (create it if it doesn't exist):

```bash
CHECKMK_BASE_URL="http://<your-checkmk-host>/<site>/check_mk/api/1.0"
CHECKMK_TOKEN="automation <your-automation-secret-uuid>"
CHECKMK_TIMEOUT="30"
```

> **Where to find these values:**  
> In CheckMK: Setup → Users → Automation users → select your automation user → copy the secret  
> Base URL format: `http://monhost.domain.net/sitename/check_mk/api/1.0`

### 4. Register in .mcp.json

The `.mcp.json` at the repo root already contains the registration:

```json
"checkmk": {
  "type": "stdio",
  "command": "/absolute/path/to/mcp-servers/checkmk/.venv/bin/python",
  "args": ["/absolute/path/to/mcp-servers/checkmk/server.py"]
}
```

> **Important:** Update the absolute paths to match your clone location.

### 5. Export env vars and reload Claude Code

```bash
set -a && source .env && set +a
```

In Claude Code: run `/reload-plugins`

### 6. Verify the connection

Ask Claude Code:
```
call checkmk_test_connection
```

Expected response: `✅ Connected to CheckMK 2.2.0p11.cee`

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `CHECKMK_BASE_URL` | Yes | — | Full API base URL including site name |
| `CHECKMK_TOKEN` | Yes | — | Automation user secret in format `automation <uuid>` |
| `CHECKMK_TIMEOUT` | No | `30` | HTTP request timeout in seconds |

### CheckMK Automation User Setup

The automation user needs these permissions in CheckMK:
- **Hosts:** Read
- **Services:** Read
- **Role:** Operator or higher (read-only access is sufficient)

In CheckMK: Setup → Users → Add user → set "Automation" as the user type → copy the generated secret.

---

## Available Tools

All tools return plain-text strings. Errors are prefixed with `❌`, warnings with `⚠️`, success with `✅`.

---

### `checkmk_test_connection`

Test connectivity and validate credentials.

**Use when:** Starting any investigation, or if other tools return unexpected errors.

**Example output:**
```
✅ Connected to CheckMK 2.2.0p11.cee
```

---

### `checkmk_list_problems`

List all services currently in WARN or CRIT state across all monitored hosts.

**Use when:** You have a MINIMAL context alert and need to identify which host/service is actually alerting.

**Example output:**
```
Found 12487 problem(s):
  [CRIT] sy1vccss01 / VCCSS listener — connect to address 10.90.4.70 and port 1080: Connection refused
  [CRIT] sy1vccss01 / Process Monolith — Processes: 0 (warn/crit below 1/1)
  [WARN] us2mastermon02 / Filesystem /var — Used: 86.35% - 33.7 GiB of 39.1 GiB
  ...
```

---

### `checkmk_get_host_status`

**Parameters:** `hostname` (string)

Get the UP/DOWN state of a specific host.

**Use when:** Confirming whether an alert is a host-level failure (entire host down) or a service-level issue.

**Example output:**
```
Host: sy1vccss01
State: UP
Address: 10.90.4.70
Output: Packet received via smart PING
```

---

### `checkmk_get_host_services`

**Parameters:** `hostname` (string)

List all services monitored on a host with their current states.

**Use when:** Assessing the full blast radius of a host issue, or finding which service is failing.

**Example output:**
```
Host sy1vccss01 — 68 service(s):
  [CRIT] VCCSS listener — connect to address 10.90.4.70 and port 1080: Connection refused
  [CRIT] VCCSS-Health — failed request HTTPConnectionPool(host='...', port=1090)
  [CRIT] Process Monolith — Processes: 0 (warn/crit below 1/1)
  [OK] CPU utilization — Total CPU: 0.29%
  [OK] Memory — Total virtual memory: 10.90% - 3.84 GiB of 35.2 GiB
  ...
```

---

### `checkmk_get_service_status`

**Parameters:** `hostname` (string), `service_name` (string — exact CheckMK service name)

Get the detailed status of a single service on a host.

**Use when:** FULL context investigation — you know both the host and service name.

**Example output:**
```
Host: sy1vccss01
Service: Process Monolith
State: CRIT
Output: Processes: 0 (warn/crit below 1/1)
Last check: 1781846938
```

> **Tip:** Service names must match exactly as shown in CheckMK (case-sensitive). Use `checkmk_get_host_services` first to find the correct name.

---

### `checkmk_list_hosts`

List all monitored hosts with their current state and IP address.

**Use when:** The hostname is unknown and you need to find the correct name to pass to other tools.

**Example output:**
```
Found 342 host(s):
  [UP] sy1vccss01 (10.90.4.70)
  [UP] sy1vccss02 (10.90.4.71)
  [DOWN] us2mastermon02 (10.30.3.11)
  ...
```

---

## Usage in Alert Investigation

### MINIMAL context (only know category/site)

```
1. checkmk_list_problems          → find all CRIT/WARN services
2. checkmk_get_host_services      → drill into suspect host
3. checkmk_get_service_status     → get full detail on failing service
```

### FULL context (host + service known)

```
1. checkmk_get_host_status        → confirm host is UP
2. checkmk_get_service_status     → get current state and output
```

### Unknown hostname

```
1. checkmk_list_hosts             → find correct hostname
2. checkmk_get_host_services      → list all services on that host
```

---

## Running Tests

```bash
cd mcp-servers/checkmk
.venv/bin/pytest tests/ -v
```

Expected: **25 tests pass** (10 client + 15 server). No live CheckMK connection needed — all tests use mocked HTTP.

```
tests/test_client.py  ........ 10 passed
tests/test_server.py  ............... 15 passed
```

---

## Security

- **Credentials:** `CHECKMK_TOKEN` is stored in `.env` only — never committed to git (`.env` is in `.gitignore`)
- **Read-only:** The server has no POST/PUT/DELETE methods. Even if an attacker gained access to this server's credentials, they can only read monitoring data
- **No token in logs:** Error messages never echo back the token value
- **Automation user:** Use a dedicated automation user with minimum required permissions (read-only operator), not an admin account

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `❌ Auth failed — check CHECKMK_TOKEN` | Token wrong or expired | Check token in CheckMK: Setup → Users → Automation users |
| `❌ Connection failed: ...` | Network unreachable or wrong URL | Verify `CHECKMK_BASE_URL` — must include site name |
| `❌ Host not found: <hostname>` | Hostname not in CheckMK | Use `checkmk_list_hosts` to find the correct name |
| `❌ Service not found: <host> / <svc>` | Service name doesn't match | Use `checkmk_get_host_services` to find exact name |
| `CHECKMK_BASE_URL env var is not set` | `.env` not sourced | Run `set -a && source .env && set +a` before starting Claude Code |
| Server not loading in Claude Code | `.mcp.json` paths wrong | Verify absolute paths in `.mcp.json` match your clone location |
| `mcp==1.26.0` install fails | Python version too old | Requires Python 3.11+; check `python3.11 --version` |
