import pytest
from tlgrm import accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_defaults(tmp_home):
    cfg = accounts.listen_config("work")
    assert cfg == {
        "enabled": False,
        "webhook_url": None,
        "webhook_headers": [],
        "filter": {"mode": "block", "list": []},
        "window": None,
    }


def test_set_enabled_and_webhook(tmp_home):
    accounts.set_listen_enabled("work", True)
    accounts.set_webhook("work", "https://x/y", ["A: b"])
    cfg = accounts.listen_config("work")
    assert cfg["enabled"] is True
    assert cfg["webhook_url"] == "https://x/y"
    assert cfg["webhook_headers"] == ["A: b"]
    accounts.clear_webhook("work")
    assert accounts.listen_config("work")["webhook_url"] is None


def test_filter_mode_and_list(tmp_home):
    accounts.filter_set_mode("work", "listen", "allow")
    accounts.filter_add("work", "listen", ["@a", "@b"])
    accounts.filter_add("work", "listen", ["@a"])  # dedup
    assert accounts.listen_config("work")["filter"] == {
        "mode": "allow",
        "list": ["@a", "@b"],
    }
    accounts.filter_remove("work", "listen", ["@a"])
    assert accounts.listen_config("work")["filter"]["list"] == ["@b"]
    accounts.filter_clear("work", "listen")
    assert accounts.listen_config("work")["filter"]["list"] == []


def test_set_webhook_rejects_dangerous_scheme(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.set_webhook("work", "ftp://example.com/hook")
    assert accounts.listen_config("work")["webhook_url"] is None
    with pytest.raises(accounts.TlgrmError):
        accounts.set_webhook("work", "http://example.com/hook\nX-Injected: 1")
    assert accounts.listen_config("work")["webhook_url"] is None


def test_bad_mode_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.filter_set_mode("work", "listen", "nonsense")
