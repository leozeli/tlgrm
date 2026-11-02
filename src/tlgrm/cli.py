import sys
import asyncio

from .parser import build_parser
from .output import emit
from .core.errors import TlgrmError, CredentialsError, NotAuthorizedError
from .webhooks import run_listener
from .daemon import daemon_install, daemon_uninstall, daemon_status, daemon_logs

__all__ = ["main", "build_parser", "emit"]


def _default_account() -> str:
    from .accounts import load_config

    result: str = load_config().get("default_account") or "default"
    return result


def _friendly_error(e: Exception) -> str:
    """Turn common Telethon errors into clear, user-facing messages."""
    try:
        from telethon import errors as tg
    except Exception:
        return str(e)
    if isinstance(e, tg.FloodWaitError):
        return f"Rate limited by Telegram; retry in {e.seconds}s."
    if isinstance(e, getattr(tg, "ApiIdInvalidError", ())):
        return "Invalid API credentials (api_id / api_hash)."
    if isinstance(
        e,
        (
            getattr(tg, "UsernameNotOccupiedError", ()),
            getattr(tg, "UsernameInvalidError", ()),
            getattr(tg, "PeerIdInvalidError", ()),
        ),
    ):
        return "Could not resolve the target — check the @username, id, or phone."
    if isinstance(e, getattr(tg, "ChatAdminRequiredError", ())):
        return "This action requires admin rights in that chat."
    if isinstance(e, getattr(tg, "MessageIdInvalidError", ())):
        return "No message with that ID."
    if isinstance(e, getattr(tg, "ChatWriteForbiddenError", ())):
        return "You don't have permission to write in that chat."
    return str(e)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    from .accounts import migrate_legacy_session

    migrate_legacy_session()

    # A --session flag points this process at its own Telethon session (resolved
    # at client-build time via config.session_path), so it never collides with a
    # running daemon/MCP server on the single-process SQLite session.
    if getattr(args, "session", None):
        import os

        os.environ["TG_SESSION_PATH"] = os.path.expanduser(args.session)

    try:
        if (
            args.command in ("send", "reply", "saved")
            and not getattr(args, "text", None)
            and not getattr(args, "file", None)
        ):
            parser.error(
                f"At least one of --text or --file is required for {args.command}."
            )

        match args.command:
            case "transcribe":
                import os
                from .stt import transcribe_audio
                from .stt.settings import resolve_backend

                if not os.path.exists(args.file):
                    emit({"success": False, "error": f"File not found: {args.file}"})
                    sys.exit(1)
                backend = args.backend or resolve_backend()
                text = transcribe_audio(
                    args.file, backend=args.backend, model=args.model
                )
                emit({"success": text is not None, "backend": backend, "text": text})
            case "listen":
                asyncio.run(
                    run_listener(
                        args.webhook_url,
                        args.webhook_header,
                        args.verbose,
                        args.only,
                        args.ignore,
                    )
                )
            case "daemon":
                match args.daemon_command:
                    case "install":
                        daemon_install(
                            args.webhook_url,
                            args.webhook_header,
                            args.verbose,
                            only=args.only,
                            ignore=args.ignore,
                        )
                    case "uninstall":
                        daemon_uninstall()
                    case "status":
                        daemon_status()
                    case "logs":
                        daemon_logs()
            case "server":
                from . import serverctl

                match args.server_command:
                    case "start":
                        serverctl.start(args.foreground)
                    case "stop":
                        serverctl.stop()
                    case "status":
                        serverctl.status()
                    case "restart":
                        serverctl.restart()
                    case "install":
                        from .daemon import server_install

                        server_install()
                    case "uninstall":
                        from .daemon import server_service_uninstall

                        server_service_uninstall()
                    case "logs":
                        from .daemon import server_logs

                        server_logs()
            case "account" if args.account_command != "add":
                from .dispatch import run_account_command

                run_account_command(args)
            case "listening":
                from . import listenctl

                acc = args.account or _default_account()
                if args.listening_command == "window":
                    match args.window_command:
                        case "set":
                            listenctl.window_set(acc, args.range)
                        case "show":
                            listenctl.window_show(acc)
                        case "clear":
                            listenctl.window_clear(acc)
                else:
                    listenctl.set_enabled(acc, args.listening_command == "enable")
            case "webhook":
                from . import listenctl

                acc = args.account or _default_account()
                match args.webhook_command:
                    case "set":
                        listenctl.webhook_set(acc, args.url, args.headers)
                    case "show":
                        listenctl.webhook_show(acc)
                    case "clear":
                        listenctl.webhook_clear(acc)
            case "filter":
                from . import listenctl
                from .listen_core import _split_tokens

                acc = args.account or _default_account()
                listenctl.filter_cmd(
                    acc,
                    args.filter_domain,
                    args.filter_op,
                    value=getattr(args, "mode", None),
                    tokens=_split_tokens(getattr(args, "targets", None)),
                )
            case "ui":
                from .ui.server import serve

                serve(args.host, args.port)
            case "stt":
                from . import sttctl

                match args.stt_command:
                    case "status":
                        sttctl.status()
                    case "enable":
                        sttctl.set_enabled(True)
                    case "disable":
                        sttctl.set_enabled(False)
                    case "set":
                        sttctl.set_config(args.backend, args.model, args.device)
            case _:
                from .dispatch import run_command_routed

                run_command_routed(args)
    except KeyboardInterrupt:
        print("\nExiting...", file=sys.stderr)
        sys.exit(0)
    except (CredentialsError, NotAuthorizedError) as e:
        emit({"success": False, "error": str(e)})
        sys.exit(1)
    except TlgrmError as e:
        emit({"success": False, "error": str(e)})
    except Exception as e:  # operation-level failures (e.g. Telethon errors)
        emit({"success": False, "error": _friendly_error(e)})


if __name__ == "__main__":
    main()
