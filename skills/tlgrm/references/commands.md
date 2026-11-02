# tlgrm command & tool cheat-sheet

All CLI commands print JSON. `--target` = `@username` | numeric id | phone.
Add `-a NAME` to any command to act as a specific account (default account otherwise);
`tlgrm account list` shows them.

## Read (always available — no special flags)

- `tlgrm whoami` — logged-in account
- `tlgrm chats [--limit 20]` — recent dialogs (id, name, type, unread_count)
- `tlgrm history --target T [--limit 10] [--offset-id ID]` — messages (newest first)
- `tlgrm search --query Q [--target T] [--limit 20]` — global or in-chat search
- `tlgrm members --target T` — participants
- `tlgrm user-info --target T` / `tlgrm chat-info --target T` — profile / chat details
- `tlgrm download --target T --message-id ID [--output PATH]` — download media

## Write (CLI always; MCP needs `--allow-write`)

- `tlgrm send --target T (--text "..." | --file PATH [--voice]) [--caption ...] [--reply-to ID] [--silent]`
- `tlgrm reply --target T --message-id ID (--text "..." | --file PATH) [--caption ...] [--voice] [--silent]`
- `tlgrm edit --target T --message-id ID --text "..."`
- `tlgrm read --target T [--max-id ID]` — mark as read
- `tlgrm forward --from A --to B --message-ids ID [ID ...]`
- `tlgrm react --target T --message-id ID --emoji E [--big]` — empty emoji clears reaction
- `tlgrm pin --target T --message-id ID [--notify]`
- `tlgrm unpin --target T [--message-id ID]` — omit ID to unpin all
- `tlgrm mute --target T [--duration SECONDS]` — default: forever
- `tlgrm unmute --target T`
- `tlgrm saved (--text "..." | --file PATH) [--caption ...] [--voice]` — send to Saved Messages
- `tlgrm create-group --title TITLE [--members ...] [--channel]`
- `tlgrm add-members --target T --members ...`
- `tlgrm schedule send --target T --text TEXT (--at "ISO8601" | --in 2h)` — schedule a message
- `tlgrm schedule list --target T` / `tlgrm schedule cancel --target T --id ID [ID ...]`
- `tlgrm poll --target T --question Q --option A --option B ... [--multiple] [--quiz --correct N]`

## Destructive (CLI always; MCP needs `--allow-write --allow-destructive`)

- `tlgrm delete --target T --message-ids ID [ID ...]`
- `tlgrm leave --target T`
- `tlgrm remove-members --target T --members ...`

## Utilities

- `tlgrm transcribe --file PATH [--backend B] [--model M]` — speech-to-text on a file (no login needed)

## Management (user-configured — don't run on your own initiative)

These set up *how* tlgrm runs, not message actions. Only touch them if the user
explicitly asks, and confirm first.

- `tlgrm account add|list|use|rename|remove` — multiple Telegram logins
- `tlgrm server start|stop|status|restart|install|uninstall|logs` — the background server that owns the connection (the CLI/MCP route through it automatically)
- `tlgrm listening enable|disable` · `tlgrm listening window set 09:00-17:00` — per-account real-time listening
- `tlgrm webhook set URL [--header "N: V"]|show|clear` — where incoming messages are forwarded
- `tlgrm filter listen|write show|mode allow|block|add T…|remove T…|clear` — who an account may listen to / message
- `tlgrm stt status|enable|disable|set [--model M] [--device cpu|cuda]` — transcription settings
- `tlgrm listen …` / `tlgrm daemon …` — legacy standalone listener (superseded by the server)

## MCP tools by tier

### Read-only (default — no flags)
`whoami`, `list_chats`, `search_messages`, `get_history`, `get_members`,
`user_info`, `chat_info`, `download_media`.

### Write tier (`--allow-write`)
`send_message`, `edit_message`, `mark_read`, `react`, `forward_messages`,
`pin`, `unpin`, `mute`, `unmute`, `create_group`, `add_members`,
`schedule_message`, `send_poll`.

### Destructive tier (`--allow-write --allow-destructive`)
`delete_messages`, `leave_chat`, `remove_members`.

## Local dashboard

`tlgrm ui` (extra: `tlgrm[ui]`) opens http://127.0.0.1:8765 — status, chats, send, listening. Same server and write guard as the CLI. Prefer the CLI or MCP when you are driving Telegram yourself.

## Output

Success for write ops: `{"success": true, ...}`. Failures: `{"success": false, "error": "..."}`.
