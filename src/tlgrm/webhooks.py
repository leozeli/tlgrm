import sys
import logging
from typing import Any

from telethon import events

from .core.client import get_client, ensure_authorized
from .core.errors import NotAuthorizedError, TlgrmError
from .stt import preload
from . import listen_core
from . import accounts
from .webhook_url import validate_webhook_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("tlgrm-webhook")


async def run_listener(
    webhook_url: str | None = None,
    webhook_headers: list[str] | None = None,
    verbose: bool = False,
    only: list[str] | None = None,
    ignore: list[str] | None = None,
) -> None:
    if webhook_url:
        try:
            validate_webhook_url(webhook_url)
        except ValueError as e:
            raise TlgrmError(str(e)) from e
    if verbose:
        logger.setLevel(logging.DEBUG)
    client = get_client()
    try:
        await ensure_authorized(client)
    except NotAuthorizedError as e:
        logger.error(str(e))
        await client.disconnect()
        return

    only_ids, only_names = await listen_core._resolve_filters(
        client, listen_core._split_tokens(only)
    )
    ignore_ids, ignore_names = await listen_core._resolve_filters(
        client, listen_core._split_tokens(ignore)
    )

    state = listen_core.ListenState()
    state.webhook_url = webhook_url
    state.headers = listen_core.parse_headers(webhook_headers)

    preload()
    me = await client.get_me()
    account: dict[str, Any] = {
        "name": accounts.load_config().get("default_account") or "default",
        "id": me.id,
    }
    pending: set[Any] = set()

    @client.on(events.NewMessage(incoming=True))  # type: ignore[untyped-decorator]
    async def handler(event: Any) -> None:
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()
            cu = getattr(chat, "username", None)
            su = getattr(sender, "username", None)
            if (only_ids or only_names) and not listen_core._matches(
                only_ids, only_names, event.chat_id, event.sender_id, cu, su
            ):
                return
            if listen_core._matches(
                ignore_ids, ignore_names, event.chat_id, event.sender_id, cu, su
            ):
                return
            await listen_core.process_event(
                event, state, account=account, pending=pending, emit_console=verbose
            )
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    logger.info(f"Listening as {me.first_name} [ID: {me.id}].")
    await client.run_until_disconnected()


# Back-compat re-exports (tests and external callers used these names).
forward_webhook = listen_core.forward_webhook
_split_tokens = listen_core._split_tokens
_resolve_filters = listen_core._resolve_filters
_matches = listen_core._matches
