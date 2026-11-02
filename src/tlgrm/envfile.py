"""Owner-only env file for settings the local UI can edit.

Process environment wins over the file. The file is an allowlist — it never
loads arbitrary variables (no ``LD_PRELOAD``, no session paths). Secret values
are stored but helpers that build a public view omit them.
"""

import os
from collections.abc import Mapping
from typing import Any

ALLOWED_KEYS: tuple[str, ...] = (
    "TG_API_ID",
    "TG_API_HASH",
    "TG_PROXY_TYPE",
    "TG_PROXY_HOST",
    "TG_PROXY_PORT",
    "TG_MTPROXY_HOST",
    "TG_MTPROXY_PORT",
    "TG_MTPROXY_SECRET",
)

SECRET_KEYS = frozenset({"TG_API_HASH", "TG_MTPROXY_SECRET"})

# Snapshot of allowlisted variables that were already exported when this
# process first looked. Those keep winning over the file for the lifetime
# of the process. Tests reset this.
_shell: dict[str, str] | None = None
_injected: set[str] = set()


def reset_for_tests() -> None:
    """Drop the captured shell snapshot so a test can start clean."""
    global _shell
    _shell = None
    _injected.clear()


def ui_env_path() -> str:
    override = os.getenv("TG_UI_ENV")
    if override:
        return os.path.expanduser(override)
    return os.path.expanduser("~/.tlgrm/ui.env")


def note_shell_env() -> dict[str, str]:
    """Allowlisted variables exported before the file was applied."""
    global _shell
    if _shell is None:
        _shell = {
            key: os.environ.get(key, "").strip()
            for key in ALLOWED_KEYS
            if os.environ.get(key, "").strip()
        }
    return _shell


