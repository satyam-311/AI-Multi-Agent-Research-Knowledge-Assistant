import asyncio
from collections.abc import Sequence
from typing import Any

_SERVER_CONFIG = {
    "arxiv": {
        "transport": "stdio",
        "command": "uv",
        "args": ["tool", "run", "arxiv-mcp-server"],
    }
}

_tools_cache: Sequence[Any] | None = None
_tools_lock = asyncio.Lock()


def get_client():
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return MultiServerMCPClient(_SERVER_CONFIG)


async def get_tools() -> Sequence[Any]:
    global _tools_cache

    if _tools_cache is not None:
        return _tools_cache

    async with _tools_lock:
        if _tools_cache is None:
            client = get_client()
            _tools_cache = await client.get_tools()
        return _tools_cache
