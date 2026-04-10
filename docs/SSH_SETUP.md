# SSH Key Setup Guide

This guide explains how to configure SSH access so the `ir-logs` MCP can connect
to IR (InteractionRouter) hosts automatically, without password prompts.

---

## How it works

The `ir-logs` MCP server connects to each IR host using:
- **User:** `contactual`
- **Auth:** Ed25519 private key (`~/.ssh/id_ed25519`)
- **Mode:** `BatchMode=yes` — no interactive prompts, fails fast if key is missing

Your public key must be present in `/home/contactual/.ssh/authorized_keys` on every
target host before the MCP can connect.

---

## Step 1 — Generate an Ed25519 key (if you don't have one)

```bash
# Check first — skip this step if the file already exists
ls ~/.ssh/id_ed25519

# Generate if missing
ssh-keygen -t ed25519 -C "yourname@company.com" -f ~/.ssh/id_ed25519
```

Your public key will be at `~/.ssh/id_ed25519.pub`.

---

## Step 2 — Add your public key to target hosts

### Option A — Using ssh-copy-id (requires temporary password access)

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub contactual@<hostname>
```

### Option B — Ask Ops to add your key

Send your public key to Operations:

```bash
cat ~/.ssh/id_ed25519.pub
```

They will add it to `contactual`'s `authorized_keys` across the fleet.

### Option C — Push to all hosts from inventory (if you already have access)

```bash
# Requires inventory.json to be present locally
cat inventory.json \
  | python3 -c "
import sys, json
inv = json.load(sys.stdin)
for host, info in inv.get('hosts', {}).items():
    roles = info.get('roles', [])
    if any('rt64' in r.lower() for r in roles):
        print(host)
" \
  | xargs -I{} ssh-copy-id -i ~/.ssh/id_ed25519.pub contactual@{}
```

---

## Step 3 — Verify connectivity

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 \
    contactual@<hostname> "echo OK"
```

Expected output: `OK`

If you see `Permission denied` — your public key is not yet in `authorized_keys` on that host.

---

## SSH Config (optional — recommended for convenience)

Add to `~/.ssh/config` to avoid repeating flags:

```
Host *.santaclara.whitepj.net *.whitepj.net
    User contactual
    IdentityFile ~/.ssh/id_ed25519
    BatchMode yes
    ConnectTimeout 10
    StrictHostKeyChecking accept-new
```

---

## Jump host / Bastion (if hosts are not directly reachable)

Set the `IR_JUMP_HOST` environment variable:

```bash
export IR_JUMP_HOST=bastion.yourdomain.net
export IR_JUMP_USER=contactual   # default: same as IR_SSH_USER
```

Or add to your `.env` file (see `.env.example` in the project root).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Permission denied (publickey)` | Key not in `authorized_keys` | Follow Step 2 |
| `Connection timed out` | Host unreachable / firewall | Check network / use jump host |
| `Config error: SSH private key not found` | Wrong `IR_SSH_KEY` path in `.env` | Set correct path |
| `No IR servers found for site: us1` | `inventory.json` missing or misconfigured | Check `INVENTORY_PATH` in `.env` |
