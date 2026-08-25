# Tools

This repository collects small tools and automation scripts I have created for Linux, macOS, and Raspberry Pi systems.

Some of these scripts are also referenced from my playbook, so I keep them here in one place for versioning, reuse, and maintenance.

Most of the top-level files are standalone utilities. The remaining structured subproject is [`file-tools/`](./file-tools).

RSS feed generators previously lived here under `rss-feed-generators/`. They moved on 2026-07-29 to the [`rss-feeds-tools`](ssh://git@git.kevininscoe.com:2223/kinscoe/rss-feeds-tools.git) repository (`~/Projects/private/rss-feeds-tools`), which is now the single home for every feed-generation script.

`ticket` previously lived here. It moved on 2026-08-16 to the private `~/private-tools` repository and was renamed `work-ticket` (with `jira-ticket` as an alias), because it names a specific employer's repositories, branch prefix, and workspace paths — details that do not belong in a public repository. Both directories are on `PATH`, so only the command's name changed. Do not add it back here.

## Repository layout

```
tools/
├── check-git-branch-source/  # Go source for check-git-branch (compiled binary)
├── check-git-repos-source/   # Go source for check-git-repos (compiled binary)
├── file-tools/               # File utility scripts
├── menu-app-source/          # Go source for menu-app (compiled binary)
├── menu-app-template.yaml    # Starter .menu-app.yaml template
├── pause-source/             # Go source for pause (compiled binary)
├── README.md
├── RUNBOOK.md
├── TODO.md                   # Pending work for the tools in this repo
└── <scripts>                 # Standalone executables (one file each; see below)
```

Pending work for these tools is tracked in [`TODO.md`](./TODO.md).

## Install

The compiled Go binaries (`check-git-repos`, `check-git-branch`, `pause`, `menu-app`) are distributed via package managers and GitHub Releases.

### Homebrew (macOS/Linux)

```bash
brew tap kevinpinscoe/homebrew-tap
brew install --cask check-git-repos
brew install --cask check-git-branch
brew install --cask pause
brew install --cask menu-app
```

These shipped as formulas until the cask migration. A formula and a cask of the
same name cannot coexist, so remove any older install first:

```bash
brew uninstall check-git-repos check-git-branch pause menu-app
```

### APT (Debian/Ubuntu)

```bash
curl -sL https://kevinpinscoe.github.io/apt/gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kevinpinscoe.gpg

echo "deb [signed-by=/etc/apt/keyrings/kevinpinscoe.gpg] \
  https://kevinpinscoe.github.io/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/kevinpinscoe.list

sudo apt update
sudo apt install check-git-repos check-git-branch pause menu-app
```

### DNF (Fedora/RHEL)

```bash
sudo curl -fsSL https://kevinpinscoe.github.io/rpm/kevinpinscoe.repo \
  -o /etc/yum.repos.d/kevinpinscoe.repo
sudo dnf install check-git-repos check-git-branch pause menu-app
```

### Download from release

Pre-built binaries for Linux (amd64/arm64) and macOS (arm64) are available on the [Releases](https://github.com/kevinpinscoe/tools/releases) page. Each release includes a `checksums.txt` for verification.

### Build from source

```bash
git clone https://github.com/kevinpinscoe/tools.git
cd tools
# Build individual binaries
go build -o ~/.local/bin/check-git-repos ./check-git-repos-source
go build -o ~/.local/bin/check-git-branch ./check-git-branch-source
go build -o ~/.local/bin/pause ./pause-source
go build -o ~/.local/bin/menu-app ./menu-app-source
```

The Python and shell scripts require no build step — copy them to any directory on your `PATH`.

### Installing menu-app

To install just `menu-app` without the other compiled tools:

**Homebrew (macOS / Linux)**

```sh
brew tap kevinpinscoe/homebrew-tap
brew install --cask menu-app
```

If you installed `menu-app` before the cask migration, run `brew uninstall
menu-app` first — the formula and the cask cannot coexist.

**APT (Debian, Ubuntu, Raspberry Pi OS)**

```sh
curl -sL https://kevinpinscoe.github.io/apt/gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kevinpinscoe.gpg

echo "deb [signed-by=/etc/apt/keyrings/kevinpinscoe.gpg] \
  https://kevinpinscoe.github.io/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/kevinpinscoe.list

sudo apt update
sudo apt install menu-app
```

**DNF (Fedora, RHEL)**

```sh
sudo curl -fsSL https://kevinpinscoe.github.io/rpm/kevinpinscoe.repo \
  -o /etc/yum.repos.d/kevinpinscoe.repo
sudo dnf install menu-app
```

See [`menu-app-source/README.md`](./menu-app-source/README.md) for binary download instructions and build-from-source steps.

## Top-level scripts

- `backup` backs up a file to `$HOME/.backups/<abs-path>/` preserving its directory structure. Supports `-l` to list all backups with timestamps, `-r <path>` to remove a single backup, and `-c` to clear all backups. Works on macOS and Linux.
- `check-git-branch` is a compiled Go binary that scans git repos under `$HOME` (and any extra paths in `$CHECK_GIT_BRANCH`) and reports any that are not on their default branch or have non-default local branches left over from previous work; silent when everything is clean.
- `check-git-repos` is a compiled Go binary that scans all git repositories under `$HOME` (and any extra paths in `$CHECK_GIT_REPOS`) and reports any that are ahead, behind, diverged, have uncommitted changes, are holding stale `.git/*.lock` files, have stashes (`STASH`/`STALE`, `--stash-stale-after`), or have a leftover untracked `CHECKPOINT.md` (reported as `CHECKPOINT` rather than `UNTRACKED`); supports `--batch-mode` for scripting, `--remove-locks` to clear stale locks, and `--lock-stale-after` to tune how old a lock must be before it counts as stale (default 5m). `--worktree` reports `WT` for a repo with a linked git worktree present (e.g. an `ai-wt/<ISSUE>` AI worktree), with `--stale-days` (default 3) additionally reporting `STALE` for one older than that. `--checkpoint` reports only the repos holding a `CHECKPOINT.md` and prints nothing else — no summary, no count, and no output at all when none are found — skipping every other check so it finishes in seconds rather than minutes.
- `claude-log-view` is a curses TUI for browsing `myclaude` logs; navigates `_<REL>` cwd-directories under `<LOG_ROOT>/` and views logs through an ANSI-stripping pipeline.
- `create-ticket-in-youtrack` / `create-ticket-in-youtrack.py` interactively creates a YouTrack issue in either `Work - Inbox` or `Kevin - Inbox`, setting the `Issue domain` custom field from the same "Is this work" answer that picks the project (`Employer work` for work, `Personal` otherwise); reads the server URL from `$YOUTRACK_SERVER` and the API token from `~/.config/YouTrack/self-host-api.txt`. Prints the human-readable issue ID and a clickable issue URL on success.
- `ddir` / `ddir.py` compares two directories recursively, reporting missing files and running side-by-side diffs on files that differ.
- `decode-tldr-tracking-links.sh` decodes TLDR newsletter tracking links so the underlying destination URL is easier to inspect.
- `eks` is a Python urwid TUI that reads `~/.environment/eks-clusters.dat`, logs in via AWS SSO, writes the selected profile to `~/.environment/.env_set.sh`, and runs `aws eks update-kubeconfig` to set the default kubectl context.
- `find-in-ai.sh` searches Markdown notes in the current tree with `rg`.
- `find-obsidian-vaults` lists the live Obsidian vaults under `$HOME` (or `-r DIR`), one path per line. Vaults inside a **linked git worktree are hidden**: the non-work project workflow creates a worktree per issue, and a worktree of a vault repository carries its own `.obsidian`, so every open project branch would otherwise invent a phantom vault — a dozen at a time on this workstation. Pass `-a` to include them. The container, cache and vendored-dependency trees are pruned rather than descended, which accounts for most of the run time and all of the `Permission denied` noise on Fedora. `-0` separates results with NUL for `xargs -0`; any script consuming this output should use it, because two vault names contain a space or an apostrophe. Portable to macOS — no GNU-only `find` predicates. **This is a locator, not an auditor.** The authoritative catalogue tool is `scripts/discover-vaults.py` in `~/Projects/private/obsidian-hacks`, which additionally reconciles against Obsidian's registration file, audits repository layout against rule 1 of `obsidian-best-practices.md`, and reports baseline plugin conformance. Prefer that one where it is available; reach for this one on a host where that repository is not checked out, or when a plain list of paths is all you need.
- `fix-file-name.sh` renames a file by replacing runs of spaces and non-alphanumeric characters with a single hyphen and lowercasing the result.
- `title` converts text to a markdown-filename-friendly slug: all non-alphanumeric runs collapse to a single hyphen, the result is lowercased, and leading/trailing hyphens are stripped. Warns and exits if the input contains a dot (use `fix-file-name.sh` for actual filenames).
- `free-port` prints a single free TCP port in a given range (default 20000–40000). Tries 200 random candidates first, then falls back to a sequential scan; skips kernel ephemeral ports, reserved ports from `/proc/sys/net/ipv4/ip_local_reserved_ports`, and any ports in `$FREE_PORT_BLOCKED_PORTS` (comma-separated, defaults to `5432`). Requires `ss` (Linux; part of `iproute2`).
- `gitcf` is a Python TUI that lists every untracked, modified or deleted file in the current git repo, lets you multi-select via an urwid checkbox picker, then commits (one batch commit if a memo is given, one per file otherwise) and pushes `HEAD` to `origin`. Every commit message is prefixed with `Committed by gitcf tool: ` — both the auto-generated `Added`/`Modified`/`Deleted <name>` messages and any memo you type; pass `--no-prefix` to suppress it for that run. Deletions are listed so that a plain-`mv` rename can be committed whole — its `?? new-name` and ` D old-name` halves are both offered. A rename/copy git has already detected (`R`/`C` codes) is shown and committed as `Renamed <old> → <new>` / `Copied <old> → <new>` instead of the generic `Modified <name>`. Unresolved merge conflicts are withheld from the picker and named on stderr, since `git add` on one would stage the conflict markers. Files that a `pre-commit` hook has already swept into an earlier commit in the same run are skipped rather than retried — see the `gitcf` troubleshooting section in `RUNBOOK.md`. `CHECKPOINT.md` is withheld from the picker outright — it must never be committed — and its presence at the repo root prints a one-line warning before the picker opens. gitcf has no branch awareness of its own, so it always prints which branch is about to receive the commits/push before opening the picker, plus a reminder to log commits on the matching YouTrack issue when that branch looks like a project branch (`KDA-10`, `KEVIN-91`, etc.). A repo listed in `~/.config/gitcf/ignore.txt` is refused outright — no `git status`, no picker — for a repo another system owns writes to (e.g. `~/Projects/private/pim-records`, Radicale's own auto-committed history).
- `jsonfmt` safely formats JSON and JSONC files in place. `jsonfmt-fedora` is a variant with Fedora-specific installer hints (`dnf` instead of Homebrew) for use on RPM-based systems.
- `k3s` is a Python urwid TUI that reads `~/.environment/k3s-clusters.dat` and sets the default kubectl context to the selected k3s cluster via `kubectl config use-context`.
- `mainbranch` switches back to the default branch and cleans up the current feature branch or git worktree; prompts for confirmation, warns about uncommitted/stashed changes, and refuses to proceed if a tmux session for the branch is still active. Use `work-ticket --clean` first when working in a worktree. Companion to `work-ticket`, which lives in the private `~/private-tools` repository.
- `mdf` lists the Markdown files (`*.md`, `*.markdown`) in the current directory only (no recursion) and presents an `fzf` chooser with a live `glow`-rendered preview pane, then opens the selected file in the `mdfried` terminal Markdown viewer. Requires `fzf`, `glow`, and `mdfried`.
- `menu-app` is a compiled Go binary (Bubble Tea TUI) that reads a `.menu-app.yaml` file from the current repository's git root and presents its entries as a menu of scripts to run; each script runs from the git root and control returns to the menu afterward. Exits with `not a git initialized directory` when run outside a repo, and offers to create a starter config from `menu-app-template.yaml` when none exists. Source in `menu-app-source/`.
- `myclaude` launches `claude` inside a named `abduco` session with `script` disk logging, and writes a cleaned `.txt` sibling next to the raw `.log` when the session exits (or via `myclaude --clean <log-file>` after a detach). Prompts for a short session name on each launch (≤ 15 chars; spaces become hyphens, non-alphanumeric chars are stripped, result is lowercased — e.g. `"Today's Journal"` → `todays-journal`). Logs land at `<LOG_ROOT>/_<REL>/<timestamp>.log`, where `_<REL>` encodes the cwd `myclaude` was launched from (e.g. `_.environment`, `_tools`, `_Projects-foo`, `_home`). `script` begins capturing immediately; `date && exec claude` runs inside that logging shell. Exports `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` so Claude Code renders into the terminal's native scrollback for cleaner logs. Also defaults `PARZIVAL_IDENTITY=ai` (override by exporting it beforehand; an explicit `--as` flag still wins) so credential fetches in a recorded session run under a restricted parzival identity — the session is logged to disk, so anything printed is captured permanently. Detach with Ctrl+\; reattach with `abduco -a <session-name>`. Requires `abduco` and `util-linux-script` (`sudo dnf install util-linux-script`), plus Claude Code >= 2.1.132.
- `myclaude-screen` is the legacy `screen`-based version of `myclaude` (preserved for platforms where `abduco` is unavailable). See `myclaude` for the current version.
- `mycodex` launches `codex` inside a named `abduco` session with `script` disk logging — identical in structure to `myclaude` but runs `codex` instead of `claude`. Logs land at `<LOG_ROOT>/CODEX/_<REL>/<timestamp>.log`. Same session management, detach key (Ctrl+\), cleanup pipeline, and `PARZIVAL_IDENTITY=ai` default as `myclaude`.
- `newest-file` prints the most recently modified file found recursively under the current directory; thin wrapper around `file-tools/list_recursively_newest_file.py`.
- `pause` is a compiled Go binary that sleeps for a specified number of seconds, displaying a live countdown status line on stderr; drop it into scripts wherever `sleep N` would leave the user wondering how long remains.
- `pull` guarantees that no commit existing on a remote is missing from this machine: it fetches every remote of every git repo under `$HOME` (plus any paths in `$CHECK_GIT_REPOS`) in parallel, then fast-forwards **every** local branch that is behind its upstream — not just the checked-out one. Failed fetches, diverged branches, and fast-forwards git refuses are each reported individually and make the run exit non-zero, so nothing is ever skipped silently. Supports `--dry-run`, `--autostash`, `--no-fetch`, `-j N`, `-q`, and explicit `PATH...` arguments. Shares the ignore list at `~/.config/check-git-repos-source/ignore.txt` with `check-git-repos`. On a real terminal a braille spinner (matching `check-git-repos`) shows discovery/fetch progress instead of sitting silent — this matters on hosts where `$HOME`/`$CHECK_GIT_REPOS` crosses a slow bind mount.
- `pull-requests` scans all git repos under a root directory (default: `~/Projects`) for open GitHub PRs authored by `$GITHUB_USER`; supports whitelist/blacklist filtering via `~/.config/pull-request/`.
- `radar.sh` displays live animated NOAA weather radar in the terminal via mpv. Downloads GIF radar loops from `radar.weather.gov`, plays them on a loop, and auto-refreshes every 2 minutes. Single-key controls switch between regional views (CONUS, Northeast, Southeast, Great Lakes, Pacific NW) and city stations (Melbourne, Jacksonville, Atlanta, NYC, Chicago, Dallas, Denver, Seattle, Los Angeles, Miami, Morristown TN). The Morristown TN (KMRX) station overlays a bordered "you are here" marker at a calibrated pixel position via an mpv `lavfi`/`drawbox` filter. Falls back to macOS Preview if mpv is unavailable. Requires `wget` and `mpv`.
- `restore` restores a file previously saved by `backup` from `$HOME/.backups/<abs-path>/` back to the current directory. Companion to `backup`.
- `set-ghostty-tab-name` sets the name of the terminal tab the calling process is running in, so an AI agent working a ticket can label its tab with the ticket key (`FLDW-12`, `KTA-1`) and re-label it with that key plus a lowercase `c` (`FLDW-12c`) once the ticket is closed — the tab then shows both which ticket the session last worked and that it is finished. Because Ghostty here runs `tmux new-session -A -s main`, the visible tab name is a tmux window name, and that is what the script sets; outside tmux it falls back to an `OSC 2` title escape. **It always targets the caller's own pane** (`$TMUX_PANE`, or process-ancestry lookup if that is unset) — a bare `tmux rename-window` renames whichever window the client is *viewing*, which with several agents running silently relabels someone else's window. `--reset` — no longer part of closing a ticket, but still available for a tab with no finished ticket to remember — unsets the tab's `automatic-rename` rather than hardcoding a name, handing naming back to tmux, which names the tab after whatever is running in it — `zsh` at an idle shell, `claude` during an AI session. Required by directive when a YouTrack or Jira ticket starts and again when it closes (`when-creating-a-youtrack-ticket.md` §§7 and 9, `when-in-work-context.md` instruction 8). Supports `-t TARGET` and `--show`.
- `trufflehog.sh` scans credential-relevant paths for secrets using TruffleHog; detects the current platform (Fedora, macOS, Raspberry Pi) and adjusts paths accordingly. Prints a summary grouped by detector. Compare output against `~/.environment/.credentials-map.md` to identify undocumented credentials.
- `walk_thru_readme_and_find_missing_files.py` checks `README.md` files for local Markdown links that point to missing files.
- `walk_thru_repo_looking_for_files_missing_from_README.py` finds Markdown files in the repo that are not linked from a sibling `README.md`.
- `wd` prints the current working directory, replacing the `$HOME` prefix with `~` when inside the home directory.
- `what-did-i` / `what-did-i-accomplish-today.py` queries git commits from GitHub (via `gh`) and Gitea (via REST API) for today (or yesterday with `what-did-i yesterday`, or a specific day with `what-did-i YYYY-MM-DD`) and writes a dated Markdown summary to `$JOURNAL_PATH/ACCOMPLISHMENTS/YYYY-MM/git-work-for-YYYY-MM-DD.md` (Linux: `~/Journal/personal-journal`; macOS: `~/Journal/Professional`); also prints to stdout.
- `youtube-md` fetches a YouTube video's title via `yt-dlp`, slugifies it using `fix-file-name.sh` rules, then runs `defuddle parse --md` on the URL and saves the result to `<slug>.md` in the current directory. Accepts the URL as an optional positional argument or prompts for it interactively.

## Subprojects

- [`file-tools/`](./file-tools) contains tools for locating, searching, or manipulating files.

## Other tools I have written or modified not on this repo

- [`skills-tui`](https://github.com/kevinpinscoe/skills-tui) — TUI-based command-line skills chooser designed to be executed by Claude Code.
- [`gitme`](https://github.com/kevinpinscoe/gitme) — quickly find local Git repositories.
- [`eng-tools`](https://github.com/kevinpinscoe/eng-tools) — collection of handy online tools for engineers with a focus on good UX.
- [`metar-tool`](https://github.com/kevinpinscoe/metar-tool) — obtains and parses weather observations (METARs) and forecasts.
- [`aws-linux-memory-tools`](https://github.com/kevinpinscoe/aws-linux-memory-tools) — tools to determine whether an AWS Linux instance is undersized on memory.
- [`get-wx`](https://github.com/kevinpinscoe/get-wx) — simple Open-Meteo weather parser written in Go.
- [`unix-hacks`](https://github.com/kevinpinscoe/unix-hacks) — Unix hacks collected over the decades.
- [`line-reorder-gui`](https://github.com/kevinpinscoe/line-reorder-gui) — GUI tool for reordering lines via drag and drop.
- [`ashpodder`](https://github.com/kevinpinscoe/ashpodder) — podcast client (a fork of bashpodder, named for Ash from Evil Dead).
- [`WXTools`](https://github.com/kevinpinscoe/WXTools) — tools for collecting, notifying, and reporting weather events.
- [`ddir`](https://github.com/kevinpinscoe/ddir) — standalone repo for the `ddir` directory-diff tool also present in this repo.
