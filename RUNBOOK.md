---
title: RUNBOOK
tags: [runbook, operations]
vault_link: runbooks/home-kinscoe-tools.md
source_path: /home/kinscoe/tools/RUNBOOK.md
---

> 📓 Indexed in the PKM knowledge vault at `runbooks/home-kinscoe-tools.md` (symlink → this file).
# RUNBOOK

Operational reference for the scripts in this repo. Each entry covers purpose,
usage, and notable behavior. Keep this in sync when script functionality changes.

## `gitcf`

Python TUI that surfaces every untracked or modified file in the current git
repo, lets you multi-select which to commit via an urwid checkbox picker,
commits the selection (one batch commit when a memo is given; one commit per
file otherwise), then pushes `HEAD` to `origin`.

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
  - **With a memo**: all selected files are staged together and committed in a
    single `git commit -m "<memo>"`. The memo is used verbatim.
  - **Without a memo** (press Enter): each file gets its own commit using the
    default scheme — `Added <basename>` for an untracked entry (`??`),
    `Modified <basename>` otherwise.
- After all commits are made, `git push origin HEAD` is run once.
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

## `mdf`

Pick a Markdown file from the current directory and open it in the `mdfried`
terminal Markdown viewer. Replaces a plain `find | fzf` one-liner with a styled
`fzf` chooser that shows a live `glow`-rendered preview of the highlighted file.

### Usage

```
mdf              # run from any directory containing Markdown files
mdf -h | --help
```

No file arguments — the chooser is the only interface.

### Behavior

- `find . -maxdepth 1 -type f \( -iname '*.md' -o -iname '*.markdown' \)`
  collects Markdown files in the **current directory only** (no recursion),
  as basenames, sorted alphabetically.
- Exits `1` with a message when the current directory has no Markdown files.
- The chooser is `fzf` styled with a rounded border, a border label, an inline
  info line, cycling, and a right-hand preview pane (60% width) that renders the
  highlighted file through `glow --style=auto` (adapts to a light or dark
  terminal). Preview width tracks `FZF_PREVIEW_COLUMNS`.
- Type to fuzzy-filter; `Enter` opens the highlighted file via `exec mdfried`.
- `Esc` / `Ctrl-C` (fzf exit code 130) is treated as a clean cancel — the
  script exits `0` and opens nothing.
- Argument handling: `-h`/`--help` prints usage; any other argument prints an
  error plus usage and exits `2`.

### Dependencies

`fzf`, `glow` (preview pane), `mdfried` (viewer). Standard `find`/`sort` from
coreutils/findutils. Uses the GNU `find -printf` extension (present on Fedora).

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

Launch `claude` inside a named `abduco` session with `script` logging to
disk, and write a cleaned text sibling next to the raw log when the session
exits. `myclaude-screen` is the legacy `screen`-based version preserved for
platforms where `abduco` is unavailable.

### Usage

```
myclaude                          # run from any directory under $HOME
myclaude --clean <log-file>       # post-process a raw .log into a .txt sibling
```

### Behavior

- Prompts for a session name before launching. Rules:
  - Leading and trailing whitespace is stripped.
  - Remaining spaces are replaced with hyphens.
  - All non-alphanumeric, non-hyphen characters are stripped.
  - The result is lowercased.
  - Empty input (or input that sanitizes to empty) → exits 1 with an error.
  - Result longer than 15 characters → exits 1 with an error.
  - Example: `"Today's Journal"` → `todays-journal` (13 chars, valid).
- Errors out if the current directory is not under `$HOME`.
- Errors out if an abduco session with the same name already exists
  (attach the existing one with `abduco -a <name>`).
- `script -a -f -q -c 'date && exec claude' <log-file>` runs inside the
  abduco session: `script` starts logging immediately, then `date` prints a
  timestamp and `exec claude` replaces the shell with claude. When claude
  exits, script exits and the abduco session ends.
- `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` is exported so Claude Code
  (>= 2.1.132) renders into the terminal's native scrollback rather than
  the fullscreen alt-screen renderer — yields significantly cleaner logs.
- `PARZIVAL_IDENTITY` is defaulted to `ai` for everything launched in the
  session, so credential fetches made by an agent run under a restricted
  identity rather than an unlabelled one. **Why:** this script records the
  entire session to disk (the raw `.log` and its cleaned `.txt`), so any
  credential printed here is captured permanently — on top of the agent's own
  context, the model provider, and the terminal scrollback. Parzival policy
  rules can gate on delivery mode, so a rule such as
  `{"identities": ["ai"], "modes": ["exec","mount"]}` lets an agent *use* a
  credential via `parzival exec` / `parzival mount` while refusing
  `parzival get`, which writes the raw value straight into this log.
  - It sets a **default only**: an explicit `--as` flag beats the environment,
    and a `PARZIVAL_IDENTITY` exported before running `myclaude` is preserved.
  - The identity is **self-asserted and is not an authentication boundary** —
    it scopes honest callers and labels the audit trail. A process that wants
    to bypass it can.
  - Harmless if parzival is not installed: nothing reads the variable.
  - Parzival lives at `~/Projects/private/parzival`; see its `THREAT-MODEL.md`
    §4b ("Accidental disclosure to a recording sink").
- Log path: `<LOG_ROOT>/CLAUDE/_<REL>/YYYY-MM-DD-HH-MM.log`
  where `<REL>` is the cwd relative to `$HOME` with `/` replaced by `-`
  (so `~/.environment` → `_.environment`, `~/Projects/foo` → `_Projects-foo`,
  and `$HOME` itself → `_home`). The leading `_` makes the per-cwd directory
  stand out in listings. The full directory is auto-created.
- After `abduco` returns, the script checks the abduco session listing to
  distinguish a true exit (session gone) from a detach (Ctrl+\ — session
  still recording):
  - **True exit:** runs the cleanup pipeline and prints `myclaude: cleaned
    log -> <path>.txt` next to the raw `.log` line.
  - **Detach:** prints a reattach hint and does **not** clean (the log is
    still being written). Run `myclaude --clean <log-file>` once the
    session has truly ended.
