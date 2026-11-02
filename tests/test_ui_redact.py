import pytest

from tlgrm.redact import (
    bind_warning,
    filter_summary,
    is_loopback_host,
    mask_webhook_url,
    present_whoami,
    redact_header,
    redact_secrets,
)
from tlgrm.ui.guard import origin_allowed, post_is_allowed, tokens_match


def test_redact_header_hides_bearer():
    assert redact_header("Authorization: Bearer SUPERSECRET") == (
        "Authorization: [REDACTED]"
    )
    assert "SUPERSECRET" not in redact_header("Authorization: Bearer SUPERSECRET")


def test_mask_webhook_url_drops_userinfo_and_query():
    masked = mask_webhook_url(
        "https://user:super-token@hooks.example/path?sig=super-token&n=1"
    )
    assert masked == "https://hooks.example/path?sig=***&n=***"
    assert masked is not None
    assert "super-token" not in masked
    assert "user:" not in masked


def test_mask_webhook_url_rejects_odd_schemes_without_echoing():
    assert mask_webhook_url(None) is None
    assert mask_webhook_url("   ") is None
    assert mask_webhook_url("file:///tmp/super-token") == "[invalid webhook url]"


def test_filter_summary_modes_and_truncation():
    assert filter_summary({"mode": "block", "list": []}).startswith("block (empty)")
    assert filter_summary({"mode": "allow", "list": []}).startswith("allow (empty)")
    summary = filter_summary({"mode": "allow", "list": [f"@{i}" for i in range(8)]})
    assert summary.startswith("allow: @0, @1")
    assert "+2" in summary


def test_present_whoami_masks_phone():
    shown = present_whoami(
        {
            "id": 7,
            "first_name": "Ada",
            "last_name": "",
            "username": "ada",
            "phone": "+15551234567",
        }
    )
    assert shown["phone_masked"] == "+155****4567"
    assert "+15551234567" not in shown.values()
    assert "phone" not in shown


def test_bind_warning_only_off_loopback():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert is_loopback_host("localhost")
    assert not is_loopback_host("0.0.0.0")
    assert bind_warning("127.0.0.1") is None
    warning = bind_warning("0.0.0.0")
    assert warning is not None
    assert "localhost" in warning.lower() or "127.0.0.1" in warning


def test_redact_secrets_skips_short_tokens():
    assert redact_secrets("port 80 failed", ["80"]) == "port 80 failed"
    assert redact_secrets("token=abcdefgh", ["abcdefgh"]) == "token=[redacted]"


@pytest.mark.parametrize(
    ("origin", "ok"),
    [
        ("http://127.0.0.1:8765", True),
        ("http://localhost:8765", True),
        ("http://evil.example:8765", False),
        ("https://127.0.0.1:8765", False),
    ],
)
def test_origin_allowed_for_loopback_bind(origin, ok):
    assert origin_allowed(origin, "127.0.0.1", 8765) is ok


def test_post_is_allowed_blocks_cross_site_fetch():
    assert post_is_allowed({}, "127.0.0.1", 8765)
    assert not post_is_allowed(
        {"sec-fetch-site": "cross-site", "origin": "http://127.0.0.1:8765"},
        "127.0.0.1",
        8765,
    )


def test_tokens_match_rejects_different_lengths():
    assert tokens_match("abc", "abc")
    assert not tokens_match("abc", "abcd")
    assert not tokens_match("", "abc")
