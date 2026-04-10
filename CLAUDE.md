# Alert Investigation Workflow

## Project Purpose
Investigate PagerDuty / CheckMK alerts, link them to Jira tickets,
identify root causes, and suggest permanent mitigations — not just quick fixes.

---

## Security: .env Files
**Never read, print, or expose the contents of any `.env` file.**
Credentials are loaded from environment variables at runtime only.
A hook enforces this at the tool level (see `.claude/settings.json`).
If env vars are missing, tell the user which ones are needed — do not try to read the file.

---

## Connections

### Jira
- MCP: `mindbender` (already connected)
- Project key: `[FILL IN — e.g. VCC, OPS, INFRA]`
- Alert tickets use label: `[FILL IN — e.g. pagerduty-alert]`
- Ticket types to cross-check: `INC`, `RP`, `MW`, `DEP`, `PRB`, `CHG`

### PagerDuty
- Base URL: `https://api.pagerduty.com`
- Credentials: env var `PAGERDUTY_API_KEY`
- [FILL IN — your PagerDuty subdomain/account name]

### CheckMK
- Base URL: `https://[FILL IN — your checkmk host]/[site]/api/1.0`
- Credentials: env vars `CHECKMK_USER`, `CHECKMK_SECRET`

---

## Alert Investigation Workflow

When given an alert, incident ID, or Jira ticket:

1. **Fetch alert details** from PagerDuty or CheckMK via API (use Bash + curl)
2. **Read the Jira ticket** using mindbender `get_issue`
3. **JIRA cross-check** — query all relevant ticket types (MW, DEP, PRB, CHG, INC, RP) — see rules below
4. **Assess context level** — determine FULL / PARTIAL / MINIMAL mode (see below)
5. **Search for similar past incidents** in Jira using `search_issues` — detect recurrence
6. **Identify root cause** — ranked by probability with evidence, not just the symptom
7. **Suggest permanent mitigation** — see definition below
8. **Update the Jira ticket** with findings, root cause, confidence score, and recommendation using `add_comment`

---

## JIRA Ticket Cross-Check Rules

After fetching the alert, query Jira for all of these within the relevant timeframe:

| Ticket Type | JQL Example | Action |
|---|---|---|
| `MW` (Maintenance Window) | `type = MW AND status != Done` | If active → suppress alert, inform user |
| `DEP` (Deployment) | `type = DEP AND created >= -2h` | If deploy < 2h before alert → rollback is #1 recommendation |
| `PRB` (Known Problem) | `type = PRB AND status != Done` | If match → apply documented workaround directly |
| `CHG` (Change Request) | `type = CHG AND status = "In Progress"` | If active → correlate before escalating |
| `INC` (Incident) | `type = INC AND labels = pagerduty-alert` | Link, do not duplicate |
| `RP` (RP ticket) | `type = RP` | Standard cross-check |

---

## Context Level Assessment (FULL / PARTIAL / MINIMAL)

Determine the context level from the user's input before responding:

**FULL** — host + service + error all identified
- Action: Resolve immediately with ranked root causes and steps

**PARTIAL** — some signals present (e.g. host known but no error, or error but no host)
- Action: Run parallel searches, show results, ask ≤2 targeted clarifying questions

**MINIMAL** — only category guessable (e.g. "something is broken in prod")
- Action: Show all active CRITICAL/WARNING alerts grouped by severity, ask user to identify which one

---

## Severity Mapping

Map PagerDuty urgency + status to a severity badge on every response:

| PD Urgency | PD Status | Badge |
|---|---|---|
| `high` | `triggered` | 🔴 CRITICAL |
| `high` | `acknowledged` | ⚠️ WARNING |
| `low` | any | 💡 INFO |

Always display: `🔴 CRITICAL | <host> | <service> DOWN | <duration>`

---

## Response Format Standard

Every alert response must include these sections (omit only if data unavailable):

```
🔴 CRITICAL  |  <host>  |  <service> DOWN  |  <X> min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📟  <PD incident ID>  |  On-call: <name>

📋  JIRA SNAPSHOT
    <MW/DEP/PRB/CHG/INC findings with action implications>

📊  ROOT CAUSE — RANKED
    #1  <X>%  <cause> — <evidence>
    #2  <X>%  <cause> — <evidence>

✅  RESOLUTION  •  <source>  •  <who>  •  <when>
    Step 1: <command>
    Step 2: <command>

CONFIDENCE  <bar>  <X>%  <level>  •  Sources: <list>
```

---

## Confidence Scoring

Calculate and display a confidence score on every response:

| Signal | Score |
|---|---|
| PD notes match same host | +35 |
| JIRA correlation found (DEP/PRB) | +20 |
| Confluence runbook found | +15 |
| Similar past INC resolved same way | +10 |
| Only Claude AI available (no data) | -30 |

Display format: `CONFIDENCE: 78% GOOD ⚡ | Sources: PD Notes + JIRA DEP`

Levels: `>= 85%` = HIGH, `>= 60%` = GOOD, `< 60%` = LOW

---

## Root Cause Ranking

After gathering all data sources, rank root causes by probability with evidence:

