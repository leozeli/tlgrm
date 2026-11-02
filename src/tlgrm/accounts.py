# src/tlgrm/accounts.py
"""Account registry and the persisted config store (~/.tlgrm/config.toml).

An account is a named Telegram login with its own session file under
~/.tlgrm/accounts/<name>.session. This module owns reading/writing the config
file and resolving which account a command targets. It writes the whole config
back on every change, so it deliberately preserves unrelated sections (e.g.
[stt]) by carrying them through the in-memory dict.
"""

import os
import re
from typing import Any

from .core.errors import TlgrmError

# Account names become a single path segment under ~/.tlgrm/accounts.
# Letters, digits, and a small bit of punctuation only — no separators, and
# no ".." — so a name cannot climb out of that directory.
_ACCOUNT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_account_name(name: str) -> str:
    """Reject path-traversal and other unsafe account names.

    Allowed: 1–64 characters from letters, digits, ``.``, ``_``, and ``-``,
    starting with a letter or digit. A name containing ``..`` is rejected
    even though the rest of the character set would allow it.
    """
    if not isinstance(name, str) or not _ACCOUNT_NAME.fullmatch(name) or ".." in name:
        raise TlgrmError(
            f"Invalid account name {name!r}. Use 1-64 characters from "
            "letters, digits, '.', '_' or '-', starting with a letter or digit, "
            "and do not include '..' or path separators."
        )
    return name


def _config_path() -> str:
    return os.getenv("TG_CONFIG_PATH", os.path.expanduser("~/.tlgrm/config.toml"))


def _accounts_dir() -> str:
    return os.path.expanduser("~/.tlgrm/accounts")


def _config_path_text() -> str:
    """Raw file text (test helper; '' if the file does not exist)."""
    path = _config_path()
    return open(path).read() if os.path.exists(path) else ""


