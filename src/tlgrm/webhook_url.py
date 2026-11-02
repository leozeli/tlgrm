"""One webhook URL check for foreground listen, `webhook set`, and the daemon.

Local and private hosts are allowed — a personal receiver often lives on
localhost or a LAN address. Anything that is not http(s), or that could break
a systemd ExecStart line, is rejected.
"""

from urllib.parse import urlparse


def validate_webhook_url(url: str) -> None:
    """Reject URLs that are not plain http(s).

    Also rejects whitespace and control characters. Daemon install embeds the
    URL in a unit file; the same rule is applied on every other path so a
    `file:`, `ftp:`, `gopher:`, or `data:` URL cannot slip through `listen`
    or `webhook set`.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid webhook URL (must be http/https): {url!r}")
    if any(c.isspace() or ord(c) < 32 for c in url):
        raise ValueError(
            "Webhook URL must not contain whitespace or control characters"
        )
