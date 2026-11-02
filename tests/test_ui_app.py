import logging
import re

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from starlette.testclient import TestClient  # noqa: E402

from tlgrm import accounts, ipc  # noqa: E402
from tlgrm.ui import bridge  # noqa: E402
from tlgrm.ui.app import create_app  # noqa: E402
from tlgrm.ui.server import missing_ui_deps  # noqa: E402


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def _client(**kwargs):
    app = create_app(ensure_server=False, **kwargs)
    return TestClient(app)


def test_ui_extra_import_names_are_known():
    # Installed in this environment; the helper still returns a list.
    assert isinstance(missing_ui_deps(), list)


def test_status_masks_phone_and_loopback_has_no_warning(monkeypatch, tmp_home):
    async def fake(cmd, account, args=None):
        assert account == "work"
        if cmd == "whoami":
            return {
                "id": 7,
                "first_name": "Ada",
                "last_name": "Lovelace",
                "username": "ada",
                "phone": "+15551234567",
            }
        raise bridge.BridgeError("unexpected")

    monkeypatch.setattr(bridge, "call_cmd", fake)
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    page = _client().get("/")
    assert page.status_code == 200
    assert "Ada" in page.text
    assert "+155****4567" in page.text
    assert "+15551234567" not in page.text
    assert "Running" in page.text
    assert "Bound outside localhost" not in page.text
    assert page.cookies.get("tlgrm_csrf")
    client = _client()
    assert client.get("/static/app.css").status_code == 200


def test_nonlocal_bind_shows_warning():
    page = _client(host="0.0.0.0").get("/settings")
    assert page.status_code == 200
    assert "Bound outside localhost" in page.text


def test_csrf_and_origin_and_secret_not_rendered(monkeypatch, tmp_home):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    from tlgrm import envfile

    envfile.reset_for_tests()
    client = _client()
    page = client.get("/settings")
    token = re.search(r'name="csrf" value="([^"]+)"', page.text)
    assert token
    csrf = token.group(1)
    rejected = client.post(
        "/settings",
        data={
            "csrf": "nope",
            "action": "save_credentials",
            "api_hash": "deadbeefsecret",
        },
    )
    assert rejected.status_code == 403
    cross = client.post(
        "/settings",
        data={"csrf": csrf, "action": "save_credentials", "api_hash": "deadbeefsecret"},
        headers={"origin": "http://evil.example:8765"},
    )
    assert cross.status_code == 403
    saved = client.post(
        "/settings",
        data={"csrf": csrf, "action": "save_credentials", "api_hash": "deadbeefsecret"},
    )
    assert saved.status_code == 200
    assert "deadbeefsecret" not in saved.text
    assert "Credentials saved" in saved.text
    assert envfile.read_ui_env()["TG_API_HASH"] == "deadbeefsecret"


def test_chats_history_and_send(monkeypatch, tmp_home, caplog):
    async def fake(cmd, account, args=None):
        if cmd == "chats":
            return [
                {
                    "id": 9,
                    "name": "Ada",
                    "username": "ada",
                    "type": "user",
                    "unread_count": 2,
                }
            ]
        if cmd == "history":
            assert args["target"] == "9"
            return [
                {
                    "id": 3,
                    "date": "2026-01-01T00:00:00+00:00",
                    "sender_id": 7,
                    "sender_name": "Ada",
                    "text": "hello there",
                    "media_type": None,
                }
            ]
        if cmd == "whoami":
            return {"id": 7, "first_name": "Me", "username": "me", "phone": ""}
        if cmd == "send":
            assert args["text"] == "ping"
            return {"success": True, "message_id": 4}
        raise bridge.BridgeError("nope")

    monkeypatch.setattr(bridge, "call_cmd", fake)
    client = _client()
    chats = client.get("/chats")
    assert chats.status_code == 200
    assert "Ada" in chats.text
    assert "/history?target=9" in chats.text
    history = client.get("/history?target=9")
    assert "hello there" in history.text
    caplog.set_level(logging.INFO, logger="tlgrm.ui")
    page = client.get("/send")
    token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    sent = client.post(
        "/send",
        data={
            "csrf": token,
            "account": "work",
            "target_manual": "@ada",
            "text": "ping",
        },
    )
    assert sent.status_code == 200
    assert "Message sent." in sent.text
    assert "ping" not in caplog.text
    assert "@ada" not in caplog.text


def test_listening_toggle(monkeypatch, tmp_home):
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    client = _client()
    page = client.get("/listening?account=work")
    token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    assert "Off" in page.text
    saved = client.post(
        "/listening",
        data={"csrf": token, "account": "work", "action": "enable"},
    )
    assert saved.status_code == 200
    assert "Listening enabled." in saved.text
    assert accounts.listen_config("work")["enabled"] is True


@pytest.mark.asyncio
async def test_call_cmd_uses_command_tier(monkeypatch):
    seen: dict[str, object] = {}

    async def ready():
        return True

    async def request(cmd, account=None, args=None, tier="destructive"):
        seen.update(cmd=cmd, tier=tier, account=account, args=args)
        return {"ok": True, "data": {"pong": True}}

    monkeypatch.setattr(bridge, "ensure_server", ready)
    monkeypatch.setattr(ipc, "request_async", request)
    await bridge.call_cmd("whoami", "work", {})
    assert seen["tier"] == "read"
    await bridge.call_cmd("send", "work", {"target": "@x", "text": "hi"})
    assert seen["tier"] == "write"
    assert seen["args"] == {"target": "@x", "text": "hi"}
