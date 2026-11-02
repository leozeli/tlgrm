"""Client factory and connection lifecycle for the core layer."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from telethon import TelegramClient

from ..config import get_api_credentials, ensure_dirs
from .errors import NotAuthorizedError


def get_client(account: str | None = None, must_exist: bool = True) -> TelegramClient:
    """Build a TelegramClient for the given account (or the default).

    The session path is resolved at call time from the account registry; a
    TG_SESSION_PATH / --session override still wins. `must_exist=False` is used
    during login, when the account is not registered yet.
    Raises CredentialsError if creds are unset.
    """
    from ..accounts import session_path_for

    ensure_dirs()
    api_id, api_hash = get_api_credentials()
    # Empty unless TG_PROXY_* or TG_MTPROXY_* is configured. The default
    # constructor path stays a direct connection.
    from ..proxy import telethon_proxy_kwargs

    extra = telethon_proxy_kwargs()
    return TelegramClient(
        session_path_for(account, must_exist), api_id, api_hash, **extra
    )


def resolve_target(target: str | int) -> str | int:
    """Treat a numeric target as a chat ID; otherwise pass it through as-is."""
    try:
        return int(target)
    except (ValueError, TypeError):
        return target


async def ensure_authorized(client: TelegramClient) -> None:
    """Connect the client and raise NotAuthorizedError if there's no session."""
    await client.connect()
    if not await client.is_user_authorized():
        raise NotAuthorizedError("Not authorized. Run 'tlgrm login' first.")


@asynccontextmanager
async def open_client(account: str | None = None) -> AsyncIterator[TelegramClient]:
    """Yield a connected, authorized client and always disconnect afterwards."""
    client = get_client(account)
    try:
        await ensure_authorized(client)
        yield client
    finally:
        await client.disconnect()
