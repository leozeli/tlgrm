"""Small helpers that keep secrets out of the UI, logs, and CLI output."""

import ipaddress
from typing import Any
from urllib.parse import parse_qsl, urlparse

from .core.serialize import mask_phone


def redact_header(header: str) -> str:
    """Show a header name and hide its value (it may be a bearer token)."""
    if ":" in header:
        return f"{header.split(':', 1)[0].strip()}: [REDACTED]"
    return header


def redact_secrets(text: str, secrets: list[str] | None = None) -> str:
    """Replace caller-supplied secret strings. Short tokens are left alone so
    a port or a single word in an error is not blanked out."""
    cleaned = text
    for secret in secrets or []:
        if secret and len(secret) >= 6 and secret in cleaned:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def mask_webhook_url(url: str | None) -> str | None:
    """Show scheme, host, and path. Drop userinfo and query values.

    An unparseable value becomes a fixed placeholder so a secret embedded in
    a bad URL is not echoed back.
    """
    if url is None:
        return None
    raw = str(url).strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        return "[invalid webhook url]"
    if ":" in host:
        host = f"[{host}]"
    netloc = host
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    query = ""
    if parsed.query:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if pairs:
            query = "?" + "&".join(f"{key}=***" for key, _value in pairs)
        else:
            query = "?***"
    return f"{parsed.scheme}://{netloc}{parsed.path or ''}{query}"


def filter_summary(flt: dict[str, Any] | None) -> str:
    """One line describing a listen or write filter."""
    data = flt or {}
    mode = str(data.get("mode") or "block")
    items = [str(item) for item in (data.get("list") or []) if str(item)]
    if not items and mode == "block":
        return "block (empty) — no extra restriction"
    if not items and mode == "allow":
        return "allow (empty) — nothing matches"
    head = ", ".join(items[:6])
    extra = len(items) - 6
    if extra > 0:
        head = f"{head} +{extra}"
    return f"{mode}: {head}"


def present_whoami(data: Any) -> dict[str, Any]:
    """Identity safe to render. The phone number is masked; the raw value is
    not copied onto the result."""
    if not isinstance(data, dict):
        return {
            "id": None,
            "first_name": "",
            "last_name": "",
            "username": "",
            "phone_masked": "",
        }
    return {
        "id": data.get("id"),
        "first_name": data.get("first_name") or "",
        "last_name": data.get("last_name") or "",
        "username": data.get("username") or "",
        "phone_masked": mask_phone(data.get("phone")),
    }


def is_loopback_host(host: str) -> bool:
    """True for localhost and loopback IPs. ``0.0.0.0`` / ``::`` are not."""
    name = (host or "").strip().lower().strip("[]")
    if name in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def bind_warning(host: str) -> str | None:
    """Warning banner when the dashboard is not bound to loopback."""
    if is_loopback_host(host):
        return None
    return (
        "Bound outside localhost. Anyone who can reach this address can use "
        "your Telegram account. Prefer 127.0.0.1."
    )
