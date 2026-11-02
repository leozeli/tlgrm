"""Forward dashboard actions to the background server.

The server owns the Telegram connection, enforces permission tiers, and runs
the write guard. The UI auto-spawns it the same way the MCP bridge does, so
the CLI, MCP, and this dashboard share one session.
"""

import asyncio
from typing import Any

from ..server.tiers import COMMAND_TIERS


class BridgeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def ensure_server() -> bool:
    """Return True once a server accepts connections."""
    from .. import ipc, serverctl

    if ipc.is_server_running():
        return True
    try:
        serverctl._spawn_detached()
    except Exception:
        return False
    for _ in range(50):
        await asyncio.sleep(0.2)
        if ipc.is_server_running():
            return True
    return False


async def call_cmd(
    cmd: str, account: str | None, args: dict[str, Any] | None = None
) -> Any:
    """Run one command at its own permission tier. Raise BridgeError on failure."""
    from .. import ipc

    if not await ensure_server():
        raise BridgeError(
            "Background server is not running. Start it with `tlgrm server start`."
        )
    clean = {k: v for k, v in (args or {}).items() if v is not None}
    tier = COMMAND_TIERS.get(cmd, "read")
    try:
        resp = await ipc.request_async(cmd, account=account, args=clean, tier=tier)
    except OSError:
        raise BridgeError("Could not reach the background server.")
    if not resp or not resp.get("ok"):
        err = (resp or {}).get("error") or {}
        message = err.get("message") or "Request failed."
        raise BridgeError(str(message))
    return resp.get("data")
