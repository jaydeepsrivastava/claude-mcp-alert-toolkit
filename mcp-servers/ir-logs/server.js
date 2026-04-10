#!/usr/bin/env node
/**
 * MCP Server — IR Logs
 * Fetches InteractionRouter logs from servers resolved from inventory.json.
 *
 * Required env vars:
 *   INVENTORY_PATH   Path to inventory.json
 *                    Default: /home/jaydeep/jaydeep_claude/inventory.json
 *   IR_SSH_USER      SSH username        e.g. "contactual"
 *   IR_SSH_KEY       Path to private key e.g. "/home/jaydeep/.ssh/id_ed25519"
 *
 * Optional env vars:
 *   IR_LOG_PATH      Log file path (fallback if journalctl fails)
 *                    Default: /var/log/contactual/p-ir.0.log
 *                    Rotated logs searched: p-ir.0.log … p-ir.3.log
 *   IR_JUMP_HOST     Bastion/jump host   e.g. "bastion.whitepj.net"
 *   IR_JUMP_USER     Jump host SSH user  Default: same as IR_SSH_USER
 *   IR_CONCURRENCY   Max parallel SSH connections (default: 10)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { Client } from "ssh2";
import fs from "fs";
import path from "path";

// ── Config ────────────────────────────────────────────────────────────────────
const INVENTORY_PATH = process.env.INVENTORY_PATH || "/home/jaydeep/jaydeep_claude/inventory.json";
const IR_SSH_USER    = process.env.IR_SSH_USER    || "contactual";
const IR_SSH_KEY     = process.env.IR_SSH_KEY     || `${process.env.HOME}/.ssh/id_ed25519`;
const IR_LOG_PATH    = process.env.IR_LOG_PATH    || "/var/log/contactual/p-ir.0.log";
// Rotated log files — searched newest-first for grep/search fallbacks
const IR_LOG_FILES   = [0, 1, 2, 3].map(n =>
  IR_LOG_PATH.replace(/p-ir\.\d+\.log$/, `p-ir.${n}.log`)
);
const IR_JUMP_HOST   = process.env.IR_JUMP_HOST   || "";
const IR_JUMP_USER   = process.env.IR_JUMP_USER   || "contactual";
const CONCURRENCY    = parseInt(process.env.IR_CONCURRENCY || "10", 10);

// ── Load inventory ────────────────────────────────────────────────────────────
// Build map:  site → [hostname, ...]
// Only hosts that have a role containing "rt64" (InteractionRouter)
// Exclude dev/qa environments
// Inventory is reloaded from disk when the cached copy is older than INVENTORY_TTL_MS.
const INVENTORY_TTL_MS = 5 * 60 * 1000; // 5 minutes
let _inventoryCache = null;   // { siteServers, allSites, loadedAt }

function loadInventory() {
  const now = Date.now();
  if (_inventoryCache && (now - _inventoryCache.loadedAt) < INVENTORY_TTL_MS) {
    return _inventoryCache;
  }

  const siteServers = {};
  try {
    const inv = JSON.parse(fs.readFileSync(INVENTORY_PATH, "utf8"));
    for (const [hostname, info] of Object.entries(inv.hosts || {})) {
      const roles = info.roles || [];
      const site  = info.site  || "";
      if (!roles.some(r => r.toLowerCase().includes("rt64"))) continue;
      if (site.includes("dev") || site.includes("qa"))      continue;
      if (site.startsWith("dlhr"))                          continue; // dev lab, not prod

      // site field may be "us1", "uk3", etc.
      // Normalise to lowercase short name (us1, uk3, on1, …)
      const siteKey = site.split("_")[0].toLowerCase();
      siteServers[siteKey] = siteServers[siteKey] || [];
      siteServers[siteKey].push(hostname);
    }
  } catch (e) {
    // Inventory not found or parse error — return empty (tools will report "no servers")
  }

  _inventoryCache = { siteServers, allSites: Object.keys(siteServers).sort(), loadedAt: now };
  return _inventoryCache;
}

// ── Resolve hosts from site or explicit list ──────────────────────────────────
function resolveHosts(site, servers) {
  if (servers && servers.length) return servers;
  const { siteServers, allSites } = loadInventory();
  if (!site || site === "all")   return allSites.flatMap(s => siteServers[s]);
  const key = site.toLowerCase();
  return siteServers[key] || [];
}

// ── SSH helper ────────────────────────────────────────────────────────────────
function sshRun(host, command, timeout = 20000) {
  return new Promise((resolve) => {
    const client  = new Client();
    const privKey = fs.existsSync(IR_SSH_KEY) ? fs.readFileSync(IR_SSH_KEY) : undefined;
    let output    = "";

    const runOn = (conn, sock) => {
      const opts = { host, port: 22, username: IR_SSH_USER, privateKey: privKey, readyTimeout: timeout };
      if (sock) opts.sock = sock;
      conn.on("ready", () => {
        conn.exec(command, (err, stream) => {
          if (err) { conn.end(); return resolve(`ERROR: ${err.message}`); }
          stream.on("data",         d => { output += d.toString(); });
          stream.stderr.on("data",  d => { output += d.toString(); });
          stream.on("close",        () => { conn.end(); resolve(output.trim()); });
        });
      });
      conn.on("error", err => resolve(`SSH ERROR: ${err.message}`));
      conn.connect(opts);
    };

    if (IR_JUMP_HOST) {
      const jump = new Client();
      jump.on("ready", () => {
        jump.forwardOut("127.0.0.1", 0, host, 22, (err, sock) => {
          if (err) { jump.end(); return resolve(`JUMP ERROR: ${err.message}`); }
          const target = new Client();
          target.on("end", () => jump.end());
          runOn(target, sock);
        });
      });
      jump.on("error", err => resolve(`JUMP SSH ERROR: ${err.message}`));
      jump.connect({ host: IR_JUMP_HOST, port: 22, username: IR_JUMP_USER, privateKey: privKey, readyTimeout: timeout });
    } else {
      runOn(client, null);
    }
  });
}

function validateSshAuth() {
  if (!IR_SSH_USER) {
    return "Config error: IR_SSH_USER is empty";
  }

  if (!IR_SSH_KEY) {
    return "Config error: IR_SSH_KEY is empty";
  }

  if (!fs.existsSync(IR_SSH_KEY)) {
    return `Config error: SSH private key not found at ${IR_SSH_KEY}`;
  }

  try {
    const st = fs.statSync(IR_SSH_KEY);
    if (!st.isFile()) {
      return `Config error: IR_SSH_KEY is not a file: ${IR_SSH_KEY}`;
    }
  } catch (e) {
    return `Config error: Cannot read IR_SSH_KEY (${e.message})`;
  }

  return null;
}

// Run command across hosts with bounded concurrency
async function runOnHosts(hosts, command) {
  if (!hosts.length) return [];
  const authError = validateSshAuth();
  if (authError) {
    return hosts.map(host => ({ host, output: authError }));
  }
  const results = [];
  for (let i = 0; i < hosts.length; i += CONCURRENCY) {
    const batch = hosts.slice(i, i + CONCURRENCY);
    const batchResults = await Promise.all(
      batch.map(async host => ({ host, output: await sshRun(host, command) }))
    );
    results.push(...batchResults);
  }
  return results;
}

function formatResults(results) {
  if (!results.length) return "No servers resolved. Check IR_SERVERS or site parameter.";
  return results.map(({ host, output }) => {
    const lineCount = output.split("\n").filter(Boolean).length;
    return `${"─".repeat(60)}\n  ${host}  (${lineCount} lines)\n${"─".repeat(60)}\n${output || "(no output)"}`;
  }).join("\n\n");
}

function safe(str) {
  return str.replace(/'/g, "").replace(/"/g, "");
}

// ── MCP Server ────────────────────────────────────────────────────────────────
const server = new McpServer({ name: "ir-logs", version: "1.0.0" });

// ─ list_sites ─
server.tool(
  "list_ir_sites",
  "List all available IR sites and server counts loaded from inventory",
  {},
  async () => {
    const { siteServers, allSites } = loadInventory();
    if (!allSites.length) {
      return { content: [{ type: "text", text: `Inventory not loaded from: ${INVENTORY_PATH}` }] };
    }
    const lines = allSites.map(s => `  ${s.toUpperCase().padEnd(6)} — ${siteServers[s].length} IR servers`);
    const total = allSites.reduce((n, s) => n + siteServers[s].length, 0);
    return { content: [{ type: "text", text: `IR sites (${allSites.length}), ${total} servers total:\n${lines.join("\n")}` }] };
  }
);

// ─ list_ir_servers ─
server.tool(
  "list_ir_servers",
  "List IR server hostnames for a site",
  {
    site: z.string().optional().default("all").describe("Site code e.g. us1, uk3, sy1 — or 'all'"),
  },
  async ({ site }) => {
    const hosts = resolveHosts(site, []);
    if (!hosts.length) return { content: [{ type: "text", text: `No IR servers found for site: ${site}` }] };
    return { content: [{ type: "text", text: `${site.toUpperCase()} — ${hosts.length} IR servers:\n${hosts.map(h => `  ${h}`).join("\n")}` }] };
  }
);

// ─ get_ir_logs ─
server.tool(
  "get_ir_logs",
  "Fetch recent IR log lines from a site (or specific servers)",
  {
    site:    z.string().optional().default("us1").describe("Site code: us1 | us2 | uk3 | uk2 | lh1 | sy1 | sk1 | on1 | pa1 | hk1 | all"),
    lines:   z.number().optional().default(100).describe("Lines per server (default 100)"),
    since:   z.string().optional().default("").describe("Time filter e.g. '1 hour ago' or '2026-04-10 05:00:00'"),
    servers: z.array(z.string()).optional().default([]).describe("Override: specific hostnames to query"),
  },
  async ({ site, lines, since, servers }) => {
    const hosts   = resolveHosts(site, servers);
    const sinceFlag = since ? `--since "${safe(since)}"` : "";
    const cmd = `journalctl -u ir ${sinceFlag} --no-pager -n ${lines} 2>/dev/null || tail -n ${lines} ${IR_LOG_FILES[0]} 2>/dev/null`;
    const results = await runOnHosts(hosts, cmd);
    return { content: [{ type: "text", text: formatResults(results) }] };
  }
);

// ─ search_ir_logs ─
server.tool(
  "search_ir_logs",
  "Search IR logs for a pattern across a site",
  {
    pattern:          z.string().describe("Grep regex e.g. 'LDAP error|VCC_node_disabled'"),
    site:             z.string().optional().default("us1").describe("Site code or 'all'"),
    since_minutes:    z.number().optional().default(60).describe("Lookback window in minutes"),
    case_insensitive: z.boolean().optional().default(false).describe("Case-insensitive match"),
    servers:          z.array(z.string()).optional().default([]).describe("Override: specific hostnames"),
  },
  async ({ pattern, site, since_minutes, case_insensitive, servers }) => {
    const hosts = resolveHosts(site, servers);
    const flag  = case_insensitive ? "-i" : "";
    const pat   = safe(pattern);
    const logFiles = IR_LOG_FILES.join(" ");
    const cmd = [
      `journalctl -u ir --since '${since_minutes} minutes ago' --no-pager 2>/dev/null | grep ${flag} '${pat}'`,
      `|| grep ${flag} '${pat}' ${logFiles} 2>/dev/null | tail -200`,
    ].join(" ");
    const raw = await runOnHosts(hosts, cmd);
    const results = raw.map(({ host, output }) => ({
      host: `${host}  [${output.split("\n").filter(Boolean).length} matches]`,
      output,
    }));
    return { content: [{ type: "text", text: formatResults(results) }] };
  }
);

// ─ get_ir_errors ─
server.tool(
  "get_ir_errors",
  "Fetch ERROR / WARN / FATAL / Exception / LDAP / Kafka lines from IR logs",
  {
    site:          z.string().optional().default("us1").describe("Site code or 'all'"),
    since_minutes: z.number().optional().default(60).describe("Lookback window in minutes"),
    servers:       z.array(z.string()).optional().default([]).describe("Override: specific hostnames"),
  },
  async ({ site, since_minutes, servers }) => {
    const hosts   = resolveHosts(site, servers);
    const pattern = "ERROR|WARN|FATAL|Exception|LDAP|VCC_node_disabled|Kafka";
    const logFiles = IR_LOG_FILES.join(" ");
    const cmd = [
      `journalctl -u ir --since '${since_minutes} minutes ago' --no-pager 2>/dev/null | grep -E '${pattern}'`,
      `|| grep -E '${pattern}' ${logFiles} 2>/dev/null | tail -200`,
    ].join(" ");
    const raw = await runOnHosts(hosts, cmd);
    const results = raw.map(({ host, output }) => ({
      host: `${host}  [${output.split("\n").filter(Boolean).length} error lines]`,
      output,
    }));
    return { content: [{ type: "text", text: formatResults(results) }] };
  }
);

// ─ get_kafka_events ─
server.tool(
  "get_kafka_events",
  "Search IR logs for a specific Kafka event type e.g. VCC_node_disabled_evt",
  {
    event_type:    z.string().optional().default("VCC_node_disabled_evt").describe("Kafka event name"),
    site:          z.string().optional().default("us1").describe("Site code or 'all'"),
    since_minutes: z.number().optional().default(30).describe("Lookback window in minutes"),
    servers:       z.array(z.string()).optional().default([]).describe("Override: specific hostnames"),
  },
  async ({ event_type, site, since_minutes, servers }) => {
    const hosts = resolveHosts(site, servers);
    const evt   = safe(event_type);
    const logFiles = IR_LOG_FILES.join(" ");
    const cmd = [
      `journalctl -u ir --since '${since_minutes} minutes ago' --no-pager 2>/dev/null | grep '${evt}'`,
      `|| grep '${evt}' ${logFiles} 2>/dev/null | tail -200`,
    ].join(" ");
    const raw = await runOnHosts(hosts, cmd);
    const results = raw.map(({ host, output }) => ({
      host: `${host}  [${output.split("\n").filter(Boolean).length} × ${evt}]`,
      output,
    }));
    return { content: [{ type: "text", text: formatResults(results) }] };
  }
);

// ─ get_ir_log_around_time ─
server.tool(
  "get_ir_log_around_time",
  "Fetch IR logs in a window around a specific timestamp — for incident investigation",
  {
    timestamp:      z.string().describe("ISO timestamp e.g. '2026-04-10 05:01:00'"),
    window_minutes: z.number().optional().default(5).describe("Minutes after timestamp (default 5)"),
    site:           z.string().optional().default("us1").describe("Site code or 'all'"),
    servers:        z.array(z.string()).optional().default([]).describe("Override: specific hostnames"),
  },
  async ({ timestamp, window_minutes, site, servers }) => {
    const hosts = resolveHosts(site, servers);
    const ts    = safe(timestamp);
    const logFiles = IR_LOG_FILES.join(" ");
    const cmd = [
      `journalctl -u ir --since "${ts}" --until "${ts} +${window_minutes} min" --no-pager 2>/dev/null`,
      `|| cat ${logFiles} 2>/dev/null | awk -v ts='${ts}' '$0 >= ts' | head -500`,
    ].join(" ");
    const results = await runOnHosts(hosts, cmd);
    return { content: [{ type: "text", text: formatResults(results) }] };
  }
);

// ── Start ─────────────────────────────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
