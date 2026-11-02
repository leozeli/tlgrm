"""Process entry for ``tlgrm ui``."""

import importlib.util
import sys

from ..redact import bind_warning

_UI_PACKAGES = ("fastapi", "uvicorn", "jinja2", "multipart")


def missing_ui_deps() -> list[str]:
    return [name for name in _UI_PACKAGES if importlib.util.find_spec(name) is None]


def _require_deps() -> None:
    missing = missing_ui_deps()
    if not missing:
        return
    sys.stderr.write(
        "tlgrm ui needs the optional UI extra "
        f"(missing: {', '.join(missing)}).\n"
        '  pip install "tlgrm[ui]"\n'
        '  # or: uv tool install "tlgrm[ui]"\n'
    )
    raise SystemExit(1)


def serve(host: str, port: int) -> None:
    """Bind the dashboard. Loopback by default; other hosts print a warning."""
    _require_deps()
    if port < 1 or port > 65535:
        sys.stderr.write("Port must be between 1 and 65535.\n")
        raise SystemExit(1)
    warning = bind_warning(host)
    if warning:
        sys.stderr.write(f"warning: {warning}\n")
    import uvicorn

    from .app import create_app

    app = create_app(host=host, port=port, ensure_server=True)
    uvicorn.run(
        app,
        host=host,
        port=port,
        access_log=False,
        log_level="info",
        server_header=False,
    )
