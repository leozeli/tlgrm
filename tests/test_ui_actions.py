import json

import pytest

from tlgrm import accounts, ipc
from tlgrm.ui import actions, views


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    return tmp_path


def test_listening_view_masks_webhook(tmp_home):
    accounts.set_webhook(
        "work",
        "https://user:super-token@hooks.example/hook?sig=super-token",
        ["Authorization: Bearer super-token"],
    )
    accounts.set_listen_enabled("work", True)
    view = views.listening_view("work")
    blob = json.dumps(view)
    assert "super-token" not in blob
    assert view["enabled"] is True
    assert view["webhook_masked"] == "https://hooks.example/hook?sig=***"
    assert view["headers"] == ["Authorization: [REDACTED]"]
    assert "listen_summary" in view
    assert "write_summary" in view


def test_set_webhook_keeps_header_until_replaced(tmp_home, monkeypatch):
    pushed: dict[str, object] = {}
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    monkeypatch.setattr(
        ipc,
        "request_sync",
        lambda cmd, account=None, **kwargs: pushed.update(cmd=cmd, account=account),
    )
    accounts.set_webhook("work", "https://old.example/hook", ["X-Token: keep-me"])
    actions.set_webhook("work", "https://new.example/hook", None, clear_header=False)
    cfg = accounts.listen_config("work")
    assert cfg["webhook_url"] == "https://new.example/hook"
    assert cfg["webhook_headers"] == ["X-Token: keep-me"]
    assert pushed == {"cmd": "reload", "account": "work"}

    actions.set_webhook(
        "work",
        "https://new.example/hook",
        actions.build_auth_header("Authorization", "new-secret"),
        clear_header=False,
    )
    assert accounts.listen_config("work")["webhook_headers"] == [
        "Authorization: new-secret"
    ]


def test_build_auth_header_rejects_newlines():
    with pytest.raises(ValueError) as exc:
        actions.build_auth_header("Authorization", "Bearer\nX-Evil: 1")
    assert "X-Evil" not in str(exc.value)
    assert actions.build_auth_header("Authorization", "") is None
    assert actions.build_auth_header("", "token") == "Authorization: token"


def test_enable_disable(tmp_home):
    actions.set_listening("work", True)
    assert accounts.listen_config("work")["enabled"] is True
    actions.set_listening("work", False)
    assert accounts.listen_config("work")["enabled"] is False
    actions.clear_webhook("work")
    assert accounts.listen_config("work")["webhook_url"] is None
