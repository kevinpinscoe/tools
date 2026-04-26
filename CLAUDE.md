# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a personal toolbox of shell scripts and utilities for development workflow automation. All scripts are standalone executables placed directly in the repo root.

## Scripts

### `ticket`
Python TUI workspace manager for Jira/ticket-based development. Runs from anywhere (not tied to a git repo). Self-bootstraps a urwid venv at `~/.local/share/ticket-venv/` on first run.

- **New ticket**: `ticket [TICKET-ID]` — prompts for ticket ID and description if not given, shows a urwid multi-select of repos from `~/.environment/vanco-repos.md`, then clones each selected repo into `~/Projects/workspaces/<TICKET>/<repo>/` on a `kevini/<TICKET>` branch and opens a tmux session with VS Code.
- **List**: `ticket -l | --list` — lists existing tickets with their descriptions.
- **Recover**: `ticket -r | --recover [TICKET-ID]` — relaunches VS Code for an existing ticket; shows a urwid picker if no ID is given.
- **Cleanup**: `ticket --clean [TICKET-ID]` — removes the entire `~/Projects/workspaces/<TICKET>/` directory (clones and all) after `yes` confirmation.

Key paths:
- Workspaces dir: `~/Projects/workspaces/`
- Per-ticket dir: `~/Projects/workspaces/<TICKET>/` (holds the cloned repos, not worktrees)
- Base VS Code workspace template: `~/Projects/kevins-work.code-workspace`
- Repo list: `~/.environment/vanco-repos.md`
- Branch naming: `kevini/<TICKET>`
- Archived original bash version: `~/tools/ticket.old`

Dependencies: `git`, `tmux`, `code`, `python3` (urwid auto-installed into a venv on first run)

### `pull-requests`
Scans all git repos under a root directory (default: `~/Projects`) for open GitHub PRs authored by `$GITHUB_USER` (defaults to `kevinpinscoe`).

- Supports whitelist/blacklist filtering via `~/.config/pull-request/whitelist.txt` and `blacklist.txt` (one path per line, `#` comments supported).
- Skips `node_modules` and `.trash` directories.
- Usage: `pull-requests [ROOT_DIR]`

Dependencies: `git`, `gh` (authenticated), `python3`

### `jsonfmt`
Formats JSON using `jq`. Two modes:
- **File mode**: `jsonfmt FILE` — validates, creates a `.jsonfmt` backup, then overwrites the file with pretty-printed JSON.
- **Stdin mode**: `some-command | jsonfmt` — formats and prints to stdout.

Dependencies: `jq`

### `myclaude`
Bash wrapper that launches `claude` inside a named `screen` session with disk logging. Session name is `claude-<cwd-relative-to-$HOME with / replaced by ->` (e.g. `$HOME/tools` → `claude-tools`, `$HOME` → `claude-home`). Errors out if cwd is outside `$HOME` or a same-named session already exists.

Inside the session: `date && claude`.

Log file path: `<LOG_ROOT>/YYYY/MM/<session>-YYYY-MM-DD-HH-MM.log`, where `LOG_ROOT` is the single-line content of `~/.environment/claude-diary-log-path.txt` (leading `~` expanded). `YYYY/MM` subdirs are auto-created. The script errors out if the config file is missing or empty.

Dependencies: `screen` (must support `-Logfile`; on macOS use a Homebrew build if the system screen is too old), `claude`.

### `claude-log-view`
Python curses TUI for browsing and viewing `myclaude` session logs. Reads the same config file as `myclaude` (`~/.environment/claude-diary-log-path.txt`) and navigates `<LOG_ROOT>/YYYY/MM/*.log`. Defaults to the current month; `m` switches to a months-with-logs list; Enter views the selected log through `<stripper> | col -b | less` where `<stripper>` is `ansifilter` if available, else `ansi2txt`. `r` toggles a raw `less -R` view. Stdlib only (no venv bootstrap). Cleaned view needs `ansifilter` (`brew install ansifilter`, also on apt/dnf) or `ansi2txt` (`colorized-logs`, apt/dnf only). Falls back to raw if no stripper is present.

### `skill` (binary, git-ignored)
A compiled Go binary. The source is not in this repo. The `.gitignore` excludes it.

## Conventions

- All shell scripts use `set -euo pipefail`.
- Scripts validate required commands with `require_cmd` / inline `command -v` checks before doing any work.
- No build system — scripts are standalone executables. Add `chmod +x` when adding new scripts.
- **When adding a new command or changing the usage/purpose of an existing one, update `RUNBOOK.md` in the same change.** `RUNBOOK.md` is the operational reference for every script in this repo; keep its usage, behavior, and dependency notes in sync with the code.

## Source trees (compiled binaries)

Some tools live in a dedicated source subdirectory (e.g. `check-git-repos-source/`) and are compiled to a binary installed in `~/bin/`. These have additional requirements:

### Testing before committing

**Always build and run the binary locally before committing changes to a source tree.** At minimum:
- `go build .` (or equivalent) must succeed with no errors.
- Exercise the changed behaviour directly — run `--version`, `--help`, the affected flag or feature, and confirm the output is correct.

### Keeping README.md in sync

**Every source subdirectory has its own `README.md`.** When making any change to a source tree that affects behaviour, flags, configuration, or install instructions, update the source directory's `README.md` in the same commit. This file is the canonical user-facing reference for that tool.

### Tagging and versioning

Tags follow [SemVer](https://semver.org/) with the tool name as a prefix:

```
<tool-name>-v<MAJOR>.<MINOR>.<PATCH>
```

Example: `check-git-repos-v1.1.0`

Increment:
- **PATCH** — bug fixes, no new behaviour.
- **MINOR** — new features, backward-compatible (new flags, new config support, etc.).
- **MAJOR** — breaking changes (removed flags, changed output format, etc.).

### GitHub Actions release workflow

Each source tree gets a GitHub Actions workflow that triggers on its version tag pattern and:
1. Cross-compiles binaries for all supported platforms.
2. Generates a `checksums.txt` (SHA-256) covering all binaries.
3. Creates a GitHub release and attaches the binaries and `checksums.txt`.

See `.github/workflows/check-git-repos-release.yml` as the reference implementation. When adding a new source tree, create a new workflow file following the same pattern, scoped to `<tool-name>-v*` tags.

### GitHub Dependabot

Each source tree must have a Dependabot entry in `.github/dependabot.yml` to keep its dependencies and the GitHub Actions it uses up to date. See `.github/dependabot.yml` for the current configuration. When adding a new source tree, add a matching `package-ecosystem` block pointing at its directory.
