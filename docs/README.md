# tlgrm Documentation

Welcome to the tlgrm documentation. tlgrm is an unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on Telethon.

> **Unofficial app notice:** tlgrm is not affiliated with, endorsed by, or sponsored by Telegram.

## Contents

| Guide | What it covers |
|-------|----------------|
| [00 · Getting Started](00-getting-started.md) | Prerequisites, installation, API credentials, first login, first message, STT quick-start |
| [01 · Features](01-features.md) | Every feature in plain language, tagged by whether it needs the background server |
| [02 · Command Reference](02-commands.md) | All commands, flags, examples, JSON output shapes, and MCP tools |
| [03 · Configuration](03-configuration.md) | Accounts, the background server, listening/filters/STT/scheduling, environment variables, GPU setup |
| [04 · MCP server](04-mcp.md) | Driving Telegram from an AI assistant — client config, permission tiers, tool list |
| [05 · Webhook & Daemon Guide](05-webhook-guide.md) | Real-time webhooks, the legacy systemd daemon, payload schema, delivery behavior |

## Quick links

- Source & issues: <https://github.com/ali-commits/tlgrm>
- Contributing: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- License: [MIT](../LICENSE)

## A 60-second tour

```bash
# Install (CLI + MCP server) — uv recommended
uv tool install "tlgrm[mcp]"      # or: pip install "tlgrm[mcp]"

# Configure credentials (one-time, from my.telegram.org)
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here

# Authenticate (one-time, interactive)
tlgrm login

# Use it — every command prints clean JSON to stdout; logs go to stderr
tlgrm chats --limit 10
tlgrm chats | jq '.[].name'
tlgrm send --target @username --text "Hello!"

# Or open the local dashboard (pip install "tlgrm[ui]")
tlgrm ui
tlgrm react --target @username --message-id 137480 --emoji "👍"
```

New here? Start with **[Getting Started](00-getting-started.md)**.

## MCP server

tlgrm ships a stdio MCP server (`tlgrm-mcp`) that exposes Telegram tools to AI assistants like Claude Desktop or Claude Code — read-only by default, with opt-in write/destructive tiers. It's a thin bridge to the background server, so it coexists with the CLI and the listener on one connection.

See the **[MCP guide](04-mcp.md)** for client configuration, permission tiers, and the full tool list.

## Speech-to-text highlights

- **Local (multilingual):** `faster-whisper` (default) and `whisper` handle Arabic, English, and code-switching.
- **Default model is `tiny`** — fast but limited. Use `TG_STT_MODEL=large-v3-turbo` for Arabic or multilingual accuracy.
- **GPU:** faster-whisper auto-detects NVIDIA GPUs and falls back to CPU. Requires CUDA 12 runtime.
- **Cloud:** openai, groq, deepgram, elevenlabs, google — set the API key, no extra package needed.
- **Standalone:** `tlgrm transcribe --file voice.ogg` works without a Telegram login.

See [Configuration → Speech-to-text backends](03-configuration.md#speech-to-text-backends) for the full reference.
