# RUNBOOK

Operational reference for the scripts in this repo. Each entry covers purpose,
usage, and notable behavior. Keep this in sync when script functionality changes.

## `gitcf`

Python TUI that surfaces every untracked or modified file in the current git
repo, lets you multi-select which to commit via an urwid checkbox picker,
makes one commit per selected file with an auto-generated message (or an
optional memo override), then pushes `HEAD` to `origin`.

The historical bash implementation (single-file argument, no push) has been
replaced.

### Usage

```
gitcf            # run from anywhere inside a git repo
gitcf -h | --help
```

No file arguments — the picker is the only interface.

### Behavior

- Repo root is resolved via `git rev-parse --show-toplevel`. Errors out if
  not inside a git repo.
- `git status --porcelain -z` enumerates untracked, modified, staged-add,
  staged-modify, and renamed entries. Pure deletions are skipped (the
  message scheme has nothing meaningful to say for a removed file). Renames
  surface their destination path; the source is dropped.
- The TUI shows each entry as `[XY]  path` with an urwid `CheckBox`. Keys:
  - `Space` toggles selection
  - `↑` / `↓` move focus
  - `Enter` confirms
  - `q` / `Esc` cancels (no commits, no push)
- After confirming selection, the script prompts once for `Commit memo (optional, Enter for default):`
  - If you enter a memo, it is used verbatim as the `git commit -m "<msg>"` message for every selected file (override mode).
  - If you press Enter, `<msg>` follows the default scheme: `Added <basename>` for an untracked entry (`??`) and `Modified <basename>` otherwise.
- For each selected entry, in order, the script runs:
  - `git add -- <path>` (staging the file from its repo-root-relative path)
  - `git commit -m "<msg>"`
- After every selected file is committed, `git push origin HEAD` is run
  once.
- On success, a final summary lists each commit message alongside the
  absolute path of the file it covered:

  ```
  Committed and pushed 2 files:
    Added foo.txt      /Users/me/repo/foo.txt
    Modified bar.go    /Users/me/repo/sub/bar.go
  ```
- Any failing git command (commit hook rejection, push rejection, etc.)
  raises `CalledProcessError` and exits non-zero with git's own output
  visible. No partial-state cleanup — already-made commits stay in place
  so the user can retry the push or fix the issue.

### First-run venv bootstrap

If `urwid` is not importable from the system Python, the script creates
`~/.local/share/gitcf-venv/`, `pip install`s `urwid` into it, and re-execs
itself under that venv's interpreter. Subsequent runs reuse the venv with
no further setup.

### Dependencies

`git`, `python3`, `urwid` (auto-installed into a per-user venv on first
run). `readline` is imported when present so backspace / line-editing
work in any future `input()` prompts.

---

## `ticket`

Python TUI workspace manager for ticket-based development. Clones selected git
repos into a per-ticket directory under `~/Projects/workspaces/`, creates
branches, and launches a tmux session with VS Code.

The historical bash implementation is preserved as `~/tools/ticket.old`.

### Usage

```
ticket                       # prompt for ticket ID, description, and repos
ticket TICKET-ID             # create workspace for the given ticket
ticket -l | --list           # list tickets with their descriptions
ticket -r | --recover [ID]   # relaunch VS Code for an existing ticket (TUI picker if no ID)
ticket --clean [ID]          # remove entire workspace directory (TUI picker if no ID)
ticket -h | --help
```

### Key paths

- Workspaces dir: `~/Projects/workspaces/`
- Per-ticket workspace: `~/Projects/workspaces/<TICKET>/`
- Cloned repos: `~/Projects/workspaces/<TICKET>/<repo-name>/`
- VS Code workspace file: `~/Projects/workspaces/<TICKET>/<TICKET>.code-workspace`
- Ticket description: `~/Projects/workspaces/<TICKET>/<TICKET>.txt`
- Short description marker: `~/Projects/workspaces/<TICKET>/.workingon` (first 25 chars)
- Base VS Code workspace template: `~/Projects/kevins-work.code-workspace`
- Repo list: `~/.environment/vanco-repos.md`

### Notes

- Ticket IDs are sanitized and uppercased; a hyphen is inserted at the
  alpha/numeric boundary.