def parse_env_text(text: str) -> dict[str, str]:
    """Parse allowlisted ``KEY=VALUE`` lines. Unknown keys and unsafe values
    are skipped so a hand-edited file cannot inject extra variables."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in ALLOWED_KEYS or not _safe_value(value):
            continue
        out[key] = value
    return out


def read_ui_env() -> dict[str, str]:
    path = ui_env_path()
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}
    return parse_env_text(text)


def inject_file_env() -> None:
    """Copy file values into ``os.environ`` for keys the shell did not set.

    Safe to call more than once. Never overrides a variable that was already
    exported, and never logs values.
    """
    shell = note_shell_env()
    for key, value in read_ui_env().items():
        if key in shell or not value:
            continue
        os.environ[key] = value
        _injected.add(key)


def update_ui_env(changes: Mapping[str, str | None]) -> None:
    """Merge ``changes`` into the env file. ``None`` deletes a key.

    Values that fail the allowlist check raise ``ValueError`` whose message
    does not include the rejected value. Shell-exported keys stay in the
    process environment; the file is still updated for other processes.
    """
    current = read_ui_env()
    shell = note_shell_env()
    for key, value in changes.items():
        if key not in ALLOWED_KEYS:
            raise ValueError(f"Unsupported setting {key}.")
        if value is None:
            current.pop(key, None)
            if key not in shell:
                os.environ.pop(key, None)
                _injected.discard(key)
            continue
        checked = _require_value(key, value)
        current[key] = checked
        if key not in shell:
            os.environ[key] = checked
            _injected.add(key)
    _write_ui_env(current)


def effective_map() -> dict[str, str]:
    """Allowlisted values a new process would see (shell, else file)."""
    shell = note_shell_env()
    file_vals = read_ui_env()
    merged: dict[str, str] = {}
    for key in ALLOWED_KEYS:
        shell_v = (shell.get(key) or "").strip()
        file_v = (file_vals.get(key) or "").strip()
        if shell_v:
            merged[key] = shell_v
        elif file_v:
            merged[key] = file_v
    return merged


def value_source(key: str) -> str:
    """``environment``, ``file``, or ``unset`` — no value attached."""
    shell = note_shell_env()
    if (shell.get(key) or "").strip():
        return "environment"
    if (read_ui_env().get(key) or "").strip():
        return "file"
    return "unset"


def preview_merged(changes: Mapping[str, str | None]) -> dict[str, str]:
    """Effective map as it would look after ``changes`` are written."""
    shell = note_shell_env()
    file_vals = read_ui_env()
    for key, value in changes.items():
        if key not in ALLOWED_KEYS:
            continue
        if value is None:
            file_vals.pop(key, None)
        else:
            file_vals[key] = value
    merged: dict[str, str] = {}
    for key in ALLOWED_KEYS:
        shell_v = (shell.get(key) or "").strip()
        file_v = (file_vals.get(key) or "").strip()
        if shell_v:
            merged[key] = shell_v
        elif file_v:
            merged[key] = file_v
    return merged


def credential_changes(form: Mapping[str, str]) -> dict[str, str | None]:
    """Blank fields mean 'leave unchanged'. Errors omit the submitted value."""
    changes: dict[str, str | None] = {}
    api_id = (form.get("api_id") or "").strip()
    api_hash = (form.get("api_hash") or "").strip()
    if api_id:
        if not api_id.isdigit():
            raise ValueError("TG_API_ID must be an integer.")
        changes["TG_API_ID"] = api_id
    if api_hash:
        if not _safe_value(api_hash):
            raise ValueError("TG_API_HASH is not a valid value.")
        changes["TG_API_HASH"] = api_hash
    return changes


def proxy_changes(
    current: Mapping[str, str], form: Mapping[str, str]
) -> dict[str, str | None]:
    """Translate the proxy form into file updates.

    A blank MTProxy secret keeps the stored secret. ``clear_mtproxy_secret=1``
    drops it. Empty SOCKS host and port clear the SOCKS keys. ``current`` is
    the file (not the shell), so a saved secret can be kept without echoing it.
    """
    host = (form.get("proxy_host") or "").strip()
    port = (form.get("proxy_port") or "").strip()
    kind = (form.get("proxy_type") or "").strip().lower()
    mt_host = (form.get("mtproxy_host") or "").strip()
    mt_port = (form.get("mtproxy_port") or "").strip()
    secret = (form.get("mtproxy_secret") or "").strip()
    clear_secret = (form.get("clear_mtproxy_secret") or "") == "1"

    changes: dict[str, str | None] = {}
    if host or port:
        if not host or not port:
            raise ValueError("SOCKS proxy needs both host and port.")
        if kind and kind not in {"socks5", "socks4", "http"}:
            raise ValueError("Proxy type must be socks5, socks4, or http.")
        changes["TG_PROXY_HOST"] = host
        changes["TG_PROXY_PORT"] = port
        changes["TG_PROXY_TYPE"] = kind or "socks5"
    else:
        changes["TG_PROXY_HOST"] = None
        changes["TG_PROXY_PORT"] = None
        changes["TG_PROXY_TYPE"] = None

    stored_secret = (current.get("TG_MTPROXY_SECRET") or "").strip()
    if clear_secret:
        new_secret = ""
    elif secret:
        if not _safe_value(secret):
            raise ValueError("MTProxy secret is not a valid value.")
        new_secret = secret
    else:
        new_secret = stored_secret

    if mt_host or mt_port or new_secret:
        if not mt_host or not mt_port or not new_secret:
            raise ValueError(
                "MTProxy needs host, port, and a secret "
                "(enter one or keep the saved secret)."
            )
        changes["TG_MTPROXY_HOST"] = mt_host
        changes["TG_MTPROXY_PORT"] = mt_port
        changes["TG_MTPROXY_SECRET"] = new_secret
    else:
        changes["TG_MTPROXY_HOST"] = None
        changes["TG_MTPROXY_PORT"] = None
        changes["TG_MTPROXY_SECRET"] = None
    return changes


def public_settings() -> dict[str, Any]:
    """Settings for display. Secret values are booleans, never strings."""
    from .proxy import ProxyConfigError, parse_proxy_config

    shell = note_shell_env()
    file_vals = read_ui_env()
    merged = effective_map()
    sources = {key: value_source(key) for key in ALLOWED_KEYS}
    mode = "none"
    error: str | None = None
    try:
        mode = parse_proxy_config(merged).mode
    except ProxyConfigError as exc:
        error = str(exc)
    overrides = False
    for key in ALLOWED_KEYS:
        shell_v = (shell.get(key) or "").strip()
        file_v = (file_vals.get(key) or "").strip()
        if shell_v and file_v and shell_v != file_v:
            overrides = True
            break
    return {
        "api_id_set": bool(merged.get("TG_API_ID")),
        "api_hash_set": bool(merged.get("TG_API_HASH")),
        "api_id_source": sources["TG_API_ID"],
        "api_hash_source": sources["TG_API_HASH"],
        "proxy_type": merged.get("TG_PROXY_TYPE") or "socks5",
        "proxy_host": merged.get("TG_PROXY_HOST", ""),
        "proxy_port": merged.get("TG_PROXY_PORT", ""),
        "proxy_source": sources["TG_PROXY_HOST"],
        "mtproxy_host": merged.get("TG_MTPROXY_HOST", ""),
        "mtproxy_port": merged.get("TG_MTPROXY_PORT", ""),
        "mtproxy_secret_set": bool(merged.get("TG_MTPROXY_SECRET")),
        "mtproxy_source": sources["TG_MTPROXY_SECRET"],
        "proxy_mode": mode,
        "proxy_error": error,
        "env_overrides_file": overrides,
    }


def _safe_value(value: str) -> bool:
    if not value or len(value) > 512:
        return False
    if any(c in value for c in "\r\n\x00"):
        return False
    return not any(ch.isspace() for ch in value)


def _require_value(key: str, value: str) -> str:
    if not _safe_value(value):
        raise ValueError(f"Invalid value for {key}.")
    return value


def _write_ui_env(data: Mapping[str, str]) -> None:
    path = ui_env_path()
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, mode=0o700, exist_ok=True)
    home = os.path.realpath(os.path.expanduser("~/.tlgrm"))
    if os.path.realpath(parent) == home:
        os.chmod(parent, 0o700)
    lines = ["# tlgrm local settings. Owner-only. Do not commit or share."]
    for key in ALLOWED_KEYS:
        value = data.get(key)
        if value:
            lines.append(f"{key}={value}")
    payload = ("\n".join(lines) + "\n").encode()
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    os.chmod(path, 0o600)