- The script's exit code is `abduco`'s exit code (i.e., the inner
  `date && exec claude` exit code on true exit, or 0 on detach).

### Session management

| Action | Command |
|---|---|
| Detach | Ctrl+\ |
| List sessions | `abduco` |
| Reattach | `abduco -a <session-name>` |

### Migration from myclaude-screen (screen → abduco)

```
┌─────────────────┬────────────────────────────────────┬───────────────────┐
│                 │ old myclaude (now myclaude-screen) │   new myclaude    │
├─────────────────┼────────────────────────────────────┼───────────────────┤
│ Session manager │ screen                             │ abduco            │
├─────────────────┼────────────────────────────────────┼───────────────────┤
│ Detach key      │ Ctrl-A D                           │ Ctrl+\            │
├─────────────────┼────────────────────────────────────┼───────────────────┤
│ Reattach        │ screen -r SESSION                  │ abduco -a SESSION │
├─────────────────┼────────────────────────────────────┼───────────────────┤
│ List sessions   │ screen -ls                         │ abduco            │
├─────────────────┼────────────────────────────────────┼───────────────────┤
│ Logger          │ screen -L via screenrc             │ script(1)         │
└─────────────────┴────────────────────────────────────┴───────────────────┘
```

### Cleanup pipeline

The cleaner produces `<basename>.txt` next to the raw `<basename>.log`:

1. Drop alt-screen toggle blocks (`CSI ?1049h … ?1049l`, `?1047`, `?47`)
   if any are present, including unmatched-enter through EOF (covers a
   crash mid-session).
2. Strip remaining ANSI escape sequences via `ansifilter` (preferred) or
   `ansi2txt`.
3. `col -b` to fold backspace overwrites.
4. `tr -d '\r'` to drop carriage returns left over from in-place redraws.
5. `cat -s` to squeeze runs of blank lines.

`LC_ALL=C` is set on the byte-oriented filters so BSD (macOS) builds don't
abort with "Illegal byte sequence" on UTF-8 multi-byte input.

**Fidelity caveat.** With `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1`, step 1's
alt-screen toggle stripping is typically a no-op (no toggles emitted), and
final prompts + assistant turns settle into the scrollback as readable text.
Some control-sequence noise still slips through during a live session
(status line, streaming-response animation, autocomplete suggestions), but
the trailing redraws no longer overwrite committed turns. Useful for grep
and diary skim, not a substitute for the structured JSONL transcript Claude
already writes under `~/.claude/projects/`.

If neither `ansifilter` nor `ansi2txt` is installed, the cleaner skips the
`.txt` sibling and prints an install hint. The raw `.log` is unaffected.

### Configuration

Log root is read from one of:

| Platform | Config file |
|---|---|
| macOS | `~/.environment/claude-diary-log-path-for-mac.txt` |
| Fedora (x86_64) | `~/.environment/claude-diary-log-path-for-fedora.txt` |
| Raspberry Pi (arm64) | `~/.environment/claude-diary-log-path-for-rpi.txt` |

Each file contains a single line: the log root directory (leading `~` is
expanded to `$HOME`). The script errors out if the file is missing or empty.

### Dependencies

- `abduco` — session management (`dnf install abduco`; `brew install abduco`)
- `script` from `util-linux-script` — terminal session recorder
  (`sudo dnf install util-linux-script` on Fedora; included in `util-linux`
  on most other Linux distros and macOS)
