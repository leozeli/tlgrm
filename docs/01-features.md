# Features

Everything tlgrm can do, in plain language. Each feature is tagged:

- 🟢 **Standalone** — works with just the CLI, no background service.
- 🔵 **Server** — needs the [background server](03-configuration.md#background-server) running (`tlgrm server start`). The server owns your Telegram connection so several things can use one account at once.

> Most one-off actions are 🟢 Standalone. Anything that *listens* continuously, runs an AI assistant, or needs to react in real time is 🔵 Server.

---

## Accounts & identity

### Personal account access — 🟢 Standalone
tlgrm acts as **you**, not a bot. It can read your chat history, see members, and message anyone you normally could — the same reach you have in the official app.

### Multiple accounts — 🟢 Standalone (one-off) · 🔵 Server (listen to all)
Log into several Telegram accounts and switch between them with `-a/--account`, just like the multi-account switcher in the mobile app. One-off commands work per account standalone; to *listen* to several accounts at the same time, run the server.
`tlgrm account add work` · `tlgrm -a work chats`

---

## Messaging

### Send, reply, edit, delete — 🟢 Standalone
Send text or files, reply to a specific message, edit your own messages, and delete messages. Voice notes, captions, silent sends, and scheduled sends are all supported.

### Forward, react, pin, mute — 🟢 Standalone
Forward messages between chats, react with emoji, pin/unpin messages, and mute/unmute chats.

### History & search — 🟢 Standalone
Pull recent messages from any chat, and search messages globally or within one chat.

### Groups & channels — 🟢 Standalone
Create groups or broadcast channels, add or remove members, and leave chats.

### Polls — 🟢 Standalone
Send polls (and quizzes) to a chat.

### Scheduled messages — 🟢 Standalone
Queue a message to send later — `--at "2026-06-20 09:00"` or `--in 2h` — and `list`/`cancel` what's queued. This uses **Telegram's own scheduling**, so it sends even when your computer is off.
`tlgrm schedule send --target @x --text "Standup!" --in 2h`

---

## Listening & automation (real-time)

### Incoming-message webhooks — 🔵 Server
Forward every incoming message to an HTTP endpoint in real time (for n8n, Make, a database, your own bot logic, etc.). Each account can point at its own webhook.
`tlgrm -a work webhook set https://example.com/hook`

### Per-account listening on/off — 🔵 Server
Turn listening on or off per account, live.
`tlgrm -a work listening enable`

### Listening windows — 🔵 Server
Only listen during a daily time range (e.g. business hours); messages outside it are ignored. Overnight ranges are supported.
`tlgrm -a work listening window set 09:00-17:00`

### Listen filters (allow / block) — 🔵 Server
Choose exactly which chats/people you listen to: an **allow** list (only these) or a **block** list (everyone except these), matched by chat or sender — reconfigurable live.
`tlgrm -a work filter listen add @noisygroup`

---

## Safety & permissions

### Write guard — 🟢 Standalone
Restrict which chats/people an account is allowed to *message*. A blocked target makes outgoing commands fail **before anything is sent** — a useful guard rail, especially when an AI assistant is driving. Combined with listen filters, you get a full per-contact "can listen × can write" matrix.
`tlgrm -a work filter write mode allow` · `tlgrm -a work filter write add @client`

---

## Speech-to-text

### Auto-transcribe incoming voice notes — 🔵 Server
Incoming voice notes and audio are transcribed automatically and the text is included in the webhook payload. Multilingual (great for Arabic + English), GPU-aware, and configurable live.
`tlgrm stt set --model large-v3-turbo --device cuda`

### Transcribe any audio file — 🟢 Standalone
Transcribe a local audio file on demand — no Telegram login required.
`tlgrm transcribe --file voice.ogg`

---

## AI assistants (MCP)

### Local dashboard — 🔵 Server
A localhost page for status, recent chats, sending, and listen/webhook settings. It uses the same background server as the CLI (and starts one if needed).
`tlgrm ui`

### MCP server — 🔵 Server
Expose your Telegram account to AI assistants (Claude, etc.) as tools — read-only by default, with opt-in write and destructive tiers. It's a thin bridge to the background server (which it auto-starts), so it coexists with the CLI and the listener on one connection. See **[MCP guide](04-mcp.md)**.

---

## Plumbing

### Background server — 🔵 Server
One persistent process owns a hot connection per account. The CLI, the MCP server, and the listener all route through it, so they run together with no `database is locked` conflict — and commands are near-instant. Run it on demand or install it as a service.
`tlgrm server start` · `tlgrm server install`

### Clean JSON output — 🟢 Standalone
Every command prints JSON to stdout (logs go to stderr), so output pipes straight into `jq` and scripts.
`tlgrm chats | jq '.[].name'`

### Run on boot (systemd) — 🔵 Server
Install the server (or the legacy webhook daemon) as a `systemd` user service so it starts automatically.
`tlgrm server install`

---

See the [command reference](02-commands.md) for exact flags, and the
[configuration guide](03-configuration.md) for setup details.
