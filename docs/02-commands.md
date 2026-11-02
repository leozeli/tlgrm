# Command Reference

Every tlgrm command prints **clean JSON to stdout**. Diagnostic logs and progress output go to **stderr**, so piping into `jq` or other tools works reliably:

```bash
tlgrm chats | jq '.[].name'
tlgrm history --target @username --limit 5 | jq '.[].text'
```

Messaging/read commands require an authenticated session (run `tlgrm login` first) and your [API credentials](03-configuration.md) in the environment. Management subcommands (`account`, `server`, `daemon`, and the config groups below) don't all need a session — e.g. `tlgrm account list` and `tlgrm server status` work without one.

## Targets

Many commands take a `--target`. It accepts any of:

- a **username**: `@username` (or `username`)
- a **numeric chat ID**: `738667936` (a purely numeric value is always treated as an ID)
- a **phone number**: `+15551234567` (must be a known contact)

---

## Accounts, server & management (0.3.0)

These command groups manage multiple accounts, the background server, and live
listening/filtering/STT/scheduling configuration. Full detail and rationale live
in [03-configuration.md](03-configuration.md); a quick map:

```bash
# Accounts (multi-login) — pick one per command with -a/--account
tlgrm account add [NAME]        # log in a new account
tlgrm account list              # accounts + default
tlgrm account use NAME          # set default
tlgrm account rename OLD NEW
tlgrm account remove NAME

# Background server (owns the connections; the CLI/MCP/listener route through it)
tlgrm server start [--foreground] | stop | restart | status
tlgrm server install | uninstall | logs   # run it as a systemd user service

# Local dashboard (needs the ui extra: pip install "tlgrm[ui]")
tlgrm ui [--host 127.0.0.1] [--port 8765]

# Per-account listening
tlgrm -a NAME listening enable | disable
tlgrm -a NAME listening window set 09:00-17:00 | show | clear
tlgrm -a NAME webhook set URL [--header "K: V"] | show | clear

# Per-contact permission filters (allow/block, matched by chat or sender)
tlgrm -a NAME filter listen show | mode allow|block | add TARGET… | remove TARGET… | clear
tlgrm -a NAME filter write  show | mode allow|block | add TARGET… | remove TARGET… | clear

# Speech-to-text (server-global, live)
tlgrm stt status | enable | disable | set [--backend B] [--model M] [--device auto|cpu|cuda]

# Scheduled messages (Telegram-native)
tlgrm schedule send --target T --text "…" --at "2026-06-20 09:00" | --in 2h
tlgrm schedule list --target T
tlgrm schedule cancel --target T --id ID…
```

---

## `tlgrm ui`

Open a local web dashboard for the common tasks: account status, recent chats and history, sending a text message, listening/webhook settings, and credential/proxy settings.

```bash
tlgrm ui                    # http://127.0.0.1:8765
tlgrm ui --port 9000
tlgrm ui --host 127.0.0.1
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host` | string | `127.0.0.1` | Bind address. Any other value prints a warning. |
| `--port` | int | `8765` | TCP port |

Requires the `ui` extra (`pip install "tlgrm[ui]"`). The page talks to the background server (and starts one if needed), so it follows the same permission tiers and write guard as the CLI. It does not print session paths, `api_hash`, phone numbers, or webhook bearer tokens in its log lines.

---

## `tlgrm login`

Interactively authenticate your personal Telegram account and store a reusable session.

```bash
tlgrm login
```

Prompts for your phone number, the login code (sent in-app), and 2FA password if enabled. Saves the session to `~/.tlgrm/tg_session.session`.

---

## `tlgrm whoami`

Show information about the currently authenticated account.

```bash
tlgrm whoami
```

**Output:**

```json
{
  "id": 738667936,
  "first_name": "Ali",
  "last_name": "",
  "username": "ali",
  "phone": "+15551234567"
}
```

---

## `tlgrm chats`

List your most recent chats/dialogs.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--limit` | int | `20` | Maximum number of chats to return |

```bash
tlgrm chats --limit 10
tlgrm chats | jq '.[] | select(.unread_count > 0)'
```

**Output:** a JSON array of:

```json
[
  {
    "id": 738667936,
    "name": "Muneerah",
    "username": "mneraah",
    "type": "user",
    "unread_count": 2
  }
]
```

`type` is one of `user`, `group`, `channel`, or `unknown`.

---

## `tlgrm history`

Fetch recent messages from a chat.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target` | string | *(required)* | Chat to read |
| `--limit` | int | `10` | Number of messages to fetch |
| `--offset-id` | int | — | Fetch messages older than this message ID |