- Use deploy timeline: if DEP ticket fired < 2h before alert, weight heavily
- Use disk/resource metrics from PD alert body if available
- Cross-reference recurrence: if same alert fired 3+ times in 30 days, flag pattern
- Rule out causes explicitly: `✅ Network ruled out — ping OK, no network alerts in site`

---

## Resolution Source Hierarchy

Never rely on a single source. Work through these in order — stop at first hit, note which level was used in the confidence score:

| Priority | Source | How to Query | Confidence Impact |
|---|---|---|---|
| 1 | **PD incident notes** | `GET /incidents/[ID]/notes` | +35 if found |
| 2 | **Confluence runbook** | `search_knowledge_base(<alert name>)` | +15 if found |
| 3 | **JIRA INC comments** (past resolved) | `search_issues: type=INC AND summary~"<service>" AND status=Done` | +10 if found |
| 4 | **JIRA PRB workaround** | `search_issues: type=PRB AND summary~"<service>"` | +20 if found |
| 5 | **Claude general knowledge** | Last resort only | -30 penalty |

### What to do when PD notes are empty (most common case)

1. Fall through to Confluence → JIRA INC → PRB in order
2. If resolution found from any source, **guide the operator through the fix**
3. After fix is confirmed working, **write back automatically**:
   - Post resolution steps as a PD incident note (`POST /incidents/[ID]/notes`)
   - Add a comment to the JIRA INC ticket with root cause + steps taken
4. This builds the PD notes knowledge base over time — Claude is the note-taker, not just the note-reader

### Write-back format (post to PD notes after resolution)
```
Root cause: <what failed and why>
Fix applied: <exact commands or steps>
Verified by: <how you confirmed it worked>
Recurrence risk: <yes/no — link PRB if yes>
Time to resolve: <X min>
```

---

## Recurrence Detection

When investigating an alert, always run:
```
search_issues: type = INC AND summary ~ "<service>" AND created >= -30d ORDER BY created DESC
```

If 3+ similar incidents found:
- Flag as recurring pattern
- Identify common root cause thread
- Recommend raising a `PRB` ticket if none exists
- Reference any open JIRA fix ticket (e.g. "JIRA-4799 would have prevented this")

---

## What "Permanent Mitigation" Means

Do NOT suggest:
- "Restart the service"
- "Acknowledge and monitor"

DO suggest:
- Alerting threshold tuning (if alert was noisy/false positive)
- Infrastructure fix (resource limits, config change)
- Code fix (with file/function reference if known)
- Runbook update (if no runbook exists or it's incomplete)
- Monitoring improvement (add missing metric, fix check interval)
- PRB ticket creation if recurring (3+ times same root cause)

---

## API Reference (fill in after credentials collected)

### PagerDuty — fetch incident
```bash
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]"
```

### PagerDuty — list recent incidents
```bash
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents?statuses[]=triggered&statuses[]=acknowledged"
```

### PagerDuty — fetch incident notes (operator resolution history)
```bash
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]/notes"
```

### PagerDuty — write resolution note back (after fix confirmed)
```bash
curl -s -X POST \
     -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     -H "Content-Type: application/json" \
     -H "From: [FILL IN — on-call engineer email or bot email]" \
     -d "{\"note\": {\"content\": \"[RESOLUTION STEPS]\"}}" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]/notes"
```

### CheckMK — get service status
```bash
curl -s -u "$CHECKMK_USER:$CHECKMK_SECRET" \
     "https://[CHECKMK_HOST]/[SITE]/api/1.0/objects/service/[HOST]~[SERVICE]"
```

### CheckMK — list recent problems
```bash
curl -s -u "$CHECKMK_USER:$CHECKMK_SECRET" \
     "https://[CHECKMK_HOST]/[SITE]/api/1.0/domain-types/service/collections/all?query={\"op\":\"=\",\"left\":\"state\",\"right\":\"2\"}"
```

---

## Environment Variables Required

| Variable | Used For |
|---|---|
| `PAGERDUTY_API_KEY` | PagerDuty REST API auth |
| `CHECKMK_USER` | CheckMK automation user |
| `CHECKMK_SECRET` | CheckMK automation password |

A `.env` file is present in the project root with all credentials pre-filled.

Load them in your shell before starting Claude Code:
```bash
# Source the .env file (recommended)
set -a && source .env && set +a

# Or export individually if preferred
export PAGERDUTY_API_KEY="..."
export CHECKMK_USER="..."
export CHECKMK_SECRET="..."
```

Or add `set -a && source /home/jaydeep/jaydeep_claude/.env && set +a` to `~/.bashrc` / `~/.zshrc` so they are always available.

**Note:** Claude will never read or print the `.env` file directly. It only uses the variables once they are exported into the shell environment.

---

## Notes
- [FILL IN — any known recurring alert patterns specific to your infra]
- [FILL IN — services you monitor and their criticality (e.g. SIP hosts, DB nodes, LBs, cache clusters)]
- [FILL IN — on-call rotation / escalation context if relevant]
- [FILL IN — CI/CD tool used (e.g. Helm, Ansible) for rollback command patterns]
