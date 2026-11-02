# tests/test_accounts.py
import os
import stat
import pytest
from tlgrm import accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("TG_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "accounts"))
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    return tmp_path


def test_load_missing_config_returns_empty(tmp_home):
    cfg = accounts.load_config()
    assert cfg == {"default_account": None, "accounts": {}}


def test_session_path_for_login_ignores_session_override(tmp_home, monkeypatch):
    # During login (must_exist=False) the new session must land at the account's
    # path, not at a --session override, so it matches where it gets registered.
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/override")
    path = accounts.session_path_for("work", must_exist=False)
    assert path.endswith("/accounts/work.session")


def test_session_path_for_normal_command_honors_override(tmp_home, monkeypatch):
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/override")
    assert accounts.session_path_for("work", must_exist=True) == "/tmp/override"


def test_save_config_removes_temp_on_write_failure(tmp_home, monkeypatch):
    import tomli_w

    monkeypatch.setattr(
        tomli_w, "dump", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom"))
    )
    with pytest.raises(ValueError):
        accounts.save_config({"default_account": None, "accounts": {}})
    assert not os.path.exists(accounts._config_path() + ".tmp")


def test_save_then_load_roundtrip(tmp_home):
    accounts.save_config(
        {"default_account": "work", "accounts": {"work": {}, "personal": {}}}
    )
    cfg = accounts.load_config()
    assert cfg["default_account"] == "work"
    assert set(cfg["accounts"]) == {"work", "personal"}


def test_saved_config_is_owner_only(tmp_home):
    accounts.save_config({"default_account": None, "accounts": {"a": {}}})
    mode = stat.S_IMODE(os.stat(accounts._config_path()).st_mode)
    assert mode == 0o600


def test_save_strips_none_for_toml(tmp_home):
    # TOML has no null; default_account None must not crash the writer.
    accounts.save_config({"default_account": None, "accounts": {}})
    assert "default_account" not in accounts._config_path_text()


def test_add_account_sets_first_as_default(tmp_home):
    accounts.add_account("personal")
    cfg = accounts.load_config()
    assert cfg["default_account"] == "personal"
    assert "personal" in cfg["accounts"]


def test_add_second_account_keeps_default(tmp_home):
    accounts.add_account("personal")
    accounts.add_account("work")
    assert accounts.load_config()["default_account"] == "personal"


def test_set_default_unknown_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.set_default("ghost")


def test_rename_moves_session_and_default(tmp_home):
    accounts.add_account("a")
    open(accounts.account_session_path("a"), "w").close()
    accounts.rename_account("a", "b")
    cfg = accounts.load_config()
    assert "b" in cfg["accounts"] and "a" not in cfg["accounts"]
    assert cfg["default_account"] == "b"
    assert os.path.exists(accounts.account_session_path("b"))


def test_remove_account_drops_session_and_repoints_default(tmp_home):
    accounts.add_account("a")
    accounts.add_account("b")
    open(accounts.account_session_path("a"), "w").close()
    accounts.set_default("a")
    accounts.remove_account("a")
    cfg = accounts.load_config()
    assert "a" not in cfg["accounts"]
    assert cfg["default_account"] == "b"
    assert not os.path.exists(accounts.account_session_path("a"))


def test_resolve_account_uses_default_then_explicit(tmp_home):
    accounts.add_account("personal")
    accounts.add_account("work")
    assert accounts.resolve_account() == "personal"  # default
    assert accounts.resolve_account("work") == "work"  # explicit
    with pytest.raises(accounts.TlgrmError):
        accounts.resolve_account("ghost")


def test_resolve_account_none_configured_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.resolve_account()


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../x",
        "a/b",
        "a\\b",
        "a..b",
        " has",
        "has space",
        "-bad",
        ".hidden",
        "a" * 65,
        "na\x00me",
        "foo/../../etc",
    ],
)
def test_unsafe_account_names_rejected(tmp_home, name):
    with pytest.raises(accounts.TlgrmError):
        accounts.add_account(name)
    with pytest.raises(accounts.TlgrmError):
        accounts.account_session_path(name)
    if name:
        # "" is treated as "no account" by session_path_for and falls back to
        # "default"; every other unsafe name must still be rejected on the
        # login path (must_exist=False), which is where the session is written.
        with pytest.raises(accounts.TlgrmError):
            accounts.session_path_for(name, must_exist=False)
    assert name not in accounts.load_config()["accounts"]


@pytest.mark.parametrize("name", ["a", "work", "Work_2", "personal-1", "a.b", "a" * 64])
def test_safe_account_names_accepted(tmp_home, name):
    accounts.add_account(name)
    path = accounts.account_session_path(name)
    base = os.path.realpath(accounts._accounts_dir())
    assert os.path.dirname(os.path.realpath(path)) == base
    assert os.path.basename(path) == f"{name}.session"
    assert stat.S_IMODE(os.stat(base).st_mode) == 0o700


def test_rename_rejects_traversal_without_dropping_source(tmp_home):
    accounts.add_account("a")
    with pytest.raises(accounts.TlgrmError):
        accounts.rename_account("a", "../b")
    cfg = accounts.load_config()
    assert "a" in cfg["accounts"]
    assert "../b" not in cfg["accounts"]


def test_session_path_rejects_symlink_escape(tmp_home):
    accounts.add_account("work")
    base = accounts._accounts_dir()
    outside = tmp_home / "outside"
    outside.mkdir()
    link = os.path.join(base, "work.session")
    os.symlink(str(outside / "stolen.session"), link)
    with pytest.raises(accounts.TlgrmError):
        accounts.account_session_path("work")
    assert not (outside / "stolen.session").exists()


def test_migrate_legacy_session(tmp_home, monkeypatch):
    legacy = tmp_home / "tg_session.session"
    legacy.write_text("session-data")
    monkeypatch.setattr(accounts, "_legacy_session_path", lambda: str(legacy))

    assert accounts.migrate_legacy_session() is True
    cfg = accounts.load_config()
    assert cfg["default_account"] == "default"
    assert os.path.exists(accounts.account_session_path("default"))
    assert not legacy.exists()
    # Idempotent: second call is a no-op.
    assert accounts.migrate_legacy_session() is False
