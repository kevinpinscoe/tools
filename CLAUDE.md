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

### `skill` (binary, git-ignored)
A compiled Go binary. The source is not in this repo. The `.gitignore` excludes it.

## Conventions

- All shell scripts use `set -euo pipefail`.
- Scripts validate required commands with `require_cmd` / inline `command -v` checks before doing any work.
- No build system — scripts are standalone executables. Add `chmod +x` when adding new scripts.
- **When adding a new command or changing the usage/purpose of an existing one, update `RUNBOOK.md` in the same change.** `RUNBOOK.md` is the operational reference for every script in this repo; keep its usage, behavior, and dependency notes in sync with the code.
