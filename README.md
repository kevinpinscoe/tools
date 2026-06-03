# Tools

This repository collects small tools and automation scripts I have created for Linux, macOS, and Raspberry Pi systems.

Some of these scripts are also referenced from my playbook, so I keep them here in one place for versioning, reuse, and maintenance.

Most of the top-level files are standalone utilities. The main structured subproject is [`rss-feed-generators/`](./rss-feed-generators), which contains self-contained RSS feed generator scripts and related notes.

## Install

The compiled Go binaries (`check-git-repos`, `check-git-branch`, `pause`) are distributed via package managers and GitHub Releases.

### Homebrew (macOS/Linux)

```bash
brew tap kevinpinscoe/homebrew-tap
brew install check-git-repos   # check-git-repos
brew install check-git-branch  # check-git-branch
brew install pause             # pause
```

### APT (Debian/Ubuntu)

```bash
curl -sL https://kevinpinscoe.github.io/apt/gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kevinpinscoe.gpg

echo "deb [signed-by=/etc/apt/keyrings/kevinpinscoe.gpg] \
  https://kevinpinscoe.github.io/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/kevinpinscoe.list

sudo apt update
sudo apt install check-git-repos check-git-branch pause
```

### DNF (Fedora/RHEL)

```bash
sudo curl -fsSL https://kevinpinscoe.github.io/rpm/kevinpinscoe.repo \
  -o /etc/yum.repos.d/kevinpinscoe.repo
sudo dnf install check-git-repos check-git-branch pause
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
```

The Python and shell scripts require no build step — copy them to any directory on your `PATH`.

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
- `free-port` prints a single free TCP port in a given range (default 20000–40000). Tries 200 random candidates first, then falls back to a sequential scan; skips kernel ephemeral ports, reserved ports from `/proc/sys/net/ipv4/ip_local_reserved_ports`, and any ports in `$FREE_PORT_BLOCKED_PORTS` (comma-separated, defaults to `5432`). Requires `ss` (Linux; part of `iproute2`).
- `gitcf` is a Python TUI that lists every untracked or modified file in the current git repo, lets you multi-select via an urwid checkbox picker, then commits (one batch commit if a memo is given, one per file otherwise) and pushes `HEAD` to `origin`.
- `jsonfmt` safely formats JSON and JSONC files in place. `jsonfmt-fedora` is a variant with Fedora-specific installer hints (`dnf` instead of Homebrew) for use on RPM-based systems.
- `k3s` is a Python urwid TUI that reads `~/.environment/k3s-clusters.dat` and sets the default kubectl context to the selected k3s cluster via `kubectl config use-context`.
- `mainbranch` switches back to the default branch and cleans up the current feature branch or git worktree; prompts for confirmation, warns about uncommitted/stashed changes, and refuses to proceed if a tmux session for the branch is still active. Use `ticket --clean` first when working in a worktree. Companion to `ticket`.
- `myclaude` launches `claude` inside a named `screen` session with disk logging, and writes a cleaned `.txt` sibling next to the raw `.log` when the session exits (or via `myclaude --clean <log-file>` after a detach). Logs land at `<LOG_ROOT>/CLAUDE/_<REL>/<timestamp>.log`, where `_<REL>` encodes the cwd `myclaude` was launched from (e.g. `_.environment`, `_tools`, `_Projects-foo`, `_home`). Exports `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` so Claude Code renders into the terminal's native scrollback instead of the fullscreen alt-screen — yields significantly cleaner captured logs. Generates a per-session screenrc that disables screen's `smcup/rmcup` (alt-screen) sequences so host-terminal scrollback works: mouse-wheel scrolls Ghostty's native scrollback directly, or tmux's pane scrollback when nested under a tmux with `mouse on`. Requires Claude Code >= 2.1.132 ([release notes](https://code.claude.com/docs/en/changelog#2-1-132)); auto-runs `claude update` and re-checks if the installed version is older.
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

## Subprojects

- [`file-tools/`](./file-tools) contains tools for locating, searching, or manipulating files.
- [`rss-feed-generators/`](./rss-feed-generators) contains self-contained RSS feed generator scripts and related notes.
