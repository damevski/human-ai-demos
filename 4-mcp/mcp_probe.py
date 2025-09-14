import asyncio, os, shlex, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import config

DISCORD_MCP_CMD = os.getenv("DISCORD_MCP_CMD")
TEST_CHANNEL_NAME = os.getenv("TEST_CHANNEL_NAME", "mcp-testing")

def jprint(prefix, obj):
    try:
        print(prefix, json.dumps(obj, indent=2))
    except Exception:
        print(prefix, obj)

async def call_tool(session, name, args):
    try:
        resp = await session.call_tool(name, args)
        print(resp)
        # The MCP tool response content is a list of content items; each may be TextContent or structured.
        is_error = getattr(resp, "isError", False)
        content = getattr(resp, "content", []) or []
        items = []
        for c in content:
            if hasattr(c, "model_dump"):
                items.append(c.model_dump())
            elif hasattr(c, "__dict__"):
                items.append(c.__dict__)
            else:
                items.append(str(c))
        jprint(f"{name} {'error' if is_error else 'ok'} ->", items)
        return resp
    except Exception as e:
        print(f"{name} failed:", e)
        return None

async def main():
    if not DISCORD_MCP_CMD:
        raise RuntimeError("Set DISCORD_MCP_CMD to your docker run command in DISCORD_MCP_CMD")

    argv = shlex.split(DISCORD_MCP_CMD)
    print("Launching:", argv)

    # Quick env echo to catch common misconfig
    print("ENV DISCORD_TOKEN set:", bool(os.getenv("DISCORD_TOKEN")))
    print("ENV DISCORD_GUILD_ID:", os.getenv("DISCORD_GUILD_ID"))
    print("ENV TEST_CHANNEL_NAME:", TEST_CHANNEL_NAME)

    async with stdio_client(StdioServerParameters(command=argv[0], args=argv[1:])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [t.name for t in (tools.tools or [])]
            print("Tools:", tool_names)

            r = await call_tool(session, "get_server_info", {})
            if not r or getattr(r, "isError", False):
                print("get_server_info failed, the server cannot resolve your guild by DISCORD_GUILD_ID.")
                print("Check that the bot is in the guild and that DISCORD_GUILD_ID is the correct numeric Server ID.")
                return

            r = await call_tool(session, "list_channels", {})
            if not r or getattr(r, "isError", False):
                print("list_channels failed, aborting.")
                return

            fc = await call_tool(session, "find_channel", {"channelName": TEST_CHANNEL_NAME})
            if not fc or getattr(fc, "isError", False):
                print(f"find_channel('{TEST_CHANNEL_NAME}') failed.")
                return

            # Try to extract a channel id robustly from the returned content items
            channel_id = None
            for c in (getattr(fc, "content", []) or []):
                # Prefer structured meta first
                if hasattr(c, "model_dump"):
                    d = c.model_dump() or {}
                    meta = d.get("meta") or {}
                    channel_id = meta.get("channelId") or channel_id
                    if not channel_id and isinstance(d.get("text"), str):
                        # Sometimes the tool returns a JSON string in text
                        try:
                            obj = json.loads(d["text"])
                            channel_id = obj.get("id") or obj.get("channelId") or channel_id
                        except Exception:
                            pass
                # Fallback if it’s a simple text content
                if not channel_id and hasattr(c, "text") and isinstance(c.text, str):
                    try:
                        obj = json.loads(c.text)
                        channel_id = obj.get("id") or obj.get("channelId") or channel_id
                    except Exception:
                        # If the tool just returned a name, ignore
                        pass

            channel_id = channel_id or os.getenv("TEST_CHANNEL_ID")
            if not channel_id:
                print("No channelId resolved. Set TEST_CHANNEL_ID explicitly or adjust parsing to your server’s response.")
                return

            await call_tool(session, "read_messages", {"channelId": channel_id, "limit": 1})

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)