- Repos are selected via a full-screen urwid TUI multi-select picker.
- Each cloned repo gets a `kevini/<TICKET>` branch and a `.workingon` file.
- Running `ticket <ID>` for an existing ticket exits with an error; use `-r`.
- `--clean` removes the entire workspace directory (git history and all).
- The `Ticket:` and `Description:` prompts use Python's `input()` with the
  `readline` module imported, so backspace and standard line-editing keys
  work via terminfo regardless of the pty's `stty erase` setting (otherwise
  bare `input()` only honors stty's cooked-mode rules, which can break
  inside tmux/terminal combinations that send non-default key sequences).

### Dependencies

`git`, `tmux`, `code`, `python3`, `urwid` (pip install urwid)

---

## `mainbranch`

Switch back to the repo's default branch and clean up the feature branch or
linked worktree. Companion to `ticket`.

### Usage

```
mainbranch            # confirm, then switch/remove
mainbranch -f | --force   # also discard uncommitted changes via reset --hard
mainbranch -h | --help
```

### Behavior

- If run from a linked worktree: `cd`s to the main repo, runs
  `git worktree remove --force`, deletes the branch, then pulls on the
  default branch.
- If run from a non-default branch in the main repo: checks out the default
  branch, deletes the feature branch, and pulls.
- Warns about uncommitted/unstaged/stashed changes but does not abort — git
  itself will refuse the checkout if anything would be overwritten. Use
  `-f` to `reset --hard` and `clean -fd` first.
- Aborts if a tmux session named after the ticket (branch suffix after
  `kevini/`) is still active.
- Worktree detection normalizes `--git-dir` and `--git-common-dir` to
  absolute paths before comparing — they can otherwise disagree in format
  and falsely flag the main working tree as a linked worktree.
- Refuses to run if `git remote show origin` can't resolve the default
  branch (e.g. network/auth failure returning `(unknown)`), so the worktree
  and branch aren't deleted before a failing `git checkout`.
- Before `git worktree remove`, asserts cwd resolves to the main repo root
  and is not inside the worktree being deleted.

### Dependencies

`git`, `tmux`

---

## `pull-requests`

Scan all git repos under a root directory for open GitHub PRs authored by
`$GITHUB_USER` (default: `kevinpinscoe`).

### Usage

```
pull-requests [ROOT_DIR]   # defaults to ~/Projects
```

### Filtering

- Whitelist: `~/.config/pull-request/whitelist.txt`
- Blacklist: `~/.config/pull-request/blacklist.txt`
- One path per line; `#` comments supported.
- `node_modules` and `.trash` are always skipped.

### Dependencies

`git`, `gh` (authenticated), `python3`

---

## `backup`

Copy a file into `~/.backups/` mirroring its absolute path.

### Usage

```
backup <file>        # back up to ~/.backups/<abs-path-without-leading-slash>/
backup -l            # list all backed-up files with timestamps
backup -r <path>     # remove a backup (use the PATH shown by -l)
backup -c            # remove all backups (prompts)
backup -h
```

### Notes

- `-r` removes empty parent directories under `~/.backups` after deletion.
- Cross-platform `stat` handling for timestamps (macOS vs Linux).

---

## `restore`

Restore a previously `backup`-ed file into the current directory. The CWD is
treated as the original path.

### Usage

```
restore <basename>   # copies ~/.backups/<cwd>/<basename> back to ./<basename>
```

---

## `jsonfmt`

Format JSON with `jq`.

### Usage

```
jsonfmt FILE                 # validate, save .jsonfmt backup, pretty-print in place
some-command | jsonfmt       # stdin → pretty-printed stdout
```

### Dependencies

`jq`

---

## `myclaude`

Launch `claude` inside a named `screen` session with logging to disk.

### Usage

```
myclaude        # run from any directory under $HOME
```

### Behavior

- Session name is derived from the current directory relative to `$HOME`,
  with `/` replaced by `-` and prefixed with `claude-`:
  - `$HOME`              → `claude-home`
  - `$HOME/tools`        → `claude-tools`
  - `$HOME/Projects/foo` → `claude-Projects-foo`
- Errors out if the current directory is not under `$HOME`.
- Errors out if a screen session with the same name already exists
  (signal to attach the existing one with `screen -r <name>`).