def _strip_none(value: Any) -> Any:
    """Recursively drop keys whose value is None (TOML cannot represent null)."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    return value


def load_config() -> dict[str, Any]:
    path = _config_path()
    if not os.path.exists(path):
        return {"default_account": None, "accounts": {}}
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib
    with open(path, "rb") as f:
        data: dict[str, Any] = tomllib.load(f)
    data.setdefault("accounts", {})
    data.setdefault("default_account", None)
    return data


def save_config(data: dict[str, Any]) -> None:
    import tomli_w

    path = _config_path()
    os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(_strip_none(data), f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)  # don't leave a stale temp file behind
        raise
    os.chmod(path, 0o600)


def account_session_path(name: str) -> str:
    """Session file for `name`, resolved and confined to the accounts directory.

    The accounts directory is created owner-only (0700) before the path is
    returned, so a login cannot write the session into a directory that was
    just created world-readable. The resolved path must stay directly inside
    that directory — a symlinked session file pointing elsewhere is refused.
    """
    validate_account_name(name)
    base = os.path.realpath(_accounts_dir())
    os.makedirs(base, mode=0o700, exist_ok=True)
    os.chmod(base, 0o700)
    filename = f"{name}.session"
    candidate = os.path.join(base, filename)
    resolved = os.path.realpath(candidate)
    if os.path.dirname(resolved) != base or os.path.basename(resolved) != filename:
        raise TlgrmError(
            f"Account session path escapes the accounts directory: {name!r}."
        )
    return candidate


def add_account(name: str) -> None:
    validate_account_name(name)
    cfg = load_config()
    cfg["accounts"].setdefault(name, {})
    if not cfg.get("default_account"):
        cfg["default_account"] = name
    save_config(cfg)
    os.makedirs(_accounts_dir(), mode=0o700, exist_ok=True)


def set_default(name: str) -> None:
    cfg = load_config()
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}. See 'tlgrm account list'.")
    cfg["default_account"] = name
    save_config(cfg)


def rename_account(old: str, new: str) -> None:
    validate_account_name(new)
    cfg = load_config()
    if old not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {old!r}.")
    if new in cfg["accounts"]:
        raise TlgrmError(f"Account already exists: {new!r}.")
    # Resolve both paths before rewriting config so a containment failure
    # cannot leave the registry pointing at a session that was not moved.
    src, dst = account_session_path(old), account_session_path(new)
    cfg["accounts"][new] = cfg["accounts"].pop(old)
    if cfg.get("default_account") == old:
        cfg["default_account"] = new
    save_config(cfg)
    if os.path.exists(src):
        os.replace(src, dst)


def remove_account(name: str) -> None:
    cfg = load_config()
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}.")
    del cfg["accounts"][name]
    if cfg.get("default_account") == name:
        cfg["default_account"] = next(iter(cfg["accounts"]), None)
    save_config(cfg)
    sess = account_session_path(name)
    if os.path.exists(sess):
        os.remove(sess)


def resolve_account(name: str | None = None) -> str:
    cfg = load_config()
    chosen = name or cfg.get("default_account")
    if not chosen:
        raise TlgrmError("No account configured. Run 'tlgrm account add' to log in.")
    if chosen not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {chosen!r}. See 'tlgrm account list'.")
    return chosen


def _legacy_session_path() -> str:
    return os.path.expanduser("~/.tlgrm/tg_session.session")


def migrate_legacy_session() -> bool:
    """Move a pre-0.3.0 single session to account 'default'. Returns True if it
    migrated, False if there was nothing to do."""
    legacy = _legacy_session_path()
    cfg = load_config()
    if not os.path.exists(legacy) or "default" in cfg["accounts"]:
        return False
    os.makedirs(_accounts_dir(), mode=0o700, exist_ok=True)
    os.replace(legacy, account_session_path("default"))
    cfg["accounts"].setdefault("default", {})
    if not cfg.get("default_account"):
        cfg["default_account"] = "default"
    save_config(cfg)
    return True


def session_path_for(account: str | None = None, must_exist: bool = True) -> str:
    """Resolve the session base path for a command.

    For normal commands a TG_SESSION_PATH / --session override still wins
    (deprecated low-level escape hatch). During login (`must_exist=False`) the
    override is ignored: the new session must land at the named account's path so
    it matches where the account is registered.
    """
    if not must_exist:
        return account_session_path(account or "default")
    override = os.getenv("TG_SESSION_PATH")
    if override:
        return override
    return account_session_path(resolve_account(account))


def _account(cfg: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}. See 'tlgrm account list'.")
    account: dict[str, Any] = cfg["accounts"][name]
    return account


def filter_config(name: str, domain: str) -> dict[str, Any]:
    """Normalized {mode, list} for a filter domain ('listen' or 'write')."""
    acc = _account(load_config(), name)
    flt = (acc.get("filter") or {}).get(domain) or {}
    return {"mode": flt.get("mode", "block"), "list": list(flt.get("list", []))}


def listen_config(name: str) -> dict[str, Any]:
    """Normalized per-account listen settings (with defaults applied)."""
    acc = _account(load_config(), name)
    return {
        "enabled": bool(acc.get("listen_enabled", False)),
        "webhook_url": acc.get("webhook_url"),
        "webhook_headers": list(acc.get("webhook_headers", [])),
        "filter": filter_config(name, "listen"),
        "window": acc.get("listen_window"),
    }


def set_listen_window(name: str, window: str) -> None:
    cfg = load_config()
    _account(cfg, name)["listen_window"] = window
    save_config(cfg)


def clear_listen_window(name: str) -> None:
    cfg = load_config()
    _account(cfg, name).pop("listen_window", None)
    save_config(cfg)


def set_listen_enabled(name: str, enabled: bool) -> None:
    cfg = load_config()
    _account(cfg, name)["listen_enabled"] = bool(enabled)
    save_config(cfg)


def set_webhook(name: str, url: str, headers: list[str] | None = None) -> None:
    from .webhook_url import validate_webhook_url

    try:
        validate_webhook_url(url)
    except ValueError as e:
        raise TlgrmError(str(e)) from e
    cfg = load_config()
    acc = _account(cfg, name)
    acc["webhook_url"] = url
    acc["webhook_headers"] = list(headers or [])
    save_config(cfg)


def clear_webhook(name: str) -> None:
    cfg = load_config()
    acc = _account(cfg, name)
    acc.pop("webhook_url", None)
    acc.pop("webhook_headers", None)
    save_config(cfg)


def _filter_node(acc: dict[str, Any], domain: str) -> dict[str, Any]:
    node: dict[str, Any] = acc.setdefault("filter", {}).setdefault(domain, {})
    return node


def filter_set_mode(name: str, domain: str, mode: str) -> None:
    if mode not in ("allow", "block"):
        raise TlgrmError(f"Filter mode must be 'allow' or 'block', got {mode!r}.")
    cfg = load_config()
    _filter_node(_account(cfg, name), domain)["mode"] = mode
    save_config(cfg)


def filter_add(name: str, domain: str, tokens: list[str]) -> None:
    cfg = load_config()
    node = _filter_node(_account(cfg, name), domain)
    lst: list[str] = node.setdefault("list", [])
    for t in tokens:
        if t and t not in lst:
            lst.append(t)
    save_config(cfg)


def filter_remove(name: str, domain: str, tokens: list[str]) -> None:
    cfg = load_config()
    node = _filter_node(_account(cfg, name), domain)
    node["list"] = [x for x in node.get("list", []) if x not in set(tokens)]
    save_config(cfg)


def filter_clear(name: str, domain: str) -> None:
    cfg = load_config()
    _filter_node(_account(cfg, name), domain)["list"] = []
    save_config(cfg)
