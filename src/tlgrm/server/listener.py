"""One incoming-message listener per account, bound to the account's hot client.
State is rebuilt from persisted config on `reload()`."""

import logging
from collections.abc import Callable
from typing import Any, cast

from telethon import TelegramClient, events

from .. import listen_core
from ..webhook_url import validate_webhook_url

logger = logging.getLogger("tlgrm-server")


class AccountListener:
    def __init__(self, client: TelegramClient, account_name: str) -> None:
        self.client = client
        self.account = account_name
        self.state = listen_core.ListenState()
        self.account_obj: dict[str, Any] = {"name": account_name, "id": None}
        self._handler: Any = None
        self._pending: set[Any] = set()

    async def reload(self) -> None:
        """Rebuild listen state (enabled, webhook, filters) from config."""
        from .. import accounts

        cfg = accounts.listen_config(self.account)
        st = listen_core.ListenState()
        st.enabled = cfg["enabled"]
        url = cfg["webhook_url"]
        if url:
            try:
                validate_webhook_url(url)
            except ValueError as e:
                logger.error(f"[{self.account}] ignoring webhook URL: {e}")
                url = None
        st.webhook_url = url
        st.headers = listen_core.parse_headers(cfg["webhook_headers"])
        st.mode = cfg["filter"]["mode"]
        st.ids, st.names = await listen_core._resolve_filters(
            self.client, cfg["filter"]["list"]
        )
        win = cfg.get("window")
        st.window = listen_core._parse_window(win) if win else None
        self.state = st
        if self.account_obj["id"] is None:
            me = await self.client.get_me()
            self.account_obj = {"name": self.account, "id": me.id}

    def start(self) -> None:
        if self._handler is not None:
            return

        _on = cast(
            Callable[[Callable[..., Any]], Callable[..., Any]],
            self.client.on(events.NewMessage(incoming=True)),
        )

        @_on
        async def handler(event: Any) -> None:
            if not self.state.enabled:
                return
            try:
                await listen_core.process_event(
                    event, self.state, account=self.account_obj, pending=self._pending
                )
            except Exception as e:
                logger.error(f"[{self.account}] listener error: {e}")

        self._handler = handler

    def stop(self) -> None:
        if self._handler is not None:
            self.client.remove_event_handler(self._handler)
            self._handler = None
