"""Shared incoming-message pipeline: filter, build payload, download+transcribe,
forward. Used by the standalone `tlgrm listen` and the server's per-account
listeners so the two never diverge."""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from telethon import TelegramClient, utils

from .config import DOWNLOADS_DIR
from .core import serialize
from .stt import transcribe_audio
from .webhook_url import validate_webhook_url

logger = logging.getLogger("tlgrm-listen")


async def forward_webhook(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    retries: int = 3,
) -> None:
    try:
        validate_webhook_url(url)
    except ValueError as e:
        logger.error(f"Refusing webhook URL: {e}")
        return
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, json=payload, headers=headers, timeout=10.0
                )
            if 200 <= resp.status_code < 300:
                logger.info(f"Webhook forwarded ({resp.status_code}).")
                return
            logger.error(f"Webhook failed {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(
                f"Webhook POST to {url} failed (attempt {attempt}/{retries}): {e}"
            )
        if attempt < retries:
            await asyncio.sleep(2 ** (attempt - 1))


def parse_headers(header_list: list[str] | None) -> dict[str, str]:
    """Turn ['Name: Value', ...] into a dict {Name: Value}."""
    out: dict[str, str] = {}
    for h in header_list or []:
        if ":" in h:
            k, v = h.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _split_tokens(values: list[str] | None) -> list[str]:
    tokens: list[str] = []
    for value in values or []:
        tokens.extend(t.strip() for t in str(value).split(",") if t.strip())
    return tokens


async def _resolve_filters(
    client: TelegramClient, tokens: list[str]
) -> tuple[set[int], set[str]]:
    ids: set[int] = set()
    names: set[str] = set()
    for token in tokens:
        try:
            entity = await client.get_entity(token)
            ids.add(utils.get_peer_id(entity))
            uname = getattr(entity, "username", None)
            if uname:
                names.add(uname.lower())
        except Exception as e:
            logger.warning(
                f"Could not resolve filter target {token!r} ({e}); matching literally."
            )
            stripped = token.lstrip("@")
            if stripped.lstrip("-").isdigit():
                ids.add(int(stripped))
            else:
                names.add(stripped.lower())
    return ids, names


def _matches(
    ids: set[int],
    names: set[str],
    chat_id: int | None,
    sender_id: int | None,
    chat_username: str | None,
    sender_username: str | None,
) -> bool:
    if chat_id in ids or sender_id in ids:
        return True
    return any(u and u.lower() in names for u in (chat_username, sender_username))


def _parse_window(text: str) -> tuple[int, int] | None:
    """Parse 'HH:MM-HH:MM' into (start_minute, end_minute), or None if invalid."""
    try:
        a, b = text.split("-")
        ah, am = (int(x) for x in a.split(":"))
        bh, bm = (int(x) for x in b.split(":"))
        if not (0 <= ah < 24 and 0 <= am < 60 and 0 <= bh < 24 and 0 <= bm < 60):
            return None
        return (ah * 60 + am, bh * 60 + bm)
    except Exception:
        return None


def _within_window(minutes: int, window: tuple[int, int]) -> bool:
    start, end = window
    if start == end:
        return True
    if start < end:
        return start <= minutes < end
    return minutes >= start or minutes < end  # overnight wrap


def _now_minutes() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


class ListenState:
    """Live, swappable listening config for one account."""

    def __init__(self) -> None:
        self.enabled = False
        self.webhook_url: str | None = None
        self.headers: dict[str, str] = {}
        self.mode = "block"  # allow | block
        self.ids: set[int] = set()
        self.names: set[str] = set()
        self.window: tuple[int, int] | None = None


def _passes(
    state: ListenState,
    chat_id: int | None,
    sender_id: int | None,
    cu: str | None,
    su: str | None,
) -> bool:
    matched = _matches(state.ids, state.names, chat_id, sender_id, cu, su)
    return matched if state.mode == "allow" else not matched


def _should_transcribe(media_type: str | None) -> bool:
    from .stt.settings import is_enabled

    return media_type in ("voice", "audio") and is_enabled()


async def build_payload(
    event: Any, account: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the webhook JSON payload for an incoming message (incl. media
    download + transcription). `account` is {"name","id"} or None (standalone)."""
    msg = event.message
    chat = await event.get_chat()
    sender = await event.get_sender()
    sender_info = serialize.serialize_sender(sender)
    chat_type = (
        "user"
        if event.is_private
        else "group"
        if event.is_group
        else "channel"
        if event.is_channel
        else "unknown"
    )
    chat_info = serialize.serialize_chat(chat, chat_type)
    chat_info["id"] = event.chat_id

    media: dict[str, Any] = {
        "present": False,
        "type": None,
        "local_path": None,
        "transcription": None,
        "self_destruct": False,
    }
    if msg.media:
        media["present"] = True
        media["type"] = serialize.media_type(msg)
        if serialize.is_self_destruct(msg):
            media["self_destruct"] = True
        else:
            try:
                path = await msg.download_media(file=DOWNLOADS_DIR)
                if path:
                    media["local_path"] = os.path.abspath(path)
                    if _should_transcribe(media["type"]):
                        text = transcribe_audio(media["local_path"])
                        if text:
                            media["transcription"] = text
            except Exception as ex:
                logger.error(f"Media download/transcribe failed: {ex}")

    payload: dict[str, Any] = {
        "event": "new_message",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": {
            "id": msg.id,
            "text": msg.text or "",
            "date": msg.date.isoformat() if msg.date else "",
            "reply_to_msg_id": msg.reply_to_msg_id,
        },
        "chat": chat_info,
        "sender": sender_info,
        "media": media,
    }
    if account is not None:
        payload["account"] = account
    return payload


async def process_event(
    event: Any,
    state: ListenState,
    account: dict[str, Any] | None = None,
    pending: set["asyncio.Task[None]"] | None = None,
    emit_console: bool = False,
) -> None:
    """Filter, build, and forward one incoming message according to `state`."""
    chat = await event.get_chat()
    sender = await event.get_sender()
    cu = getattr(chat, "username", None)
    su = getattr(sender, "username", None)
    if state.window is not None and not _within_window(_now_minutes(), state.window):
        return
    if not _passes(state, event.chat_id, event.sender_id, cu, su):
        return
    payload = await build_payload(event, account)
    if emit_console or not state.webhook_url:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    if state.webhook_url:
        loop = asyncio.get_running_loop()
        task = loop.create_task(
            forward_webhook(state.webhook_url, payload, state.headers)
        )
        if pending is not None:
            pending.add(task)
            task.add_done_callback(pending.discard)
