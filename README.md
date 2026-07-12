# Tools

This repository collects small tools and automation scripts I have created for Linux, macOS, and Raspberry Pi systems.

Some of these scripts are also referenced from my playbook, so I keep them here in one place for versioning, reuse, and maintenance.

Most of the top-level files are standalone utilities. The main structured subproject is [`rss-feed-generators/`](./rss-feed-generators), which contains self-contained RSS feed generator scripts and related notes.

## Repository layout

```
tools/
├── check-git-branch-source/  # Go source for check-git-branch (compiled binary)
├── check-git-repos-source/   # Go source for check-git-repos (compiled binary)
├── file-tools/               # File utility scripts
├── menu-app-source/          # Go source for menu-app (compiled binary)
├── menu-app-template.yaml    # Starter .menu-app.yaml template
├── pause-source/             # Go source for pause (compiled binary)
├── rss-feed-generators/      # Self-contained RSS feed generator scripts
├── README.md
├── RUNBOOK.md
└── <scripts>                 # Standalone executables (one file each; see below)
```

## Install

The compiled Go binaries (`check-git-repos`, `check-git-branch`, `pause`, `menu-app`) are distributed via package managers and GitHub Releases.

### Homebrew (macOS/Linux)

```bash
brew tap kevinpinscoe/homebrew-tap
brew install check-git-repos   # check-git-repos
brew install check-git-branch  # check-git-branch
brew install pause             # pause
brew install menu-app          # menu-app
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
brew install menu-app
```

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
- `check-git-branch` is a compiled Go binary that scans git repos under `$HOME` (or `$CHECK_GIT_BRANCH`) and reports any that are not on their default branch or have non-default local branches left over from previous work; silent when everything is clean.
- `check-git-repos` is a compiled Go binary that scans all git repositories under `$HOME` (and any extra paths in `$CHECK_GIT_REPOS`) and reports any that are ahead, behind, diverged, or have uncommitted changes; supports `--batch-mode` for scripting and a lock mechanism to prevent concurrent runs.
- `claude-log-view` is a curses TUI for browsing `myclaude` logs; navigates `_<REL>` cwd-directories under `<LOG_ROOT>/CLAUDE/` and views logs through an ANSI-stripping pipeline.
- `create-ticket-in-youtrack` / `create-ticket-in-youtrack.py` interactively creates a YouTrack issue in either `Work - Inbox` or `Kevin - Inbox`; reads the server URL from `$YOUTRACK_SERVER` and the API token from `~/.config/YouTrack/self-host-api.txt`. Prints the human-readable issue ID and a clickable issue URL on success.
- `ddir` / `ddir.py` compares two directories recursively, reporting missing files and running side-by-side diffs on files that differ.
- `decode-tldr-tracking-links.sh` decodes TLDR newsletter tracking links so the underlying destination URL is easier to inspect.
- `eks` is a Python urwid TUI that reads `~/.environment/eks-clusters.dat`, logs in via AWS SSO, writes the selected profile to `~/.environment/.env_set.sh`, and runs `aws eks update-kubeconfig` to set the default kubectl context.
- `find-in-ai.sh` searches Markdown notes in the current tree with `rg`.
- `find-obsidian-vaults` finds Obsidian vaults under `$HOME` by locating `.obsidian` directories.
- `fix-file-name.sh` renames a file by replacing runs of spaces and non-alphanumeric characters with a single hyphen and lowercasing the result.
- `title` converts text to a markdown-filename-friendly slug: all non-alphanumeric runs collapse to a single hyphen, the result is lowercased, and leading/trailing hyphens are stripped. Warns and exits if the input contains a dot (use `fix-file-name.sh` for actual filenames).
- `free-port` prints a single free TCP port in a given range (default 20000–40000). Tries 200 random candidates first, then falls back to a sequential scan; skips kernel ephemeral ports, reserved ports from `/proc/sys/net/ipv4/ip_local_reserved_ports`, and any ports in `$FREE_PORT_BLOCKED_PORTS` (comma-separated, defaults to `5432`). Requires `ss` (Linux; part of `iproute2`).
- `gitcf` is a Python TUI that lists every untracked or modified file in the current git repo, lets you multi-select via an urwid checkbox picker, then commits (one batch commit if a memo is given, one per file otherwise) and pushes `HEAD` to `origin`.
- `jsonfmt` safely formats JSON and JSONC files in place. `jsonfmt-fedora` is a variant with Fedora-specific installer hints (`dnf` instead of Homebrew) for use on RPM-based systems.
- `k3s` is a Python urwid TUI that reads `~/.environment/k3s-clusters.dat` and sets the default kubectl context to the selected k3s cluster via `kubectl config use-context`.
- `mainbranch` switches back to the default branch and cleans up the current feature branch or git worktree; prompts for confirmation, warns about uncommitted/stashed changes, and refuses to proceed if a tmux session for the branch is still active. Use `ticket --clean` first when working in a worktree. Companion to `ticket`.
- `mdf` lists the Markdown files (`*.md`, `*.markdown`) in the current directory only (no recursion) and presents an `fzf` chooser with a live `glow`-rendered preview pane, then opens the selected file in the `mdfried` terminal Markdown viewer. Requires `fzf`, `glow`, and `mdfried`.
- `menu-app` is a compiled Go binary (Bubble Tea TUI) that reads a `.menu-app.yaml` file from the current repository's git root and presents its entries as a menu of scripts to run; each script runs from the git root and control returns to the menu afterward. Exits with `not a git initialized directory` when run outside a repo, and offers to create a starter config from `menu-app-template.yaml` when none exists. Source in `menu-app-source/`.
- `myclaude` launches `claude` inside a named `abduco` session with `script` disk logging, and writes a cleaned `.txt` sibling next to the raw `.log` when the session exits (or via `myclaude --clean <log-file>` after a detach). Prompts for a short session name on each launch (≤ 15 chars; spaces become hyphens, non-alphanumeric chars are stripped, result is lowercased — e.g. `"Today's Journal"` → `todays-journal`). Logs land at `<LOG_ROOT>/CLAUDE/_<REL>/<timestamp>.log`, where `_<REL>` encodes the cwd `myclaude` was launched from (e.g. `_.environment`, `_tools`, `_Projects-foo`, `_home`). `script` begins capturing immediately; `date && exec claude` runs inside that logging shell. Exports `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` so Claude Code renders into the terminal's native scrollback for cleaner logs. Detach with Ctrl+\; reattach with `abduco -a <session-name>`. Requires `abduco` and `util-linux-script` (`sudo dnf install util-linux-script`), plus Claude Code >= 2.1.132.
- `myclaude-screen` is the legacy `screen`-based version of `myclaude` (preserved for platforms where `abduco` is unavailable). See `myclaude` for the current version.
- `mycodex` launches `codex` inside a named `abduco` session with `script` disk logging — identical in structure to `myclaude` but runs `codex` instead of `claude`. Logs land at `<LOG_ROOT>/CODEX/_<REL>/<timestamp>.log`. Same session management, detach key (Ctrl+\), and cleanup pipeline as `myclaude`.
- `newest-file` prints the most recently modified file found recursively under the current directory; thin wrapper around `file-tools/list_recursively_newest_file.py`.
- `pause` is a compiled Go binary that sleeps for a specified number of seconds, displaying a live countdown status line on stderr; drop it into scripts wherever `sleep N` would leave the user wondering how long remains.
- `pull-requests` scans all git repos under a root directory (default: `~/Projects`) for open GitHub PRs authored by `$GITHUB_USER`; supports whitelist/blacklist filtering via `~/.config/pull-request/`.
- `radar.sh` displays live animated NOAA weather radar in the terminal via mpv. Downloads GIF radar loops from `radar.weather.gov`, plays them on a loop, and auto-refreshes every 2 minutes. Single-key controls switch between regional views (CONUS, Northeast, Southeast, Great Lakes, Pacific NW) and city stations (Melbourne, Jacksonville, Atlanta, NYC, Chicago, Dallas, Denver, Seattle, Los Angeles, Miami). Falls back to macOS Preview if mpv is unavailable. Requires `wget` and `mpv`.
- `restore` restores a file previously saved by `backup` from `$HOME/.backups/<abs-path>/` back to the current directory. Companion to `backup`.
- `ticket` is a Python TUI workspace manager for ticket-based development; clones selected repos into `~/Projects/workspaces/<TICKET>/` on a `kevini/<TICKET>` branch and opens a tmux + VS Code session.
- `trufflehog.sh` scans credential-relevant paths for secrets using TruffleHog; detects the current platform (Fedora, macOS, Raspberry Pi) and adjusts paths accordingly. Prints a summary grouped by detector. Compare output against `~/.environment/.credentials-map.md` to identify undocumented credentials.
- `walk_thru_readme_and_find_missing_files.py` checks `README.md` files for local Markdown links that point to missing files.
- `walk_thru_repo_looking_for_files_missing_from_README.py` finds Markdown files in the repo that are not linked from a sibling `README.md`.
- `wd` prints the current working directory, replacing the `$HOME` prefix with `~` when inside the home directory.
- `what-did-i` / `what-did-i-accomplish-today.py` queries git commits from GitHub (via `gh`) and Gitea (via REST API) for today (or yesterday with `what-did-i yesterday`) and writes a dated Markdown summary to `$JOURNAL_PATH/ACCOMPLISHMENTS/YYYY-MM/git-work-for-YYYY-MM-DD.md` (Linux: `~/Journal/Personal Journal`; macOS: `~/Journal/Professional`); also prints to stdout.
- `youtube-md` fetches a YouTube video's title via `yt-dlp`, slugifies it using `fix-file-name.sh` rules, then runs `defuddle parse --md` on the URL and saves the result to `<slug>.md` in the current directory. Accepts the URL as an optional positional argument or prompts for it interactively.

## Subprojects

- [`file-tools/`](./file-tools) contains tools for locating, searching, or manipulating files.
- [`rss-feed-generators/`](./rss-feed-generators) contains self-contained RSS feed generator scripts and related notes.

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