```bash
tlgrm history --target @username --limit 5
tlgrm history --target @username --limit 20 --offset-id 137480
```

**Output:** a JSON array (newest first) of:

```json
[
  {
    "id": 137480,
    "date": "2026-06-14T06:11:59+00:00",
    "sender_id": 738667936,
    "sender_name": "Muneerah",
    "text": "See you soon!",
    "media_type": null
  }
]
```

`media_type` is `null` or one of `photo`, `voice`, `video`, `audio`, `document`, `other`.

---

## `tlgrm search`

Search messages globally or within a specific chat.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` | string | *(required)* | Search keywords |
| `--target` | string | — | Limit search to this chat (omit for global) |
| `--limit` | int | `20` | Maximum results to return |

```bash
# Global search
tlgrm search --query "meeting notes"

# Search within a chat
tlgrm search --query "invoice" --target @workgroup --limit 5
```

**Output:** a JSON array of message objects (same shape as `history`).

---

## `tlgrm members`

List the participants of a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Group/channel to inspect |

```bash
tlgrm members --target @somegroup
tlgrm members --target @somegroup | jq 'length'   # member count
```

**Output:** a JSON array of:

```json
[
  {
    "id": 738667936,
    "first_name": "Muneerah",
    "last_name": "",
    "username": "mneraah",
    "phone": "",
    "is_bot": false
  }
]
```

> Visibility of fields like `phone` depends on the other user's privacy settings.

---

## `tlgrm user-info`

Show profile information for a user.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | User to look up |

```bash
tlgrm user-info --target @username
```

**Output:**

```json
{
  "id": 738667936,
  "first_name": "Muneerah",
  "last_name": "",
  "username": "mneraah",
  "phone": "",
  "is_bot": false,
  "bio": ""
}
```

---

## `tlgrm chat-info`

Show information about a chat or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat/channel to inspect |

```bash
tlgrm chat-info --target @somegroup
```

**Output:**

```json
{
  "id": -1001234567890,
  "title": "My Group",
  "username": "somegroup",
  "type": "group",
  "members_count": 42,
  "description": "..."
}
```

---

## `tlgrm download`

Download media from a specific message.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat containing the message |
| `--message-id` | int | Yes | ID of the message with media |
| `--output` | path | No | Output file or directory (defaults to `TG_DOWNLOADS_DIR`) |

```bash
tlgrm download --target @username --message-id 137480
tlgrm download --target @username --message-id 137480 --output ~/Downloads/
```

**Output:**

```json
{ "success": true, "path": "/home/ali/.tlgrm/downloads/photo_137480.jpg" }
```

---

## `tlgrm send`

Send a text message, a file/media, or a voice note.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Recipient (see [Targets](#targets)) |
| `--text` | string | One of | Text body. Required unless `--file` is given. |
| `--file` | path | One of | Path to a file/media to send. Required unless `--text` is given. |
| `--caption` | string | No | Caption for a file |
| `--voice` | flag | No | Send the file as a voice note |
| `--reply-to` | int | No | Reply to this message ID |
| `--silent` | flag | No | Send without notification |

```bash
# Text
tlgrm send --target @username --text "Hello!"

# Image with caption
tlgrm send --target @username --file ./photo.jpg --caption "Sunset"

# Voice note
tlgrm send --target @username --file ./audio.ogg --voice

