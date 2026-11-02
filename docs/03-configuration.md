# Configuration

tlgrm is configured entirely through **environment variables** (and an optional `~/.tlgrm/config.toml`). Only the API credentials are required; everything else has sensible defaults.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TG_API_ID` | Yes | — | Your Telegram `api_id` from [my.telegram.org](https://my.telegram.org). Must be an integer. |
| `TG_API_HASH` | Yes | — | Your Telegram `api_hash` from my.telegram.org. |
| `TG_SESSION_PATH` | No | `~/.tlgrm/tg_session` | Base path for the Telethon session file (`.session` appended automatically). |
| `TG_DOWNLOADS_DIR` | No | `~/.tlgrm/downloads` | Directory where incoming media is saved by the webhook listener. |
| `TG_PROXY_HOST` | No | — | SOCKS/HTTP proxy host. Used together with `TG_PROXY_PORT`. |
| `TG_PROXY_PORT` | No | — | SOCKS/HTTP proxy port. |
| `TG_PROXY_TYPE` | No | `socks5` | `socks5`, `socks4`, or `http`. |
| `TG_MTPROXY_HOST` | No | — | MTProxy host. Do not set this together with `TG_PROXY_*`. |
| `TG_MTPROXY_PORT` | No | — | MTProxy port. |
| `TG_MTPROXY_SECRET` | No | — | MTProxy secret. Never printed by the UI or error text. |
| `TG_UI_ENV` | No | `~/.tlgrm/ui.env` | Env file written by `tlgrm ui` settings. Process environment wins. |

If `TG_API_ID` or `TG_API_HASH` is missing, tlgrm prints setup instructions and exits with status `1`.

## Accounts (multi-login)

tlgrm supports multiple Telegram accounts, each a named login with its own
session under `~/.tlgrm/accounts/<name>.session`. Names are limited to
letters, digits, `.`, `_`, and `-` (1–64 characters, starting with a letter or
digit). Path-traversal names (`..`, slashes) are rejected, and the session path
is resolved and checked so it cannot leave the accounts directory.

```bash
tlgrm account add personal     # interactive login
tlgrm account add work
tlgrm account list             # shows accounts and which is default
tlgrm account use work         # set the default account
tlgrm -a personal chats        # run a command as a specific account
tlgrm account rename work job
tlgrm account remove personal  # log out + delete the session
```

Commands without `-a/--account` use the default account. An existing pre-0.3.0
login (`~/.tlgrm/tg_session.session`) is migrated to account `default`
automatically on first run.

> `--session PATH` / `TG_SESSION_PATH` still work as a low-level override but are
> deprecated in favor of named accounts.

## Background server

`tlgrm server` is an optional persistent process that owns **one hot connection
per account** over an owner-only Unix socket at `~/.tlgrm/server.sock`. It exists
to make several consumers coexist and to keep things fast.

```bash
tlgrm server start      # start it in the background (detached)
tlgrm server status     # {"running": true/false}
tlgrm server stop
tlgrm server restart
tlgrm server install    # run it on boot as a systemd user service
tlgrm server uninstall  # remove the service
tlgrm server logs       # recent service logs
```

When the server is running, **CLI commands automatically route through it** —
no per-command login handshake, so commands are near-instant — and when it
isn't, the CLI falls back to a direct one-shot connection. Because the server
is the single owner of each account's session, this **structurally eliminates
the `database is locked` / `AUTH_KEY_DUPLICATED` conflict** you'd otherwise hit
running the CLI alongside a long-running listener: there's only ever one
connection per account. With the server running you no longer need per-consumer
`--session` files.

`tlgrm account add` and `tlgrm login` always connect directly (they create the
session and need interactive input); everything else routes through the server
when it's up.

### Per-account listening (live)

With the server running, each account listens for incoming messages
independently, driven by **persisted, live-reconfigurable** config — every
command below takes effect immediately (no restart) and also persists:

```bash
tlgrm -a work listening enable          # start listening on this account
tlgrm -a work webhook set https://example.com/work --header "Authorization: Bearer X"
tlgrm -a work webhook show
tlgrm -a work filter listen mode allow  # allow = whitelist; block = blacklist
tlgrm -a work filter listen add @boss @work_group
tlgrm -a work filter listen remove @work_group
tlgrm -a work filter listen show
tlgrm -a work listening disable
```

A `filter listen` target is an `@username`, id, or phone, matched by the
message's **chat or sender**. `mode allow` forwards only matching messages;
`mode block` forwards everything except matches. Each account can point at its
own webhook, so you can route `work` and `personal` to different endpoints.

The webhook payload now includes an **`account`** object (`{"name", "id"}`)
identifying which account received the message — so a downstream knows where it
came from and which account to reply through.

> If no server is running, these commands still update the stored config; it
> takes effect when you next `tlgrm server start`.

### Scheduled messages

Schedule a message with Telegram's own server-side scheduling — it fires even
when the tlgrm server (or your machine) is offline:

```bash
tlgrm schedule send --target @x --text "Standup!" --at "2026-06-20 09:00"
tlgrm schedule send --target @x --text "ping" --in 2h     # 90s / 30m / 2h / 1d
tlgrm schedule list --target @x                            # what's queued
tlgrm schedule cancel --target @x --id 12345              # cancel by id
```

> Generic scheduling of arbitrary tasks (any command on a timer) is not yet
> available — only messages.

### Listening windows

Restrict an account to listen only during a daily time range — outside it,
incoming messages are ignored (the connection stays up, nothing is forwarded):

```bash
tlgrm -a work listening window set 09:00-17:00   # business hours
tlgrm -a work listening window set 22:00-06:00   # overnight range (wraps midnight)
tlgrm -a work listening window show
tlgrm -a work listening window clear
```

Times are local. Applies when listening via the server; takes effect live.

### Write guard (who an account may message)

The companion to the listen filter: a per-account **write filter** restricts
which chats/users an account is allowed to *send to*. A blocked target makes
outgoing commands (`send`, `reply`, `edit`, `forward`, `react`, `pin`,
`schedule`, `poll`) fail with a permission error **before anything is sent** —
a useful safety rail for the AI/MCP path.

```bash
tlgrm -a work filter write mode allow   # allow = only these may be messaged
tlgrm -a work filter write add @client_a @client_b
tlgrm -a work filter write show
# block mode (the default) instead blocks only the listed targets:
tlgrm -a work filter write mode block
tlgrm -a work filter write add @do_not_message
```

`mode block` (default) with an empty list means you can message anyone;
`mode allow` with a list means *only* those targets are allowed (so switching to
`allow` before adding any entries blocks **all** sends except to your own Saved
Messages). The guard applies in both direct and server mode and is read fresh per
command, so changes take effect immediately.

> The write guard matches a target **as you write it** (normalized `@name`/id),
> with no network lookup — so an `@username` and that chat's numeric id count as
> separate entries. To block a contact regardless of how it's addressed, list
> both forms.

Together, `filter listen` and `filter write` give a full per-contact
**listen × write** permission matrix — listen to someone but never reply, reply
but never listen, both, or neither.

## Proxies

The Telegram client opens a direct connection unless you set **one** of these:

- **SOCKS / HTTP:** `TG_PROXY_HOST` and `TG_PROXY_PORT` (optional `TG_PROXY_TYPE`, default `socks5`). Install a proxy library first: `pip install "python-socks[asyncio]"` (or `pysocks`).
- **MTProxy:** `TG_MTPROXY_HOST`, `TG_MTPROXY_PORT`, and `TG_MTPROXY_SECRET`. Telethon's built-in MTProxy connection is used. No extra package.

`tlgrm ui` can edit the same variables and stores them in `~/.tlgrm/ui.env` (mode `0600`). A value already exported in the environment wins over the file. The background server reads them when it opens a connection, so run `tlgrm server restart` after a change. `tlgrm server install` also snapshots whatever proxy variables are exported at install time into `~/.tlgrm/daemon.env`.

Setting both SOCKS and MTProxy is an error. Incomplete values name the missing variable and do not echo secrets.

## Setting variables

### Temporarily (current shell only)

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

### Permanently

Add the `export` lines to your shell profile:

- **bash:** `~/.bashrc`
- **zsh:** `~/.zshrc`
- **fish:** `set -Ux TG_API_ID 1234567`

### For the systemd daemon

systemd **user** services do **not** inherit your interactive shell's exports (`~/.bashrc` / `~/.zshrc`). So `tlgrm daemon install` snapshots the relevant settings from the installing shell into an owner-only env file at `~/.tlgrm/daemon.env`, which the unit loads via `EnvironmentFile=`. The captured variables include your STT config (`TG_STT_MODEL`, `TG_STT_DEVICE`, `TG_STT_LANGUAGE`, …), any cloud STT keys (`OPENAI_API_KEY`, …), `HF_TOKEN`, and `LD_LIBRARY_PATH` (so a GPU build keeps working under the service).

Recommended flow — export everything you want first, then install:

```bash
export TG_STT_MODEL=large-v3-turbo
export OPENAI_API_KEY=...        # only if using a cloud STT backend
tlgrm daemon install --webhook-url https://example.com/webhook
```

To change a setting later, edit `~/.tlgrm/daemon.env` and restart the service:

```bash
systemctl --user restart tlgrm-daemon
```

### Running the MCP server, listener, and CLI at the same time

A Telethon session is **single-process**: it's a SQLite file one connection holds, and the same auth key must not drive two live connections at once (Telegram would invalidate it). Historically this meant the MCP server, a listener, and the CLI couldn't share an account.

**The [background server](#background-server) resolves this completely.** Start it once (`tlgrm server start`, or `tlgrm server install` for a systemd service) and it becomes the **single owner** of each account's connection. Every other consumer routes through it:

- The **CLI** auto-detects the server and routes commands through it (falling back to a direct connection only when no server runs).
- **`tlgrm-mcp`** is a bridge to the server (and auto-spawns one if needed).
- The **listener** runs *inside* the server (per account; configure with `tlgrm listening …` / `tlgrm webhook …`).

So they all run at once on the same account with no `database is locked` and no `AUTH_KEY_DUPLICATED` — there is only ever one connection per account.

```bash
tlgrm login                 # default account
tlgrm account add work      # more accounts as needed
tlgrm server install        # run the server on boot (or: tlgrm server start)
# now use the CLI, point your MCP client at tlgrm-mcp, and configure listening —
# all routed through the one server.
```

> `--session PATH` / `TG_SESSION_PATH` still exist as a low-level override but are **deprecated** in favor of named accounts + the server.

## Files and directories

| Path | Created by | Contents |
|------|-----------|----------|
| `~/.tlgrm/` | tlgrm (on first run) | Application data root (owner-only, `0700`) |
| `~/.tlgrm/tg_session.session` | `tlgrm login` | **Sensitive** — your authenticated session |
| `~/.tlgrm/downloads/` | webhook listener | Auto-downloaded incoming media (owner-only, `0700`) |
| `~/.tlgrm/config.toml` | user (optional) | STT backend preferences |
| `~/.config/systemd/user/tlgrm-daemon.service` | `tlgrm daemon install` | systemd unit (written `0600`) |
| `~/.tlgrm/daemon.env` | `tlgrm daemon install` | env snapshot the service loads (owner-only `0600`) |

> **Security:** the session file grants full access to your Telegram account, and the systemd unit may embed webhook auth headers. `~/.tlgrm/` and the downloads directory are created owner-only (`0700`). Never commit session files to version control — the default `.gitignore` already excludes them.

## Changing storage locations

Point tlgrm at custom locations, e.g. an encrypted volume:

```bash
export TG_SESSION_PATH=/secure/vault/tlgrm/session
export TG_DOWNLOADS_DIR=/secure/vault/tlgrm/media
```

Parent directories are created automatically if they do not exist.

---

## Speech-to-text backends

tlgrm supports pluggable STT backends. When the `stt` extra is installed, the webhook daemon transcribes incoming voice notes automatically, and the `tlgrm transcribe` command is available for standalone use (no login required).

### Selection precedence

1. `TG_STT_BACKEND` environment variable (highest priority)
2. `backend` key in `[stt]` section of `~/.tlgrm/config.toml`
3. Cloud API key auto-detect (first found wins, in order: openai, groq, deepgram, elevenlabs, google)
4. `faster-whisper` — the default

### Environment variables

| Variable | Description |
|----------|-------------|
| `TG_STT_BACKEND` | Force a backend: `faster-whisper`, `whisper`, `openai`, `groq`, `deepgram`, `elevenlabs`, `google` |
| `TG_STT_MODEL` | Override the model name/size used by the backend |
| `TG_STT_DEVICE` | faster-whisper device: `auto` (default), `cpu`, or `cuda` |
| `TG_STT_COMPUTE` | faster-whisper compute type (default: `int8` on CPU, `float16` on GPU) |
| `TG_STT_LANGUAGE` | Force a language for whisper-family backends (e.g. `ar`, `en`); use `en-US`-style codes for Google |
| `OPENAI_API_KEY` | API key for the OpenAI backend |
| `GROQ_API_KEY` | API key for the Groq backend |
| `DEEPGRAM_API_KEY` | API key for the Deepgram backend |
| `ELEVENLABS_API_KEY` | API key for the ElevenLabs backend |
| `GOOGLE_API_KEY` | API key for the Google Speech-to-Text backend |

### Backends and install commands

| Backend | Type | Install | Notes |
|---------|------|---------|-------|
| `faster-whisper` | Local | `pip install "tlgrm[stt]"` | **Default.** Fast, low RAM. Auto-downloads models. GPU-aware. |
| `whisper` | Local | `pip install "tlgrm[stt-whisper]"` | Original OpenAI Whisper. Auto-downloads models. |
| `openai` | Cloud | *(no extra needed)* | Requires `OPENAI_API_KEY`. Audio sent to OpenAI. |
| `groq` | Cloud | *(no extra needed)* | Requires `GROQ_API_KEY`. Audio sent to Groq. |
| `deepgram` | Cloud | *(no extra needed)* | Requires `DEEPGRAM_API_KEY`. Audio sent to Deepgram. |
| `elevenlabs` | Cloud | *(no extra needed)* | Requires `ELEVENLABS_API_KEY`. Audio sent to ElevenLabs. |
| `google` | Cloud | *(no extra needed)* | Requires `GOOGLE_API_KEY`. Audio sent to Google. |

All local backends require **FFmpeg** on your system path.

### Model guidance

The default model is **`tiny`** — it is fast but has lower accuracy, especially for non-English audio. For good **Arabic or multilingual** transcription accuracy, use a larger model:

```bash
export TG_STT_MODEL=large-v3-turbo   # good balance of speed and accuracy (recommended)
export TG_STT_MODEL=large-v3         # highest accuracy
```

Models are downloaded automatically on first use and cached locally (`~/.cache/huggingface/hub/`).

To force a language and avoid auto-detection overhead:

```bash
export TG_STT_LANGUAGE=ar   # Arabic
export TG_STT_LANGUAGE=en   # English
```

### GPU acceleration

With `TG_STT_DEVICE=auto` (the default), `faster-whisper` uses an NVIDIA GPU when one is available and falls back to CPU automatically. Using a GPU requires the CUDA 12 runtime and cuDNN:

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Alternatively, a system CUDA toolkit (e.g. installed via your OS package manager) works too. Without the CUDA libraries, faster-whisper logs a warning and runs on CPU. To override device selection:

```bash
export TG_STT_DEVICE=cpu    # force CPU even if a GPU is present
export TG_STT_DEVICE=cuda   # force GPU (fails if no usable CUDA device)
export TG_STT_COMPUTE=float32   # override compute type (default: int8/float16)
```

The daemon pre-warms the STT model at startup so the first voice note transcribes without delay.

### Live STT control (`tlgrm stt`)

STT is a **server-global** resource (one shared, hot model set). Configure it
live — no restart — with the `stt` commands:

```bash
tlgrm stt status                         # backend, model, device, enabled?
tlgrm stt set --model large-v3-turbo     # change model (Arabic/multilingual)
tlgrm stt set --device cuda              # force GPU (or cpu/auto)
tlgrm stt set --backend faster-whisper
tlgrm stt disable                        # stop auto-transcribing incoming voice
tlgrm stt enable
```

When the server is running, a change drops its cached models so the next
transcription reloads with the new settings; the server also **pre-warms** the
model at startup so the first voice note isn't delayed. `stt disable` only turns
off automatic transcription of *incoming* messages — the `tlgrm transcribe`
command below always works. Settings persist in the `[stt]` section of
`~/.tlgrm/config.toml`.

### Standalone transcription

`tlgrm transcribe` does not require a Telegram login:

```bash
# Use the default backend (faster-whisper, tiny model)
tlgrm transcribe --file voice.ogg

# Use a large model for Arabic
tlgrm transcribe --file voice.ogg --model large-v3-turbo

# Use a cloud backend
tlgrm transcribe --file voice.ogg --backend openai   # needs OPENAI_API_KEY

# Specify a backend and model together
tlgrm transcribe --file voice.ogg --backend faster-whisper --model large-v3-turbo
```

### Config file (`~/.tlgrm/config.toml`)

You can persist STT preferences without environment variables:

```toml
[stt]
backend = "faster-whisper"
model = "large-v3-turbo"
```

Environment variables override config file values.

> **Privacy note:** Cloud backends transmit voice audio to a third-party provider. Review your chosen provider's privacy policy before enabling cloud transcription.
