# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a personal toolbox of shell scripts and utilities for development workflow automation. All scripts are standalone executables placed directly in the repo root.

## Scripts

### `ticket`
Manages git worktrees for Jira/ticket-based development. Must be run from a git repository root (requires `.git` in `$PWD`).

- **New ticket**: `ticket [TICKET-ID]` — prompts for a ticket ID and comment, creates a git worktree at `wt/kevini-<ticket>`, copies a base VS Code workspace, and opens a tmux session.
- **Existing ticket**: If no new ticket is created (empty input), falls back to `pick` (interactive fuzzy finder) to select an existing ticket from `~/Projects/workspaces/*.txt`.
- **Cleanup**: `ticket --clean [TICKET-ID]` — removes the `.txt` and `.code-workspace` files for a ticket (does NOT remove the git worktree).

Key paths:
- Workspaces dir: `~/Projects/workspaces/`
- Base workspace: `~/Projects/kevins-acst.code-workspace`
- Worktrees: `<repo>/wt/kevini-<ticket>/`
- Branch naming: `kevini-<ticket>`

Dependencies: `git`, `tmux`, `code`, `pick`

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
