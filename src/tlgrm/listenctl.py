"""CLI-side handlers for live listen configuration. Each writes persisted config
and, if a server is running, pushes a `reload` so the change applies live."""

from . import accounts, ipc
from .core.errors import TlgrmError
from .output import emit


def _push_reload(account: str) -> None:
    if ipc.is_server_running():
        ipc.request_sync("reload", account=account, args={}, tier="read")


def set_enabled(account: str, enabled: bool) -> None:
    accounts.set_listen_enabled(account, enabled)
    _push_reload(account)
    emit({"success": True, "account": account, "enabled": bool(enabled)})


def webhook_set(account: str, url: str, headers: list[str] | None = None) -> None:
    try:
        accounts.set_webhook(account, url, headers)
    except TlgrmError as e:
        emit({"success": False, "error": str(e)})
        return
    _push_reload(account)
    emit({"success": True, "account": account, "webhook_url": url})


def webhook_clear(account: str) -> None:
    accounts.clear_webhook(account)
    _push_reload(account)
    emit({"success": True, "account": account, "webhook_url": None})


def _redact_header(h: str) -> str:
    """Show the header name but hide its value (it may carry a bearer token)."""
    return f"{h.split(':', 1)[0].strip()}: [REDACTED]" if ":" in h else h


def webhook_show(account: str) -> None:
    cfg = accounts.listen_config(account)
    emit(
        {
            "success": True,
            "account": account,
            "webhook_url": cfg["webhook_url"],
            "webhook_headers": [_redact_header(h) for h in cfg["webhook_headers"]],
        }
    )


def window_set(account: str, window: str) -> None:
    from .listen_core import _parse_window

    if _parse_window(window) is None:
        emit(
            {
                "success": False,
                "error": f"Invalid window {window!r} (use HH:MM-HH:MM, e.g. 09:00-17:00).",
            }
        )
        return
    accounts.set_listen_window(account, window)
    _push_reload(account)
    emit({"success": True, "account": account, "window": window})


def window_clear(account: str) -> None:
    accounts.clear_listen_window(account)
    _push_reload(account)
    emit({"success": True, "account": account, "window": None})


def window_show(account: str) -> None:
    emit(
        {
            "success": True,
            "account": account,
            "window": accounts.listen_config(account)["window"],
        }
    )


def filter_cmd(
    account: str,
    domain: str,
    op: str,
    value: str | None = None,
    tokens: list[str] | None = None,
) -> None:
    if op == "show":
        emit(
            {
                "success": True,
                "account": account,
                "domain": domain,
                "filter": accounts.filter_config(account, domain),
            }
        )
        return
    if op == "mode":
        assert value is not None
        accounts.filter_set_mode(account, domain, value)
    elif op == "add":
        accounts.filter_add(account, domain, tokens or [])
    elif op == "remove":
        accounts.filter_remove(account, domain, tokens or [])
    elif op == "clear":
        accounts.filter_clear(account, domain)
    _push_reload(account)
    emit(
        {
            "success": True,
            "account": account,
            "domain": domain,
            "filter": accounts.filter_config(account, domain),
        }
    )
