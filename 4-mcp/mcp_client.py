import json
from typing import Dict, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    def __init__(self, cmd_argv: List[str]):
        self.cmd_argv = cmd_argv
        self.exit_stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None
        self._stdio = None
        self._write = None

    async def start(self) -> None:
        self.exit_stack = AsyncExitStack()
        stdio = await self.exit_stack.enter_async_context(
            stdio_client(StdioServerParameters(command=self.cmd_argv[0], args=self.cmd_argv[1:]))
        )
        self._stdio, self._write = stdio
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self._stdio, self._write)
        )
        await self.session.initialize()

    async def stop(self) -> None:
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = None
        self.session = None
        self._stdio = None
        self._write = None

    async def list_tool_names(self) -> List[str]:
        assert self.session is not None
        reply = await self.session.list_tools()
        return [t.name for t in (reply.tools or [])]

    async def call_tool_text(self, tool_name: str, args: Dict) -> str:
        assert self.session is not None
        resp = await self.session.call_tool(tool_name, args)
        items = resp.content or []
        for it in items:
            if getattr(it, "type", None) == "text":
                return it.text
        return json.dumps(
            [getattr(i, "model_dump", lambda: {"type": getattr(i, "type", None)})() for i in items],
            ensure_ascii=False
        )