import pytest

from tlgrm import proxy
from tlgrm.core import client
from tlgrm.envfile import reset_for_tests
from tlgrm.proxy import ProxyConfigError, parse_proxy_config, telethon_proxy_kwargs


SECRET = "00112233445566778899aabbccddeeff"


def test_no_proxy_is_empty():
    assert parse_proxy_config({}).mode == "none"


def test_socks_plan_and_kwargs(monkeypatch):
    monkeypatch.setattr(proxy, "socks_backend_available", lambda: True)
    plan = parse_proxy_config({"TG_PROXY_HOST": "127.0.0.1", "TG_PROXY_PORT": "1080"})
    assert plan.mode == "socks"
    assert plan.kind == "socks5"
    assert plan.port == 1080
    monkeypatch.setenv("TG_PROXY_HOST", "127.0.0.1")
    monkeypatch.setenv("TG_PROXY_PORT", "1080")
    monkeypatch.delenv("TG_PROXY_TYPE", raising=False)
    for key in ("TG_MTPROXY_HOST", "TG_MTPROXY_PORT", "TG_MTPROXY_SECRET"):
        monkeypatch.delenv(key, raising=False)
    reset_for_tests()
    assert telethon_proxy_kwargs()["proxy"] == ("socks5", "127.0.0.1", 1080)


def test_socks_without_backend_names_the_package(monkeypatch):
    monkeypatch.setattr(proxy, "socks_backend_available", lambda: False)
    monkeypatch.setenv("TG_PROXY_HOST", "127.0.0.1")
    monkeypatch.setenv("TG_PROXY_PORT", "1080")
    for key in (
        "TG_PROXY_TYPE",
        "TG_MTPROXY_HOST",
        "TG_MTPROXY_PORT",
        "TG_MTPROXY_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_for_tests()
    with pytest.raises(ProxyConfigError) as exc:
        telethon_proxy_kwargs()
    assert "python-socks" in str(exc.value)


def test_incomplete_mtproxy_does_not_echo_secret():
    with pytest.raises(ProxyConfigError) as exc:
        parse_proxy_config(
            {"TG_MTPROXY_SECRET": SECRET, "TG_MTPROXY_PORT": "not-a-port"}
        )
    assert SECRET not in str(exc.value)
    assert "not-a-port" not in str(exc.value)


def test_mtproxy_repr_hides_secret():
    plan = parse_proxy_config(
        {
            "TG_MTPROXY_HOST": "mt.example",
            "TG_MTPROXY_PORT": "443",
            "TG_MTPROXY_SECRET": SECRET,
        }
    )
    assert plan.secret == SECRET
    assert SECRET not in repr(plan)
    assert "mt.example" in repr(plan)


def test_both_proxy_styles_rejected():
    with pytest.raises(ProxyConfigError) as exc:
        parse_proxy_config(
            {
                "TG_PROXY_HOST": "127.0.0.1",
                "TG_PROXY_PORT": "1080",
                "TG_MTPROXY_HOST": "mt.example",
                "TG_MTPROXY_PORT": "443",
                "TG_MTPROXY_SECRET": SECRET,
            }
        )
    assert "only one" in str(exc.value)
    assert SECRET not in str(exc.value)


def test_get_client_passes_socks_proxy(monkeypatch):
    from tlgrm import proxy as proxy_mod

    captured: dict[str, object] = {}

    class _FakeClient:
        def __init__(self, session, api_id, api_hash, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(proxy_mod, "socks_backend_available", lambda: True)
    monkeypatch.setattr(client, "TelegramClient", _FakeClient)
    monkeypatch.setattr(client, "ensure_dirs", lambda: None)
    monkeypatch.setattr(client, "get_api_credentials", lambda: (1, "h"))
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/sessions/ui")
    monkeypatch.setenv("TG_PROXY_HOST", "10.1.2.3")
    monkeypatch.setenv("TG_PROXY_PORT", "9050")
    monkeypatch.setenv("TG_PROXY_TYPE", "socks4")
    for key in ("TG_MTPROXY_HOST", "TG_MTPROXY_PORT", "TG_MTPROXY_SECRET"):
        monkeypatch.delenv(key, raising=False)
    reset_for_tests()

    client.get_client()
    assert captured["kwargs"] == {"proxy": ("socks4", "10.1.2.3", 9050)}
