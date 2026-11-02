"""Read-only view models for the dashboard. No Telegram I/O."""

from typing import Any
from urllib.parse import urlencode

from .. import accounts
from ..core.errors import TlgrmError
from ..redact import filter_summary, mask_webhook_url, redact_header


def account_names() -> tuple[str | None, list[str]]:
    cfg = accounts.load_config()
    names = [str(name) for name in (cfg.get("accounts") or {})]
    default = cfg.get("default_account")
    return (str(default) if default else None), names


def resolve_requested(requested: str | None) -> tuple[str | None, str | None]:
    """Return ``(account, error)``. No configured account is not an error."""
    if requested:
        try:
            return accounts.resolve_account(requested), None
        except TlgrmError as exc:
            return None, str(exc)
    try:
        return accounts.resolve_account(None), None
    except TlgrmError:
        return None, None


def with_account(path: str, account: str | None) -> str:
    if not account:
        return path
    return f"{path}?{urlencode({'account': account})}"


def listening_view(account: str) -> dict[str, Any]:
    """Listen settings safe to render. The raw webhook URL is not included."""
    cfg = accounts.listen_config(account)
    write = accounts.filter_config(account, "write")
    return {
        "enabled": bool(cfg["enabled"]),
        "window": cfg.get("window"),
        "webhook_masked": mask_webhook_url(cfg.get("webhook_url")),
        "webhook_set": bool(cfg.get("webhook_url")),
        "headers": [redact_header(h) for h in cfg.get("webhook_headers") or []],
        "listen_summary": filter_summary(cfg.get("filter") or {}),
        "write_summary": filter_summary(write),
    }
