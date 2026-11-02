"""FastAPI routes for the local dashboard.

Pages are server-rendered. Posts carry a CSRF cookie plus a matching form
field, and cross-site browser requests are rejected. Access logs are left
off by the runner so query strings (which can be phone targets) are not
written out.
"""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import envfile, ipc
from ..core.errors import TlgrmError
from ..redact import bind_warning, present_whoami, redact_secrets
from . import actions, bridge, views
from .guard import post_is_allowed, tokens_match

logger = logging.getLogger("tlgrm.ui")

_HERE = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_HERE / "templates"))
_CSRF = "tlgrm_csrf"
_FLASH = "tlgrm_flash"

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self'; img-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
}


def create_app(
    *, host: str = "127.0.0.1", port: int = 8765, ensure_server: bool = True
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Snapshot the real environment before the file is copied in, so
        # exported variables keep priority for this process.
        envfile.note_shell_env()
        envfile.inject_file_env()
        app.state.server_ready = False
        if ensure_server:
            app.state.server_ready = await bridge.ensure_server()
        yield

    app = FastAPI(
        title="tlgrm",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.host = host
    app.state.port = port
    app.state.bind_warning = bind_warning(host)
    app.state.flashes = {}
    app.mount(
        "/static",
        StaticFiles(directory=str(_HERE / "static")),
        name="static",
    )

    def render(
        request: Request,
        name: str,
        context: dict[str, Any],
        status_code: int = 200,
    ) -> Response:
        token = request.cookies.get(_CSRF) or secrets.token_urlsafe(32)
        account = context.get("account")
        default, names = views.account_names()
        ctx: dict[str, Any] = {
            "warning": app.state.bind_warning,
            "accounts": names,
            "default_account": default,
            "csrf": token,
            "flash": _take_flash(request),
            "q": views.with_account("", account) if account else "",
            **context,
        }
        response = _TEMPLATES.TemplateResponse(
            request, name, ctx, status_code=status_code
        )
        if request.cookies.get(_CSRF) != token:
            response.set_cookie(
                _CSRF, token, httponly=True, samesite="strict", path="/"
            )
        if request.cookies.get(_FLASH):
            response.delete_cookie(_FLASH, path="/")
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    def redirect(_request: Request, path: str, *, kind: str, text: str) -> Response:
        token = secrets.token_urlsafe(18)
        app.state.flashes[token] = {"kind": kind, "text": text[:400]}
        response = RedirectResponse(path, status_code=303)
        response.set_cookie(
            _FLASH, token, max_age=60, httponly=True, samesite="strict", path="/"
        )
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    async def posted(request: Request) -> dict[str, str]:
        if not post_is_allowed(request.headers, app.state.host, app.state.port):
            raise HTTPException(status_code=403, detail="Cross-origin request blocked")
        form = await request.form()
        sent = str(form.get("csrf") or "")
        expected = request.cookies.get(_CSRF) or ""
        if not tokens_match(expected, sent):
            raise HTTPException(status_code=403, detail="Bad form token")
        return {key: str(value) for key, value in form.items() if key != "csrf"}

    @app.get("/")
    async def status(request: Request, account: str | None = None) -> Response:
        logger.info("GET /")
        chosen, acc_err = views.resolve_requested(account)
        me = None
        me_err = None
        if chosen and not acc_err:
            try:
                me = present_whoami(await bridge.call_cmd("whoami", chosen, {}))
            except bridge.BridgeError as exc:
                me_err = exc.message
        listen = views.listening_view(chosen) if chosen else None
        return render(
            request,
            "status.html",
            {
                "title": "Status",
                "active": "status",
                "account": chosen,
                "acc_err": acc_err,
                "me": me,
                "me_err": me_err,
                "listen": listen,
                "server_running": ipc.is_server_running(),
            },
        )

    @app.get("/chats")
    async def chats(
        request: Request, account: str | None = None, limit: int = 30
    ) -> Response:
        logger.info("GET /chats")
        chosen, acc_err = views.resolve_requested(account)
        rows: list[Any] = []
        err = acc_err
        if chosen and not acc_err:
            try:
                data = await bridge.call_cmd(
                    "chats", chosen, {"limit": _clamp(limit, 1, 100)}
                )
                rows = list(data or [])
            except bridge.BridgeError as exc:
                err = exc.message
        return render(
            request,
            "chats.html",
            {
                "title": "Chats",
                "active": "chats",
                "account": chosen,
                "chats": rows,
                "error": err,
            },
        )

    @app.get("/history")
    async def history(
        request: Request,
        target: str = "",
        account: str | None = None,
        limit: int = 30,
    ) -> Response:
        logger.info("GET /history")
        chosen, acc_err = views.resolve_requested(account)
        messages: list[Any] = []
        err = acc_err
        clean = target.strip()
        if not clean:
            err = err or "Pick a chat."
        elif chosen and not acc_err:
            try:
                _check_target(clean)
                data = await bridge.call_cmd(
                    "history",
                    chosen,
                    {"target": clean, "limit": _clamp(limit, 1, 100), "offset_id": 0},
                )
                messages = list(data or [])
            except (ValueError, bridge.BridgeError) as exc:
                err = redact_secrets(str(exc), [clean])
        self_id = None
        if chosen and not acc_err:
            try:
                me = present_whoami(await bridge.call_cmd("whoami", chosen, {}))
                self_id = me.get("id")
            except bridge.BridgeError:
                self_id = None
        return render(
            request,
            "history.html",
            {
                "title": "History",
                "active": "chats",
                "account": chosen,
                "target": clean,
                "messages": messages,
                "self_id": self_id,
                "error": err,
            },
        )

    @app.get("/send")
    async def send_form(
        request: Request, account: str | None = None, target: str = ""
    ) -> Response:
        logger.info("GET /send")
        chosen, acc_err = views.resolve_requested(account)
        rows: list[Any] = []
        if chosen and not acc_err:
            try:
                data = await bridge.call_cmd("chats", chosen, {"limit": 30})
                rows = list(data or [])
            except bridge.BridgeError:
                rows = []
        return render(
            request,
            "send.html",
            {
                "title": "Send",
                "active": "send",
                "account": chosen,
                "acc_err": acc_err,
                "chats": rows,
                "target": target.strip(),
                "error": None,
            },
        )

    @app.post("/send")
    async def send_post(request: Request) -> Response:
        logger.info("POST /send")
        form = await posted(request)
        chosen, acc_err = views.resolve_requested(form.get("account") or None)
        target = (form.get("target_manual") or "").strip() or (
            form.get("target") or ""
        ).strip()
        text = (form.get("text") or "").strip()
        back = views.with_account("/send", chosen)
        if acc_err or not chosen:
            return redirect(
                request, "/send", kind="err", text=acc_err or "No account configured."
            )
        try:
            _check_target(target)
            if not text:
                raise ValueError("Message text is required.")
            if len(text) > 4096:
                raise ValueError("Message is too long.")
            await bridge.call_cmd("send", chosen, {"target": target, "text": text})
        except (ValueError, bridge.BridgeError) as exc:
            # Shown in the page, not written to the log. The path log line
            # above has no target and no message body.
            return redirect(
                request,
                back,
                kind="err",
                text=getattr(exc, "message", str(exc))[:400],
            )
        return redirect(request, back, kind="ok", text="Message sent.")

    @app.get("/listening")
    async def listening(request: Request, account: str | None = None) -> Response:
        logger.info("GET /listening")
        chosen, acc_err = views.resolve_requested(account)
        listen = views.listening_view(chosen) if chosen else None
        return render(
            request,
            "listening.html",
            {
                "title": "Listening",
                "active": "listening",
                "account": chosen,
                "acc_err": acc_err,
                "listen": listen,
                "error": None,
            },
        )

    @app.post("/listening")
    async def listening_post(request: Request) -> Response:
        logger.info("POST /listening")
        form = await posted(request)
        chosen, acc_err = views.resolve_requested(form.get("account") or None)
        if acc_err or not chosen:
            return redirect(
                request,
                "/listening",
                kind="err",
                text=acc_err or "No account configured.",
            )
        action = form.get("action") or ""
        url = (form.get("url") or "").strip()
        header_value = form.get("header_value") or ""
        back = views.with_account("/listening", chosen)
        try:
            if action == "enable":
                actions.set_listening(chosen, True)
                text = "Listening enabled."
            elif action == "disable":
                actions.set_listening(chosen, False)
                text = "Listening disabled."
            elif action == "webhook_clear":
                actions.clear_webhook(chosen)
                text = "Webhook cleared."
            elif action == "webhook_set":
                header = actions.build_auth_header(
                    form.get("header_name") or "", header_value
                )
                actions.set_webhook(
                    chosen,
                    url,
                    header,
                    clear_header=(form.get("clear_header") or "") == "1",
                )
                text = "Webhook saved."
            else:
                raise ValueError("Unknown action.")
        except (ValueError, TlgrmError) as exc:
            return redirect(
                request,
                back,
                kind="err",
                text=redact_secrets(str(exc), [url, header_value]),
            )
        return redirect(request, back, kind="ok", text=text)

    @app.get("/settings")
    async def settings(request: Request, account: str | None = None) -> Response:
        logger.info("GET /settings")
        chosen, acc_err = views.resolve_requested(account)
        return render(
            request,
            "settings.html",
            {
                "title": "Settings",
                "active": "settings",
                "account": chosen,
                "acc_err": acc_err,
                "settings": envfile.public_settings(),
                "error": None,
            },
        )

    @app.post("/settings")
    async def settings_post(request: Request) -> Response:
        logger.info("POST /settings")
        form = await posted(request)
        chosen, _acc_err = views.resolve_requested(form.get("account") or None)
        back = views.with_account("/settings", chosen)
        action = form.get("action") or ""
        secret_bits = [
            form.get("api_hash") or "",
            form.get("mtproxy_secret") or "",
            form.get("api_id") or "",
        ]
        try:
            if action == "save_credentials":
                actions.save_credentials(form)
                text = "Credentials saved. Restart `tlgrm server` if it is already running."
            elif action == "save_proxy":
                actions.save_proxy(form)
                text = "Proxy settings saved. Restart `tlgrm server` to apply them."
            else:
                raise ValueError("Unknown action.")
        except (ValueError, TlgrmError) as exc:
            return redirect(
                request, back, kind="err", text=redact_secrets(str(exc), secret_bits)
            )
        return redirect(request, back, kind="ok", text=text)

    return app


def _take_flash(request: Request) -> dict[str, str] | None:
    token = request.cookies.get(_FLASH)
    if not token:
        return None
    flashes: dict[str, dict[str, str]] = request.app.state.flashes
    return flashes.pop(token, None)


def _clamp(value: int, low: int, high: int) -> int:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _check_target(target: str) -> None:
    if not target or len(target) > 128 or any(ord(c) < 32 for c in target):
        raise ValueError("Invalid target.")