# Silent reply
tlgrm send --target @username --text "Got it" --reply-to 137480 --silent
```

**Output:**

```json
{
  "success": true,
  "message_id": 137480,
  "to": "@username",
  "text": "Hello!",
  "media_type": null
}
```

`media_type` is `null` for text, `"file"` for files, or `"voice"` for voice notes.

---

## `tlgrm reply`

Reply to a specific message.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat containing the message |
| `--message-id` | int | Yes | ID of the message to reply to |
| `--text` | string | One of | Reply text |
| `--file` | path | One of | File to send as the reply |
| `--caption` | string | No | Caption for the file |
| `--voice` | flag | No | Send the file as a voice note |
| `--silent` | flag | No | Send without notification |

```bash
tlgrm reply --target @username --message-id 137480 --text "Thanks!"
```

**Output:** same shape as `send`.

---

## `tlgrm edit`

Edit a message you previously sent.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat containing the message |
| `--message-id` | int | Yes | ID of the message to edit |
| `--text` | string | Yes | New text content |

```bash
tlgrm edit --target @username --message-id 137480 --text "Edited text"
```

**Output:**

```json
{ "success": true, "message_id": 137480, "to": "@username", "text": "Edited text" }
```

---

## `tlgrm read`

Mark a chat (or messages up to a specific ID) as read.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat to mark as read |
| `--max-id` | int | No | Mark up to this message ID (omit to mark all) |

```bash
tlgrm read --target @username
tlgrm read --target @username --max-id 137480
```

**Output:** `{ "success": true }`

---

## `tlgrm forward`

Forward one or more messages from one chat to another.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--from` | string | Yes | Source chat |
| `--to` | string | Yes | Destination chat |
| `--message-ids` | int… | Yes | One or more message IDs (space-separated) |

```bash
tlgrm forward --from @username --to @otheruser --message-ids 137480 137481
```

**Output:**

```json
{ "success": true, "forwarded_ids": [137480, 137481], "to": "@otheruser" }
```

---

## `tlgrm react`

React to a message with an emoji. Pass an empty string to clear an existing reaction.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat containing the message |
| `--message-id` | int | Yes | ID of the message |
| `--emoji` | string | Yes | Emoji to react with (empty string clears the reaction) |
| `--big` | flag | No | Send as a big/animated reaction |

```bash
tlgrm react --target @username --message-id 137480 --emoji "👍"
tlgrm react --target @username --message-id 137480 --emoji ""   # clear reaction
```

**Output:**

```json
{ "success": true, "message_id": 137480, "emoji": "👍" }
```

---

## `tlgrm pin`

Pin a message in a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat |
| `--message-id` | int | Yes | ID of the message to pin |
| `--notify` | flag | No | Notify members of the pin |

```bash
tlgrm pin --target @somegroup --message-id 137480
tlgrm pin --target @somegroup --message-id 137480 --notify
```

**Output:** `{ "success": true, "message_id": 137480 }`

---

## `tlgrm unpin`

Unpin a message, or unpin all messages if `--message-id` is omitted.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat |
| `--message-id` | int | No | ID of the message to unpin (omit to unpin all) |

```bash
tlgrm unpin --target @somegroup --message-id 137480
tlgrm unpin --target @somegroup   # unpins all
```

**Output:** `{ "success": true }`

---

## `tlgrm mute`

Mute notifications for a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat to mute |
| `--duration` | int | No | Seconds to mute (default: forever) |

```bash
tlgrm mute --target @username
tlgrm mute --target @username --duration 3600   # mute for 1 hour
```

**Output:** `{ "success": true }`

---

## `tlgrm unmute`

Unmute a previously muted chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat to unmute |

```bash
tlgrm unmute --target @username
```

**Output:** `{ "success": true }`

---

## `tlgrm saved`

Send a message or file to your own **Saved Messages** (the "Saved" chat in Telegram).

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--text` | string | One of | Text to save |
| `--file` | path | One of | File to save |
| `--caption` | string | No | Caption for the file |
| `--voice` | flag | No | Send the file as a voice note |

```bash
tlgrm saved --text "Remember to review this later"
tlgrm saved --file ./report.pdf --caption "Q2 report"
```

**Output:** same shape as `send`.

---

## `tlgrm delete`

Delete one or more messages.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat containing the messages |
| `--message-ids` | int… | Yes | One or more message IDs (space-separated) |

```bash
tlgrm delete --target @username --message-ids 137480 137481 137482
```

**Output:**

```json
{ "success": true, "deleted_ids": [137480, 137481, 137482], "from": "@username" }
```

---

## `tlgrm create-group`

Create a new group or broadcast channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--title` | string | Yes | Group or channel title |
| `--members` | string… | No | Initial members (usernames, IDs, or phones) |
| `--channel` | flag | No | Create a broadcast channel instead of a group |

```bash
tlgrm create-group --title "Project Team" --members @alice @bob
tlgrm create-group --title "Announcements" --channel
```

**Output:**

