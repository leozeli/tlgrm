import pytest
from tlgrm import listenctl, accounts, ipc


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)  # no live push
    return tmp_path


def test_enable_disable(tmp_home, capsys):
    listenctl.set_enabled("work", True)
    assert accounts.listen_config("work")["enabled"] is True
    assert '"enabled": true' in capsys.readouterr().out.lower()
    listenctl.set_enabled("work", False)
    assert accounts.listen_config("work")["enabled"] is False


def test_webhook_set_rejects_non_http_and_does_not_save(tmp_home, monkeypatch, capsys):
    pushed = {}
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    monkeypatch.setattr(ipc, "request_sync", lambda *a, **k: pushed.update(called=True))
    listenctl.webhook_set("work", "file:///tmp/hook", ["Authorization: Bearer SECRET"])
    out = capsys.readouterr().out
    assert '"success": false' in out
    assert "SECRET" not in out
    assert accounts.listen_config("work")["webhook_url"] is None
    assert pushed == {}


def test_webhook_set_show_clear(tmp_home, capsys):
    listenctl.webhook_set("work", "https://x", ["A: b"])
    assert accounts.listen_config("work")["webhook_url"] == "https://x"
    listenctl.webhook_clear("work")
    assert accounts.listen_config("work")["webhook_url"] is None


def test_webhook_show_redacts_header_values(tmp_home, capsys):
    listenctl.webhook_set("work", "https://x", ["Authorization: Bearer SECRET"])
    capsys.readouterr()  # drop the set output
    listenctl.webhook_show("work")
    out = capsys.readouterr().out
    assert "Authorization" in out
    assert "SECRET" not in out
    assert "[REDACTED]" in out


def test_filter_ops_and_live_push(tmp_home, monkeypatch):
    pushed = {}
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    monkeypatch.setattr(
        ipc,
        "request_sync",
        lambda cmd, account=None, **k: (
            pushed.update(cmd=cmd, account=account) or {"ok": True, "data": {}}
        ),
    )
    listenctl.filter_cmd("work", "listen", "mode", value="allow")
    listenctl.filter_cmd("work", "listen", "add", tokens=["@a"])
    assert accounts.listen_config("work")["filter"] == {"mode": "allow", "list": ["@a"]}
    assert pushed == {"cmd": "reload", "account": "work"}  # pushed live
