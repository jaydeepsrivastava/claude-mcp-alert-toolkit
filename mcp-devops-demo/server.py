from mcp.server.fastmcp import FastMCP
import subprocess

mcp = FastMCP("devops-assistant")

def run_cmd(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception as e:
        return str(e)

@mcp.tool()
def disk_usage() -> str:
    """Check disk usage"""
    return run_cmd("df -h")

@mcp.tool()
def cpu_processes() -> str:
    """Top CPU consuming processes"""
    return run_cmd("ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head")

@mcp.tool()
def memory_usage() -> str:
    """Check memory usage"""
    return run_cmd("free -h")

@mcp.tool()
def ping_host(host: str) -> str:
    """Ping a host"""
    return run_cmd(f"ping -c 3 {host}")

@mcp.tool()
def search_logs(keyword: str) -> str:
    """Search logs for a keyword"""
    return run_cmd(f"grep -i '{keyword}' /var/log/messages | tail -n 20")

if __name__ == "__main__":
    mcp.run()