- Inside the session, runs `date && claude`.
- `screen -L -Logfile ...` writes a log file at:
  `<LOG_ROOT>/YYYY/MM/<session>-YYYY-MM-DD-HH-MM.log`
  `YYYY/MM` subdirs are auto-created.

### Configuration

- `~/.environment/claude-diary-log-path.txt` — single line with the log root
  directory (leading `~` is expanded to `$HOME`). The script errors out if
  this file is missing or empty.

### Dependencies

`screen` >= 4.06 (required for `-Logfile`; the script parses
`screen -version` and exits 1 if too old). On macOS the stock
`/usr/bin/screen` is too old — install via Homebrew and ensure
`/opt/homebrew/bin` precedes `/usr/bin` on `PATH`. Also needs
`claude`, `bash`, `date`, `mkdir`.

---

## `claude-log-view`

Curses TUI picker for `myclaude` session logs. Reads the log root from
`~/.environment/claude-diary-log-path.txt` and browses
`<LOG_ROOT>/YYYY/MM/*.log`.

### Usage

```
claude-log-view
```

### Behavior

- Opens on the current month's log list; falls back to the newest month
  with logs if the current month is empty.
- Press `m` to switch to a list of all months that contain logs; Enter on
  a month drops into its file list.
- Enter on a log views it in `less` via
  `<stripper> | col -b | tr -d '\r' | cat -s | less` (cleaned,
  readable), where `<stripper>` is `ansifilter` if available, otherwise
  `ansi2txt`. `col -b` collapses backspaces; `tr -d '\r'` removes the
  carriage returns a TUI emits on every redraw; `cat -s` squeezes
  consecutive blank lines.
- `col` and `tr` are run with `LC_ALL=C` so BSD (macOS) builds don't
  abort with "Illegal byte sequence" on UTF-8 multi-byte input; `less`
  keeps the user's locale so unicode still renders.
- If no stripper is present the cleaned view falls back to raw and the
  header indicates so: `[cleaned→raw (no stripper: brew install ansifilter)]`.
- `r` toggles raw mode — raw mode uses `less -R` on the unprocessed file
  (expect garbled output for TUI sessions; useful for sanity checks).
- `q` / `Esc` quits; in months mode `Esc` / `m` returns to the file list.
- If no ANSI stripper is available, cleaned view silently falls back to
  `less -R`.

### Dependencies

`python3` (stdlib only), `less`. For cleaned view, `col` plus an ANSI
stripper — either `ansifilter` or `ansi2txt` (from `colorized-logs`).

Install one of the strippers:

- macOS: `brew install ansifilter`
  (`colorized-logs` is **not** in Homebrew.)
- Debian trixie: `sudo apt install ansifilter` or `sudo apt install colorized-logs`
- Fedora: `sudo dnf install ansifilter` or `sudo dnf install colorized-logs`

---

---

## `file-tools/` subdirectory

Tools for locating, searching, or manipulating files.

### `newest-file`

Wrapper script for `file-tools/list_recursively_newest_file.py`. Finds and
prints the single most recently modified file under the current directory,
skipping any path components that begin with a dot (`.git`, `.terraform`, etc.).

#### Usage

```
newest-file          # run from any directory
```

#### Output

```
<relative/path/to/file>  YYYY-MM-DD HH:MM:SS
```

#### Dependencies

`python3`

---

## `ddir`

Compare two directories recursively. Reports files missing from either side and
runs a side-by-side diff on any files that exist in both directories but differ
in content. Hidden files and directories (names starting with `.`) are skipped.

The `ddir` shell wrapper calls `ddir.py` from `~/tools/`.

### Usage

```
ddir <dir-a> <dir-b>
```

### Output

```
-- Missing <path>          File exists in one directory but not the other
** <a> and <b> differ      Side-by-side diff of files with differing content
Summary statistics at the end (file counts, missing, differing)
```

### Dependencies

`python3`, `diff`

---

## `check-git-repos`

Go program that walks `$HOME` recursively, finds every git repository, and reports any whose current branch is out of sync with its remote. Repos with no configured upstream are silently skipped. All repos are checked concurrently.

Source lives in `~/tools/check-git-repos-source/`; the compiled binary installs to `~/bin/check-git-repos`.

Install by curling the release binary (see `check-git-repos-source/README.md` for per-platform URLs) or via `make install` from source.

### Usage

