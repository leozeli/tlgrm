# Changelog

All notable changes to tlgrm are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Local web dashboard** — `tlgrm ui` (optional `ui` extra) serves a localhost page for status, recent chats and history, sending, and listening/webhook settings. It routes through the background server, so the CLI, MCP, and dashboard share one connection and the write guard still applies.
- **SOCKS and MTProxy** — `TG_PROXY_HOST` / `TG_PROXY_PORT` / `TG_PROXY_TYPE` and `TG_MTPROXY_HOST` / `TG_MTPROXY_PORT` / `TG_MTPROXY_SECRET`. The client stays a direct connection until one of these is set. Values can also be saved from the dashboard to `~/.tlgrm/ui.env`; exported variables win.

## [0.3.2] — 2026-06-17

### Fixed

- **Server startup race.** When two servers were spawned at once — e.g. the
  systemd unit and the one the MCP bridge auto-spawns — the second would delete
  the first's socket, rebind, and both processes would then drive the same
  Telegram session (`database is locked` / `AUTH_KEY_DUPLICATED`), breaking both.
  Startup now takes an exclusive single-instance lock (`~/.tlgrm/server.lock`):
  the first process to acquire it owns the socket and the connection; any other
  stands down cleanly instead of stealing it. The lock is released on exit (and
  by the OS on crash), so there is no stale-lock problem.

## [0.3.1] — 2026-06-16

### Added

- **`tlgrm --version`** — print the installed version and exit.

### Internal

- Converted the command dispatchers in `execute.py` and `cli.py` from `if/elif`
  ladders to `match` statements (no behavior change).

## [0.3.0] — 2026-06-16

### Changed

- **The MCP server (`tlgrm-mcp`) is now a thin bridge to the `tlgrm server`.**
  Tool calls route through the single owned connection (the server enforces
  permission tiers and the write guard), and a server is auto-spawned if none is
  running. Adds `--account`; `--session` is no longer needed (accepted but
  ignored). The MCP server, the webhook daemon, and the CLI can now all run at
  once without the `database is locked` conflict.

### Added

- **Multi-account support.** Log into multiple Telegram accounts, each a named
  profile (`tlgrm account add/list/use/rename/remove`) with its own session.
  Select one per command with `-a/--account`. A pre-0.3.0 single session is
  migrated to account `default` automatically.
- **Background server + dual-mode CLI.** `tlgrm server start` runs a persistent
  process that owns one hot connection per account over an owner-only Unix
  socket. CLI commands automatically route through it when it's running (fast,
  no per-command login) and fall back to a direct connection when it isn't —
  which structurally eliminates the "database is locked" session conflict.
  `tlgrm server install` runs it as a systemd user service.
- **Server-side per-account listening with live config.** With the server
  running, each account listens for incoming messages independently. Configure
  it live (no restart): `tlgrm listening enable/disable`, `tlgrm webhook
  set/show/clear`, and `tlgrm filter listen show/mode/add/remove/clear` (an
  allow/block list matched by chat or sender). The webhook payload now includes
  an `account` field identifying which account received the message.
- **Per-account write guard (`filter write`).** Restrict which chats/users an
  account may message: `tlgrm filter write mode allow|block` + `add/remove/clear`.
  Blocked targets make outgoing commands (send, reply, edit, forward, react, pin,
  schedule, poll) fail fast — before anything is sent. Combined with `filter
  listen`, this forms a full per-contact listen×write permission matrix.
- **Live STT control (`tlgrm stt`).** Configure speech-to-text without a restart:
  `tlgrm stt status/enable/disable/set --backend/--model/--device`. Settings are
  server-global and applied live (the server drops cached models and re-warms);
  `disable` stops auto-transcribing incoming voice notes. The server pre-warms the
  model at startup.
- **Scheduled messages.** `tlgrm schedule send --target X --text Y --at "<datetime>"`
  or `--in 2h`, plus `schedule list` and `schedule cancel --id …` — backed by
  Telegram's own scheduling, so they fire even when the tlgrm server isn't running.
- **Listening windows.** `tlgrm listening window set 09:00-17:00` restricts an
  account to listen only during that daily range (overnight ranges supported);
  `show`/`clear` to inspect/remove.

### Internal

- Adopted a formatter, linter, and two type checkers: **ruff** (format + lint),
  **mypy** (`strict`), and **pyrefly**, wired into **prek** pre-commit hooks. The
  entire `src/` tree is now fully type-annotated and passes both checkers; tests
  run in parallel (`pytest-xdist`) with a per-test timeout. See `CONTRIBUTING.md`.
