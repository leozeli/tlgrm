# tests/test_cli_parser.py
import sys
import pytest
from tlgrm import cli
from tlgrm.cli import build_parser


def test_parser_has_all_commands():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    for cmd in [
        "login",
        "chats",
        "send",
        "edit",
        "delete",
        "history",
        "members",
        "listen",
        "daemon",
        "search",
        "reply",
        "read",
        "download",
        "whoami",
        "user-info",
        "chat-info",
        "forward",
        "react",
        "pin",
        "unpin",
        "mute",
        "unmute",
        "saved",
        "create-group",
        "add-members",
        "remove-members",
        "leave",
        "schedule",
        "poll",
        "transcribe",
    ]:
        assert cmd in sub.choices


def test_send_requires_target():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["send", "--text", "hi"])  # missing --target


def test_global_session_flag(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["--session", "/tmp/sessions/mcp", "chats"])
    assert args.session == "/tmp/sessions/mcp"
    assert args.command == "chats"


def test_session_flag_sets_env(monkeypatch):
    # main() should export the resolved session path before dispatching.
    monkeypatch.setenv("TG_API_ID", "1")
    monkeypatch.setenv("TG_API_HASH", "h")
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    monkeypatch.setattr(sys, "argv", ["tlgrm", "--session", "~/mcp_sess", "chats"])
    from tlgrm import dispatch

    monkeypatch.setattr(dispatch, "run_command_routed", lambda args: None)
    monkeypatch.setattr(cli.asyncio, "run", lambda coro: coro)
    cli.main()
    import os

    assert os.environ["TG_SESSION_PATH"] == os.path.expanduser("~/mcp_sess")


def test_missing_credentials_exits_1_with_json(monkeypatch, capsys):
    # The behavior-preservation contract: credential failures exit 1 and
    # report the error as JSON.
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setattr(sys, "argv", ["tlgrm", "chats"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert '"success": false' in capsys.readouterr().out


def test_global_account_flag():
    parser = build_parser()
    args = parser.parse_args(["-a", "work", "chats"])
    assert args.account == "work"
    assert args.command == "chats"


def test_account_subcommands_present():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert "account" in sub.choices
    args = parser.parse_args(["account", "add", "personal"])
    assert args.account_command == "add"
    assert args.name == "personal"


def test_account_add_name_optional():
    parser = build_parser()
    args = parser.parse_args(["account", "add"])
    assert args.name is None


def test_filter_write_subcommands():
    parser = build_parser()
    args = parser.parse_args(["filter", "write", "add", "@boss"])
    assert args.filter_domain == "write" and args.filter_op == "add"
    assert args.targets == ["@boss"]
    args = parser.parse_args(["filter", "write", "mode", "allow"])
    assert args.mode == "allow"


def test_schedule_subcommands():
    parser = build_parser()
    a = parser.parse_args(
        ["schedule", "send", "--target", "@x", "--text", "hi", "--in", "2h"]
    )
    assert a.schedule_command == "send" and a.in_ == "2h"
    a = parser.parse_args(["schedule", "cancel", "--target", "@x", "--id", "5", "6"])
    assert a.schedule_command == "cancel" and a.ids == [5, 6]


def test_ui_command_defaults_to_loopback():
    parser = build_parser()
    args = parser.parse_args(["ui"])
    assert args.command == "ui"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    args = parser.parse_args(["ui", "--host", "0.0.0.0", "--port", "9000"])
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_ui_command_dispatches(monkeypatch):
    called = {}
    monkeypatch.setattr(sys, "argv", ["tlgrm", "ui", "--port", "8799"])
    from tlgrm.ui import server as ui_server

    monkeypatch.setattr(
        ui_server, "serve", lambda host, port: called.update(host=host, port=port)
    )
    cli.main()
    assert called == {"host": "127.0.0.1", "port": 8799}


def test_version_flag_exits_zero_and_prints(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("tlgrm ")
