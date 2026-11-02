# Getting Started

`tlgrm` is a personal Telegram account CLI client, MCP server, and webhook background service built on the [Telethon](https://github.com/LonamiWebs/Telethon) library. It lets you script interactions, manage conversations, and bridge your personal Telegram messages into downstream automated workflows.

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is not affiliated with, endorsed by, or sponsored by Telegram.

## Prerequisites

- **Python** `>=3.10`
- **A Telegram account** and access to its phone number (for the login code)
- **Your own Telegram API credentials** — `api_id` and `api_hash` (see below)
- **FFmpeg** — only required for optional local speech-to-text of voice messages

## 1. Get your Telegram API credentials

tlgrm acts as your *user account* via the Telegram client API (MTProto), which requires your own application credentials. tlgrm does **not** bundle any — a shared `api_id` would be rate-limited for everyone.

1. Open **[my.telegram.org](https://my.telegram.org)** and log in (a code is sent **inside the Telegram app**).
2. Click **API development tools**.
3. Create a new application:
   - **App title:** e.g. `tlgrm` — the title must not contain the word "Telegram"
   - **Short name:** `tlgrm`
   - **Platform:** Desktop
4. Copy the resulting **`api_id`** (number) and **`api_hash`** (hex string).

> Each phone number can have only **one** `api_id`, and the `api_hash` cannot be reset — so register it on the account you intend to keep.

## 2. Install tlgrm

With [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install tlgrm
uv tool install "tlgrm[mcp]"   # + MCP server
uv tool install "tlgrm[stt]"   # + speech-to-text
uv tool install "tlgrm[ui]"    # + local web dashboard
uv tool install "tlgrm[all]"   # everything
```

Or with `pip`:

```bash
pip install tlgrm
pip install "tlgrm[mcp]"
pip install "tlgrm[stt]"
pip install "tlgrm[ui]"
pip install "tlgrm[all]"
```

The `stt` extra installs `faster-whisper`, the default local STT backend. It also requires **FFmpeg** on your system path. For cloud STT backends (openai, groq, deepgram, elevenlabs, google), no extra package is needed — just set the corresponding API key. See [03-configuration.md](03-configuration.md#speech-to-text-backends) for details.

## 3. Configure your credentials

Export the credentials from step 1:

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

Add these lines to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to persist them. See [03-configuration.md](03-configuration.md) for all available settings.

## 4. First-time login

Authenticate your personal Telegram account. This is interactive (Telegram sends a code to your app), so run it in a terminal:

```bash
tlgrm login
```

Follow the prompts:
1. Your phone number in international format (e.g. `+15551234567`)
2. The verification code sent to your Telegram app
3. Your 2FA password, if you have one enabled

On success your account details are shown and an authenticated session is stored at `~/.tlgrm/tg_session.session`. You will not need to log in again unless you delete that file.

> **Keep your session file private** — anyone with it can access your account. It is git-ignored by default.

## 5. Send your first message

```bash
# By username
tlgrm send --target @username --text "Hello from tlgrm!"

# By numeric chat ID
tlgrm send --target 738667936 --text "Hi!"
```

Every command prints **clean JSON to stdout** (logs go to **stderr**), so you can pipe reliably into `jq` or other tools:

```bash
tlgrm chats --limit 5 | jq '.[].name'
tlgrm history --target @username --limit 3 | jq '.[].text'
```

## 6. (Optional) Speech-to-text

Install the `stt` extra to enable automatic voice note transcription in the webhook daemon and to use `tlgrm transcribe` standalone:

```bash
pip install "tlgrm[stt]"   # requires FFmpeg
```

The default model (`tiny`) is fast but has limited accuracy for Arabic and mixed-language audio. For much better results:

```bash
export TG_STT_MODEL=large-v3-turbo   # recommended for Arabic / multilingual
tlgrm transcribe --file voice.ogg
```

If you have an NVIDIA GPU, faster-whisper uses it automatically (CUDA 12 runtime required). See [03-configuration.md](03-configuration.md#speech-to-text-backends) for the full backend reference, GPU setup, and cloud backend options.

## Next steps

- Explore every command in the [Command Reference](02-commands.md).
- Forward incoming messages to an HTTP endpoint with the [Webhook & Daemon Guide](05-webhook-guide.md).
- Tune paths and behavior via [Configuration](03-configuration.md).
- Expose Telegram tools to an AI assistant: see [the MCP guide](04-mcp.md).
- Prefer a page over flags: `pip install "tlgrm[ui]"` then `tlgrm ui` (localhost only).
