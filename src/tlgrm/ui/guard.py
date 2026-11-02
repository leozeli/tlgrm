"""Request checks for the local dashboard.

Browsers send ``Origin`` and ``Sec-Fetch-Site`` on cross-site form posts.
A matching CSRF cookie is checked separately by the app, after the body is read.
"""

import secrets
from collections.abc import Mapping
from urllib.parse import urlparse

from ..redact import is_loopback_host


def tokens_match(expected: str, got: str) -> bool:
    if not expected or not got or len(expected) != len(got):
        return False
    return secrets.compare_digest(expected, got)


def origin_allowed(origin: str, bind_host: str, port: int) -> bool:
    """Allow same-dashboard origins.

    A loopback bind accepts any loopback origin on this port (so ``localhost``
    and ``127.0.0.1`` both work). Any other bind accepts only an origin whose
    host equals the bind host — a browser cross-site post carries the
    attacker's origin, which fails this check.
    """
    parsed = urlparse(origin)
    if parsed.scheme != "http":
        return False
    if parsed.port not in (None, port):
        return False
    origin_host = (parsed.hostname or "").lower()
    if is_loopback_host(bind_host):
        return is_loopback_host(origin_host)
    return origin_host == bind_host.strip().lower().strip("[]")


def post_is_allowed(headers: Mapping[str, str], bind_host: str, port: int) -> bool:
    fetch_site = (headers.get("sec-fetch-site") or "").lower()
    if fetch_site in {"cross-site", "cross-origin"}:
        return False
    origin = headers.get("origin")
    if not origin:
        return True
    return origin_allowed(origin, bind_host, port)
