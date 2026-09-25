"""Standalone proof of a real stdio MCP session with tigergraph-mcp.

This is intentionally separate from the fraud application. It discovers the
server's exposed tools before any production transport integration is attempted.
"""

import asyncio
import json
import os
import sys
from datetime import timedelta

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from dotenv import load_dotenv


async def main() -> None:
    load_dotenv()
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tigergraph_mcp.main", "--transport", "stdio"],
        env=os.environ.copy(),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await session.initialize()
            print(
                json.dumps(
                    {
                        "event": "initialize",
                        "protocol_version": str(initialized.protocolVersion),
                    }
                )
            )

            tools = await session.list_tools()
            query_tools = [tool for tool in tools.tools if "query" in tool.name]
            print(
                json.dumps(
                    {
                        "event": "tools/list",
                        "tool_count": len(tools.tools),
                        "query_tools": [
                            {"name": tool.name, "input_schema": tool.inputSchema}
                            for tool in query_tools
                        ],
                    }
                )
            )

            installed_query = next(
                (tool for tool in query_tools if "run_installed_query" in tool.name),
                None,
            )
            if installed_query is None:
                raise RuntimeError("The MCP server did not expose an installed-query tool.")

            result = await session.call_tool(
                installed_query.name,
                {
                    "graph_name": os.environ.get("TG_GRAPHNAME", "HHGOA_Fraud"),
                    "query_name": "get_transaction_context",
                    "params": {"flagged_txn_id": "3514948", "lookback_days": 90},
                },
                read_timeout_seconds=timedelta(seconds=90),
            )
            print(
                json.dumps(
                    {
                        "event": "tools/call",
                        "tool": installed_query.name,
                        "is_error": result.isError,
                        "content": [getattr(item, "text", str(item)) for item in result.content],
                    }
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