- Added a project logo.

## [0.2.1] — 2026-06-16

### Added

- **Listener chat/user filtering.** `tlgrm listen` and `tlgrm daemon install` now
  accept `--only CHAT` (whitelist — forward only matching chats/users) and
  `--ignore CHAT` (blacklist — never forward matching chats/users). Each takes an
  `@username`, id, or phone, is repeatable and comma-separated, and matches a
  message by its chat *or* its sender. The filter is applied before any media
  download, so ignored chats cost nothing.

## [0.2.0] — 2026-06-16

This release rolls up everything since the first public release (0.1.0). The
headline change is that the **CLI, webhook daemon, and MCP server can now run at
the same time** against one account, plus a much stronger speech-to-text stack
and a more robust daemon.

### Added

- **Per-consumer sessions (`--session PATH`).** A Telethon session is
  single-process, so running the daemon and the MCP server against the same
  session deadlocked. You can now give each long-running consumer its own
  session/login with `--session` on both `tlgrm` and `tlgrm-mcp` (it overrides
  `TG_SESSION_PATH` for that process). The daemon, MCP server, and your CLI then
  run concurrently — no `database is locked`, no risk of `AUTH_KEY_DUPLICATED`.
  See [docs/configuration.md](docs/configuration.md#running-the-daemon-mcp-server-and-cli-at-the-same-time).
- **`tlgrm transcribe`** — standalone speech-to-text for any audio file, no
  Telegram login required (`--file`, `--backend`, `--model`).
- **GPU acceleration for faster-whisper.** With `TG_STT_DEVICE=auto` (default),
  an NVIDIA GPU is detected and used when its CUDA runtime is available, with an
  automatic fall back to CPU at load *or* inference time.
- **`TG_STT_LANGUAGE`** — force a transcription language (e.g. `ar`, `en`) to
  skip auto-detection.
- **Daemon environment snapshot.** systemd user services don't inherit your
  shell, so `tlgrm daemon install` now snapshots the relevant settings (STT
  model, cloud API keys, GPU `LD_LIBRARY_PATH`, …) into an owner-only
  `~/.tlgrm/daemon.env` that the unit loads via `EnvironmentFile=`.
- **STT model pre-warming.** The daemon loads the STT model at startup so the
  first incoming voice note transcribes without delay.
- `uv.lock` is now tracked for reproducible installs.

### Changed

- **Speech-to-text is now multilingual-only.** Backends were narrowed to the
  multilingual whisper family plus cloud providers — `faster-whisper` (default),
  `whisper`, and cloud `openai` / `groq` / `deepgram` / `elevenlabs` / `google`.
  faster-whisper defaults to CPU and downloads models on demand. For good Arabic
  or multilingual accuracy, set `TG_STT_MODEL=large-v3-turbo`.
- **Logs go to stderr.** All progress and log output is on stderr, so stdout is
  pure JSON and pipeable to `jq`.
- **Friendlier errors.** Common Telethon failures (rate limits, invalid
  credentials, unresolved targets, permission errors, …) are mapped to clear,
  human-readable messages instead of raw tracebacks.
- **Documentation overhaul.** README trimmed to ≤200 lines; expanded and
  reorganized `docs/` (configuration, commands, getting-started, webhook guide).

### Fixed

- **`whisper` backend ffmpeg preflight.** The `whisper` backend now checks for
  `ffmpeg` up front and reports a clear error if it's missing (the default
  `faster-whisper` backend bundles its own decoder and needs no system ffmpeg).
- Broken/failed STT model loads are no longer cached, so a transient failure
  doesn't poison later transcriptions.

### Removed

- Non-multilingual STT backends (which couldn't handle Arabic) were dropped in
  favor of the multilingual-only set above.

### Internal

- The CLI was split into focused modules (`parser`, `dispatch`, `output`) over a
  thin `main()`; the session path is resolved at client-build time so flags and
  environment overrides are always honored.

## [0.1.3] — 2026-06-15

- Daemon: snapshot environment into an `EnvironmentFile`; ffmpeg preflight for
  the `whisper` backend; documented the single-process session limitation.

## [0.1.2] — 2026-06-15

- Speech-to-text narrowed to multilingual backends; logs moved to stderr; CLI
  split into modules; friendly Telethon error messages; docs refresh.

## [0.1.1] — 2026-06-14

- Added the `tlgrm transcribe` command; faster-whisper became the default and
  defaults to CPU.

## [0.1.0] — 2026-06-14

- Initial public release: unofficial Telegram command-line client, MCP server,
  and webhook daemon built on Telethon.
