import pytest
from tlgrm.server.listener import AccountListener


class _FakeClient:
    def __init__(self):
        self.handlers = []

    def on(self, _event):
        def deco(fn):
            self.handlers.append(fn)
            return fn

        return deco

    def remove_event_handler(self, fn):
        self.handlers.remove(fn)

    async def get_me(self):
        return type("Me", (), {"id": 777})()

    async def get_entity(self, token):
        raise ValueError("unresolved")


@pytest.mark.asyncio
async def test_reload_builds_state_from_config(monkeypatch):
    monkeypatch.setattr(
        "tlgrm.accounts.listen_config",
        lambda name: {
            "enabled": True,
            "webhook_url": "https://x",
            "webhook_headers": ["A: b"],
            "filter": {"mode": "allow", "list": ["123", "@foo"]},
        },
    )
    c = _FakeClient()
    lis = AccountListener(c, "work")
    await lis.reload()
    assert lis.state.enabled is True
    assert lis.state.webhook_url == "https://x"
    assert lis.state.headers == {"A": "b"}
    assert lis.state.mode == "allow"
    assert 123 in lis.state.ids and "foo" in lis.state.names
    assert lis.account_obj == {"name": "work", "id": 777}


@pytest.mark.asyncio
async def test_reload_ignores_non_http_webhook(monkeypatch):
    monkeypatch.setattr(
        "tlgrm.accounts.listen_config",
        lambda name: {
            "enabled": True,
            "webhook_url": "file:///etc/passwd",
            "webhook_headers": [],
            "filter": {"mode": "block", "list": []},
        },
    )
    lis = AccountListener(_FakeClient(), "work")
    await lis.reload()
    assert lis.state.enabled is True
    assert lis.state.webhook_url is None


async def test_start_registers_one_handler_and_stop_removes(monkeypatch):
    monkeypatch.setattr(
        "tlgrm.accounts.listen_config",
        lambda name: {
            "enabled": True,
            "webhook_url": None,
            "webhook_headers": [],
            "filter": {"mode": "block", "list": []},
        },
    )
    c = _FakeClient()
    lis = AccountListener(c, "work")
    await lis.reload()
    lis.start()
    assert len(c.handlers) == 1
    lis.start()  # idempotent
    assert len(c.handlers) == 1
    lis.stop()
    assert c.handlers == []