- `claude` >= 2.1.132 — required for `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN`
  (the script auto-runs `claude update` and re-checks if the installed
  version is older; see [Claude Code 2.1.132 release notes](https://code.claude.com/docs/en/changelog#2-1-132))
- `bash`, `date`, `mkdir`, `sort` (for `sort -V` semver comparison)
- Cleanup pipeline also needs: `perl`, `col`, `tr`, `cat`, and one of
  `ansifilter` (preferred) or `ansi2txt`
  (`brew install ansifilter` on macOS; `dnf install ansifilter` or
  `dnf install colorized-logs` on Fedora)

---

## `myclaude-screen`

Legacy `screen`-based version of `myclaude`, preserved for platforms where
`abduco` is unavailable. Identical to the original `myclaude` before the
abduco migration. See `## myclaude` for the current version and log format.

### Usage

```
myclaude-screen                   # run from any directory under $HOME
myclaude-screen --clean <log-file>
```

### Dependencies

`screen` >= 4.06 (required for `-Logfile`; on macOS install via Homebrew).
All other dependencies same as `myclaude`.

---

## `mycodex`

Launch `codex` inside a named `abduco` session with `script` logging to disk,
and write a cleaned text sibling next to the raw log when the session exits.
Identical in structure to `myclaude` but targets the `codex` CLI instead of
`claude`. Logs land under `CODEX/` rather than `CLAUDE/` in the shared log root.

### Usage

```
mycodex                          # run from any directory under $HOME
mycodex --clean <log-file>       # post-process a raw .log into a .txt sibling
```

### Behavior

- Prompts for a session name before launching. Rules:
  - Leading and trailing whitespace is stripped.
  - Remaining spaces are replaced with hyphens.
  - All non-alphanumeric, non-hyphen characters are stripped.
  - The result is lowercased.
  - Empty input (or input that sanitizes to empty) → exits 1 with an error.
  - Result longer than 15 characters → exits 1 with an error.
- Errors out if the current directory is not under `$HOME`.
- Errors out if an abduco session with the same name already exists.
- `script -a -f -q -c 'date && exec codex' <log-file>` runs inside the
  abduco session: `script` starts logging immediately, then `date` prints a
  timestamp and `exec codex` replaces the shell with codex.
- `PARZIVAL_IDENTITY` is defaulted to `ai`, exactly as in `myclaude` and for
  the same reason: the session is recorded to disk, so a credential printed
  here is captured permanently. A parzival rule such as
  `{"identities": ["ai"], "modes": ["exec","mount"]}` lets an agent *use* a
  credential while being refused `parzival get`, which would write the raw
  value into this log. Both launchers share the one identity, so a single
  policy rule covers them. Default only — an explicit `--as` flag wins, and a
  pre-exported `PARZIVAL_IDENTITY` is preserved. Self-asserted, not an
  authentication boundary. See `~/Projects/private/parzival` THREAT-MODEL.md §4b.
- Log path: `<LOG_ROOT>/CODEX/_<REL>/YYYY-MM-DD-HH-MM.log`
  where `<REL>` is the cwd relative to `$HOME` with `/` replaced by `-`
  (e.g. `~/.environment` → `_.environment`, `~/Projects/foo` → `_Projects-foo`,
  `$HOME` itself → `_home`).
- After `abduco` returns, detach vs. true exit is detected via the abduco
  session listing:
  - **True exit:** runs the cleanup pipeline and writes a `.txt` sibling.
  - **Detach:** prints a reattach hint; run `mycodex --clean <log-file>` once
    the session has truly ended.

### Session management

| Action | Command |
|---|---|
| Detach | Ctrl+\ |
| List sessions | `abduco` |
| Reattach | `abduco -a <session-name>` |

### Cleanup pipeline

Same pipeline as `myclaude` — see `## myclaude` for full details. Produces
`<basename>.txt` next to the raw `<basename>.log`:

1. Drop alt-screen toggle blocks via `perl`.
2. Strip ANSI escapes via `ansifilter` (preferred) or `ansi2txt`.
3. `col -b` to fold backspace overwrites.
4. `tr -d '\r'` to drop carriage returns.
5. `cat -s` to squeeze blank-line runs.

### Configuration

Uses the same log-root config files as `myclaude`:

| Platform | Config file |
|---|---|
| macOS | `~/.environment/claude-diary-log-path-for-mac.txt` |
| Fedora (x86_64) | `~/.environment/claude-diary-log-path-for-fedora.txt` |
| Raspberry Pi (arm64) | `~/.environment/claude-diary-log-path-for-rpi.txt` |

### Dependencies

- `abduco` — session management (`dnf install abduco`; `brew install abduco`)
- `script` from `util-linux-script` — terminal session recorder
  (`sudo dnf install util-linux-script` on Fedora)
- `codex` — must be on `$PATH`
- `bash`, `date`, `mkdir`
- Cleanup pipeline: `perl`, `col`, `tr`, `cat`, and one of `ansifilter` or
  `ansi2txt` (`brew install ansifilter` on macOS; `dnf install ansifilter` on
  Fedora)

---

## `claude-log-view`

Curses TUI picker for `myclaude` session logs. Reads the log root from
`~/.environment/claude-diary-log-path.txt` and browses
`<LOG_ROOT>/CLAUDE/_<REL>/*.log`, where each `_<REL>` directory groups logs
by the cwd `myclaude` was launched from (e.g. `_.environment`, `_tools`,
`_Projects-foo`, `_home`).

### Usage

```
claude-log-view
```

### Behavior

- Opens on the `_<REL>` cwd-directory matching the current cwd (mirrors
  `myclaude`'s session-naming rule: `/` → `-`, `$HOME` itself → `_home`);
  falls back to the most recently modified `_<REL>` directory if the
  current cwd has no logs.
- Press `d` to switch to a list of all `_<REL>` directories that contain
  logs (sorted newest-first by mtime); Enter on a directory drops into
  its file list.
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
- `q` / `Esc` quits; in cwds mode `Esc` / `d` returns to the file list.
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

## `eks`

Python urwid TUI for switching to an EKS cluster. Reads
`~/.environment/eks-clusters.dat`, performs AWS SSO login for the selected
profile, writes the profile to `~/.environment/.env_set.sh`, and runs
`aws eks update-kubeconfig` to merge the cluster into `~/.kube/config`.

### Usage

```
eks
```

No arguments. The TUI is the only interface.

### Data file format

`~/.environment/eks-clusters.dat` — one cluster per line:

```
<cluster-name>:(<aws-profile>):<optional description>
```

Example:
```
my-cluster:(my-sso-profile):Production EKS
```

Lines beginning with `#` and blank lines are ignored. Entries are sorted
alphabetically by cluster name before display.

### Behavior

- Opens a full-screen urwid RadioButton picker showing Cluster, Profile, and
  Description columns.
- `Space` selects; `Enter` confirms and exits the TUI; `Q` / `Esc` cancels.
- On confirmation:
  1. `aws sso login --profile <profile>` — authenticates (opens browser).
  2. Writes `~/.environment/.env_set.sh` exporting `AWS_PROFILE`,
     `AWS_DEFAULT_PROFILE`, and unsetting `AWS_ACCESS_KEY_ID` /
     `AWS_SECRET_ACCESS_KEY`.
  3. Waits 2 seconds for the SSO token to settle.
  4. `aws eks update-kubeconfig --name <cluster> --profile <profile>` — merges
     the cluster into `~/.kube/config` using the correct profile (non-fatal if
     it fails).
  5. If `~/bin/what_aws_eks_cluster_am_i_in.sh` exists, runs it to print a
     confirmation banner.

### Dependencies

`aws` CLI (v2, authenticated SSO), `python3`, `urwid`

---

## `k3s`

Python urwid TUI for switching the default kubectl context to a k3s cluster.
Reads `~/.environment/k3s-clusters.dat` and runs `kubectl config use-context`
on the selected entry.

### Usage

```
k3s
```

No arguments. The TUI is the only interface.

### Data file format

`~/.environment/k3s-clusters.dat` — one cluster per line:

```
<cluster-name>:(<context-name>):<optional description>
```

Example:
```
lab:(lab)
dev:(dev)
prod:(prod)
```

Lines beginning with `#` and blank lines are ignored. Entries are sorted
alphabetically by cluster name before display.

### Behavior

- Opens a full-screen urwid RadioButton picker showing Cluster, Context, and
  Description columns.
- `Space` selects; `Enter` confirms and exits the TUI; `Q` / `Esc` cancels.
- On confirmation, runs:
  1. `kubectl config use-context <context>` — sets the default context.
  2. `kubectl config current-context` — prints confirmation to stdout.
- Cancelled or empty selection exits 0 with `Cancelled.` on stderr.

### First-run venv bootstrap

If `urwid` is not importable from the system Python the script will fail
with an `ImportError`. Install urwid system-wide or into a venv:

```
pip install urwid          # user-level
sudo dnf install python3-urwid   # Fedora system-wide
```

### Dependencies

`kubectl` (configured and on `$PATH`), `python3`, `urwid`

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

### Nested repos inside gitignored directories

If a repo lives inside another repo that gitignores it (e.g. a reference clone
dropped into a subdirectory that the parent lists in `.gitignore`), it is
automatically skipped — no ignore file entry is needed. Detection happens
post-walk: the tool runs `git check-ignore` against the enclosing repo and
excludes the nested repo if the parent gitignores its path.

### Build

```sh
cd ~/tools/check-git-repos-source
make install   # rebuild and reinstall to ~/bin/check-git-repos
make build     # build only
make clean     # remove local build artifact
```

### Dependencies

`go` 1.26+, `git`

---

## `check-git-branch`

Go program that walks git repositories under `$HOME` (or paths in `$CHECK_GIT_BRANCH`) and reports any whose current branch is not the remote default, or that have non-default local branches left over from previous work. Purely local — no `git fetch` is performed. All repos are checked concurrently. Silent when everything is clean.

Source lives in `~/tools/check-git-branch-source/`; the compiled binary installs to `~/bin/check-git-branch`.

Install by curling the release binary (see `check-git-branch-source/README.md` for per-platform URLs) or via `make install` from source.

### Usage

```
check-git-branch                 # scan and report
check-git-branch --batch-mode    # scan without progress spinner (systemd/cron)
check-git-branch --ignore-prefix # treat ignore entries as text prefixes (see below)
check-git-branch --version       # print version and exit
check-git-branch --help          # print usage and exit
```

### Output

```
~/Projects/foo - NOT AT DEFAULT BRANCH (feature/login)
~/Projects/bar - non-current local branches: feature/old-work, hotfix/123
~/Projects/baz - NOT AT DEFAULT BRANCH (feature/wip) | non-current local branches: feature/old-work
~/Projects/qux - LOCAL ONLY
~/Projects/lib - ORIGIN/HEAD ISN'T SET
```

One line per repo, silent when clean. Both conditions appear on the same line separated by ` | ` when both fire.

| Status | Meaning |
|--------|---------|
| `NOT AT DEFAULT BRANCH (name)` | Current branch is not the remote default |
| `non-current local branches: …` | Non-default local branches exist (stale work from a previous feature) |
| `LOCAL ONLY` | No remote configured |
| `ORIGIN/HEAD ISN'T SET` | origin exists but `HEAD` ref is unset — run `git remote set-head origin --auto` to fix |
| `REMOTE CANNOT BE DETERMINED` | git remote query failed |

### Scan root — `CHECK_GIT_BRANCH`

By default the tool scans `$HOME`. Set `CHECK_GIT_BRANCH` to a colon-separated list of paths to scan instead:

```sh
export CHECK_GIT_BRANCH=~/Projects:/srv/repos
```

`~` is expanded. Every listed path must exist and be a directory or the program exits with an error.

### Ignore file

`~/.config/check-git-branch/ignore.txt` — one path per line (`~` expanded). Any repo whose path starts with an ignored prefix is skipped entirely. Lines beginning with `#` are comments. File is optional.

### `--ignore-prefix`

Changes ignore-file matching to treat each entry as a plain text path-prefix rather than an exact path/parent. Useful for ticket-prefix workspace layouts (e.g. one entry skips `DOSD-5844`, `DOSD-5904`, etc.).

### Build

```sh
cd ~/tools/check-git-branch-source
make install   # rebuild and reinstall to ~/bin/check-git-branch
make build     # build only
make clean     # remove local build artifact
```

### Dependencies

`go` 1.26+, `git`

---

## `menu-app`

Go program (Bubble Tea TUI) that reads a `.menu-app.yaml` file from the **git root** of the current directory and presents its entries as a selectable menu of scripts. Selecting an item runs its script — from the git root — and then returns to the menu.

Source lives in `~/tools/menu-app-source/`; the compiled binary installs to `~/bin/menu-app`. A starter config template lives at `~/tools/menu-app-template.yaml`.

### Install

**Homebrew (macOS / Linux)**

```sh
brew tap kevinpinscoe/homebrew-tap
brew install --cask menu-app
```

`menu-app` shipped as a formula until the cask migration. If an older install
is present, `brew uninstall menu-app` first — a formula and a cask of the same
name cannot coexist.

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

For binary download or build-from-source, see `menu-app-source/README.md`.

### Usage

```
menu-app             # open the menu for the current repository
menu-app --version   # print version and exit
menu-app --help      # print usage and exit
```

### Config file — `.menu-app.yaml`

Must live at the git root. Flat list of items; each item has a `name` (shown in the menu) and a `script` (path **relative to the git root**), plus an optional `prompt`:

```yaml
items:
  - name: Run tests
    script: scripts/test.sh
  - name: Build project
    script: scripts/build.sh
  - name: Deploy to URL
    script: scripts/deploy.sh
    prompt: "Enter URL:"
```

- Scripts must be executable (`chmod +x scripts/test.sh`).
- Scripts run with the git root as their working directory.
- `prompt` is optional (added in v2.0.0). When present, selecting the item shows a text input labeled with the prompt text first; the typed value is passed to the script as its sole argument. Esc cancels back to the menu without running the script.

### Behavior

| Situation | Behavior |
|-----------|----------|
| Not inside a git repository | Prints `not a git initialized directory` to stderr, exits `1` |
| `git` not on `PATH` | Prints `git is not installed or not found in PATH`, exits `1` |
| Inside a repo, no `.menu-app.yaml` | Prompts `Create one from the template? [y/N]`; on `y` writes the template to the git root, then exits |
| `.menu-app.yaml` present, has items | Opens the menu |
| `items:` empty or missing | Prints an error, exits `1` |
| Item missing `name` or `script` | Prints an error, exits `1` |
| Malformed YAML | Prints the parse error with the file path, exits `1` |
| Item has a `prompt` | Shows a text input first; Enter runs the script with the typed text as its sole argument, Esc cancels back to the menu |
| Selected script missing / a directory | Shows an error screen, returns to the menu |
| Selected script exits non-zero | Shows the exit code, returns to the menu |

The git root is found with `git rev-parse --show-toplevel`.

### Keys

| Key | Action |
|-----|--------|
| `Enter` | Run the highlighted script |
| `/` | Filter the list |
| `q` / `Ctrl+C` | Quit |
| any key (result screen) | Return to the menu |

### Build

```sh
cd ~/tools/menu-app-source
make install   # rebuild and reinstall to ~/bin/menu-app
make build     # build only (outputs ./menu-app)
make clean     # remove local build artifact
```

`make build`/`make install` stamp the version from the latest `menu-app-v*`
git tag (`git describe`, with the `menu-app-v` prefix stripped so only the
bare number/suffix is injected — `main.go`'s `--version` output adds the `v`
itself), so `menu-app --version` reports e.g. `v1.0.0` or
`v1.0.0-3-gabc123` when ahead of a tag; it falls back to `dev` outside git. A
bare `go build` (no ldflags) reports `dev`.

### Dependencies

`go` 1.26+, `git`. Go modules: `bubbletea`, `bubbles`, `lipgloss`, `gopkg.in/yaml.v3`.

### Release history

Each release is a `menu-app-v*` tag on `main`, picked up by the
`menu-app-release.yml` GitHub Actions workflow, which builds binaries and
`.deb`/`.rpm` packages, cuts the GitHub release, and repository-dispatches
`new-release` to `kevinpinscoe/apt` and `kevinpinscoe/rpm` plus a Homebrew
cask update to `kevinpinscoe/homebrew-tap` — all three install paths above
update together from one tag push.

| Version | Date | Changes |
|---|---|---|
| `v1.0.0` | 2026-06-25 | Initial release. |
| `v1.0.1` | 2026-06-30 | Added `.deb`/`.rpm` packaging via `nfpm` and the APT/RPM repo dispatch; fixed `sha256sum -c` checksum verification of the downloaded `nfpm` tarball (it resolves paths relative to cwd, so verification must run from `/tmp` against the original filename). |
| `v1.0.2` | 2026-07-11 | Fixed `VERSION` derivation drift — redundant/inconsistent `menu-app-v` prefix stripping between the Makefile and the release workflow. |
| `v2.0.0` | 2026-07-21 | Added an optional per-item `prompt` field to `.menu-app.yaml`: shows a text input before running a script and passes the typed value as the script's sole argument. |

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

---

## `pause`

Compiled Go binary that wraps `sleep` with a live countdown status line on
stderr. Source lives in `pause-source/`; binary is installed at
`~/tools/pause` (git-ignored).

### Usage

```
pause <seconds>      # sleep with live countdown
pause --version      # print version and exit
pause --help         # print this help
```

`<seconds>` is a required non-negative integer.

### Status line (TTY)

When stderr is a terminal a single overwriting line is shown and refreshed
continuously:

- Total ≤ 60 s: `Pausing for 45 seconds   ⠙   32s remaining`
- Total > 60 s: `Pausing for 1m 30s   ⠙   1m 15s remaining`

The braille spinner rotates every 100 ms; the remaining-time counter
decrements each second. When the pause ends the status line is erased.

### Non-TTY

When stderr is not a terminal (pipe, redirect, cron, systemd), a single
line is printed once and the process sleeps silently:

```
Waiting for 1m 30s
```

### Build

```sh
cd ~/tools/pause-source
make install   # rebuild and reinstall to ~/tools/pause
make build     # local build only (outputs ./pause)
make clean     # remove local build artifact
```

### Dependencies

`go` 1.26+

---

## `what-did-i` / `what-did-i-accomplish-today.py`

Queries today's git commits from GitHub and Gitea and writes a dated Markdown
summary to the Journal accomplishments directory. Also prints to stdout.

The `what-did-i` shell wrapper calls `what-did-i-accomplish-today.py` from the
same directory.

### Usage

```
what-did-i                # summarise today's commits
what-did-i yesterday      # summarise yesterday's commits
what-did-i 2026-07-21     # summarise a specific date (backfill a missed day)
what-did-i -h | --help    # show usage and exit
```

### Output file

| OS | Path |
|---|---|
| Linux (Fedora) | `~/Journal/personal-journal/ACCOMPLISHMENTS/YYYY-MM/git-work-for-YYYY-MM-DD.md` |
| macOS | `~/Journal/Professional/ACCOMPLISHMENTS/YYYY-MM/git-work-for-YYYY-MM-DD.md` |

The directory is grouped by month (`YYYY-MM`) and created automatically if it does not exist. The filename itself is still date-stamped (`YYYY-MM-DD`) so files within a month sort naturally.

The `what-did-i` wrapper detects the OS via `uname -s` and exports `JOURNAL_PATH` before invoking Python. Running the `.py` script directly without that env var set will exit with an error.

### Output format

```markdown
# What did I accomplish today

Date: YYYY-MM-DD

## Commits

### GitHub

#### kevinpinscoe/<repo>

- `<sha>` <commit message> (YYYY-MM-DD HH:MM)

### Gitea (git.kevininscoe.com)

#### kinscoe/<repo>

- `<sha>` <commit message> (YYYY-MM-DD HH:MM)
```

Sections show "*(no commits today)*" (or "*(no commits yesterday)*") when nothing was found.

### Behavior

**`yesterday` argument** — passing the literal word `yesterday` (case-insensitive) as an argument shifts the target date one day back. The output file is named for the shifted date (`git-work-for-YYYY-MM-DD.md`) and placed in the corresponding month directory. The heading becomes `# What did I accomplish YYYY-MM-DD` instead of "today".

**`YYYY-MM-DD` argument** — passing an ISO date targets that specific day, for backfilling a run that was missed or failed. It takes precedence over `yesterday` if both are given. Note that backfilling rewrites the run marker (below) with the backfilled date, which will make the monitoring check see a stale date — re-run `what-did-i yesterday` afterwards to restore it.

**Run marker** — after writing the note, the script writes `~/.local/state/what-did-i-last-run.json`:

```json
{
  "date": "2026-07-25",
  "output_file": "/home/kinscoe/Journal/personal-journal/ACCOMPLISHMENTS/2026-07/git-work-for-2026-07-25.md",
  "output_bytes": 3416,
  "github_ok": true,
  "gitea_ok": true,
  "github_commits": 1,
  "gitea_commits": 30,
  "written_at": "2026-07-26T22:39:52.705236+00:00"
}
```

`github_ok` / `gitea_ok` are **reachability probes** (`gh api /user` and Gitea `/user`), not commit counts — a quiet day and a broken credential both produce zero commits, so counts cannot tell them apart. `~/admin/check-what-did-i/` asserts against these flags.

**GitHub** — uses `gh api /users/kevinpinscoe/events` to identify repos that
received a `PushEvent` on the target date. For each such repo, calls
`GET /repos/{owner}/{repo}/commits?since=<day>T00:00:00Z&until=<next>T00:00:00Z&author=kevinpinscoe`
to retrieve the commit details. Only repos that actually had a push that day incur
a second API call; the other ~900+ repos are never queried.

> **Backfill horizon.** GitHub caps this feed at **300 events** — page 4 returns
> HTTP 422 — so repo discovery only reaches as far back as those 300 events span.
> At current activity that is roughly two weeks. Backfilling a day older than the
> horizon yields `*(no commits …)*` under GitHub even though the commits exist;
> Gitea has no equivalent limit and backfills correctly at any depth. Before
> re-running an old day, compare commit SHAs against the existing note — a
> regeneration past the horizon will drop GitHub commits the note already holds.
>
> The loop pages to exhaustion deliberately. It previously stopped as soon as a
> page's *oldest* event predated the target, but the feed is not strictly ordered —
> a lone 2026-05-05 event on page 1 ended the loop immediately, so any day whose
> events had scrolled to page 2+ silently reported zero GitHub commits. Fixed
> 2026-07-26; the cap makes full paging cost at most three calls.

**Gitea** — resolves the token from `~/.config/gitea/api` if that file still
exists, otherwise from OpenBao (`mount=app`, path `gitea`, field `token`) using
the vault token at `~/.environment/.vault-token`. The on-disk file was shredded
2026-07-12, so OpenBao is the effective source of truth. If neither yields a
token the run degrades to a GitHub-only report rather than aborting. Lists all repos via
`GET /api/v1/repos/search` (paginated, 50 per page). Filters to repos whose
`updated_at` field falls on today's date, then calls
`GET /api/v1/repos/{owner}/{repo}/commits?since=<today>&limit=50` for each.
Commits are filtered to those authored by `kevin.inscoe@gmail.com`.

All timestamps are converted from UTC to local time in the output.

### Configuration

No configuration files are needed beyond the standard tool authentication:

- `gh` must be authenticated (`gh auth status` should show `kevinpinscoe`).
- The Gitea token must be retrievable from OpenBao:
  `bao kv get -field=token -mount=app gitea`. This requires a valid vault token
  at `~/.environment/.vault-token`. (A legacy `~/.config/gitea/api` file is still
  honoured if present, but it was shredded on 2026-07-12.)

**`BAO_BIN`** — the `bao` binary is located via `$BAO_BIN`, then
`shutil.which("bao")`, then `~/.local/bin/bao`. The fallback matters: systemd's
default `PATH` excludes `~/.local/bin`, which broke the nightly timer for six
days in July 2026 while the command still worked interactively. Set `BAO_BIN`
explicitly to test against a different binary.

### Systemd timer

A systemd service and timer run `what-did-i yesterday` automatically at 00:30 daily. Unit files and the full operational runbook live at `~/admin/what-did-i/RUNBOOK.md` (repo: `ssh://git@git.kevininscoe.com:2223/kinscoe/fedora-admin.git`).

The unit sets `Environment=PATH=/home/kinscoe/.local/bin:/usr/local/bin:/usr/bin:/bin` so `bao` resolves — see `BAO_BIN` under Configuration.

A companion check, `check-what-did-i.service`/`.timer` (daily 08:00), monitors this job and alerts to Telegram on failure. See `~/admin/check-what-did-i/RUNBOOK.md`.

### Dependencies

`python3` (stdlib only — no `pip install` needed), `gh` (authenticated)

## `trufflehog.sh`

Bash wrapper around `trufflehog filesystem` that scans credential-relevant paths for secrets. Detects the current platform (Fedora, macOS, Raspberry Pi) from `uname -s` and adjusts the scan paths accordingly. Paths that do not exist on the current machine are silently skipped. After scanning it prints a summary grouped by detector type to stdout. Raw findings (one JSON object per line) are written to an output file for further inspection.

Use the output to compare against `~/.environment/.credentials-map.md` and identify undocumented credential locations.

### Usage

```
trufflehog.sh [OUTFILE]
```

`OUTFILE` defaults to `/tmp/trufflehog-findings.json`. The file is overwritten on each run.

### Paths scanned

**All platforms:**
`~/.secrets`, `~/.config`, `~/.aws`, `~/.environment`, `~/.dotfiles`, `~/.vault-token`, `~/.codex`, `~/.jenkins_scripts_token`, `~/tools`, `~/admin`, `~/skills`, `~/todo`

**macOS only (additional):**
`~/.homebrew`, `~/.gh_token`, `~/.realm-release`, `~/Library/Application Support/Claude/claude_desktop_config.json`

### Behavior

- Runs `trufflehog filesystem` with `--json --no-verification` (no external API calls).
- Logs scan metadata (host, date, paths) to stderr before starting.
- After the scan, a Python inline script reads the output file and prints total finding count and a per-detector breakdown with source file paths.

### Reading results

High-signal detectors: `AWS`, `AWSSessionKey`, `GCP`, `GCPApplicationDefaultCredentials`, `PrivateKey`, `JWT`, `GoogleOauth2`.

Typical noise to filter out: browser SQLite databases (`librewolf`, `Slack` service-worker caches), compiled app JS caches (`Claude/Code Cache/`), VM bundle binaries (`.vhdx`), and reference documentation (`codex` plugin docs, cheatsheets).

### Dependencies

`trufflehog` (install: `curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b ~/.local/bin`), `python3` (stdlib only)

---

## `title`

Convert text to a markdown-filename-friendly slug. The intended use is turning
cut-and-pasted headings or freeform text into clean Markdown filenames.

**This tool processes text only.** To rename an actual file on disk, use
`fix-file-name.sh`.

### Usage

```
title "Some String Here"
title ALSO WORKS WITHOUT QUOTES
```

All arguments are joined into a single string before processing.

### Transformation rules

1. All contiguous runs of non-alphanumeric characters (spaces, underscores,
   brackets, punctuation, etc.) are replaced with a single `-`.
2. The result is lowercased.
3. Any leading or trailing hyphens are stripped.

Dots are treated as punctuation and are replaced like any other non-alphanumeric
character. If the input contains a dot, `title` assumes you accidentally passed
a filename, prints a warning, recommends `fix-file-name.sh`, and exits 1.

### Examples

```
"My Meeting Notes"       →  "my-meeting-notes"
"Q1 Report (Draft)"      →  "q1-report-draft"
"  leading spaces  "     →  "leading-spaces"
"hello__world"           →  "hello-world"
"report.txt"             →  error: use fix-file-name.sh
```

### Dependencies

`bash`, `sed`, `tr`

---

## `youtube-md`

Fetch a YouTube video's title, slugify it, then parse the page with `defuddle`
and save the result as a Markdown file in the current directory.

### Usage

```
youtube-md [URL]
```

If `URL` is omitted the script prompts interactively.

### Behavior

1. Validates that `yt-dlp` and `defuddle` are on `$PATH`; exits 1 if either is
   missing.
2. Fetches the video title with `yt-dlp --print "%(title)s" --no-download`.
   All `yt-dlp` warnings are suppressed (stderr → `/dev/null`). Exits 1 if
   the title comes back empty (invalid URL, private video, etc.).
3. Slugifies the title using the same rules as `fix-file-name.sh`: runs of
   non-alphanumeric characters (except dots) collapse to a single hyphen; a
   hyphen immediately before a dot is dropped; leading/trailing hyphens are
   stripped; the result is lowercased.
4. Runs `defuddle parse --md "$URL"` and redirects stdout to `<slug>.md` in
   `$PWD`. Prints a warning to stderr if the file already exists (it is
   overwritten).
5. Prints `Saved: <filename>` to stdout on success.

### Examples

```
youtube-md https://www.youtube.com/watch?v=dQw4w9WgXcQ
# → Saved: rick-astley-never-gonna-give-you-up-official-video-4k-remaster.md

youtube-md   # prompts for URL
```

### Dependencies

`yt-dlp`, `defuddle`, `bash`, `sed`, `tr`

---

## `fix-file-name.sh`

Rename a file so its name contains only lowercase alphanumeric characters, dots,
and hyphens. Consecutive runs of anything else (spaces, underscores, brackets,
punctuation) collapse to a single hyphen; a hyphen immediately before a dot is
dropped; leading and trailing hyphens are stripped.

### Usage

```
fix-file-name.sh <file>
```

One positional argument: the path to the file (relative or absolute). The file
must already exist.

### Behavior

- Processes the basename only; the directory component is preserved unchanged.
- Each contiguous run of characters that are not `[a-zA-Z0-9.]` is replaced with
  a single `-`.
- A hyphen immediately before a dot (`-.`) is removed, so trailing punctuation
  before an extension does not produce names like `report-.pdf`.
- Leading and trailing hyphens produced by the above are stripped.
- The entire name (after the substitutions above) is lowercased via `tr`.
- If the computed new name equals the original, prints `No change needed:` and
  exits 0 — no `mv` is run.
- If the destination already exists, exits 1 with an error message.

### Examples

```
"Hello World (2024)!.txt"  →  "hello-world-2024.txt"
"  leading spaces.pdf"     →  "leading-spaces.pdf"
"Report_Q1.XLSX"           →  "report-q1.xlsx"
```

### Dependencies

`bash`, `sed`, `tr`

---

## `wd`

Print the current working directory. If the cwd is anywhere inside `$HOME`,
the `$HOME` prefix is replaced with `~` so the output is relative to home.

### Usage

```
wd
```

No arguments.

### Output examples

| cwd | output |
|-----|--------|
| `/home/kinscoe/ai` | `~/ai` |
| `/home/kinscoe` | `~` |
| `/tmp/work` | `/tmp/work` |

### Dependencies

`bash`

---

## Release signing (compiled binaries)

The compiled Go tools (`check-git-repos`, `check-git-branch`, `pause`,
`menu-app`) each have a per-tool release workflow in `.github/workflows/`
triggered by a `<tool>-v*` tag (e.g. `menu-app-v1.0.0`). Each workflow
cross-compiles the binaries, writes a `checksums.txt` (SHA-256), signs it with
[cosign](https://github.com/sigstore/cosign) (keyless / Sigstore OIDC), and
publishes a GitHub release.

### Release notes

Each workflow builds its release body with `.github/release-notes.sh <tool>
<tag>`, which walks the git log between the preceding `<tool>-v*` tag and the
one being released — restricted to that tool's `<tool>-source/` directory — and
groups the commit subjects by conventional-commit type (security fixes first,
then breaking changes, features, bug fixes, other). `docs:`, `test:`, `chore:`,
`ci:`, and merge commits are filtered out.

GitHub's built-in `generate_release_notes` is deliberately not used: it cannot
scope commits to one tool's directory in a monorepo, and it lists only merged
pull requests, so work committed directly to `main` — most of this repo — would
be omitted. Before 2026-07-26 no body was set at all and every release here
published empty; existing releases were backfilled with the same script.

Preview the notes for any tag locally before tagging:

```bash
cd ~/tools
bash .github/release-notes.sh menu-app menu-app-v2.0.0
```

The workflows check out with `fetch-depth: 0` because the script needs full
history and tags.

### Packaging

All four workflows additionally build `.deb` (amd64/arm64) and `.rpm`
(x86_64/aarch64) packages using `nfpm` and upload them alongside the
binaries. After the release is published they dispatch `new-release` events
to `kevinpinscoe/apt` and `kevinpinscoe/rpm`, which automatically ingest the
packages into the GitHub Pages-hosted APT and RPM repositories. (`menu-app`
had this from the start; `check-git-repos`, `check-git-branch`, and `pause`
gained it on 2026-07-11 — before that their apt/rpm packages silently
drifted behind GitHub Releases with every tag that wasn't manually
repackaged.)

Each workflow's binary embeds its version via `-ldflags "-X
main.version=..."` at build time (derived from the release tag) rather than
a hardcoded constant in `main.go` — this was also fixed on 2026-07-11 after
`check-git-repos`'s `--version` output was found to have drifted from its
actual released version.

All four per-tool workflows also update `kevinpinscoe/homebrew-tap`'s
`Casks/<tool>.rb` directly at the end of the job, using `HOMEBREW_TAP_TOKEN`.
The job clones the tap, runs `.github/homebrew-cask.py` (shared by all four
workflows) to write the whole cask from `checksums.txt` and the release tag,
then commits and pushes.

Before the 2026-07-27 cask migration each workflow embedded its own copy of a
formula generator that regex-patched `Formula/<tool>.rb` in place — rewriting
`version`, the per-platform `url`, and `sha256` line by line. Two things were
wrong with that. It failed silently if the formula's layout drifted, shipping a
formula still pointed at the previous release; and `brews:`/formulas are the
deprecated path (GoReleaser deprecated `brews:` in v2.10, removal announced for
v2.16). `homebrew-cask.py` writes the file whole instead, so the output is a
pure function of the checksums and the tag, and it errors out if an expected
binary is missing from `checksums.txt` rather than emitting a partial cask.

The generated cask deliberately matches what GoReleaser's `homebrew_casks:`
emits for the standalone Go repos (`get-wx`, `metar-tool`, `skills-tui`,
`aws-linux-memory-tools`), so every cask in the tap reads the same regardless
of which pipeline produced it. Casks serve Linux as well as macOS —
Homebrew/brew#19121 added Linux binary support — so nothing was lost by moving
off formulas.

Earlier history: the old repo-level `release.yml` (GoReleaser, triggered on an
unprefixed `vX.Y.Z` tag) published three formulas once for `v1.0.0` and nothing
replaced it afterward, so the tap was pinned to v1.0.0 until the per-tool
generators were added on 2026-07-11. `menu-app` had no formula at all until
that same date despite being documented as `brew install`-able.

Each workflow also accepts `workflow_dispatch` with a required `tag` input,
so a past release tag can be re-run (`gh workflow run
<tool>-release.yml --ref main -f tag=<tool>-vX.Y.Z`) to backfill packages
for a version that was tagged before this packaging step existed. The
`tag` input is required because `workflow_dispatch` only honors triggers
present in the workflow file at the ref being dispatched — dispatching
directly against an old tag (which predates the trigger) fails, so dispatch
against `main` and pass the historical tag explicitly instead.

### Signature format — Sigstore bundle

As of June 2026 the workflows sign `checksums.txt` into a single Sigstore
**bundle** file, `checksums.txt.bundle`, using:

```
cosign sign-blob --yes --bundle checksums.txt.bundle checksums.txt
```

The bundle contains both the signature and the signing certificate.

> **Why the change:** newer cosign (pulled by `cosign-installer`) defaults to
> the new bundle format and **ignores** the older `--output-signature` /
> `--output-certificate` flags, then fails with `create bundle file: open :
> no such file or directory`. All four release workflows were switched to
> `--bundle` to fix this.

- **Releases tagged from June 2026 onward** attach `checksums.txt` +
  `checksums.txt.bundle`.
- **Older releases** still attach the legacy `checksums.txt.sig` +
  `checksums.txt.pem` pair. Verify whichever assets a given release shipped.

### Verifying a download

```sh
# 1. Confirm the binary matches the published checksum
sha256sum --check checksums.txt        # run from the dir holding the binaries

# 2. Verify the checksum file's Sigstore bundle (new format)
cosign verify-blob \
  --bundle checksums.txt.bundle \
  --certificate-identity-regexp 'https://github.com/kevinpinscoe/tools/.*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  checksums.txt
```

For an older release, verify with the legacy flags instead:

```sh
cosign verify-blob \
  --signature checksums.txt.sig \
  --certificate checksums.txt.pem \
  --certificate-identity-regexp 'https://github.com/kevinpinscoe/tools/.*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  checksums.txt
```

### Dependencies

`cosign` (for verification), `sha256sum` (coreutils)
