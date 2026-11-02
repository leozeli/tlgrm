<div align="center">

<img src="https://raw.githubusercontent.com/ali-commits/tlgrm/main/assets/logo.png" alt="tlgrm logo" width="160" height="160">

# tlgrm

**An unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on [Telethon](https://github.com/LonamiWebs/Telethon).**

Drive your *personal* Telegram account from the terminal — or from an AI assistant — and bridge incoming messages to an HTTP webhook in real time.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: unofficial](https://img.shields.io/badge/Telegram-unofficial%20client-lightgrey.svg)](https://github.com/ali-commits/tlgrm)

</div>

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is **not affiliated with, endorsed by, or sponsored by Telegram**.

---

## Features

- **Personal account** — acts as *you* (MTProto user account, not a bot): read history, list members, message anyone you can.
- **Multi-account** — log into several Telegram accounts, switch with `-a/--account`, and listen to all of them at once (like the mobile app).
- **30+ commands** — send/reply/edit/delete, history & global search, reactions, forwarding, pin & mute, group management, scheduling, polls.
- **Background server** — an optional persistent process owns one hot connection per account; the CLI, MCP server, and webhook listener all route through it, so they run together with no `database is locked` conflict (and commands are near-instant).
- **Real-time webhooks** — forward incoming messages to an HTTP endpoint, per-account, optionally as a `systemd` service.
- **Live filtering & permissions** — per-account allow/block lists for both *listening* (`filter listen`) and *writing* (`filter write`), plus daily listening windows — all reconfigurable live.
- **Scheduled messages** — `schedule send --at/--in`, `list`, `cancel` (Telegram-native, fires even when offline).
- **MCP server** — `tlgrm-mcp` lets AI assistants drive Telegram (read-only by default), as a thin bridge to the server.
- **Local dashboard** — `tlgrm ui` opens a localhost page for status, chats, sending, and listen/webhook settings.
- **Speech-to-text** — auto-transcribe incoming voice notes (multilingual, GPU-aware, live-configurable via `tlgrm stt`), or transcribe any file with `tlgrm transcribe`.
- **Clean JSON output** — commands print JSON to stdout (logs go to stderr), so it pipes straight into `jq` and scripts.

→ **[See the full feature list](docs/01-features.md)** — each one tagged by whether it needs the background server.

## Quick start

```bash
# 1. Get your API credentials from my.telegram.org → API development tools
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here

# 2. Install — uv recommended (https://docs.astral.sh/uv/)
uv tool install "tlgrm[all]"      # everything (CLI + MCP + UI + speech-to-text)
# uv tool install tlgrm           # CLI only
# uv tool install "tlgrm[mcp]"    # CLI + MCP server

# 3. Log in once
tlgrm login

# 4. Go
tlgrm chats --limit 10
tlgrm send --target @username --text "Hello!"
tlgrm chats | jq '.[].name'   # stdout is clean JSON; logs go to stderr
```

**Prefer pip?** Same package and extras: `pip install tlgrm` (or `"tlgrm[mcp]"`, `"tlgrm[stt]"`, `"tlgrm[all]"`).

---

## Telegram API credentials

tlgrm does **not** ship with API credentials — you must supply your own:

1. Go to **[my.telegram.org](https://my.telegram.org)** → **API development tools**.
2. Create an application (Platform: *Desktop*). The title must not contain the word "Telegram".
3. Copy the `api_id` (a number) and `api_hash` (a hex string).
4. Export them (add to your shell profile to persist):

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

See [docs/03-configuration.md](docs/03-configuration.md) for all configuration options.

---

## Commands (29)

Every command prints **clean JSON to stdout** — logs and progress go to **stderr**, so piping into `jq` works reliably.

### Account & read

| Command | Description |
|---------|-------------|
| `tlgrm login` | Authenticate your Telegram account (interactive, one-time) |
| `tlgrm whoami` | Show the logged-in account |
| `tlgrm chats [--limit N]` | List recent chats/dialogs |
| `tlgrm history --target T [--limit N] [--offset-id ID]` | Fetch message history |
| `tlgrm search --query Q [--target T] [--limit N]` | Search messages globally or in a chat |
| `tlgrm members --target T` | List members of a group or channel |
| `tlgrm user-info --target T` | Show profile info for a user |
| `tlgrm chat-info --target T` | Show info about a chat/channel |
| `tlgrm download --target T --message-id ID [--output PATH]` | Download media from a message |

### Write

| Command | Description |
|---------|-------------|
| `tlgrm send --target T (--text … \| --file …) [--caption …] [--voice] [--reply-to ID] [--silent]` | Send a message, file, media, or voice note |
| `tlgrm reply --target T --message-id ID (--text … \| --file …) [--caption …] [--voice] [--silent]` | Reply to a specific message |
| `tlgrm edit --target T --message-id ID --text …` | Edit a sent message |
| `tlgrm read --target T [--max-id ID]` | Mark a chat as read |
| `tlgrm forward --from A --to B --message-ids ID …` | Forward messages between chats |
| `tlgrm react --target T --message-id ID --emoji E [--big]` | React to a message |
| `tlgrm pin --target T --message-id ID [--notify]` | Pin a message |
| `tlgrm unpin --target T [--message-id ID]` | Unpin a message (or all) |
| `tlgrm mute --target T [--duration SECONDS]` | Mute a chat |
| `tlgrm unmute --target T` | Unmute a chat |
| `tlgrm saved (--text … \| --file …) [--caption …] [--voice]` | Send to Saved Messages |

### Groups, scheduling & advanced

| Command | Description |
|---------|-------------|
| `tlgrm create-group --title TITLE [--members …] [--channel]` | Create a group or channel |
| `tlgrm add-members --target T --members …` | Add members to a group/channel |
| `tlgrm remove-members --target T --members …` | Remove members from a group/channel |
| `tlgrm leave --target T` | Leave a group or channel |
| `tlgrm schedule --target T --text TEXT --at (SECONDS\|ISO8601)` | Schedule a text message |
| `tlgrm poll --target T --question Q --option A --option B … [--quiz --correct N]` | Send a poll or quiz |
| `tlgrm transcribe --file PATH [--backend …] [--model …]` | Transcribe audio (no login required) |

### Webhook daemon

| Command | Description |
|---------|-------------|
| `tlgrm listen [--webhook-url URL] [--webhook-header "N: V"] [--verbose]` | Listen for incoming messages (foreground) |
| `tlgrm daemon install\|uninstall\|status\|logs` | Manage the background systemd daemon |

Full reference with all flags, output shapes, and examples: **[docs/02-commands.md](docs/02-commands.md)**.

---

## MCP server

tlgrm ships a **stdio MCP server** (`tlgrm-mcp`). It is **read-only by default**; add `--allow-write` for write tools and `--allow-write --allow-destructive` for delete/leave/remove.

```json
{
  "mcpServers": {
    "tlgrm": {
      "command": "uvx",
      "args": ["--from", "tlgrm[mcp]", "tlgrm-mcp", "--allow-write"],
      "env": { "TG_API_ID": "...", "TG_API_HASH": "..." }
    }
  }
}
```

The MCP server is a **thin bridge** to the [background server](docs/03-configuration.md#background-server): every tool call routes through the one owned connection (which enforces the permission tier and the write guard), and a server is **auto-spawned** if none is running. So the MCP server, the webhook daemon, and your CLI all run at once with no `database is locked` conflict — no `--session` juggling. Add `--account NAME` to act as a specific [account](docs/03-configuration.md#accounts-multi-login) (otherwise the server's default account is used). Requires a prior `tlgrm login`.

Full setup, permission tiers, and tool list: **[MCP guide](docs/04-mcp.md)**.

---

## Local web UI

```bash
uv tool install "tlgrm[ui]"      # or: pip install "tlgrm[ui]"
tlgrm ui                         # http://127.0.0.1:8765
tlgrm ui --port 9000             # still bound to 127.0.0.1
```

`tlgrm ui` is a small localhost dashboard over the same background server as the CLI and MCP (it starts the server if it is not already running). Pages cover status, recent chats and history, sending a text message (the write guard still applies), listening and webhook settings, and credentials/proxy settings.

It binds to **127.0.0.1** unless you pass `--host`. Any other address prints a warning and shows one in the page: anyone who can open that URL can use your account.

Settings show whether `TG_API_ID` and `TG_API_HASH` are set and never display those values. Optional SOCKS (`TG_PROXY_HOST`, `TG_PROXY_PORT`, `TG_PROXY_TYPE`) and MTProxy (`TG_MTPROXY_*`) fields are saved to an owner-only `~/.tlgrm/ui.env`. A variable already exported in the environment wins. Restart `tlgrm server` after a proxy change. SOCKS needs an extra package: `pip install "python-socks[asyncio]"` (PySocks also works). See [configuration](docs/03-configuration.md#proxies).

---

## Speech-to-text (optional)

Install the `stt` extra to auto-transcribe incoming voice notes in the webhook daemon, or to run `tlgrm transcribe` standalone (no login needed).

```bash
uv tool install "tlgrm[stt]"         # faster-whisper (default, recommended)
uv tool install "tlgrm[stt-whisper]" # original openai-whisper
uv tool install "tlgrm[stt-all]"     # all local backends
# (or pip install "tlgrm[stt]", etc.)
```

Cloud backends (openai, groq, deepgram, elevenlabs, google) need no extra package — just set the API key:

```bash
export OPENAI_API_KEY=sk-...   # auto-selects openai backend
```

**Model tip:** the default model is `tiny` (fast, lower accuracy). For good **Arabic / multilingual** accuracy, use a larger model:

```bash
export TG_STT_MODEL=large-v3-turbo   # recommended for Arabic
```

**GPU:** faster-whisper auto-detects NVIDIA GPUs (`TG_STT_DEVICE=auto`). CUDA 12 runtime required: `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`. Full backend reference: **[docs/03-configuration.md](docs/03-configuration.md#speech-to-text-backends)**.

---

## Security

- Your **session file** (`~/.tlgrm/tg_session.session`) grants full account access — keep it private (git-ignored by default).
- Enable **Two-Step Verification** on your Telegram account.
- The systemd unit file is written owner-only (`0600`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Telegram API credentials are not configured` | Export `TG_API_ID` and `TG_API_HASH` (see [above](#telegram-api-credentials)) |
| `Not authorized. Run 'tlgrm login' first.` | Run `tlgrm login` |
| Transcription never appears | Install the `stt` extra **and** FFmpeg |
| `systemctl not found` | The daemon needs systemd; use `tlgrm listen` directly |
| Cannot create an app at my.telegram.org | Brand-new accounts are sometimes blocked; wait and retry |
| MCP tool not available | Check the permission tier — write/destructive tools need explicit flags |
| `tlgrm ui` says the UI extra is missing | `pip install "tlgrm[ui]"` or `uv tool install "tlgrm[ui]"` |

---

## Documentation

| Guide | What it covers |
|-------|----------------|
| [00 · Getting Started](docs/00-getting-started.md) | Install, credentials, login, first message |
| [01 · Features](docs/01-features.md) | Every feature in plain language, tagged by server need |
| [02 · Command Reference](docs/02-commands.md) | Every command, flag, output shape |
| [03 · Configuration](docs/03-configuration.md) | Accounts, server, listening/filters/STT, env vars |
| [04 · MCP server](docs/04-mcp.md) | Driving Telegram from an AI assistant |
| [05 · Webhook & Daemon Guide](docs/05-webhook-guide.md) | Webhooks, systemd, payload schema |

---

## Contributing & License

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Released under the [MIT License](LICENSE) © 2026 Ali Alrabeei. tlgrm is unofficial and not affiliated with, endorsed by, or sponsored by Telegram.
