import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or ""
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

# How to start the Discord MCP server over stdio.
# If you already pass DISCORD_TOKEN/GUILD_ID via env, this default works:
DISCORD_MCP_CMD = os.getenv(
    "DISCORD_MCP_CMD",
    "docker run --rm -i saseq/discord-mcp:latest"
)

# If you want this client to pass env vars into Docker, set:
# DISCORD_MCP_CMD='docker run --rm -i -e DISCORD_TOKEN=$DISCORD_TOKEN -e DISCORD_GUILD_ID=$DISCORD_GUILD_ID saseq/discord-mcp:latest'

# Optional filtering
DISCORD_ALLOWED_CHANNELS = {
    p.strip() for p in (os.getenv("DISCORD_ALLOWED_CHANNELS") or "").split(",") if p.strip()
}

# Tool names exposed by your Discord MCP server.
# These defaults match SaseQ/discord-mcp; override via env if needed.
DISCORD_SEND_TOOL = os.getenv("DISCORD_SEND_TOOL", "send_message")
DISCORD_READ_TOOL = os.getenv("DISCORD_READ_TOOL", "read_messages")