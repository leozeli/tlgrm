import os
import sys
import shutil
import subprocess
import json

from .webhook_url import validate_webhook_url

SERVICE_NAME = "tlgrm-daemon"
USER_SERVICE_DIR = os.path.expanduser("~/.config/systemd/user")
SERVICE_FILE_PATH = os.path.join(USER_SERVICE_DIR, f"{SERVICE_NAME}.service")
ENV_FILE_PATH = os.path.expanduser("~/.tlgrm/daemon.env")

SERVER_SERVICE_NAME = "tlgrm-server"
SERVER_SERVICE_FILE_PATH = os.path.join(
    USER_SERVICE_DIR, f"{SERVER_SERVICE_NAME}.service"
)

# systemd user services do NOT inherit your interactive shell's exports, so we
# snapshot the relevant settings into an env file the unit loads. This keeps the
# daemon's STT model, GPU library path, and cloud API keys working.
_ENV_KEYS = [
    "TG_API_ID",
    "TG_API_HASH",
    "TG_SESSION_PATH",
    "TG_DOWNLOADS_DIR",
    "TG_STT_BACKEND",
    "TG_STT_MODEL",
    "TG_STT_DEVICE",
    "TG_STT_COMPUTE",
    "TG_STT_LANGUAGE",
    "HF_TOKEN",
    "LD_LIBRARY_PATH",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "GOOGLE_API_KEY",
]


