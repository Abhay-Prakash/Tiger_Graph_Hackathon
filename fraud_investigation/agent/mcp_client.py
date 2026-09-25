"""Real stdio MCP transport for the fraud investigation agent.

The application never imports or invokes pyTigerGraph here. TigerGraph access
is performed by the official ``tigergraph-mcp`` server process.
"""

import asyncio
import json
import logging
import os
import re
import sys
import threading
from datetime import timedelta
from typing import Any, Dict, List, Optional, Protocol

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)
_JSON_FENCE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


class MCPTransport(Protocol):
    """Small synchronous boundary that makes the protocol transport testable."""

    def start(self) -> List[str]: ...
    def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any: ...
    def close(self) -> None: ...


class StdioMCPTransport:
    """Owns one official tigergraph-mcp subprocess for an investigation run."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._tools: Dict[str, Any] = {}
        self._shutdown: Optional[asyncio.Event] = None

    def start(self) -> List[str]:
        if self._session is not None:
            return list(self._tools)
        self._thread = threading.Thread(target=self._run_loop, name="tigergraph-mcp", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise TimeoutError("Timed out starting tigergraph-mcp stdio session")
        if self._startup_error is not None:
            raise RuntimeError("Unable to initialize tigergraph-mcp session") from self._startup_error
        return list(self._tools)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except BaseException as exc:
            self._startup_error = exc
        finally:
            self._ready.set()
        self._loop.close()

    async def _serve(self) -> None:
        load_dotenv()
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tigergraph_mcp.main", "--transport", "stdio"],
            env=os.environ.copy(),
            cwd=os.getcwd(),
        )
        try:
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    self._session = session
                    await session.initialize()
                    tools = await session.list_tools()
                    self._tools = {tool.name: tool.inputSchema for tool in tools.tools}
                    self._shutdown = asyncio.Event()
                    self._ready.set()
                    await self._shutdown.wait()
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            raise

    def call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if self._loop is None or self._session is None:
            raise RuntimeError("MCP session is not initialized")
        future = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(tool_name, arguments, read_timeout_seconds=timedelta(seconds=90)),
            self._loop,
        )
        return future.result(timeout=100)

    def close(self) -> None:
        if self._loop is None or self._shutdown is None:
            return
        self._loop.call_soon_threadsafe(self._shutdown.set)
        if self._thread is not None:
            self._thread.join(timeout=15)
        self._session = None


class TigerGraphMCPClient:
    """Synchronous application adapter backed exclusively by real MCP calls."""

    def __init__(
        self,
        conn: Optional[Any] = None,
        use_mcp: bool = True,
        start_session: bool = False,
        transport: Optional[MCPTransport] = None,
    ) -> None:
        if conn is not None:
            logger.warning("Ignoring deprecated direct TigerGraph connection; production transport is MCP only")
        self.use_mcp = use_mcp
        self._transport = transport
        self._tool_names: List[str] = []
        self.protocol_trace: List[Dict[str, Any]] = []
        self.last_call_succeeded = False
        self.failure_reason: Optional[str] = None
        self.transport_name = "mock_mcp"
        if start_session:
            self.start()

    def start(self) -> bool:
        if not self.use_mcp:
            return False
        try:
            self._transport = self._transport or StdioMCPTransport()
            self._tool_names = self._transport.start()
            self.transport_name = "stdio_mcp"
            self.protocol_trace.extend([
                {"event": "initialize", "transport": "stdio_mcp", "server": "tigergraph-mcp"},
                {"event": "tools/list", "tool_count": len(self._tool_names)},
            ])
            logger.info("MCP initialized; discovered %d tools", len(self._tool_names))
            return True
        except Exception as exc:
            self.failure_reason = str(exc)
            self.transport_name = "MCP_UNAVAILABLE"
            logger.warning("MCP transport unavailable: %s", exc)
            return False

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()

    def is_live(self) -> bool:
        return self.transport_name == "stdio_mcp" and self._transport is not None

    def _resolve_tool(self, requested_name: str) -> Optional[str]:
        if requested_name in self._tool_names:
            return requested_name
        prefixed = f"tigergraph__{requested_name}"
        return prefixed if prefixed in self._tool_names else None

    @staticmethod
    def _result_text(result: Any) -> str:
        content = getattr(result, "content", None)
        if content is None and isinstance(result, dict):
            content = result.get("content", [])
        texts = []
        for item in content or []:
            texts.append(getattr(item, "text", item.get("text", "") if isinstance(item, dict) else ""))
        return "\n".join(texts)

    @staticmethod
    def _decode_payload(text: str) -> Dict[str, Any]:
        match = _JSON_FENCE.search(text)
        decoded = json.loads(match.group(1) if match else text)
        if not isinstance(decoded, dict):
            raise ValueError("MCP tool response was not a JSON object")
        return decoded

    @staticmethod
    def _normalize_query_data(data: Any) -> Dict[str, Any]:
        result = data.get("result", data) if isinstance(data, dict) else data
        if isinstance(result, list):
            merged: Dict[str, Any] = {}
            for item in result:
                if isinstance(item, dict):
                    merged.update(item)
            return merged
        return result if isinstance(result, dict) else {"result": result}

    def _add_nodes_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        vertex_id = arguments.get("vertex_id", "case_id")
        records = []
        for item in arguments.get("vertices", []):
            if isinstance(item, tuple):
                identifier, attributes = item
                records.append({vertex_id: identifier, **attributes})
            else:
                records.append(item)
        return {
            "graph_name": os.getenv("TG_GRAPHNAME", "HHGOA_Fraud"),
            "vertex_type": arguments["vertex_type"],
            "vertex_id": vertex_id,
            "vertices": records,
        }

    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.last_call_succeeded = False
        if not self.is_live():
            return {"success": False, "operation": tool_name, "transport": self.transport_name,
                    "error": self.failure_reason or "MCP session is not active", "data": {}}

        if tool_name == "upsert_vertices":
            actual_tool = self._resolve_tool("add_nodes")
            actual_arguments = self._add_nodes_arguments(arguments)
        else:
            actual_tool = self._resolve_tool(tool_name)
            actual_arguments = dict(arguments)
            actual_arguments.setdefault("graph_name", os.getenv("TG_GRAPHNAME", "HHGOA_Fraud"))
        if actual_tool is None:
            return {"success": False, "operation": tool_name, "transport": "stdio_mcp",
                    "error": f"MCP tool not discovered: {tool_name}", "data": {}}

        try:
            result = self._transport.call(actual_tool, actual_arguments)
            if getattr(result, "isError", False) or (isinstance(result, dict) and result.get("isError")):
                raise RuntimeError(self._result_text(result))
            payload = self._decode_payload(self._result_text(result))
            if not payload.get("success", False):
                raise RuntimeError(payload.get("error", "MCP tool returned an unsuccessful response"))
            data = self._normalize_query_data(payload.get("data", {})) if tool_name == "run_installed_query" else payload.get("data", {})
            self.last_call_succeeded = True
            event = {"event": "tools/call", "transport": "stdio_mcp", "server": "tigergraph-mcp", "tool": actual_tool}
            if "query_name" in actual_arguments:
                event["query_name"] = actual_arguments["query_name"]
            self.protocol_trace.append(event)
            logger.info("MCP tool call succeeded: %s", actual_tool)
            return {"success": True, "operation": tool_name, "transport": "stdio_mcp", "data": data}
        except Exception as exc:
            self.failure_reason = str(exc)
            logger.warning("MCP tool call failed (%s): %s", actual_tool, exc)
            return {"success": False, "operation": tool_name, "transport": "stdio_mcp", "error": str(exc), "data": {}}

    def _run_installed_query(self, query_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.call_mcp_tool("run_installed_query", {"query_name": query_name, "params": params})["data"]

    def run_query_get_transaction_context(self, flagged_txn_id: str, lookback_days: int = 90) -> Dict[str, Any]:
        return self._run_installed_query("get_transaction_context", {"flagged_txn_id": flagged_txn_id, "lookback_days": lookback_days})

    def run_query_get_customer_case_history(self, customer_id: str) -> Dict[str, Any]:
        return self._run_installed_query("get_customer_case_history", {"customer_id": customer_id})

    def run_query_detect_region_anomaly(self, customer_id: str, flagged_txn_id: str) -> Dict[str, Any]:
        return self._run_installed_query("detect_region_anomaly", {"customer_id": customer_id, "flagged_txn_id": flagged_txn_id})

    def run_query_detect_shared_device(self, flagged_txn_id: str) -> Dict[str, Any]:
        return self._run_installed_query("detect_shared_device", {"flagged_txn_id": flagged_txn_id})

    def run_query_detect_velocity_burst(self, customer_id: str, flagged_txn_id: str, window_hours: int = 24) -> Dict[str, Any]:
        return self._run_installed_query("detect_velocity_burst", {"customer_id": customer_id, "flagged_txn_id": flagged_txn_id, "window_hours": window_hours})
