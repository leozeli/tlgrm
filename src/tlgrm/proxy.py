"""Optional SOCKS / MTProxy settings for the Telethon client.

Nothing is configured unless the env vars (or the UI env file) say so. The
default client constructor stays a direct connection. This is a thin hook
over Telethon's existing proxy argument — not a separate proxy stack.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .core.errors import TlgrmError

_PROXY_TYPES = frozenset({"socks5", "socks4", "http"})


class ProxyConfigError(TlgrmError):
    """SOCKS / MTProxy env vars are incomplete or contradictory.

    Messages name the variables that are missing. They do not echo secrets.
    """


@dataclass(frozen=True)
class ProxyPlan:
    mode: str  # none | socks | mtproxy
    kind: str | None = None
    host: str | None = None
    port: int | None = None
    secret: str | None = field(default=None, repr=False)


def parse_proxy_config(env: Mapping[str, str]) -> ProxyPlan:
    """Pure parse of proxy variables. Raises ProxyConfigError when incomplete."""

    def grab(key: str) -> str:
        return (env.get(key) or "").strip()

    socks_host = grab("TG_PROXY_HOST")
    socks_port = grab("TG_PROXY_PORT")
    socks_type = grab("TG_PROXY_TYPE")
    mt_host = grab("TG_MTPROXY_HOST")
    mt_port = grab("TG_MTPROXY_PORT")
    mt_secret = grab("TG_MTPROXY_SECRET")

    socks_any = bool(socks_host or socks_port or socks_type)
    mt_any = bool(mt_host or mt_port or mt_secret)
    if socks_any and mt_any:
        raise ProxyConfigError(
            "Both SOCKS (TG_PROXY_*) and MTProxy (TG_MTPROXY_*) are set. "
            "Configure only one."
        )
    if not socks_any and not mt_any:
        return ProxyPlan(mode="none")
    if socks_any:
        if not socks_host or not socks_port:
            raise ProxyConfigError(
                "SOCKS proxy needs both TG_PROXY_HOST and TG_PROXY_PORT."
            )
        kind = (socks_type or "socks5").lower()
        if kind not in _PROXY_TYPES:
            raise ProxyConfigError("TG_PROXY_TYPE must be socks5, socks4, or http.")
        return ProxyPlan(
            mode="socks",
            kind=kind,
            host=socks_host,
            port=_port("TG_PROXY_PORT", socks_port),
        )
    if not mt_host or not mt_port or not mt_secret:
        raise ProxyConfigError(
            "MTProxy needs TG_MTPROXY_HOST, TG_MTPROXY_PORT, and TG_MTPROXY_SECRET."
        )
    return ProxyPlan(
        mode="mtproxy",
        host=mt_host,
        port=_port("TG_MTPROXY_PORT", mt_port),
        secret=mt_secret,
    )


def socks_backend_available() -> bool:
    """True when Telethon will be able to open a SOCKS/HTTP proxy socket."""
    try:
        import python_socks  # noqa: F401
    except ImportError:
        pass
    else:
        return True
    try:
        import socks  # noqa: F401  PySocks
    except ImportError:
        return False
    return True


def telethon_proxy_kwargs() -> dict[str, Any]:
    """Keyword args for ``TelegramClient``. Empty when no proxy is configured.

    Loads the UI env file first (without overriding exported variables).
    """
    from .envfile import inject_file_env

    inject_file_env()
    plan = parse_proxy_config(os.environ)
    if plan.mode == "none":
        return {}
    if plan.mode == "socks":
        if not socks_backend_available():
            raise ProxyConfigError(
                "A SOCKS/HTTP proxy is configured but neither python-socks nor "
                "PySocks is installed. Install one with: "
                "pip install 'python-socks[asyncio]'"
            )
        return {"proxy": (plan.kind or "socks5", plan.host, plan.port)}
    from telethon import connection

    return {
        "connection": connection.ConnectionTcpMTProxyRandomizedIntermediate,
        "proxy": (plan.host, plan.port, plan.secret),
    }


def _port(name: str, raw: str) -> int:
    if not raw.isdigit():
        raise ProxyConfigError(f"{name} must be an integer port between 1 and 65535.")
    number = int(raw)
    if number < 1 or number > 65535:
        raise ProxyConfigError(f"{name} must be an integer port between 1 and 65535.")
    return number
