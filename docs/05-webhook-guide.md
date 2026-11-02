# Webhook & Daemon Guide

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is not affiliated with, endorsed by, or sponsored by Telegram.

One of tlgrm's most powerful features is acting as a real-time bridge that forwards your **incoming** Telegram messages to an external HTTP webhook. This is useful for connecting your personal Telegram account to a database or workflow automation system (n8n, Make, custom APIs, etc.).

When a message arrives, tlgrm:

1. Builds a structured JSON payload (sender, chat, message, media).
2. Downloads any attached media to `TG_DOWNLOADS_DIR`.
3. Optionally transcribes voice/audio using the configured [STT backend](03-configuration.md#speech-to-text-backends) (if the `stt` extra or a cloud API key is available).
4. POSTs the payload to your webhook URL (with retries), or prints it to stdout if no URL is set.

Logs and progress output go to **stderr**, keeping stdout clean.

> Only **incoming** messages trigger the webhook — your own outgoing messages are ignored.

---

## Foreground mode

Run the listener in your terminal to test an endpoint:

```bash
tlgrm listen --webhook-url https://your-server.com/webhook \
             --webhook-header "Authorization: Bearer YOUR_SECRET_TOKEN"
```

Without `--webhook-url`, payloads are printed to stdout instead of forwarded — handy for development:

```bash
tlgrm listen --verbose
```

### Custom headers

Secure or tag your endpoint by passing one or more `--webhook-header` options (repeatable):

```bash
tlgrm listen --webhook-url https://example.com/webhook \
             --webhook-header "X-Auth-Token: secret123" \
             --webhook-header "X-Client-ID: personal-bot"
```

Header values are redacted from logs. The receiver must check `Authorization` (or whichever secret header you send) and reject requests that do not match — tlgrm only attaches the header; it does not authenticate callers for you.

---

## Filtering which chats to listen to

By default the listener processes every incoming message. Two repeatable options
let you narrow that down — they work in both foreground (`tlgrm listen`) and
daemon (`tlgrm daemon install`) mode:

- `--only CHAT` — **whitelist.** Forward *only* messages that match. Everything
  else is ignored.
- `--ignore CHAT` — **blacklist.** Never forward messages that match.

Each `CHAT` is an `@username`, a numeric chat/user id, or a phone number. Both
options are repeatable and accept comma-separated lists, so these are equivalent:

```bash
tlgrm listen --ignore @noisygroup --ignore @spammer
tlgrm listen --ignore @noisygroup,@spammer
```

A message **matches** if its **chat** or its **sender** matches the target. That
means `--ignore @someone` drops both their direct messages *and* their messages
inside groups, and `--only @myboss` forwards their messages wherever they appear.

```bash
# Only forward messages from one work group and one person
tlgrm listen --webhook-url https://example.com/hook \
             --only @work_group --only @manager

# Forward everything except two noisy chats
tlgrm listen --webhook-url https://example.com/hook \
             --ignore @announcements --ignore -1001234567890
```

If both are given, a message must pass the whitelist **and** not be on the
blacklist. Targets are resolved once at startup; the filter is applied **before**
any media is downloaded, so ignored chats cost nothing. For ids, use the value
shown by `tlgrm chats` (supergroups/channels look like `-100…`).

The same flags work for the daemon:

```bash
tlgrm daemon install --webhook-url https://example.com/hook \
                     --ignore @announcements,@noisygroup
```

---

## Background daemon (systemd)

Instead of keeping a terminal open, run tlgrm as a persistent `systemd` **user** service. Requires `systemd`/`systemctl`.

### 1. Install & start

Builds the unit at `~/.config/systemd/user/tlgrm-daemon.service` (written owner-only, `0600`, since it may embed auth headers), enables start-on-boot, and starts the process:

```bash
tlgrm daemon install --webhook-url https://your-server.com/webhook \
                     --webhook-header "Authorization: Bearer YOUR_TOKEN"
```

> The webhook URL and headers are validated before the unit is written (http or https only; no whitespace, control characters, or quotes that could corrupt the unit file). The same URL check is applied to `tlgrm listen` and `tlgrm webhook set`. Header values are redacted in the install command's JSON result; the unit file still stores them and is mode `0600`. The receiver must validate `Authorization`.

If the STT extra is installed, the daemon pre-warms the model at startup so the first voice note transcribes without delay.

### 2. Check status

```bash
tlgrm daemon status
```

### 3. Read logs

```bash
tlgrm daemon logs
```

Shows the 30 most recent journal entries. For a live tail, use `journalctl` directly:

```bash
journalctl --user -u tlgrm-daemon -f
```

### 4. Stop & uninstall

```bash
tlgrm daemon uninstall
```

> **Daemon environment:** systemd user services don't inherit your shell, so `tlgrm daemon install` snapshots your relevant settings — STT model, GPU library path, cloud API keys — into an owner-only `~/.tlgrm/daemon.env` that the unit loads. Export what you want (e.g. `TG_STT_MODEL=large-v3-turbo`) **before** installing, or edit that file and `systemctl --user restart tlgrm-daemon`. See [03-configuration.md](03-configuration.md#for-the-systemd-daemon).

> **Run it alongside the MCP server or CLI:** a Telethon session is single-process, so give the daemon its **own** session — log it in (`tlgrm --session ~/.tlgrm/daemon.session login`) and `export TG_SESSION_PATH=~/.tlgrm/daemon.session` before `tlgrm daemon install` (it's captured into `daemon.env`). Then the daemon, an MCP server, and your CLI run together without `database is locked`. See [running them concurrently](03-configuration.md#running-the-mcp-server-listener-and-cli-at-the-same-time).

---

## Webhook payload schema

Each webhook POST sends a JSON body with this structure:

```json
{
  "event": "new_message",
  "timestamp": "2026-06-14T06:12:00.123456+00:00",
  "account": {
    "name": "work",
    "id": 31193026
  },
  "message": {
    "id": 137475,
    "text": "Check this out!",
    "date": "2026-06-14T06:11:59+00:00",
    "reply_to_msg_id": null
  },
  "chat": {
    "id": 738667936,
    "name": "Muneerah",
    "username": "mneraah",
    "type": "user"
  },
  "sender": {
    "id": 738667936,
    "first_name": "Muneerah",
    "last_name": "",
    "username": "mneraah",
    "phone": "+601****6023",
    "display_name": "Muneerah"
  },
  "media": {
    "present": true,
    "type": "voice",
    "local_path": "/home/ali/.tlgrm/downloads/voice_137475.ogg",
    "transcription": "Hello, I will be home in ten minutes!"
  }
}
```

### Field reference

| Field | Type | Notes |
|-------|------|-------|
| `event` | string | Always `"new_message"` |
| `timestamp` | string | UTC ISO-8601 time the event was processed |
| `account` | object | `{name, id}` of the tlgrm account that received the message (present when listening via the server) |
| `message.id` | int | Telegram message ID |
| `message.text` | string | Message text (empty string for media-only messages) |
| `message.date` | string | ISO-8601 send time |
| `message.reply_to_msg_id` | int or null | ID of the message being replied to, if any |
| `chat.type` | string | `user`, `group`, `channel`, or `unknown` |
| `sender.*` | object | Sender identity fields (may be empty per privacy settings). `phone` is masked (`+601****6023`), never the raw number |
| `media.present` | bool | Whether the message has media |
| `media.type` | string or null | `photo`, `voice`, `video`, `audio`, `document`, or `other` |
| `media.local_path` | string or null | Absolute path to the downloaded file |
| `media.self_destruct` | bool | `true` if the media was self-destructing (TTL) and was therefore skipped |
| `media.transcription` | string or null | STT transcription of voice/audio (see [STT backends](03-configuration.md#speech-to-text-backends)) |

> If the `stt` extra is installed or a cloud API key is set, incoming voice notes and audio are transcribed automatically and the text appears in `media.transcription`. Without any STT backend, the field is `null` and everything else works unchanged.

For better Arabic or multilingual accuracy, set a larger model before starting the daemon:

```bash
export TG_STT_MODEL=large-v3-turbo
tlgrm daemon install --webhook-url https://example.com/webhook
```

---

## Delivery behavior

- Forwarding runs as a background task so it never blocks the listener.
- Failed POSTs are retried up to 3 times with exponential backoff, then logged and dropped.
- A `2xx` response is considered success; anything else is logged as an error (to stderr).

> tlgrm does not currently sign webhook payloads (e.g. HMAC). If your endpoint is public, send a secret header such as `Authorization` and validate it on the receiver — reject any request that does not match.