```json
{ "success": true, "id": -1001234567890, "title": "Project Team", "type": "group" }
```

---

## `tlgrm add-members`

Add members to an existing group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Group/channel to add members to |
| `--members` | string… | Yes | Members to add (usernames, IDs, or phones) |

```bash
tlgrm add-members --target @somegroup --members @alice @bob
```

**Output:** `{ "success": true, "added": ["@alice", "@bob"] }`

---

## `tlgrm remove-members`

Remove members from a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Group/channel |
| `--members` | string… | Yes | Members to remove (usernames, IDs, or phones) |

```bash
tlgrm remove-members --target @somegroup --members @alice
```

**Output:** `{ "success": true, "removed": ["@alice"] }`

---

## `tlgrm leave`

Leave a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Group/channel to leave |

```bash
tlgrm leave --target @somegroup
```

**Output:** `{ "success": true }`

---

## `tlgrm schedule`

Schedule a text message to be sent at a future time.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Recipient |
| `--text` | string | Yes | Text of the scheduled message |
| `--at` | string | Yes | When to send: seconds from now (integer) or ISO-8601 datetime |

```bash
# 10 minutes from now
tlgrm schedule --target @username --text "Happy birthday!" --at 600

# Exact time
tlgrm schedule --target @username --text "Happy birthday!" --at "2026-06-15T09:00:00"
```

**Output:**

```json
{ "success": true, "message_id": 137481, "scheduled_at": "2026-06-15T09:00:00+00:00" }
```

---

## `tlgrm poll`

Send a poll or quiz to a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | Yes | Chat to send the poll to |
| `--question` | string | Yes | Poll question |
| `--option` | string | Yes (×2+) | Answer option (repeatable; at least two) |
| `--multiple` | flag | No | Allow multiple answers |
| `--quiz` | flag | No | Make this a quiz (one correct answer) |
| `--correct` | int | No | Index (0-based) of the correct answer (quiz only) |

```bash
# Regular poll
tlgrm poll --target @somegroup --question "Lunch?" --option "Pizza" --option "Salad" --option "Tacos"

# Quiz
tlgrm poll --target @somegroup --question "Capital of France?" \
           --option "London" --option "Paris" --option "Berlin" \
           --quiz --correct 1
```

**Output:** `{ "success": true, "message_id": 137482 }`

---

## `tlgrm transcribe`

Transcribe an audio file using the configured speech-to-text backend. **No Telegram login required.**

| Flag | Required | Description |
|------|----------|-------------|
| `--file` | Yes | Path to the audio file |
| `--backend` | No | Override backend: `faster-whisper`, `whisper`, `openai`, `groq`, `deepgram`, `elevenlabs`, `google` |
| `--model` | No | Override the model (e.g. `large-v3-turbo`, `base`) |

```bash
# Default (faster-whisper, tiny model)
tlgrm transcribe --file voice.ogg

# Large model for Arabic / multilingual accuracy
tlgrm transcribe --file voice.ogg --model large-v3-turbo

# Cloud backend
tlgrm transcribe --file voice.ogg --backend openai   # needs OPENAI_API_KEY

# Force a language
TG_STT_LANGUAGE=ar tlgrm transcribe --file voice.ogg
```

**Output:**

```json
{ "success": true, "backend": "faster-whisper", "text": "..." }
```

