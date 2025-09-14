import asyncio
import json
import os
import shlex
from typing import Dict, List, Iterable

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.chat_history import InMemoryChatMessageHistory

from config import (
    DISCORD_MCP_CMD,
    DISCORD_ALLOWED_CHANNELS,
    DISCORD_SEND_TOOL,
    DISCORD_READ_TOOL,
)
from graph import GRAPH, SYSTEM_MSG
from mcp_client import MCPClient

# Per-channel histories
_histories: Dict[str, InMemoryChatMessageHistory] = {}


def history(cid: str) -> InMemoryChatMessageHistory:
    if cid not in _histories:
        _histories[cid] = InMemoryChatMessageHistory()
    return _histories[cid]


def allowed_channels() -> Iterable[str]:
    """
    For SaseQ/discord-mcp, read_messages requires channelId.
    To avoid schema guessing, we iterate explicitly over allowed channels.
    """
    if not DISCORD_ALLOWED_CHANNELS:
        raise RuntimeError(
            "DISCORD_ALLOWED_CHANNELS is empty. "
            "Set it to one or more channel IDs so we can poll with read_messages(channelId=...)."
        )
    return DISCORD_ALLOWED_CHANNELS


async def debug_print_tool_schemas(client: MCPClient) -> None:
    if not client.session:
        return
    reply = await client.session.list_tools()  # type: ignore[attr-defined]
    print("=== MCP tools and schemas ===")
    for t in reply.tools or []:
        print(t.name, getattr(t, "inputSchema", None))
    print("=============================")


async def main() -> None:
    argv = shlex.split(DISCORD_MCP_CMD)
    client = MCPClient(argv)
    await client.start()

    try:
        if os.getenv("DEBUG_MCP_SCHEMAS", "").lower() in {"1", "true", "yes"}:
            await debug_print_tool_schemas(client)

        tool_names = {t.lower(): t for t in await client.list_tool_names()}
        if DISCORD_SEND_TOOL.lower() not in tool_names or DISCORD_READ_TOOL.lower() not in tool_names:
            have = ", ".join(sorted(tool_names.values()))
            raise RuntimeError(
                f"Discord MCP tools not found. Have: {have}. Need: {DISCORD_SEND_TOOL}, {DISCORD_READ_TOOL}"
            )

        send_tool = tool_names[DISCORD_SEND_TOOL.lower()]
        read_tool = tool_names[DISCORD_READ_TOOL.lower()]

        # Main loop: poll each allowed channel explicitly, then reply in-place.
        while True:
            any_found = False
            for chan in allowed_channels():
                # SaseQ server expects camelCase: channelId + optional limit
                print(f"[read_messages] channelId={chan}", flush=True)
                msgs_raw = await client.call_tool_text(read_tool, {"channelId": chan, "limit": 5})
                try:
                    msgs: List[Dict] = json.loads(msgs_raw) if msgs_raw else []
                except Exception:
                    msgs = []

                if not msgs:
                    continue

                any_found = True
                for m in msgs:
                    # Normalize message fields
                    message_id = str(
                        m.get("messageId")
                        or m.get("message_id")
                        or m.get("id")
                        or ""
                    )
                    content = (m.get("content") or m.get("text") or "").strip()
                    if not content:
                        continue

                    # Build conversation and invoke LangGraph
                    h = history(chan)
                    h.add_message(HumanMessage(content=content))
                    prior = [SYSTEM_MSG] + h.messages

                    state = GRAPH.invoke({"messages": prior})
                    ai_text = ""
                    for msg in reversed(state["messages"]):
                        if isinstance(msg, AIMessage):
                            ai_text = msg.content
                            break
                    if not ai_text:
                        ai_text = "I didn’t produce a response."

                    h.add_message(AIMessage(content=ai_text))

                    # Send reply back using camelCase required by SaseQ server
                    send_payload_variants = [
                        # Preferred for SaseQ/discord-mcp
                        (
                            {"channelId": chan, "content": ai_text, "replyToMessageId": message_id}
                            if message_id else
                            {"channelId": chan, "content": ai_text}
                        ),
                        # Fallbacks for other servers (kept for portability)
                        (
                            {"channel_id": chan, "content": ai_text, "reply_to_id": message_id}
                            if message_id else
                            {"channel_id": chan, "content": ai_text}
                        ),
                        (
                            {"channel": chan, "text": ai_text, "reply_to": message_id}
                            if message_id else
                            {"channel": chan, "text": ai_text}
                        ),
                    ]

                    sent_ok = False
                    for payload in send_payload_variants:
                        try:
                            _ = await client.call_tool_text(send_tool, payload)
                            sent_ok = True
                            break
                        except Exception:
                            continue

                    if not sent_ok:
                        print(f"[send_message] failed for channel {chan}", flush=True)

            # Back off a bit if nothing was read
            await asyncio.sleep(0.3 if any_found else 0.8)

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())