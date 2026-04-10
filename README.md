# Claude MCP Servers — Alert Investigation Toolkit

A set of [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers that extend
Claude with real-time access to infrastructure logs, Jira, PagerDuty, and system metrics —
enabling AI-assisted alert investigation directly from Claude Desktop or Claude Code CLI.

---

## What's included

| MCP Server | Runtime | Purpose |
|---|---|---|
| [`mcp-servers/ir-logs`](mcp-servers/ir-logs/) | Node.js | Fetch & search InteractionRouter logs from production hosts via SSH |
| [`mcp-devops-demo`](mcp-devops-demo/) | Python | Disk, CPU, memory, ping, and log search on the local/WSL host |
| `mindbender` | Remote HTTP | Jira ticket lookup, creation, comments, sprint management |

---

## Architecture

```
Claude Desktop / Claude Code CLI
        │
        ├── mindbender MCP  ──────────► Jira (remote HTTPS, no local setup)
        │
        ├── devops-assistant MCP ─────► WSL: disk / CPU / memory / ping
        │
        └── ir-logs MCP ─────SSH────► Production IR hosts
                                       /var/log/contactual/p-ir.*.log
                                       User: contactual | Key: ~/.ssh/id_ed25519
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| WSL2 (Ubuntu) | All MCP servers run inside WSL |
| Node.js ≥ 18 | For `ir-logs` MCP — `node --version` |
| Python ≥ 3.10 | For `devops-assistant` MCP — `python3 --version` |
| Ed25519 SSH key | Must be authorised for `contactual` user on IR hosts |
| Claude Desktop | [Download](https://claude.ai/download) — Windows app |

---

## Quick Start

### 1. Clone the repo

```bash
git clone <repo-url>
cd jaydeep_claude
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env — fill in INVENTORY_PATH, IR_SSH_KEY, PAGERDUTY_API_KEY, etc.
nano .env
```

### 3. Install dependencies

```bash
# ir-logs MCP (Node.js)
cd mcp-servers/ir-logs
npm install
cd ../..

# devops-assistant MCP (Python)
cd mcp-devops-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 4. Configure SSH access

See **[docs/SSH_SETUP.md](docs/SSH_SETUP.md)** for the full guide.

TL;DR — your `~/.ssh/id_ed25519.pub` must be in `authorized_keys` of the `contactual`
user on every IR host. Ask Operations to add it if you don't have existing access.

### 5. Configure Claude Desktop

```bash
# Find your Windows username
cmd.exe /c echo %USERNAME%
```

Copy the template and replace `<YOUR_WSL_USER>` with your WSL username:

```bash
# On Windows (from WSL):
cp claude_desktop_config.template.json \
   /mnt/c/Users/<WINDOWS_USER>/AppData/Roaming/Claude/claude_desktop_config.json

# Then edit the file and replace all <YOUR_WSL_USER> placeholders
sed -i 's/<YOUR_WSL_USER>/'"$(whoami)"'/g' \
   /mnt/c/Users/<WINDOWS_USER>/AppData/Roaming/Claude/claude_desktop_config.json
```

Restart Claude Desktop. All three MCPs should appear as available tools.

### 6. Load credentials into shell (for Claude Code CLI)

```bash
# Add to ~/.bashrc or ~/.zshrc so vars are always exported
set -a && source ~/jaydeep_claude/.env && set +a
```

---

## MCP Tools Reference

### ir-logs

| Tool | Description |
|---|---|
| `list_ir_sites` | List all sites and server counts from inventory |
| `list_ir_servers` | List IR hostnames for a given site |
| `get_ir_logs` | Fetch recent log lines (site / specific hosts / time filter) |
| `get_ir_errors` | Fetch ERROR / WARN / FATAL / Exception / LDAP / Kafka lines |
| `search_ir_logs` | Grep logs with regex across a site |
| `get_kafka_events` | Filter for a specific Kafka event type |
| `get_ir_log_around_time` | Fetch logs in a window around a timestamp (incident investigation) |

### devops-assistant

| Tool | Description |
|---|---|
| `disk_usage` | `df -h` on the WSL host |
| `cpu_processes` | Top CPU-consuming processes |
| `memory_usage` | `free -h` |
| `ping_host` | Ping a host by name or IP |
| `search_logs` | Grep `/var/log/messages` for a keyword |

### mindbender (remote)

Full Jira integration — ticket lookup, create INC/PRB/CHG, add comments, search, link issues.
No local setup required — connects to `https://mindbender.cceng.8x8.com/mcp` over HTTPS.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `INVENTORY_PATH` | Yes | — | Path to `inventory.json` (host/site map) |
| `IR_SSH_USER` | No | `contactual` | SSH user for IR hosts |
| `IR_SSH_KEY` | No | `~/.ssh/id_ed25519` | Path to SSH private key |
| `IR_LOG_PATH` | No | `/var/log/contactual/p-ir.0.log` | IR log file path on hosts |
| `IR_JUMP_HOST` | No | _(none)_ | Bastion/jump host for unreachable sites |
| `IR_JUMP_USER` | No | same as `IR_SSH_USER` | Jump host SSH user |
| `IR_CONCURRENCY` | No | `10` | Max parallel SSH connections |
| `PAGERDUTY_API_KEY` | Yes* | — | PagerDuty REST API key |
| `CHECKMK_USER` | Yes* | — | CheckMK automation user |
| `CHECKMK_SECRET` | Yes* | — | CheckMK automation password |
| `CHECKMK_BASE_URL` | Yes* | — | CheckMK base URL |

_* Required for PagerDuty/CheckMK features in the alert investigation workflow._

---

## Project Structure

```
.
├── README.md                            # This file
├── .env.example                         # Credential template — copy to .env
├── .gitignore
├── claude_desktop_config.template.json  # Claude Desktop config template
├── CLAUDE.md                            # Alert investigation workflow for Claude
│
├── docs/
│   └── SSH_SETUP.md                     # SSH key onboarding guide
│
├── mcp-servers/
│   └── ir-logs/                         # Node.js MCP — IR log access via SSH
│       ├── server.js
│       ├── package.json
│       └── package-lock.json
│
└── mcp-devops-demo/                     # Python MCP — local system metrics
    ├── server.py
    └── requirements.txt
```

---

## Adding a New Team Member

1. Clone this repo
2. `cp .env.example .env` → fill in values
3. Run `npm install` in `mcp-servers/ir-logs/`
4. Run `python3 -m venv .venv && pip install -r requirements.txt` in `mcp-devops-demo/`
5. Generate SSH key: `ssh-keygen -t ed25519 -C "name@company.com"`
6. Send `~/.ssh/id_ed25519.pub` to Operations — they add it to `contactual` authorized_keys on all IR hosts
7. Copy `claude_desktop_config.template.json` → Windows Claude config path, replace `<YOUR_WSL_USER>`
8. Restart Claude Desktop

Full SSH guide: [docs/SSH_SETUP.md](docs/SSH_SETUP.md)

---

## Security Notes

- **Never commit `.env`** — it is gitignored. Use `.env.example` as the template.
- **Never commit `inventory.json`** — it contains internal hostnames and is gitignored.
- SSH private keys stay on each developer's machine — they are never shared or committed.
- The `contactual` user on IR hosts is read-only for log access.
- `CLAUDE.md` enforces that Claude never reads or prints `.env` contents.
