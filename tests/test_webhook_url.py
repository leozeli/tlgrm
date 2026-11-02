import pytest

from tlgrm import daemon, listen_core, webhook_url
from tlgrm.core.errors import TlgrmError


def test_validators_are_one_function():
    assert daemon.validate_webhook_url is webhook_url.validate_webhook_url
    assert listen_core.validate_webhook_url is webhook_url.validate_webhook_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/hook",
        "http://localhost:5678/webhook",
        "http://127.0.0.1/hook",
        "http://192.168.1.10:8080/n8n",
        "http://[::1]:8080/hook",
        "https://user:token@example.com/hook",
        "HTTP://example.com/hook",
    ],
)
def test_validate_webhook_url_accepts_http(url):
    webhook_url.validate_webhook_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://evil/x",
        "ftp://example.com/hook",
        "javascript:alert(1)",
        "data:text/plain,hi",
        "http://",
        "https://",
        "/etc/passwd",
        "example.com/hook",
        "http://example.com/hook\nX",
        " http://example.com",
        "",
    ],
)
def test_validate_webhook_url_rejects_dangerous_or_broken(url):
    with pytest.raises(ValueError):
        webhook_url.validate_webhook_url(url)


@pytest.mark.asyncio
async def test_forward_webhook_does_not_post_dangerous_scheme(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("should not construct an HTTP client")

    monkeypatch.setattr(listen_core.httpx, "AsyncClient", boom)
    await listen_core.forward_webhook("gopher://evil/x", {"event": "new_message"})


@pytest.mark.asyncio
async def test_run_listener_rejects_before_connect(monkeypatch):
    from tlgrm import webhooks

    def boom():
        raise AssertionError("should not connect")

    monkeypatch.setattr(webhooks, "get_client", boom)
    with pytest.raises(TlgrmError, match="http/https"):
        await webhooks.run_listener("file:///etc/passwd")


def _stub_install(monkeypatch, sink):
    monkeypatch.setattr(daemon, "check_systemctl", lambda: True)
    monkeypatch.setattr(daemon, "_write_env_file", lambda: [])
    monkeypatch.setattr(daemon, "run_systemctl_cmd", lambda args: (True, "", ""))
    monkeypatch.setattr(daemon.shutil, "which", lambda _name: "/usr/bin/tlgrm")
    monkeypatch.setattr(daemon.os, "chmod", lambda *_a, **_k: None)
    monkeypatch.setattr(daemon.os, "makedirs", lambda *_a, **_k: None)
    monkeypatch.setattr(daemon.os, "open", lambda *_a, **_k: 0)

    class _Sink:
        def write(self, s):
            sink["text"] += s

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(daemon.os, "fdopen", lambda *_a, **_k: _Sink())


def test_daemon_install_redacts_headers_in_stdout(monkeypatch, capsys):
    sink = {"text": ""}
    _stub_install(monkeypatch, sink)
    daemon.daemon_install(
        "https://example.com/hook",
        webhook_headers=["Authorization: Bearer SECRET"],
    )
    out = capsys.readouterr().out
    assert '"success": true' in out
    assert "Authorization" in out
    assert "[REDACTED]" in out
    assert "SECRET" not in out
    # The unit still needs the real header so the service can authenticate.
    assert "Bearer SECRET" in sink["text"]


def test_daemon_install_rejects_non_http_before_writing(monkeypatch, capsys):
    def fail_write():
        raise AssertionError("should not write the env file")

    monkeypatch.setattr(daemon, "check_systemctl", lambda: True)
    monkeypatch.setattr(daemon, "_write_env_file", fail_write)
    daemon.daemon_install(
        "file:///etc/passwd",
        webhook_headers=["Authorization: Bearer SECRET"],
    )
    out = capsys.readouterr().out
    assert '"success": false' in out
    assert "http/https" in out
    assert "SECRET" not in out
