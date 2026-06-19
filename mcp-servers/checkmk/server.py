from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP
from client import CheckMKClient

mcp = FastMCP("checkmk")

_STATE_HOST = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
_STATE_SVC = {0: "OK", 1: "WARN", 2: "CRIT", 3: "UNKNOWN"}


def _client() -> CheckMKClient:
    return CheckMKClient()


def _is_error(result: object) -> bool:
    return isinstance(result, str)


@mcp.tool()
def checkmk_test_connection() -> str:
    """Test connectivity and credentials. Call first to confirm CheckMK is reachable before using other tools."""
    client = _client()
    result = client.get("version")
    if _is_error(result):
        return result
    assert isinstance(result, dict)
    version = result.get("versions", {}).get("checkmk", str(result))
    return f"✅ Connected to CheckMK {version}"


@mcp.tool()
def checkmk_list_problems() -> str:
    """List all services in WARN or CRIT state across all monitored hosts. Use first for MINIMAL context investigations to identify which host/service is alerting."""
    client = _client()
    result = client.get(
        "domain-types/service/collections/all",
        params={
            "query": json.dumps({"op": ">=", "left": "state", "right": "1"}),
            "columns": ["host_name", "display_name", "state", "plugin_output"],
        },
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    services = result.get("value", [])
    if not services:
        return "⚠️ No WARN/CRIT services found"

    lines = [f"Found {len(services)} problem(s):"]
    for svc in services:
        ext = svc.get("extensions", {})
        state = _STATE_SVC.get(ext.get("state"), "?")
        output = (ext.get("plugin_output") or "")[:100]
        lines.append(f"  [{state}] {ext.get('host_name')} / {ext.get('display_name')} — {output}")
    return "\n".join(lines)


@mcp.tool()
def checkmk_get_host_status(hostname: str) -> str:
    """Get the up/down status of a specific host. Use to confirm whether an alert is host-level or service-level."""
    client = _client()
    result = client.get(
        "domain-types/host/collections/all",
        params={
            "query": json.dumps({"op": "=", "left": "name", "right": hostname}),
            "columns": ["name", "state", "address", "plugin_output"],
        },
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    hosts = result.get("value", [])
    if not hosts:
        return f"❌ Host not found: {hostname}"
    ext = hosts[0].get("extensions", {})
    state = _STATE_HOST.get(ext.get("state"), "UNKNOWN")
    return (
        f"Host: {hostname}\n"
        f"State: {state}\n"
        f"Address: {ext.get('address', 'n/a')}\n"
        f"Output: {ext.get('plugin_output', 'n/a')}"
    )


@mcp.tool()
def checkmk_get_service_status(hostname: str, service_name: str) -> str:
    """Get detailed status of one service on a host. Use during FULL context investigation when both host and service name are known.
    service_name: exact CheckMK service name (e.g. 'CPU load', 'Disk IO SUMMARY', 'Memory')"""
    client = _client()
    result = client.get(
        "domain-types/service/collections/all",
        params={
            "query": json.dumps({
                "op": "and",
                "expr": [
                    {"op": "=", "left": "host_name", "right": hostname},
                    {"op": "=", "left": "description", "right": service_name},
                ],
            }),
            "columns": ["host_name", "description", "state", "plugin_output", "last_check"],
        },
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    services = result.get("value", [])
    if not services:
        return f"❌ Service not found: {hostname} / {service_name}"
    ext = services[0].get("extensions", {})
    state = _STATE_SVC.get(ext.get("state"), "?")
    return (
        f"Host: {hostname}\n"
        f"Service: {service_name}\n"
        f"State: {state}\n"
        f"Output: {ext.get('plugin_output', 'n/a')}\n"
        f"Last check: {ext.get('last_check', 'n/a')}"
    )


@mcp.tool()
def checkmk_list_hosts() -> str:
    """List all monitored hosts with their current state. Use when the hostname is unknown and you need to find the correct name."""
    client = _client()
    result = client.get(
        "domain-types/host/collections/all",
        params={"columns": ["name", "address", "state"]},
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    hosts = result.get("value", [])
    if not hosts:
        return "⚠️ No hosts found"

    lines = [f"Found {len(hosts)} host(s):"]
    for host in hosts:
        ext = host.get("extensions", {})
        state = _STATE_HOST.get(ext.get("state"), "?")
        lines.append(f"  [{state}] {ext.get('name', host.get('id', '?'))} ({ext.get('address', '')})")
    return "\n".join(lines)


@mcp.tool()
def checkmk_get_host_services(hostname: str) -> str:
    """List all services on a specific host with their current states. Use to assess the full blast radius when a host issue is suspected."""
    client = _client()
    result = client.get(
        f"objects/host/{hostname}/collections/services",
        params={"columns": ["display_name", "state", "plugin_output"]},
    )
    if _is_error(result):
        return result
    assert isinstance(result, dict)

    services = result.get("value", [])
    if not services:
        return f"⚠️ No services found for host {hostname}"

    lines = [f"Host {hostname} — {len(services)} service(s):"]
    for svc in services:
        ext = svc.get("extensions", {})
        state = _STATE_SVC.get(ext.get("state"), "?")
        output = (ext.get("plugin_output") or "")[:80]
        lines.append(f"  [{state}] {ext.get('display_name', '?')} — {output}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