def _write_env_file() -> list[str]:
    """Snapshot the relevant env vars currently set in the installing shell into
    an owner-only env file the service loads. Returns the captured key names."""
    lines: list[str] = []
    for k in _ENV_KEYS:
        v = os.environ.get(k)
        if v and "\n" not in v and "\r" not in v:
            lines.append(f"{k}={v}")
    os.makedirs(os.path.dirname(ENV_FILE_PATH), mode=0o700, exist_ok=True)
    fd = os.open(ENV_FILE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(
            "# tlgrm daemon environment — edit to add settings the service should use\n"
        )
        f.write(
            "# (e.g. TG_STT_MODEL=large-v3-turbo, OPENAI_API_KEY=..., LD_LIBRARY_PATH=...)\n"
        )
        if lines:
            f.write("\n".join(lines) + "\n")
    os.chmod(ENV_FILE_PATH, 0o600)
    return [line.split("=", 1)[0] for line in lines]


def _redact_header_value(header: str) -> str:
    """Show the header name but hide its value (it may carry a bearer token)."""
    if ":" not in header:
        return "[REDACTED]"
    return f"{header.split(':', 1)[0].strip()}: [REDACTED]"


def validate_filter_tokens(tokens: list[str] | None) -> None:
    """Filter targets (@username/id/phone) are embedded in the systemd ExecStart
    line, so reject anything with whitespace, quotes, or control characters that
    could break or inject into the unit."""
    for token in tokens or []:
        if not token:
            raise ValueError("Empty --only/--ignore value.")
        if (
            any(c.isspace() for c in token)
            or any(ord(c) < 32 for c in token)
            or any(c in token for c in ('"', "'", "$", "`", ";", "\\"))
        ):
            raise ValueError(f"Filter target contains illegal characters: {token!r}")


def validate_webhook_headers(headers: list[str] | None) -> None:
    """Ensure each header is 'Name: Value' with no characters that could break
    the systemd ExecStart line."""
    for header_str in headers or []:
        if ":" not in header_str:
            raise ValueError(f"Invalid header (expected 'Name: Value'): {header_str!r}")
        if any(c in header_str for c in ("\n", "\r", '"')) or any(
            ord(c) < 32 for c in header_str
        ):
            raise ValueError(f"Header contains illegal characters: {header_str!r}")


def check_systemctl() -> bool:
    if not shutil.which("systemctl"):
        return False
    return True


def run_systemctl_cmd(args: list[str]) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            ["systemctl", "--user"] + args, capture_output=True, text=True, check=True
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def daemon_install(
    webhook_url: str,
    webhook_headers: list[str] | None = None,
    verbose: bool = False,
    only: list[str] | None = None,
    ignore: list[str] | None = None,
) -> None:
    if not check_systemctl():
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "systemctl not found. Is systemd installed?",
                },
                indent=2,
            )
        )
        return

    try:
        validate_webhook_url(webhook_url)
        validate_webhook_headers(webhook_headers)
        validate_filter_tokens(only)
        validate_filter_tokens(ignore)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        return

    # Find the absolute path to the tlgrm binary
    tlgrm_path = shutil.which("tlgrm")
    if not tlgrm_path:
        # Fallback to sys.argv[0] if not found in PATH
        tlgrm_path = os.path.abspath(sys.argv[0])

    verbose_flag = "--verbose" if verbose else ""

    # Process custom headers into command arguments
    header_args: list[str] = []
    if webhook_headers:
        for header_str in webhook_headers:
            header_args.append(f'--webhook-header "{header_str}"')
    header_str = " ".join(header_args)

    # Chat/user filters (validated above to be shell-safe, so embed unquoted).
    filter_args = " ".join(
        [f"--only {t}" for t in (only or [])]
        + [f"--ignore {t}" for t in (ignore or [])]
    )

    # Snapshot the installing shell's relevant env into an owner-only file the
    # service loads (systemd user units don't inherit your shell environment).
    try:
        captured_env = _write_env_file()
    except Exception as e:
        print(
            json.dumps(
                {"success": False, "error": f"could not write env file: {e}"}, indent=2
            )
        )
        return

    # Construct service contents
    service_content = f"""[Unit]
Description=tlgrm webhook daemon
After=network.target

[Service]
EnvironmentFile=-{ENV_FILE_PATH}
ExecStart={tlgrm_path} listen --webhook-url {webhook_url} {header_str} {filter_args} {verbose_flag}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""

    try:
        # The unit embeds webhook headers, which may carry secrets (e.g. a
        # bearer token), so keep the directory and file owner-only readable.
        os.makedirs(USER_SERVICE_DIR, mode=0o700, exist_ok=True)
        os.chmod(USER_SERVICE_DIR, 0o700)
        fd = os.open(SERVICE_FILE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(service_content)
        os.chmod(SERVICE_FILE_PATH, 0o600)

        # Reload daemon
        success, out, err = run_systemctl_cmd(["daemon-reload"])
        if not success:
            raise Exception(f"daemon-reload failed: {err}")

        # Enable and start service
        success, out, err = run_systemctl_cmd(["enable", f"{SERVICE_NAME}.service"])
        if not success:
            raise Exception(f"enable failed: {err}")

        success, out, err = run_systemctl_cmd(["start", f"{SERVICE_NAME}.service"])
        if not success:
            raise Exception(f"start failed: {err}")

        print(
            json.dumps(
                {
                    "success": True,
                    "message": "tlgrm daemon installed and started successfully!",
                    "service": SERVICE_NAME,
                    "path": SERVICE_FILE_PATH,
                    "env_file": ENV_FILE_PATH,
                    "captured_env": captured_env,
                    "webhook_url": webhook_url,
                    "webhook_headers": [
                        _redact_header_value(h) for h in (webhook_headers or [])
                    ],
                    "only": only or [],
                    "ignore": ignore or [],
                    "executable": tlgrm_path,
                },
                indent=2,
            )
        )

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))


def daemon_uninstall() -> None:
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found."}, indent=2))
        return

    try:
        # Stop service
        run_systemctl_cmd(["stop", f"{SERVICE_NAME}.service"])
        # Disable service
        run_systemctl_cmd(["disable", f"{SERVICE_NAME}.service"])

        # Remove file
        if os.path.exists(SERVICE_FILE_PATH):
            os.remove(SERVICE_FILE_PATH)

        # Reload daemon
        run_systemctl_cmd(["daemon-reload"])

        print(
            json.dumps(
                {
                    "success": True,
                    "message": "tlgrm daemon uninstalled and removed successfully!",
                },
                indent=2,
            )
        )
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))


def daemon_status() -> None:
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found."}, indent=2))
        return

    # Check if file exists
    if not os.path.exists(SERVICE_FILE_PATH):
        print(
            json.dumps(
                {"success": True, "installed": False, "status": "not installed"},
                indent=2,
            )
        )
        return

    # Run show and is-active
    success_active, out_active, _ = run_systemctl_cmd(
        ["is-active", f"{SERVICE_NAME}.service"]
    )
    success_enabled, out_enabled, _ = run_systemctl_cmd(
        ["is-enabled", f"{SERVICE_NAME}.service"]
    )

    # Read properties for details
    _, out_show, _ = run_systemctl_cmd(
        [
            "show",
            f"{SERVICE_NAME}.service",
            "--property=ActiveState,SubState,LoadState,UnitFileState,MainPID",
        ]
    )

    props: dict[str, str] = {}
    for line in out_show.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v

    print(
        json.dumps(
            {
                "success": True,
                "installed": True,
                "service": SERVICE_NAME,
                "active_state": props.get("ActiveState", "unknown"),
                "sub_state": props.get("SubState", "unknown"),
                "enabled": out_enabled.strip() == "enabled",
                "load_state": props.get("LoadState", "unknown"),
                "main_pid": int(props.get("MainPID", "0")),
                "unit_file_path": SERVICE_FILE_PATH,
            },
            indent=2,
        )
    )


def daemon_logs() -> None:
    try:
        # Use journalctl to get recent daemon logs
        result = subprocess.run(
            ["journalctl", "--user", "-u", SERVICE_NAME, "-n", "30", "--no-pager"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
    except Exception as e:
        print(f"Error reading daemon logs: {e}")


def server_install() -> None:
    """Install & start the tlgrm server as a systemd user service."""
    if not check_systemctl():
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "systemctl not found. Is systemd installed?",
                },
                indent=2,
            )
        )
        return

    tlgrm_path = shutil.which("tlgrm") or os.path.abspath(sys.argv[0])
    try:
        captured_env = _write_env_file()
    except Exception as e:
        print(
            json.dumps(
                {"success": False, "error": f"could not write env file: {e}"}, indent=2
            )
        )
        return

    service_content = f"""[Unit]
