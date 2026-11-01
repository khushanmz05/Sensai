"""Expose isolated Python execution through the existing approval-aware MCP loop."""
import json
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent
from sandbox.runner import run_python

server = FastMCP('sensai-python')


@server.tool()
async def execute_python(code: str) -> CallToolResult:
    """Execute Python source in an isolated Linux sandbox; return stdout, stderr/traceback,
    exit_code and status. Use print() to return results. Standard library only, no network,
    host files, writes or subprocesses. Limits: 2 CPU seconds, 5 wall seconds, 256 MiB,
    4 KiB combined output. If status is not ok, inspect stderr and submit corrected code
    within the turn's call limit. Never claim execution unless this tool returned a result.
    """
    result = await run_python(code)
    return CallToolResult(
        isError=result['status'] != 'ok', structuredContent=result,
        content=[TextContent(type='text', text=json.dumps(result, ensure_ascii=False))],
    )


if __name__ == '__main__':
    server.run(transport='stdio')
