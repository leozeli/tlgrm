"""Mutations the dashboard shares with the CLI: listen config and env file.

Telegram sends go through the server bridge so the write guard still runs.
"""

from collections.abc import Mapping

from .. import accounts, envfile
from ..listenctl import push_reload
from ..proxy import parse_proxy_config


def set_listening(account: str, enabled: bool) -> None:
    accounts.set_listen_enabled(account, enabled)
    push_reload(account)


def set_webhook(
    account: str,
    url: str,
    header: str | None,
    *,
    clear_header: bool,
) -> None:
    existing = list(accounts.listen_config(account)["webhook_headers"])
    if header:
        headers = [header]
    elif clear_header:
        headers = []
    else:
        headers = existing
    accounts.set_webhook(account, url, headers)
    push_reload(account)


def clear_webhook(account: str) -> None:
    accounts.clear_webhook(account)
    push_reload(account)


def build_auth_header(name: str, value: str) -> str | None:
    """Build one ``Name: value`` header. A blank value means 'no new header'."""
    raw_name = name.strip() or "Authorization"
    raw_value = value.strip()
    if not raw_value:
        return None
    if any(c in raw_name for c in ":\r\n") or any(c in raw_value for c in "\r\n"):
        raise ValueError("Header name or value contains invalid characters.")
    if not raw_name or any(ch.isspace() for ch in raw_name):
        raise ValueError("Header name contains invalid characters.")
    return f"{raw_name}: {raw_value}"


def save_credentials(form: Mapping[str, str]) -> None:
    changes = envfile.credential_changes(form)
    if changes:
        envfile.update_ui_env(changes)


def save_proxy(form: Mapping[str, str]) -> None:
    changes = envfile.proxy_changes(envfile.read_ui_env(), form)
    merged = envfile.preview_merged(changes)
    # Reject a contradictory result before writing, so a bad form cannot
    # leave the file half-applied. The error names variables, not secrets.
    parse_proxy_config(merged)
    envfile.update_ui_env(changes)