Description=tlgrm server (owns Telegram connections)
After=network.target

[Service]
EnvironmentFile=-{ENV_FILE_PATH}
ExecStart={tlgrm_path} server start --foreground
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    try:
        os.makedirs(USER_SERVICE_DIR, mode=0o700, exist_ok=True)
        os.chmod(USER_SERVICE_DIR, 0o700)
        fd = os.open(
            SERVER_SERVICE_FILE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(fd, "w") as f:
            f.write(service_content)
        os.chmod(SERVER_SERVICE_FILE_PATH, 0o600)

        success, out, err = run_systemctl_cmd(["daemon-reload"])
        if not success:
            raise Exception(f"daemon-reload failed: {err}")
        success, out, err = run_systemctl_cmd(
            ["enable", f"{SERVER_SERVICE_NAME}.service"]
        )
        if not success:
            raise Exception(f"enable failed: {err}")
        success, out, err = run_systemctl_cmd(
            ["start", f"{SERVER_SERVICE_NAME}.service"]
        )
        if not success:
            raise Exception(f"start failed: {err}")

        print(
            json.dumps(
                {
                    "success": True,
                    "message": "tlgrm server installed and started as a systemd service.",
                    "service": SERVER_SERVICE_NAME,
                    "path": SERVER_SERVICE_FILE_PATH,
                    "env_file": ENV_FILE_PATH,
                    "captured_env": captured_env,
                    "executable": tlgrm_path,
                },
                indent=2,
            )
        )
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))


def server_service_uninstall() -> None:
    """Stop & remove the tlgrm-server systemd service."""
    if not check_systemctl():
        print(json.dumps({"success": False, "error": "systemctl not found."}, indent=2))
        return
    try:
        run_systemctl_cmd(["stop", f"{SERVER_SERVICE_NAME}.service"])
        run_systemctl_cmd(["disable", f"{SERVER_SERVICE_NAME}.service"])
        if os.path.exists(SERVER_SERVICE_FILE_PATH):
            os.remove(SERVER_SERVICE_FILE_PATH)
        run_systemctl_cmd(["daemon-reload"])
        print(
            json.dumps(
                {"success": True, "message": "tlgrm server service removed."}, indent=2
            )
        )
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))


def server_logs() -> None:
    """Show recent tlgrm-server journal logs."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                "--user",
                "-u",
                SERVER_SERVICE_NAME,
                "-n",
                "30",
                "--no-pager",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
    except Exception as e:
        print(f"Error reading server logs: {e}")
