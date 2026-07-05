# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a personal toolbox of shell scripts and utilities for development workflow automation. All scripts are standalone executables placed directly in the repo root.

## Hard Requirements — apply to every task in this repo

These are non-negotiable and apply regardless of how small the change is. Do not finish any task without completing both steps.

**1. README.md and RUNBOOK.md must be updated in the same commit as any tool change.**
Any time a tool in `~/tools/` is created or modified — even a one-line fix — update:
- `README.md`: the one-line entry in the top-level scripts list.
- `RUNBOOK.md`: the full operational reference (usage, flags, behavior, dependencies).

Do not commit the tool change without these updates already staged. Do not submit a PR or consider the task done until both files are committed.

**2. cspell custom-words changes must be committed and pushed in `~/.dotfiles` before finishing.**
Any time words are added to `~/.config/cspell/custom-words.txt` (e.g. to satisfy the spellcheck hook), you MUST:
1. Stage the updated `custom-words.txt` in `~/.dotfiles`.
2. Commit it there.
3. Push to the remote.

The `~/.dotfiles` repo is the authoritative source for the shared cspell dictionary. Skipping this causes spellcheck failures in other repos.

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
Bash wrapper that launches `claude` inside a named `abduco` session, with `script(1)` capturing all terminal output to disk. (The older `screen`-based implementation is preserved alongside it as `myclaude-screen`.) On start it prompts interactively for a session name — max 15 chars, lowercased with spaces converted to `-` and any non-`[a-z0-9-]` characters stripped. Errors out if the cwd is outside `$HOME`, if an `abduco` session of the same name already exists, or if `claude` is older than 2.1.132 (it first attempts `claude update`).

Inside the session it runs `date && exec claude`. It exports `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` (Claude Code ≥ 2.1.132) so `claude` renders into the terminal's native scrollback instead of the alternate-screen TUI — that is what lets `script` capture cleanly.

Log file path: `<LOG_ROOT>/_<REL>/YYYY-MM-DD-HH-MM.log` (plus a cleaned `.txt` sibling written when the session exits), where `<REL>` is the cwd relative to `$HOME` with `/` replaced by `-` (`$HOME` itself → `home`), and `LOG_ROOT` is the single-line content of the per-platform config file `~/.environment/claude-diary-log-path-for-{fedora,mac,rpi}.txt` (leading `~` expanded). The `_<REL>` subdir is auto-created. The script errors out if the config file is missing or empty.

Detach with `Ctrl+\` (the session keeps running and logging); reattach with `abduco -a <session>`; list sessions with `abduco`. On a true exit the raw `.log` is cleaned into its `.txt` sibling automatically; after a *detach* the cleaner is deferred to avoid racing the still-open log — finish it later with `myclaude --clean <log-file>` (also usable standalone on any log). The cleaner strips alt-screen frame redraws and ANSI escapes; if the cleaned result is empty (e.g. a crash left only fullscreen frames) it is discarded and the raw `.log` is kept.

Dependencies: `abduco`, `script`, `claude`, `date`, `mkdir`. The `.txt` cleaner additionally needs an ANSI stripper — `ansifilter` or `ansi2txt` (from `colorized-logs`) — plus `perl`, `col`, and `tr`; if no stripper is present the raw `.log` is kept and the `.txt` is skipped.

### `claude-log-view`
Python curses TUI (stdlib only, no venv bootstrap) for browsing and viewing `myclaude` session logs. A picker lists the `_<REL>` cwd groups newest-first; Enter drills into a group's `*.log` files, `d` returns to the group list, `j`/`k`/`g`/`G`/`PgUp`/`PgDn` navigate, `r` toggles raw (`less -R`) vs. cleaned (`<stripper> | col -b | tr -d '\r' | cat -s | less`), and `q`/`Esc` quits. Cleaned view needs `ansifilter` (`brew install ansifilter`, also apt/dnf) or `ansi2txt` (`colorized-logs`, apt/dnf only); it falls back to raw if neither is present.

> **⚠ Out of sync with `myclaude`.** `claude-log-view` still reads the retired single config `~/.environment/claude-diary-log-path.txt` (not the per-platform `-for-{fedora,mac,rpi}.txt` files) and looks under `<LOG_ROOT>/CLAUDE/_<REL>/` (subdir constant `CLAUDE`, all-caps). `myclaude` never wrote to an all-caps `CLAUDE/` dir, and as of the 2026-07-05 log relocation it writes a flat `<LOG_ROOT>/_<REL>/`. Until `claude-log-view` is updated to match (read `claude-diary-log-path-for-<platform>.txt` and drop the `CLAUDE` subdir), it will not find current logs.

### `skill` (binary, git-ignored)
A compiled Go binary. The source is not in this repo. The `.gitignore` excludes it.

## Conventions

- All shell scripts use `set -euo pipefail`.
- Scripts validate required commands with `require_cmd` / inline `command -v` checks before doing any work.
- No build system — scripts are standalone executables. Add `chmod +x` when adding new scripts.
- **Any time a tool is created or updated — regardless of how small the change — you MUST update both `README.md` and `RUNBOOK.md` in the same commit before finishing.** `README.md` carries the one-line description in the top-level scripts list; `RUNBOOK.md` is the full operational reference (usage, behavior, dependencies). Do not skip this step even for minor changes.
- **Any time words are added to `~/.config/cspell/custom-words.txt`** (e.g. to satisfy the spellcheck hook during a commit), you MUST also stage, commit, and push that file in the `~/.dotfiles` repo before finishing. The dotfiles repo is the authoritative source for the shared cspell dictionary; skipping this causes spellcheck failures in other repos.

## Source trees (compiled binaries)

Some tools live in a dedicated source subdirectory (e.g. `check-git-repos-source/`) and are compiled to a binary installed in `~/bin/`. These have additional requirements:

### Go version policy

**Always set the `go` directive in `go.mod` to the latest stable Go version installed on this machine** — do not use an old minimum version. Go CVEs are frequent and often critical; staying current is a security requirement, not optional.

- Check the installed version before writing a new `go.mod`: `go version`
- Use the `MAJOR.MINOR` form (e.g. `go 1.26`) — omit the patch level.
- When reviewing or modifying an existing source tree, check whether its `go.mod` is behind the currently installed Go and bump it if so.
- The GitHub Actions release workflow uses `go-version-file: <dir>/go.mod`, so bumping `go.mod` automatically upgrades the build environment too.

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

### Cross-platform sync after any release

After pushing a tag and/or releasing any tool in `~/tools` (whether a script update or a compiled binary release), **append dated TODO entries to the other two platforms' `~/todo` files** so the user knows to sync on those machines.

The current machine is the Fedora desktop (`fedora/TODO.md`). The other two are `mac/TODO.md` and `rpi/TODO.md`. Add entries to both.

**Minimum entry for every release** — a `git pull` to pick up the latest scripts:
```
YYYY-MM-DD cd ~/tools && git pull  # <tool-name> vX.Y.Z: <one-line summary of what changed>
```

**Additional entry when a compiled binary was released** — the user also needs to download and install the new binary from GitHub. Add a second entry for the relevant platform(s) where that binary runs:
```
YYYY-MM-DD <install command from the tool's README.md>  # install <tool-name> vX.Y.Z binary
```

Use today's date. Commit the TODO changes with a message like `todo: remind mac+rpi to sync tools after <tool-name> vX.Y.Z`. Do this in the same session as the release — do not skip it.