Local backends require their extra installed (e.g. `tlgrm[stt]`); cloud backends require their API key. See [Configuration → Speech-to-text](03-configuration.md#speech-to-text-backends).

---

## `tlgrm listen`

Listen for **incoming** messages in the foreground and optionally forward them to a webhook.

| Flag | Type | Description |
|------|------|-------------|
| `--webhook-url` | URL | http(s) endpoint to POST each message to (omit to print to console) |
| `--webhook-header` | `"Name: Value"` | Custom header to include in the POST (repeatable) |
| `--only` | `CHAT` | Whitelist: only forward messages whose chat or sender matches (`@username`, id, or phone). Repeatable / comma-separated. |
| `--ignore` | `CHAT` | Blacklist: never forward messages whose chat or sender matches. Repeatable / comma-separated. |
| `--verbose` | flag | Print full JSON payloads and debug logs to stderr |

```bash
# Forward to a webhook
tlgrm listen --webhook-url https://example.com/webhook \
             --webhook-header "Authorization: Bearer SECRET"

# Development: print to console
tlgrm listen --verbose
```

Runs until interrupted (`Ctrl+C`). Logs go to **stderr**. Incoming media is auto-downloaded to `TG_DOWNLOADS_DIR`. Self-destructing (TTL) media is skipped; the payload includes `"media.self_destruct": true`.

See [Webhook & Daemon Guide](05-webhook-guide.md) for the full payload schema.

---

## `tlgrm daemon`

Manage tlgrm as a background `systemd` **user** service. Requires `systemd`/`systemctl`.

### `tlgrm daemon install`

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--webhook-url` | URL | Yes | http(s) endpoint to forward messages to |
| `--webhook-header` | `"Name: Value"` | No | Custom header (repeatable) |
| `--only` | `CHAT` | No | Whitelist chats/users to listen to (repeatable / comma-separated) |
| `--ignore` | `CHAT` | No | Blacklist chats/users to ignore (repeatable / comma-separated) |
| `--verbose` | flag | No | Enable verbose logging in the daemon |

```bash
tlgrm daemon install --webhook-url https://example.com/webhook \
                     --webhook-header "Authorization: Bearer YOUR_TOKEN"
```

Writes a unit to `~/.config/systemd/user/tlgrm-daemon.service` (owner-only, `0600`), reloads systemd, enables, and starts the service.

### `tlgrm daemon status`

```bash
tlgrm daemon status
```

**Output:**

```json
{
  "success": true,
  "installed": true,
  "service": "tlgrm-daemon",
  "active_state": "active",
  "sub_state": "running",
  "enabled": true,
  "load_state": "loaded",
  "main_pid": 48213,
  "unit_file_path": "/home/ali/.config/systemd/user/tlgrm-daemon.service"
}
```

### `tlgrm daemon logs`

```bash
tlgrm daemon logs
```

Prints the 30 most recent journal lines. For a live tail:

```bash
journalctl --user -u tlgrm-daemon -f
```

### `tlgrm daemon uninstall`

```bash
tlgrm daemon uninstall
```

Stops, disables, and removes the service and its unit file.

---

## MCP tools

The `tlgrm-mcp` stdio MCP server exposes Telegram operations as tools to any MCP-compatible AI assistant. Requires `pip install "tlgrm[mcp]"` and a prior `tlgrm login`. See [the MCP guide](04-mcp.md) for client configuration.

> `tlgrm-mcp` is a **bridge** to the [background server](03-configuration.md#background-server): tool calls route through the one owned connection (which enforces tiers and the write guard), and a server is auto-spawned if none is running — so running the MCP server, the daemon, and the CLI together is safe (one connection, no `database is locked`). Pass `--account NAME` to act as a specific account.

### Read-only tier (default — no flags needed)

| Tool | Equivalent CLI |
|------|---------------|
| `whoami` | `tlgrm whoami` |
| `list_chats` | `tlgrm chats` |
| `get_history` | `tlgrm history` |
| `search_messages` | `tlgrm search` |
| `get_members` | `tlgrm members` |
| `user_info` | `tlgrm user-info` |
| `chat_info` | `tlgrm chat-info` |
| `download_media` | `tlgrm download` |

### Write tier (`--allow-write`)

| Tool | Equivalent CLI |
|------|---------------|
| `send_message` | `tlgrm send` |
| `edit_message` | `tlgrm edit` |
| `mark_read` | `tlgrm read` |
| `react` | `tlgrm react` |
| `forward_messages` | `tlgrm forward` |
| `pin` | `tlgrm pin` |
| `unpin` | `tlgrm unpin` |
| `mute` | `tlgrm mute` |
| `unmute` | `tlgrm unmute` |
| `create_group` | `tlgrm create-group` |
| `add_members` | `tlgrm add-members` |
| `schedule_message` | `tlgrm schedule` |
| `send_poll` | `tlgrm poll` |

### Destructive tier (`--allow-write --allow-destructive`)

| Tool | Equivalent CLI |
|------|---------------|
| `delete_messages` | `tlgrm delete` |
| `leave_chat` | `tlgrm leave` |
| `remove_members` | `tlgrm remove-members` |

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Missing/invalid credentials, or not authorized (`tlgrm login` required) |

Per-operation failures (e.g. an invalid target) are reported as `{"success": false, "error": "..."}` in the JSON output while still exiting `0`.
