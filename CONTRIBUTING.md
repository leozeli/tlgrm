# Contributing to tlgrm

Thanks for your interest in contributing! tlgrm is an unofficial, MIT-licensed command-line client and webhook daemon for Telegram. Contributions of all kinds — bug reports, features, docs, and fixes — are welcome.

## Code of conduct

Be respectful and constructive. Assume good faith, keep discussions on-topic, and help make the project welcoming to everyone.

## Getting set up

```bash
# Clone your fork
git clone https://github.com/<your-username>/tlgrm.git
cd tlgrm

# Install with the dev tools + all runtime extras (uv recommended)
uv sync --extra dev --extra all

# Install the pre-commit hooks (ruff format + lint run on every commit)
uv run prek install

# Provide your own Telegram API credentials for manual testing
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```


## Project layout

```
src/tlgrm/
├── cli.py            # argparse entry point and command dispatch
├── core/             # async library: client, messages, chats, users, serialize, errors
├── mcp/              # MCP server (tlgrm-mcp): server.py, __main__.py
├── ui/               # local web dashboard (`tlgrm ui`)
├── stt/             # pluggable speech-to-text backends (local + cloud)
├── webhooks.py       # real-time listener and webhook forwarding
├── config.py         # environment-based configuration and credentials
└── daemon.py         # systemd user-service management
skills/tlgrm/         # Claude Code skill
docs/                 # user documentation
```

## Making changes

1. **Open an issue first** for anything non-trivial, so we can agree on the approach.
2. Create a branch: `git checkout -b feature/short-description`.
3. Keep changes focused and match the surrounding code style.
4. Update the relevant docs in `docs/` and the `README.md` when behavior changes.
5. Run the checks (see **Code quality** below) and verify the CLI works:

   ```bash
   TG_API_ID=1 TG_API_HASH=x python -c "import tlgrm.cli"
   tlgrm --help
   ```

## Code quality

The project uses **ruff** (linter + formatter), **mypy** and **pyrefly** (two
type checkers), and **prek** (a fast `pre-commit` runner) — all installed via
`uv sync --extra dev`. The source is fully typed and both checkers run clean;
keep it that way.

```bash
uv run ruff format src tests      # auto-format (or: ./scripts/format.sh)
uv run ruff check src tests --fix # lint + autofix
uv run mypy src                   # type-check (strict)
uv run pyrefly check              # type-check (Pyrefly, fast)
uv run pytest                     # run the test suite (parallel)
```

Both type checkers are kept passing. Telethon and the optional STT/MCP backends
are treated as untyped (mypy's `ignore_missing_imports` / Pyrefly's
`replace-imports-with-any`) because their inline types are imprecise.

`prek install` (run during setup) wires ruff format + lint to run automatically
on every commit; run all hooks across the repo with `uv run prek run --all-files`.
Tool configuration lives in `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`) and
`.pre-commit-config.yaml`.

## Coding conventions

- Target **Python 3.10+**.
- Commands print **structured JSON** to stdout; errors use `{"success": false, "error": "..."}`.
- Keep new runtime dependencies minimal; make heavy/optional ones (like Whisper) lazy imports behind an extra.
- Prefer small, composable functions and reuse the helpers in `core/` (`authed_client`, `resolve_target`, `emit`).

## Commit & PR guidelines

- Write clear, imperative commit messages (e.g. "Add retry to webhook forwarding").
- Reference related issues (e.g. `Fixes #12`).
- In the PR description, explain **what** changed and **why**, and how you tested it.
- Keep PRs reasonably small and single-purpose.

## Reporting bugs

Open an issue with:

- What you ran (command and flags, with secrets redacted)
- What you expected vs. what happened
- The error output (redact tokens, phone numbers, and personal data)
- Your OS and Python version

## Reporting security issues

**Please do not open public issues for security vulnerabilities.** Instead, report them privately to the maintainer (see the contact on the project's profile / commit history) with details and reproduction steps. We'll coordinate a fix and disclosure timeline.

Be especially mindful that tlgrm handles **session files and API credentials** that grant full access to a user's Telegram account.

## License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