```
check-git-repos                 # scan and report
check-git-repos --batch-mode    # scan without progress spinner (systemd/cron)
check-git-repos --disable-lock  # avoid git lock files (skips fetch — see warning)
check-git-repos --ignore-prefix # treat ignore entries as text prefixes (see below)
check-git-repos --version       # print version and exit
check-git-repos --help          # print usage and exit
```

`--disable-lock` is for running alongside another git process (IDE, concurrent
scan) that may hold `.git/index.lock` or `.git/FETCH_HEAD`. It skips `git fetch`
and passes `--no-optional-locks` to every git invocation.

**Warning:** with `--disable-lock`, no fetch runs, so `AHEAD` / `BEHIND` reflect
whatever the last fetch saw and will be stale relative to the remote. Dirty-tree
detection (`STAGED` / `UNSTAGED` / `UNTRACKED`) is unaffected.

`--ignore-prefix` changes how `ignore.txt` entries are matched. By default an
entry only matches an exact path or a parent directory (e.g.
`~/Projects/workspaces/DOSD` skips `…/DOSD/foo` but not `…/DOSD-5844/foo`). With
`--ignore-prefix`, each entry is treated as a plain text path-prefix, so the
same entry also skips `…/DOSD-5844`, `…/DOSD-5904`, and any sibling whose name
starts with `DOSD`. Useful for ticket-prefix-style workspace layouts.

### Output

```
~/Projects/foo is AHEAD
~/Projects/bar is BEHIND
~/Projects/baz is AHEAD and BEHIND (diverged)
```

Prints `All repos are up to date` when nothing is out of sync.

### Ignore file

`~/.config/check-git-repos-source/ignore.txt` — one path per line (`~` is
expanded). Any repo whose path starts with an ignored prefix is skipped
entirely during the walk. Lines beginning with `#` are treated as comments.
The file is optional; if it does not exist the tool runs without error.

Example:

```
# skip archived work
~/archives/playbook
```

### Build

```sh
cd ~/tools/check-git-repos-source
make install   # rebuild and reinstall to ~/bin/check-git-repos
make build     # build only
make clean     # remove local build artifact
```

### Dependencies

`go` 1.21+, `git`

---

## `skill`

Compiled Go binary; source is not in this repo. Listed in `.gitignore`.

---

## `create-ticket-in-youtrack` / `create-ticket-in-youtrack.py`

Interactively create a new YouTrack issue in either `Work - Inbox` or
`Kevin - Inbox`. The `create-ticket-in-youtrack` shell wrapper calls
`create-ticket-in-youtrack.py` from the same directory.

### Usage

```sh
create-ticket-in-youtrack
# or directly:
python3 ~/tools/create-ticket-in-youtrack.py
```

No CLI args — all input is interactive.

### Behavior

1. Prompts `Is this work (Y/n):` — chooses `Work - Inbox` (default) or
   `Kevin - Inbox`.
2. Prompts for a required `Description` and an optional `Ticket link` URL.
3. Derives the issue summary from the first line of the description
   (truncated to 120 chars with `…` if longer).
4. Resolves the target project ID via `GET /api/admin/projects` by name.
5. Creates the issue via `POST /api/issues`, requesting both the
   internal `id` and the human-readable `idReadable` (e.g. `WORK-123`).
6. If a ticket link was supplied, sets the `Ticket link` custom field.
   Failure to set it is logged as `WARN:` and does not abort.
7. Prints two final lines on success:
   - `CREATED: <idReadable> in <project name>`
   - `URL: <YOUTRACK_SERVER>/issue/<idReadable>` — a clickable link to
     the issue. Falls back to the internal `id` if `idReadable` is
     missing from the response.

Exit codes: `0` = success (a failed ticket-link set still returns `0`),
`1` = missing env var, unreadable token, project not found, or HTTP error.

### Configuration

- `YOUTRACK_SERVER` env var — full URL of the YouTrack instance
  (e.g. `https://youtrack.example.com`). Set in
  `~/.environment/self-hosted-services.sh`, sourced by `~/.bashrc` and
  `~/.zshrc`. The script exits immediately with an error if this var is
  not set.
- `~/.config/YouTrack/self-host-api.txt` — permanent API token, one
  line, `chmod 600`.

### Dependencies

Python 3 standard library only (`urllib`, `json`, `pathlib`). No `pip install`
required.
