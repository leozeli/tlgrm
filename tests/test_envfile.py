import json
import os
import stat

import pytest

from tlgrm import envfile
from tlgrm.envfile import (
    credential_changes,
    parse_env_text,
    public_settings,
    update_ui_env,
)
from tlgrm.proxy import ProxyConfigError
from tlgrm.ui import actions


SECRET = "cafebabecafebabe"


def test_parse_ignores_unknown_keys_and_comments():
    parsed = parse_env_text(
        "\n".join(
            [
                "# comment",
                "LD_PRELOAD=/tmp/evil",
                "TG_API_ID=42",
                "TG_API_HASH=abc def",
                "NOT_A_KEY=1",
            ]
        )
    )
    assert parsed == {"TG_API_ID": "42"}


def test_file_is_owner_only_and_public_view_hides_secrets():
    update_ui_env(
        {
            "TG_API_ID": "99",
            "TG_API_HASH": SECRET,
            "TG_MTPROXY_HOST": "mt.example",
            "TG_MTPROXY_PORT": "443",
            "TG_MTPROXY_SECRET": SECRET,
        }
    )
    path = envfile.ui_env_path()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    shown = public_settings()
    blob = json.dumps(shown)
    assert SECRET not in blob
    assert shown["api_id_set"] is True
    assert shown["api_hash_set"] is True
    assert shown["mtproxy_secret_set"] is True
    assert shown["mtproxy_host"] == "mt.example"
    assert "api_hash" not in shown


def test_shell_wins_over_file(monkeypatch):
    monkeypatch.setenv("TG_PROXY_HOST", "from-env")
    envfile.reset_for_tests()
    update_ui_env({"TG_PROXY_HOST": "from-file"})
    assert os.environ["TG_PROXY_HOST"] == "from-env"
    assert envfile.read_ui_env()["TG_PROXY_HOST"] == "from-file"
    assert envfile.effective_map()["TG_PROXY_HOST"] == "from-env"
    assert public_settings()["env_overrides_file"] is True


def test_file_fills_unset_keys(monkeypatch):
    monkeypatch.delenv("TG_PROXY_HOST", raising=False)
    envfile.reset_for_tests()
    update_ui_env({"TG_PROXY_HOST": "from-file", "TG_PROXY_PORT": "1080"})
    assert os.environ["TG_PROXY_HOST"] == "from-file"
    assert envfile.value_source("TG_PROXY_HOST") == "file"


def test_credential_error_omits_the_value():
    bad = "not-an-integer-secret"
    with pytest.raises(ValueError) as exc:
        credential_changes({"api_id": bad, "api_hash": ""})
    assert bad not in str(exc.value)


def test_blank_secret_keeps_stored_value():
    changes = envfile.proxy_changes(
        {"TG_MTPROXY_SECRET": SECRET},
        {
            "proxy_host": "",
            "proxy_port": "",
            "proxy_type": "socks5",
            "mtproxy_host": "mt.example",
            "mtproxy_port": "443",
            "mtproxy_secret": "",
            "clear_mtproxy_secret": "",
        },
    )
    assert changes["TG_MTPROXY_SECRET"] == SECRET
    assert changes["TG_PROXY_HOST"] is None


def test_save_proxy_rejects_both_styles_without_writing():
    with pytest.raises(ProxyConfigError):
        actions.save_proxy(
            {
                "proxy_host": "127.0.0.1",
                "proxy_port": "1080",
                "proxy_type": "socks5",
                "mtproxy_host": "mt.example",
                "mtproxy_port": "443",
                "mtproxy_secret": SECRET,
            }
        )
    assert envfile.read_ui_env() == {}


def test_newline_value_is_rejected_without_echo():
    nasty = "abc\nLD_PRELOAD=evil"
    with pytest.raises(ValueError) as exc:
        update_ui_env({"TG_API_HASH": nasty})
    assert "LD_PRELOAD" not in str(exc.value)
    assert not os.path.exists(envfile.ui_env_path())
