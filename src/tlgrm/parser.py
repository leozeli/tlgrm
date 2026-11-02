"""argparse command-line parser for tlgrm (kept separate from dispatch/main)."""

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tlgrm",
        description="tlgrm - unofficial command-line client & webhook daemon for Telegram",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tlgrm {__version__}",
        help="Show the tlgrm version and exit",
    )
    parser.add_argument(
        "--session",
        metavar="PATH",
        help="Telethon session base path to use for this command (overrides "
        "TG_SESSION_PATH). Use a separate session per long-running consumer "
        "so the CLI, daemon, and MCP server don't share one and lock each other out.",
    )
    parser.add_argument(
        "-a",
        "--account",
        metavar="NAME",
        help="Account to act as (defaults to the configured default account). "
        "Manage accounts with `tlgrm account`.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Interactively log in to Telegram")

    ap = sub.add_parser("account", help="Manage Telegram accounts (multi-login)")
    asub = ap.add_subparsers(dest="account_command", required=True)
    aadd = asub.add_parser("add", help="Log in a new account")
    aadd.add_argument(
        "name", nargs="?", default=None, help="Account name (default: 'default')"
    )
    asub.add_parser("list", help="List accounts and the default")
    ause = asub.add_parser("use", help="Set the default account")
    ause.add_argument("name")
    aren = asub.add_parser("rename", help="Rename an account")
    aren.add_argument("old")
    aren.add_argument("new")
    arem = asub.add_parser("remove", help="Log out and delete an account")
    arem.add_argument("name")

    p = sub.add_parser("chats", help="List recent chats/dialogs")
    p.add_argument("--limit", type=int, default=20, help="Max chats (default: 20)")

    p = sub.add_parser("send", help="Send a message or file/media")
    p.add_argument("--target", required=True, help="Username, chat ID, or phone number")
    p.add_argument("--text", help="Text message content")
    p.add_argument("--file", help="Path to a file/media to send")
    p.add_argument("--caption", help="Caption for the file (overrides --text)")
    p.add_argument("--voice", action="store_true", help="Send the file as a voice note")
    p.add_argument("--reply-to", type=int, help="Reply to this message ID")
    p.add_argument("--silent", action="store_true", help="Send without notification")

    p = sub.add_parser("edit", help="Edit an existing sent message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--text", required=True)

    p = sub.add_parser("delete", help="Delete messages")
    p.add_argument("--target", required=True)
    p.add_argument("--message-ids", required=True, nargs="+")

    p = sub.add_parser("history", help="Retrieve message history")
    p.add_argument("--target", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument(
        "--offset-id", type=int, default=0, help="Start before this message ID"
    )

    p = sub.add_parser("members", help="Retrieve chat members/participants")
    p.add_argument("--target", required=True)

    p = sub.add_parser("search", help="Search messages (global, or within --target)")
    p.add_argument("--query", required=True)
    p.add_argument("--target", help="Limit search to this chat (omit for global)")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("reply", help="Reply to a specific message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--caption")
    p.add_argument("--voice", action="store_true")
    p.add_argument("--silent", action="store_true", help="Send without notification")

    p = sub.add_parser("read", help="Mark a chat/messages as read")
    p.add_argument("--target", required=True)
    p.add_argument("--max-id", type=int, help="Mark up to this message ID")

    p = sub.add_parser("download", help="Download media from a message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--output", help="Output file or directory")

    sub.add_parser("whoami", help="Show the logged-in account")

    p = sub.add_parser("user-info", help="Show info about a user")
    p.add_argument("--target", required=True)

    p = sub.add_parser("chat-info", help="Show info about a chat")
    p.add_argument("--target", required=True)

    p = sub.add_parser("forward", help="Forward messages between chats")
    p.add_argument("--from", dest="from_chat", required=True)
    p.add_argument("--to", dest="to_chat", required=True)
    p.add_argument("--message-ids", required=True, nargs="+")

    p = sub.add_parser("react", help="React to a message with an emoji")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument(
        "--emoji", required=True, help="Emoji (empty string clears the reaction)"
    )
    p.add_argument("--big", action="store_true")

    p = sub.add_parser("pin", help="Pin a message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--notify", action="store_true")

    p = sub.add_parser("unpin", help="Unpin a message (or all if --message-id omitted)")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", type=int)

    p = sub.add_parser("mute", help="Mute a chat")
    p.add_argument("--target", required=True)
    p.add_argument("--duration", type=int, help="Seconds to mute (default: forever)")

    p = sub.add_parser("unmute", help="Unmute a chat")
    p.add_argument("--target", required=True)

    p = sub.add_parser("saved", help="Send to your Saved Messages")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--caption")
    p.add_argument("--voice", action="store_true")

    p = sub.add_parser("create-group", help="Create a group or channel")
    p.add_argument("--title", required=True)
    p.add_argument("--members", nargs="*", default=[])
    p.add_argument("--channel", action="store_true", help="Create a broadcast channel")

    p = sub.add_parser("add-members", help="Add members to a group/channel")
    p.add_argument("--target", required=True)
    p.add_argument("--members", required=True, nargs="+")

    p = sub.add_parser("remove-members", help="Remove members from a group/channel")
    p.add_argument("--target", required=True)
    p.add_argument("--members", required=True, nargs="+")

    p = sub.add_parser("leave", help="Leave a group/channel")
    p.add_argument("--target", required=True)

    sc = sub.add_parser("schedule", help="Schedule messages (Telegram-native)")
    scsub = sc.add_subparsers(dest="schedule_command", required=True)
    scsend = scsub.add_parser("send", help="Schedule a message")
    scsend.add_argument("--target", required=True)
    scsend.add_argument("--text", required=True)
    when = scsend.add_mutually_exclusive_group(required=True)
    when.add_argument("--at", help="ISO-8601 datetime, or seconds-from-now")
    when.add_argument("--in", dest="in_", help="Relative delay, e.g. 90s, 30m, 2h, 1d")
    sclist = scsub.add_parser("list", help="List scheduled messages in a chat")
    sclist.add_argument("--target", required=True)
    sccancel = scsub.add_parser("cancel", help="Cancel scheduled messages")
    sccancel.add_argument("--target", required=True)
    sccancel.add_argument("--id", dest="ids", required=True, nargs="+", type=int)

    p = sub.add_parser("poll", help="Send a poll or quiz")
    p.add_argument("--target", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--option", action="append", required=True, dest="options")
    p.add_argument("--multiple", action="store_true")
    p.add_argument("--quiz", action="store_true")
    p.add_argument("--correct", type=int, help="Index of the correct answer (quiz)")

    _only_help = (
        "Whitelist: only listen to this chat/user (@username, id, or "
        "phone). Repeatable or comma-separated. Matches the chat or the sender."
    )
    _ignore_help = (
        "Blacklist: never listen to this chat/user (@username, id, or "
        "phone). Repeatable or comma-separated. Matches the chat or the sender."
    )

    p = sub.add_parser("listen", help="Run webhook listener for new messages")
    p.add_argument("--webhook-url")
    p.add_argument("--webhook-header", action="append")
    p.add_argument("--only", action="append", metavar="CHAT", help=_only_help)
    p.add_argument("--ignore", action="append", metavar="CHAT", help=_ignore_help)
    p.add_argument("--verbose", action="store_true")

    lsp = sub.add_parser("listening", help="Enable/disable listening for an account")
    lssub = lsp.add_subparsers(dest="listening_command", required=True)
    lssub.add_parser("enable", help="Enable listening for the account")
    lssub.add_parser("disable", help="Disable listening for the account")
    lwin = lssub.add_parser("window", help="Listen only during a daily time window")
    lwsub = lwin.add_subparsers(dest="window_command", required=True)
    lwset = lwsub.add_parser("set", help="Set the window, e.g. 09:00-17:00")
    lwset.add_argument("range")
    lwsub.add_parser("show")
    lwsub.add_parser("clear")

    wp = sub.add_parser("webhook", help="Configure the account's webhook")
    wsub = wp.add_subparsers(dest="webhook_command", required=True)
    wset = wsub.add_parser("set", help="Set the webhook URL")
    wset.add_argument("url")
    wset.add_argument("--header", action="append", dest="headers")
    wsub.add_parser("show", help="Show the webhook")
    wsub.add_parser("clear", help="Clear the webhook")

    fp = sub.add_parser("filter", help="Configure listen/write filters")
    fpsub = fp.add_subparsers(dest="filter_domain", required=True)
    for _domain in ("listen", "write"):
        dpar = fpsub.add_parser(_domain, help=f"{_domain} filter (allow/block list)")
        dsub = dpar.add_subparsers(dest="filter_op", required=True)
        dsub.add_parser("show")
        dmode = dsub.add_parser("mode")
        dmode.add_argument("mode", choices=["allow", "block"])
        dadd = dsub.add_parser("add")
        dadd.add_argument("targets", nargs="+")
        drem = dsub.add_parser("remove")
        drem.add_argument("targets", nargs="+")
        dsub.add_parser("clear")

    dp = sub.add_parser("daemon", help="Manage tlgrm systemd background daemon")
    dsub = dp.add_subparsers(dest="daemon_command", required=True)
    ip = dsub.add_parser("install", help="Install & start systemd user daemon")
    ip.add_argument("--webhook-url", required=True)
    ip.add_argument("--webhook-header", action="append")
    ip.add_argument("--only", action="append", metavar="CHAT", help=_only_help)
    ip.add_argument("--ignore", action="append", metavar="CHAT", help=_ignore_help)
    ip.add_argument("--verbose", action="store_true")
    dsub.add_parser("uninstall", help="Stop & remove systemd user daemon")
    dsub.add_parser("status", help="Show daemon systemd status")
    dsub.add_parser("logs", help="Show recent daemon logs")

    sp = sub.add_parser("server", help="Manage the background tlgrm server")
    spsub = sp.add_subparsers(dest="server_command", required=True)
    spstart = spsub.add_parser("start", help="Start the server")
    spstart.add_argument(
        "--foreground",
        action="store_true",
        help="Run in the foreground instead of detaching",
    )
    spsub.add_parser("stop", help="Stop the server")
    spsub.add_parser("status", help="Show server status")
    spsub.add_parser("restart", help="Restart the server")
    spsub.add_parser(
        "install", help="Install & start the server as a systemd user service"
    )
    spsub.add_parser("uninstall", help="Stop & remove the systemd server service")
    spsub.add_parser("logs", help="Show recent server logs")

    stp = sub.add_parser("stt", help="Configure speech-to-text (server-global)")
    stsub = stp.add_subparsers(dest="stt_command", required=True)
    stsub.add_parser("status", help="Show STT settings")
    stsub.add_parser("enable", help="Enable incoming-voice transcription")
    stsub.add_parser("disable", help="Disable incoming-voice transcription")
    stset = stsub.add_parser("set", help="Set backend/model/device")
    stset.add_argument("--backend")
    stset.add_argument("--model")
    stset.add_argument("--device", choices=["auto", "cpu", "cuda"])

    p = sub.add_parser(
        "ui",
        help="Open the local web dashboard (default bind 127.0.0.1:8765)",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1). Any other address prints a warning.",
    )
    p.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")

    p = sub.add_parser("transcribe", help="Transcribe an audio file (speech-to-text)")
    p.add_argument("--file", required=True, help="Path to the audio file")
    p.add_argument(
        "--backend",
        help="Override the STT backend (faster-whisper, whisper, "
        "openai, groq, deepgram, elevenlabs, google)",
    )
    p.add_argument("--model", help="Override the backend model")

    return parser
