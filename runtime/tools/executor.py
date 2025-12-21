"""
ToolExecutor abstraction (scaffold).
Provides a single place to reason about trusted vs untrusted tools and future sandboxing.

Design notes:
- Trusted tools: small set of in-process helpers (fast, no network)
- Untrusted tools: must be executed via sandbox (ToolDispatcher._execute_in_sandbox)
"""
from typing import Dict, Any
from runtime.tools.tool_dispatcher import ToolDispatcher, ToolResult
import asyncio

class ToolExecutor:
    def __init__(self, dispatcher: ToolDispatcher = None):
        # 使用现有的 ToolDispatcher 作为默认实现
        self.dispatcher = dispatcher or ToolDispatcher()

    async def execute(self, tool_name: str, params: Dict[str, Any], task_id: str) -> ToolResult:
        """
        Execute a tool. This abstraction allows us to mark trusted tool calls
        (which could be executed in-process) vs untrusted (sandboxed).
        """
        # Placeholder decision: currently treat all as sandboxed / untrusted.
        # Future: consult a trust registry to run some tools in-process for performance.
        return await self.dispatcher.execute(tool_name, params, task_id)

    # Synchronous wrapper for code paths that need sync execution (scaffold)
    def execute_sync(self, tool_name: str, params: Dict[str, Any], task_id: str) -> ToolResult:
        return asyncio.get_event_loop().run_until_complete(self.execute(tool_name, params, task_id))


