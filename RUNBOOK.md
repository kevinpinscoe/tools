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

Python TUI that surfaces every untracked, modified or deleted file in the
current git repo, lets you multi-select which to commit via an urwid checkbox
picker,
commits the selection (one batch commit when a memo is given; one commit per
file otherwise), then pushes `HEAD` to `origin`.

Every commit message it writes is prefixed with `Committed by gitcf tool: `
so gitcf-authored commits are identifiable in `git log`.

The historical bash implementation (single-file argument, no push) has been
replaced.

### Usage

```
gitcf                # run from anywhere inside a git repo
gitcf --no-prefix    # commit without the "Committed by gitcf tool: " prefix
gitcf -h | --help
```

No file arguments — the picker is the only interface. `--no-prefix` is the
only other accepted argument; anything else exits non-zero with the usage
text on stderr.

### Behavior

- Repo root is resolved via `git rev-parse --show-toplevel`. Errors out if
  not inside a git repo.
- **A denylisted repo is refused outright, before anything else runs.** Right after resolving
  the repo root, gitcf checks it (and every parent directory) against
  `~/.config/gitcf/ignore.txt` — one path per line, `~` expanded, blank lines and `#` comments
  skipped, same format as `check-git-repos`' `~/.config/check-git-repos-source/ignore.txt`
  (a **separate** file, though: that one is which repos to skip *scanning*, this one is which
  repos gitcf must never *commit or push to* — a repo can need ordinary fetching to stay in
  sync while still being unsafe to write into by hand, e.g. `~/Projects/private/pim-records`,
  which is Radicale's own auto-committed history mirrored from `web1`). A match prints
  `ERROR: <repo> is denylisted for gitcf (see ~/.config/gitcf/ignore.txt) — use plain git
  commands instead.` and exits 1 — no `git status` is run, no picker opens. This is a hard
  block with **no `--force`/bypass flag**: plain git commands still work in a denylisted repo,
  only gitcf's automatic commit+push is refused. A missing `ignore.txt` means an empty
  denylist, not an error. The file itself is host-local config, not tracked in any repository.
- **The target branch is always announced.** gitcf has no branch awareness of its own — it
  commits and pushes whatever is currently checked out, main, a feature branch, or a
  worktree's own branch, without distinguishing between them. Before anything else it prints
  `Committing to branch: <branch>` to stderr, so the branch about to receive commits/push is
  always visible rather than assumed. If the branch name matches an issue-key pattern
  (`[A-Z][A-Z0-9]*-\d+`, e.g. `KDA-10`, `KEVIN-91`) it also prints a reminder that
  `when-creating-a-youtrack-ticket.md` §12 expects a comment on that issue for each commit —
  gitcf makes no YouTrack calls itself, this is a printed nudge only. The same branch name is
  echoed again in the `Pushing <branch> to origin...` line before the push runs.
- `git status --porcelain -z` enumerates untracked, modified, staged-add,
  staged-modify, renamed and deleted entries.
- **A rename or copy git has already detected (`R`/`C` codes — e.g. after `git mv`, or
  `git add -A` over a moved file) is labeled and committed as one.** `git status -z` emits
  both the destination path and the source path for these records; gitcf keeps both, shows
  `old-name.txt → new-name.txt` in the picker instead of just the destination, and commits
  with `Renamed <old> → <new>` (or `Copied <old> → <new>` for a `C` code) instead of the
  generic `Modified <name>` it used to fall through to.
- **A rename git has *not* yet detected — a plain `mv` with no `git add` — still shows up as
  two separate entries, and deletions in general are offered like anything else.** This used
  to be hidden, on the theory that a removed file's name made no meaningful message. That
  quietly hid the second half of every plain-`mv` rename: moving or promoting a file leaves
  `?? new-name` beside ` D old-name`, and committing only the half gitcf showed stranded the
  deletion in the working tree, where it resurfaced later as a mystery `deleted:` entry in
  `git status`. Select both halves and the rename lands whole. Give a memo while you are at
  it: batch mode stages both into one commit, where git pairs them and records an actual
  `R100` rename. Per-file mode (no memo) is still correct — two commits, nothing stranded —
  it just cannot show the pairing, because the halves land one commit apart. (Confirmed
  during the KDA-9 review — this was already working correctly; no code change was needed
  for it.)
- **`CHECKPOINT.md` is withheld from the picker outright, and its presence is announced.**
  `CHECKPOINT.md` is deliberately left untracked but visible at a repo's root — it is the
  handoff marker between AI sessions and must never be committed (see
  `~/ai/directives/gitignore.md`'s "Must never do" and `project-planning-with-ai.md`). gitcf
  excludes it from `git status` output before the picker ever sees it, so it cannot be
  selected, committed, or pushed by this tool under any circumstance. If a `CHECKPOINT.md`
  exists at the repo root, gitcf also prints a one-line note to stderr before the picker
  opens — `Note: CHECKPOINT.md present at repo root — AI work may be in flight; review the
  picker carefully before committing.` — since its presence is a signal that a session may
  still have work in progress, even though the file itself never appears as a pickable entry.
- **Unresolved merge conflicts are withheld, and named.** The seven unmerged codes
  (`UU`, `DD`, `AU`, `UD`, `UA`, `DU`, `AA`) never reach the picker: `git add` on one of
  them marks the conflict resolved and stages whatever is in the file, `<<<<<<<` markers
  included. They are printed to stderr before the TUI opens — `Skipping N unresolved merge
  conflict(s) — resolve, then git add:` — so they are visibly withheld rather than silently
  missing. If nothing else is pending, gitcf says so and exits 1 without opening the picker.
  A conflict that has been resolved and staged reports as `M `/`A `/`D ` and appears
  normally.
- The TUI shows each entry as `[XY]  path` with an urwid `CheckBox`. Keys:
  - `Space` toggles selection
  - `↑` / `↓` move focus
  - `Enter` confirms
  - `q` / `Esc` cancels (no commits, no push)
- After confirming selection, the script prompts once for `Commit memo (optional, Enter for default):`
  - **With a memo**: all selected files are staged together and committed in a
    single `git commit -m "<memo>"`.
  - **Without a memo** (press Enter): each file gets its own commit using the
    default scheme — `Added <basename>` for an untracked entry (`??`),
    `Deleted <basename>` for a deletion (` D`, `D `), `Modified <basename>`
    otherwise.
- **Commit message prefix.** Both message paths above are prepended with
  `Committed by gitcf tool: ` before the commit is made, so every gitcf commit
  is greppable in history. Pass `--no-prefix` to skip it for that run.
  Prefixing is idempotent — a message that already starts with the prefix is
  left alone, which matters at the retry prompt below (it echoes the previous,
  already-prefixed message back).
- **Empty-index skip.** Before each commit, and again after any commit
  failure, gitcf runs `git diff --cached --quiet` to ask whether anything is
  actually staged. If nothing is, the file is skipped with
  `Skipping <path>: already committed by an earlier commit in this run` (or
  `Nothing to commit: the selected files are already committed.` in the batch
  path) instead of entering the retry prompt below. See *Troubleshooting* for
  why this case exists.
- If a `git commit` fails — typically a `pre-commit` / `commit-msg` hook such
  as the spellcheck hook — the script does not crash. It prompts
  `Commit failed. Enter a new message, or press Enter to retry '<prev>', or 'q' to abort:`
  and retries with the message you supply (prefix reapplied per the rule
  above). Entering `q` aborts with git's exit code; already-made commits stay
  in place. The prompt is offered **only** when something is still staged — an
  empty index is never a message problem, so it is never retried.
- After all commits are made, `git push origin HEAD` is run once.
- On success, a final summary lists each commit message alongside the
  absolute path of the file it covered:

  ```
  Committed and pushed 2 files:
    Committed by gitcf tool: Added foo.txt      /Users/me/repo/foo.txt
    Committed by gitcf tool: Modified bar.go    /Users/me/repo/sub/bar.go
  ```
  If every selected file was skipped, the summary is replaced by
  `No new commits were made in this run.` (the push still runs, so any
  pre-existing local commits are flushed).
- A failing `git commit` is handled by the retry prompt described above. Any
  other failing git command (`git add`, or a rejected `git push`) raises
  `CalledProcessError` and exits non-zero with git's own output visible. No
  partial-state cleanup — already-made commits stay in place so the user can
  retry the push or fix the issue.

### Troubleshooting

#### The retry prompt repeats forever and no message works

**Symptom.** The first file commits fine, then gitcf prints a `git status`
dump ending in `no changes added to commit` followed by
`Commit failed. Enter a new message, or press Enter to retry '…', or 'q' to abort:`
— over and over, no matter what message is typed.

**Cause.** The repo has a `pre-commit` hook that regenerates derived files and
re-stages them. `~/KnowledgeVault` is the known case: its
`.githooks/pre-commit` refreshes `PKM/toc.md`, `PKM/index.md`,
`PKM/runbooks/index.md`, and `PKM/moc-map.md`, then `git add`s whichever
changed. If you select several of those files in the picker, the **first**
commit sweeps all of them in. gitcf then reaches the second one, stages
nothing, and `git commit` exits non-zero with an empty index. Before the fix
below, gitcf assumed every commit failure was a message problem and looped on
the retry prompt, which can never succeed.

**Resolution.** Fixed 2026-08-08 by the empty-index skip described under
*Behavior*: gitcf now checks `git diff --cached --quiet` and skips the file
rather than prompting. On a gitcf build without that check, press `q` to
abort — the earlier commits are already made and the tree is intact; then
re-run `gitcf` and select only files that are genuinely still modified.

**Verify.** In `~/KnowledgeVault`, select two or more of the hook-generated
files in one run. Expected output is one commit followed by
`Skipping PKM/moc-map.md: already committed by an earlier commit in this run
(a pre-commit hook swept it in).` and no retry prompt.

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

## `mainbranch`

Switch back to the repo's default branch and clean up the feature branch or
linked worktree. Companion to `work-ticket`, which lives in the private
`~/private-tools` repository (it was `ticket` here until 2026-08-16).

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
- Log path: `<LOG_ROOT>/_<REL>/YYYY-MM-DD-HH-MM.log`
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
`claude`. Logs land under a `CODEX/` subdirectory of the shared log root;
`myclaude` writes straight into the root, with no subdirectory of its own.

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

Curses TUI picker for `myclaude` session logs. Reads the log root from the
same per-platform config file `myclaude` uses — one of
`~/.environment/claude-diary-log-path-for-{mac,fedora,rpi}.txt`, selected by
platform — and browses `<LOG_ROOT>/_<REL>/*.log`, where each `_<REL>`
directory groups logs by the cwd `myclaude` was launched from (e.g.
`_.environment`, `_tools`, `_Projects-foo`, `_home`).

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

### Homebrew formula → cask migration

`check-git-repos` (and `check-git-branch`) shipped as Homebrew **formulae** until the `kevinpinscoe/tap` repo migrated both to **casks**. A Mac that installed either one before the migration still has the old formula-based install linked in the Cellar, pointed at a tap file that no longer exists — so `brew outdated` silently drops it from its report instead of erroring, since it has nothing left to diff the installed formula against.

Symptom: the tool is missing from `brew outdated` / doesn't show as needing an upgrade, even though the tap has a newer version. Fix:

```sh
brew uninstall --formula check-git-repos check-git-branch
brew install --cask kevinpinscoe/tap/check-git-repos kevinpinscoe/tap/check-git-branch
```

If the cask install then fails with `Refusing to write insecure trust store: trust store directory ~/.homebrew is group or world writable`, Homebrew's cask trust store rejected a group-writable `~/.homebrew` directory. Fix with `chmod -R go-w ~/.homebrew` and re-run the install.

### Usage

```
check-git-repos                 # scan and report
check-git-repos --batch-mode    # scan without progress spinner (systemd/cron)
check-git-repos --checkpoint    # report only repos holding a CHECKPOINT.md
check-git-repos --disable-lock  # avoid git lock files (skips fetch — see warning)
check-git-repos --ignore-prefix # treat ignore entries as text prefixes (see below)
check-git-repos --remove-locks  # clear stale .git/*.lock files before scanning
check-git-repos --lock-stale-after 5m   # age before a lock counts as stale
check-git-repos --worktree      # report WT for repos with a linked git worktree
check-git-repos --stale-days 5  # age before a worktree counts as stale (default 3)
check-git-repos --version       # print version and exit
check-git-repos --help          # print usage and exit
```

`--disable-lock` is for running alongside another git process (IDE, concurrent
scan) that may hold `.git/index.lock` or `.git/FETCH_HEAD`. It skips `git fetch`
and passes `--no-optional-locks` to every git invocation.

**Warning:** with `--disable-lock`, no fetch runs, so `AHEAD` / `BEHIND` reflect
whatever the last fetch saw and will be stale relative to the remote. Dirty-tree
detection (`STAGED` / `UNSTAGED` / `UNTRACKED` / `CHECKPOINT`) is unaffected.

`--ignore-prefix` changes how `ignore.txt` entries are matched. By default an
entry only matches an exact path or a parent directory (e.g.
`~/Projects/workspaces/DOSD` skips `…/DOSD/foo` but not `…/DOSD-5844/foo`). With
`--ignore-prefix`, each entry is treated as a plain text path-prefix, so the
same entry also skips `…/DOSD-5844`, `…/DOSD-5904`, and any sibling whose name
starts with `DOSD`. Useful for ticket-prefix-style workspace layouts.

### `--checkpoint` — where is the unfinished AI work?

Added in v1.13.0. Reports only repositories containing a `CHECKPOINT.md` — the
crash-resumable work file an AI agent writes before starting multi-step work and
deletes when it finishes — and prints nothing else:

```
$ check-git-repos --checkpoint
/opt/containers is CHECKPOINT
~/Projects/private/gitops is CHECKPOINT
~/admin is CHECKPOINT
```

**Nothing found means nothing printed.** No summary, no count, no
`All repos are up to date`. Silence is the whole signal — an empty run means no
unfinished AI work is outstanding anywhere on the machine. That is deliberate:
the mode is meant to be run habitually, and a "none found" line every time is
noise that trains you to stop reading it.

It skips `git fetch`, the ahead/behind comparison, `git status` and the lock
scan entirely, finishing in seconds against the several minutes a full scan
takes. It therefore takes precedence over `--disable-lock`, `--remove-locks` and
`--lock-stale-after`, which have nothing to do in this mode. `ignore.txt` and
`CHECK_GIT_REPOS` apply as normal; output is sorted.

It tests the filesystem rather than reading `git status`, which makes it find
three things the `CHECKPOINT` status cannot:

1. **Checkpoints below the repo root.** Each repository's whole working tree is
   searched. In a tracking repo — `~/admin`, `/opt/containers` — a project's
   `CHECKPOINT.md` belongs in that project's own subdirectory, so a root-only
   test would not be enough.
2. **Checkpoints in a brand-new untracked directory.** `git status --porcelain`
   collapses those into one `?? dir/` entry, so the `CHECKPOINT` status reports
   the repo as plain `UNTRACKED` instead.
3. **A committed `CHECKPOINT.md`.** It is never supposed to be tracked, so one
   that was committed by mistake is worth surfacing rather than hiding.

A checkpoint inside a nested repository is attributed to that nested repo, not
to the repo enclosing it.

**Troubleshooting — a repo you expected is missing.** In order of likelihood:
the `CHECKPOINT.md` was deleted because that work actually finished; the repo or
one of its parents is listed in `~/.config/check-git-repos-source/ignore.txt`;
the repo is outside `$HOME` and not listed in `$CHECK_GIT_REPOS`; or the file is
named something else (`CHECKPOINT.md.bak` and `MY-CHECKPOINT.md` do not count —
only the exact basename `CHECKPOINT.md`). Confirm with
`find <repo> -name CHECKPOINT.md`.

### Lock detection — `LOCKED`, `--remove-locks`, `--lock-stale-after`

A repo is reported `LOCKED` when its `.git/` tree contains a `*.lock` file older
than `--lock-stale-after` (default `5m`). That normally means a git process was
killed or crashed mid-operation and left its lock behind.

`--remove-locks` deletes those stale locks from every discovered repo before the
scan runs, printing each removed path, or `no stale locks found` if there were
none. It honours the same threshold, so a lock held by a live git process is left
alone.

`--lock-stale-after` accepts any Go duration (`90s`, `5m`, `1h`) and applies to
both the `LOCKED` status and `--remove-locks`. Setting it to `0` disables the age
test — every `*.lock` file counts as stale and `--remove-locks` will delete locks
that live git processes are still holding, which corrupts the operation holding
them. Only use `0` when nothing else is touching these repos.

**Known bug fixed in v1.11.0.** Through v1.10.2 the tool routinely reported
`LOCKED` for repos that had no lock files, and `--remove-locks` would print
`no stale locks found` in the same run that then reported a dozen repos locked.
Cause: `git fetch` spawns a detached `git maintenance run --auto` that outlives
it and creates `*.lock` files under `.git/`, and the lock scan ran after the
fetch with no staleness test — so the tool was reporting locks it had just
created itself. v1.11.0 runs the fetch with `maintenance.auto=false` and
`gc.auto=0`, moves the lock scan ahead of every git invocation, and adds the age
threshold above. Full write-up in `check-git-repos-source/README.md`.

### Checkpoint detection — `CHECKPOINT` (v1.12.0+)

A repo is reported `CHECKPOINT` when it has an untracked file whose basename is
`CHECKPOINT.md`. That is the crash-resumable work checkpoint an AI agent writes
before starting multi-step work and deletes once the work is finished, so a
leftover one means work was started here and never completed.

`CHECKPOINT.md` is deliberately never committed *and* deliberately never added to
`.gitignore` (see `~/ai/directives/project-planning-with-ai.md`) — being
untracked in `git status` is exactly how a leftover one gets noticed. Through
v1.11.0 that meant every repo with an in-flight AI session reported `UNTRACKED`,
which reads as forgotten commits and hides the genuinely untracked files among
the false ones. v1.12.0 gives it its own status so the signal survives without
being mistaken for something else.

Rules:

- A repo whose only untracked file is `CHECKPOINT.md` reports `CHECKPOINT` alone,
  never `UNTRACKED`.
- A repo with both reports both: `~/Projects/wip is UNTRACKED, CHECKPOINT`.
- Only the exact basename matches. `CHECKPOINT.md.bak` and `MY-CHECKPOINT.md`
  are ordinary untracked files.
- The match is on basename, so a `CHECKPOINT.md` in a subdirectory counts too —
  which is what the tracking repos (`personal-projects`, `vanco-project-tracking`,
  `~/admin`) need, since their checkpoints live in each project's own directory
  rather than at the repo root.
- A *tracked* `CHECKPOINT.md` with uncommitted edits is `UNSTAGED`, unchanged.

**Known limitation.** `git status --porcelain` collapses an entirely-untracked
directory into one `?? dir/` entry instead of listing its contents, so a
`CHECKPOINT.md` inside a brand-new untracked directory still reports as
`UNTRACKED`. Fixing it would need `--untracked-files=all`, which is materially
slower across every repo under `$HOME`, so it is left as-is.

### Stash detection — `STASH`, `STALE`, `--stash-stale-after`

Added in v1.14.0.

A repo is reported `STASH` when it holds any stashes, and `STALE` when at least
one of them is older than `--stash-stale-after` (default `14d`). The two are
mutually exclusive: a repo holding both a fresh stash and an old one reports
`STALE`, because the old one is the actionable finding.

**This is the only status that reports something `git status` cannot show you.**
A repository holding a six-month-old stash presents a perfectly clean working
tree — nothing in normal use will ever mention it, while the content sits in no
commit on no branch. That is not hypothetical: stashes months old were found on
this workstation, on repos that had been reporting clean the whole time.

`--stash-stale-after` accepts `d` and `w` as well as Go's own duration units, so
`14d`, `2w`, `36h` and `90m` all work. Setting it to `0` treats every stash as
stale.

```bash
check-git-repos --stash-stale-after 30d   # more forgiving
check-git-repos --stash-stale-after 0     # every stash counts as stale
```

Stashes live in `refs/stash` in the **common** git directory, so they belong to
the repository rather than to any one worktree — a stash made inside a linked
worktree is reported once, against the repo. A repository that has never stashed
has no `refs/stash`, so the check costs one git call that returns immediately.
Full-sweep timing is unchanged in practice: 139s against 151s for v1.13.0 across
this host.

Before acting on a finding, look at what the stash actually holds:

```bash
git -C <repo> stash list
git -C <repo> stash show --include-untracked --name-only 'stash@{0}'
git -C <repo> ls-tree -r --name-only 'stash@{0}^3'   # the untracked payload
```

The `^3` matters — untracked files stashed with `--include-untracked` live in a
third parent commit, and a plain `stash show` will not list them.

### Worktree detection — `WT`, `STALE`, `--worktree`, `--stale-days`

Added in v1.15.0.

Off by default. With `--worktree`, a repo reports `WT` when `git worktree list`
shows any linked worktree beyond its own primary working tree. This host's AI
agents work exclusively out of `ai-wt/<ISSUE-ID>/` worktrees (human work uses
`wt/` instead, by the same global convention across the work and personal
environments — see the AI directives), so `--worktree` is primarily how to
notice one of those left behind after a session ended without cleaning up.

A worktree found this way that is also older than `--stale-days` (default `3`,
a whole number of days) additionally reports `STALE`:

```bash
check-git-repos --worktree                  # report WT / WT, STALE
check-git-repos --worktree --stale-days 7   # more forgiving
check-git-repos --worktree --stale-days 0   # every worktree found counts as stale
```

Unlike `STASH`/`STALE`, `WT` and `STALE` are **not** mutually exclusive — a stale
worktree reports `WT, STALE` together, since both facts are worth seeing at once.
If a repo has both an old stash and a stale worktree, `STALE` is still printed
only once.

**Age is the worktree directory's own modification time**, not the age of its
HEAD commit or its last checkout — git records no creation timestamp for a
worktree itself. In ordinary use that mtime is set when the worktree is created
and changes again only if a top-level entry inside it is added or removed;
editing a file already present, or committing, does not touch it. That makes it
a reasonable stand-in for "when was this worktree created" without extra git
plumbing, though a worktree whose top level was touched more recently (a new
file dropped at its root) will read younger than it actually is. Full write-up
in `check-git-repos-source/README.md`.

### Output

```
~/Projects/foo is AHEAD
~/Projects/bar is BEHIND
~/Projects/baz is AHEAD and BEHIND (diverged)
~/Projects/qux is STAGED, UNTRACKED
~/Projects/wedged is LOCKED
~/Projects/marky is CHECKPOINT
~/Projects/spike is STASH
~/Projects/oldwork is STALE
~/tools is WT                       # with --worktree
~/private-tools is WT, STALE        # with --worktree, worktree older than --stale-days
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

Go program that walks git repositories under `$HOME` (and any extra paths in `$CHECK_GIT_BRANCH`) and reports any whose current branch is not the remote default, or that have non-default local branches left over from previous work. Purely local — no `git fetch` is performed. All repos are checked concurrently. Silent when everything is clean.

Source lives in `~/tools/check-git-branch-source/`; the compiled binary installs to `~/bin/check-git-branch`.

Install by curling the release binary (see `check-git-branch-source/README.md` for per-platform URLs) or via `make install` from source.

**Homebrew formula → cask migration:** see the note under [`check-git-repos`](#check-git-repos) — the same tap migration and old-formula/`~/.homebrew` trust-store gotcha applies here too.

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

### Extra scan roots — `CHECK_GIT_BRANCH`

The tool always scans `$HOME`. Set `CHECK_GIT_BRANCH` to a colon-separated list
of **additional** paths to scan as well:

```sh
export CHECK_GIT_BRANCH=/srv/repos:/opt/src
```

`~` is expanded. Every listed path must exist and be a directory or the program
exits with an error. `$HOME` is always scanned regardless of this variable, and a
repo reachable through more than one root is reported once. Repos found outside
`$HOME` are displayed with their full absolute path.

**Changed in v2.0.0 (breaking).** This variable used to *replace* `$HOME` rather
than add to it — setting it meant `$HOME` was not scanned at all. It is now
additive, matching `CHECK_GIT_REPOS` in `check-git-repos`; the two variables
previously looked identical but behaved oppositely, which is what prompted the
change. On this host `CHECK_GIT_BRANCH` is set to `/opt/containers` in
`~/.dotfiles/bash/.bash.d/01_bashrc_fedora_env`, and `$HOME` is picked up
automatically. To keep part of `$HOME` out of the scan, use the ignore file
below — that is now the only mechanism for it.

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

## `pull`

**Purpose:** Guarantee that no commit existing on a remote is missing from this machine. `pull` fetches every remote of every git repo it can find and fast-forwards **every** local branch that is behind its upstream. Anything that cannot be made current — a failed fetch, a divergence, a fast-forward git refuses — is reported individually and makes the run exit non-zero. Nothing is ever skipped silently.

**Platforms:** macOS, Fedora, Debian/Trixie, Raspberry Pi 5, or any machine where `~/tools` is on `PATH`.

**Dependencies:**

- `bash`, `git`, `find`. **Does not depend on `check-git-repos`** — see *History* below for why.

**Files:**

- `~/tools/pull`: executable script
- `~/.config/check-git-repos-source/ignore.txt`: ignore list, **shared with `check-git-repos`**. Entries are matched as plain path prefixes (equivalent to that tool's `--ignore-prefix` mode) and pruned inside `find`, so an ignored tree is never walked. On the container host this also excludes `/mac-home/go/pkg/` — the Go module cache, which holds no `.git` directories but is large enough on the slow `/mac-home` bind mount to cost ~20s of dead walking if left in.

**Usage:**

```bash
pull                       # every repo under $HOME (+ $CHECK_GIT_REPOS)
pull --dry-run             # report what would happen; change nothing
pull ~/Projects/private    # limit the sweep to given paths
pull --autostash           # stash local changes that block a fast-forward
pull --no-fetch            # no network; fast-forward from refs already on disk
pull -j 16                 # more parallel fetches (default 8)
pull -q                    # only repos that needed something, plus the summary
```

**How it works:**

1. **Discovery.** Walks `$HOME` plus any colon-separated paths in `$CHECK_GIT_REPOS` (or just the `PATH...` arguments, if given) for `.git` directories, pruning ignore-file prefixes. Clones that an enclosing repo gitignores — vendored checkouts, example repos — are dropped, matching `check-git-repos`.
2. **Fetch.** Runs `git fetch --all --prune --quiet` in every repo, `-j` at a time in parallel (~5s for 43 repos on the Pi). `maintenance.auto=false` and `gc.auto=0` are set per invocation so a sweep over every repo on the box never kicks off background repacks in all of them. **Every fetch's exit status is checked**, and a failure is reported with git's own error text.
3. **Fast-forward.** For each repo, enumerates *all* local branches with `git for-each-ref` and, for each one with an upstream:
   - **Behind only** → fast-forwarded. If the branch is checked out (in this repo or a linked worktree), that is `git merge --ff-only` run *in that worktree*, so the index and working tree move with the ref. If it is checked out nowhere, the ref is moved directly with `git update-ref -m "pull: fast-forward to …" refs/heads/<br> <new> <old>` — the old value is passed so a concurrent update fails rather than clobbers, and `-m` leaves the move in the branch reflog.
   - **Diverged** (ahead *and* behind) → left completely alone and listed as needing attention. The commits are local after the fetch; merge vs rebase vs reset is a human's decision.
   - **Not behind** → nothing.
   - **No upstream** → skipped. Nothing tracks it, so it cannot be behind anything.
   - **Upstream configured but gone** (merged-and-deleted remote branch that `--prune` removed) → printed as a note only. It is not a failure and does not affect the exit status: a branch that no longer exists on the remote has no commits to be missing.
4. **Summary.** `pull: done — N branch(es) fast-forwarded, N repo(s) already current, N failure(s), N needing attention`, then every attention item on stderr. Exits zero only when there were no failures and nothing needs attention.

**Progress spinner:**

On a real terminal (`[[ -t 2 ]]`), a braille spinner runs on stderr during discovery and fetch — the same `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` frames, 80ms cadence, and `\r`/`\r\033[K` redraw-and-clear style as `check-git-repos`. It shows `scanning for repositories…` during discovery, then `fetching N repo(s) (J parallel)… (done/N)` per completed fetch batch, and is cleared before the fast-forward loop starts printing its own per-repo lines. It never appears when stderr isn't a terminal (cron, CI, piped output) or during `--dry-run`/`--no-fetch`, since those paths are effectively instant. This exists because discovery alone can take the better part of a minute when `$HOME`/`$CHECK_GIT_REPOS` crosses a slow bind mount (e.g. the container's `/mac-home`) — without it, a slow run looks indistinguishable from a hang, since `say()` only prints a line for a repo that changed, diverged, or needs attention.

**Notes:**

- **The unit of work is a branch, not a repo.** A repo whose `main` is current but whose `topic` is 5 behind gets `topic` fast-forwarded.
- `--ff-only` is the whole contract: `pull` never creates a merge commit and never rewrites history, regardless of the host's `pull.rebase` / `pull.ff` config.
- **Dirty trees.** By default a fast-forward that git refuses because uncommitted changes are in the way is reported as a failure — nothing is stashed, reset, or committed behind your back. `--autostash` opts into stashing and restoring. Be aware that `git merge --autostash` **exits zero even when re-applying the stash conflicts**; `pull` therefore checks the index afterwards and reports `the autostash conflicted` as needing attention. Your changes are safe in `git stash` when that happens, but the worktree has conflict markers in it.
- **Remote branches with no local branch** are not turned into local branches. Their commits are local in `refs/remotes` after the fetch, which is what the contract requires; inventing a local branch per remote branch is noise, not correctness.
- **Detached HEAD** repos are fetched and their branches fast-forwarded normally; the detached HEAD itself is left where it is.
- `--no-fetch` makes the run purely local — useful when the network is down or when a fetch has just been done and you only want the fast-forward half.
- A repo whose fetch fails is still fast-forwarded from whatever remote-tracking refs are already on disk, so a broken remote degrades rather than blocks — but it is counted as a failure.
- Paths containing spaces are handled throughout (discovery is `-print0`/NUL-delimited).
- Requires bash; avoids `mapfile`, `wait -n`, and associative arrays so it also runs under the bash 3.2 that ships with macOS.

**History — why this does not shell out to `check-git-repos`:**

`pull` used to run `check-git-repos --ignore-prefix` and pull whatever it reported as `BEHIND`. That inherited four ways for remote commits to stay unpulled while the run still reported success:

1. **A failed fetch was invisible.** `check-git-repos` runs `git fetch` and *ignores its exit status* (`check-git-repos-source/main.go`, `checkRepo`), so an unreachable host, an unloaded SSH key, or a DNS hiccup makes a repo report **no status at all** — indistinguishable from up to date. Most repos on a given machine tend to share one forge, so a single bad moment for that host silently hid nearly all of them and `pull` cheerfully exited zero.
2. **Only the checked-out branch was ever compared.** Any other local branch could sit arbitrarily far behind and was never even mentioned.
3. **A repo whose HEAD had no upstream** (detached HEAD, or an untracked branch) produced no ahead/behind data, therefore no status line, therefore `pull` never heard about it.
4. **The scan took minutes.** Anything that fell behind *during* the scan was missed for that run, and the pre-pull re-verification could only ever cancel a pull, never discover one.

Doing the fetch here fixes all four and is roughly 30× faster.

**History — where this script came from:**

`pull` lived in the private `private-tools` repository until 2026-08-12, when it moved here so it sits alongside `check-git-repos`, whose ignore file it shares. Its history before that date is in `ssh://git@git.kevininscoe.com:2223/kinscoe/private-tools.git`.

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

**Gitea** — resolves the token from OpenBao (`mount=app`, path `gitea`, field
`token`) using the vault token at `~/.environment/.vault-token`. That is the only
source: the on-disk `~/.config/gitea/api` was shredded 2026-07-12, and the code
path that honoured it was removed on 2026-08-02 so a reappearing file cannot
silently shadow OpenBao with a stale token. If OpenBao does not yield a token the
run degrades to a GitHub-only report rather than aborting. Lists all repos via
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
  at `~/.environment/.vault-token`. There is no on-disk token file and no
  fallback — see the Gitea note above.

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

## `radar.sh`

Full-screen terminal weather radar viewer. Downloads animated GIF radar
loops from `radar.weather.gov`, plays them looped via `mpv`, and
auto-refreshes every 2 minutes in the background. Originally adapted from a
[public gist](https://gist.github.com/craigderington/c30f7237be9499b6af60f855435e5d0b)
with macOS-specific fixes.

### Usage

```
./radar.sh
```

No arguments — it's fully interactive. On start it downloads the default
station (Morristown TN / KMRX) and begins playback.

### Controls

| Key | Action |
|-----|--------|
| `c` `n` `s` `w` `p` | Regional views: CONUS, Northeast, Southeast, Great Lakes, Pacific NW |
| `1`–`9`, `0` | City stations: Melbourne, Miami, Jacksonville, Atlanta, NYC, Chicago, Dallas, Denver, Seattle, Los Angeles |
| `m` | Morristown TN (KMRX) — default station, includes the "you are here" marker |
| `r` | Force an immediate refresh of the current station |
| `h` / `?` | Show the controls panel |
| `q` | Quit and clean up |

### Behavior

- Detects the terminal's graphics renderer (`kitty` protocol under Kitty or
  Ghostty, `tct` otherwise) and passes it to `mpv --vo`. Inside `tmux` the
  kitty graphics protocol isn't forwarded, so it falls back to mpv's default
  GUI window instead of `--vo`.
- Radar loop GIFs download to `/tmp/radar.gif` via `wget`; a background loop
  refreshes that file every 120 seconds and swaps it in place (`mv`) so
  playback isn't interrupted mid-download.
- If `mpv` fails to launch, falls back to opening the GIF in the macOS
  default viewer (`open -g`) — that fallback does not carry the "you are
  here" marker overlay described below.
- All temp files (`/tmp/radar.gif`, `/tmp/radar_weather.json`,
  `/tmp/radar_status.txt`) and the `mpv` background process are cleaned up
  on exit via a `trap` on `EXIT INT TERM`.

### "You are here" marker

The station lookup table (`get_radar_entry`) carries an optional 4th field —
a `PIXEL_X,PIXEL_Y` position on that station's 600×550 standard-loop image.
Only the `m` (KMRX / Morristown TN) entry has one set, calibrated to 10
miles west of Greeneville, TN (`343,275`). When a station has a calibrated
position, `start_mpv` adds an `mpv --vf=lavfi=[drawbox=...,drawbox=...]`
filter chain that draws a filled marker directly into the video frames: a
black outer square (`MARK_SIZE + 2×MARK_BORDER` px) for contrast, with a red
inner square (`MARK_SIZE` px, default 16px, 4px border) on top. The border
is necessary because a plain red fill can blend into the radar colormap's
own red/orange storm-intensity pixels.

To calibrate a marker for a different station or location: play that
station, take an mpv screenshot (`s`), overlay a pixel grid on it, and
locate the target pixel using nearby cities with known lat/long as
reference points (simple linear interpolation is accurate enough at this
map scale — no need to account for the projection's curvature). Add the
`PIXEL_X,PIXEL_Y` as a 4th `|`-delimited field to that station's
`get_radar_entry` case.

### Dependencies

`bash`, `mpv`, `wget`. `tput` is used for cursor hiding/terminal cleanup but
degrades gracefully (`|| true`) if unavailable.

---

## `find-obsidian-vaults`

List the live Obsidian vaults under a root, one path per line. A **locator, not
an auditor** — read "Relationship to `discover-vaults.py`" below before reaching
for it.

### Usage

```
find-obsidian-vaults              # every live vault under $HOME
find-obsidian-vaults -r ~/web     # scan a subtree instead
find-obsidian-vaults -0           # NUL-separated, for `xargs -0`
find-obsidian-vaults -a           # also list vaults inside linked git worktrees
find-obsidian-vaults -h
```

### Behavior

Finds every `.obsidian` directory under the root and prints its parent — the
vault directory. `.obsidian` itself is pruned, so the plugin tree beneath it is
never walked.

**Linked git worktrees are excluded by default.** The non-work project workflow
creates one worktree per YouTrack issue, and a worktree of a vault repository
carries its own `.obsidian`. Without this filter every open project branch
invents a phantom vault — on 2026-08-20 that was 13 of 37 reported paths. The
test is structural rather than path-based:

```
git -C <vault> rev-parse --path-format=absolute --git-dir --git-common-dir
```

A linked worktree's `--git-dir` is `<repo>/.git/worktrees/<name>` while its
`--git-common-dir` is still `<repo>/.git`. In a primary checkout the two are
equal, and in a submodule they are also equal, so this distinguishes a worktree
from both. Path matching cannot do the job: worktrees usually live at
`<repo>/ai-wt/<ISSUE-ID>/`, but a repository whose root *is* the vault cannot
host one inside itself, so those are created at
`~/sandbox/obsidian/<repo>-<ISSUE-ID>/`, outside the repository entirely.

`--path-format=absolute` is not optional. Without it `--git-common-dir` can
answer with a bare `.git`, which compares unequal to an absolute `--git-dir` and
reports every repository as a worktree.

**Pruned rather than descended:** `$HOME/.local/share/containers`,
`$HOME/.local/share/Trash`, `$HOME/.cache`, `$HOME/.Trash`,
`$HOME/Library/Caches`, and any `node_modules`, `.venv`, or `.git` directory.
These hold no vaults, account for most of the run time, and on Fedora produce
dozens of `Permission denied` lines from the podman overlay store that bury the
answer. Whatever still reaches stderr is therefore worth reading.

**Use `-0` from scripts.** Two vault names contain a space or an apostrophe
(`Obsidian Hacks`, `Kevin's Bible Study`), so newline-separated output is unsafe
in a `for` loop or an unquoted expansion.

### Relationship to `discover-vaults.py`

`~/Projects/private/obsidian-hacks/scripts/discover-vaults.py` is the
**authoritative** vault tool. It does everything this script does, then
reconciles the result against `~/.config/obsidian/obsidian.json`, audits each
vault's layout against rule 1 of `~/ai/directives/obsidian-best-practices.md`,
and grades `obsidian-paste-image-rename` conformance — in text, Markdown or
JSON. Anything feeding the vault catalogue uses that script.

Prefer it wherever it is checked out. This script exists for the cases it cannot
cover: a host without that repository — the Mac work environment, a fresh
machine — or a one-off where a plain list of paths is all that is wanted. Both
agreed exactly on the 24 live vaults when this was written, 2026-08-20.

### Dependencies

`find` and `git`. Without `git` the worktree filter cannot run: the script warns
on stderr and lists worktree copies rather than failing.

Portable to macOS — no GNU-only `find` predicates. In particular not `-printf`,
which the previous version relied on and which BSD `find` does not have.

---

## `set-ghostty-tab-name`

Name the terminal tab the calling process is running in, so a ticket being worked
is visible at a glance on the status bar.

### Terminology — "tab"

Throughout this entry, **tab** means one labelled entry on the tmux status bar:

```
main   0:FLDW-19   1:FC-1   2:zsh   7:KTA-1   10:travel
       └─ tab 0 ─┘ └tab 1─┘
```

tmux calls these *windows*; Ghostty calls its own things *tabs* and they are not
the same object. Because Ghostty is configured with
`command = /usr/bin/tmux new-session -A -s main`, there is exactly **one** Ghostty
tab, and everything visible on that bar is tmux's. This entry uses "tab" for what
is on the bar, because that is what is actually being looked at.

Ghostty's own titlebar is **not** involved. `set-titles` is `off`, so tmux never
sends it a title. Turning that on (`set-titles on`, `set-titles-string "#W"` in
`~/.dotfiles/tmux/.tmux.conf`) would make the titlebar follow the active tab's
name — but that is a separate label and this script does not touch it.

### Usage

```
set-ghostty-tab-name FLDW-12          # name this tab (work Jira ticket)
set-ghostty-tab-name KTA-1            # name this tab (personal YouTrack issue)
set-ghostty-tab-name KTA-1c           # that issue, now closed ("c" = closed)
set-ghostty-tab-name --reset          # release it (see below — not literally "zsh")
set-ghostty-tab-name --show           # print this tab's name
set-ghostty-tab-name -t 8 FLDW-12     # name tab 8 instead
```

A closed ticket is marked by re-naming the tab, not by releasing it: append a
lowercase `c` to the same key. A tab still reading `KTA-1` claims work in flight,
while a released tab loses which ticket the session was on; `KTA-1c` says both.
The suffix is a tab-label convention only — the key in YouTrack or Jira is
unchanged, and so is the `Ghostty tab name` field on the issue.

| Option | Effect |
|---|---|
| `-t TARGET` | Act on another tab. Normally the number on the bar (`8`). Any tmux target also works: `%8` (pane id), `main:7`, or a tab's name. |
| `-r`, `--reset` | Release the tab back to naming itself. Not the ticket-close move — that is the `c` suffix above. |
| `-s`, `--show` | Print the tab's name and exit. |
| `-h`, `--help` | Usage. |

Tab numbers have **gaps** — deleting a tab does not renumber the rest, so a bar
reading `… 5:KOA-17  7:claude …` has no tab 6. `-t 6` errors rather than picking
a neighbour.

Silent on success. Nothing is printed unless something went wrong.

### The human equivalent

Right-click a tab on the status bar → **`Rename`** → type the name. That menu is
tmux's (`MouseDown3Status`), drawn inside the Ghostty window, which is why it
looks like Ghostty's own. It runs `rename-window`, exactly as this script does,
and has exactly the same side effect described under *Naming a tab opts it out*
below.

### Required by directive

Naming the tab is **not optional** when working a ticket:

| Directive | Requires |
|---|---|
| `when-creating-a-youtrack-ticket.md` §7 | Name the tab the issue key when `Status` moves to `In Progress` |
| `when-creating-a-youtrack-ticket.md` §9 | Rename the tab to that key plus a lowercase `c` — `KTA-1c` — when the issue reaches `Done` or `Wont do` |
| `when-in-work-context.md` instruction 8 | The same for a Jira ticket, on a Work host |

Both directives require the rule to be **skipped silently** where it cannot
apply — a host whose `~/tools` has not been synced has no such command on `PATH`,
and outside tmux there is no bar to label. Neither may block a status change. A
tab the human has renamed is left alone.

The tab's name is also recorded on the YouTrack issue in `Ghostty tab name`
(prototype `157-25`, 128 chars), so the mapping can be read from either end. That
field's width is where this script's own 128-character limit comes from.

### Behavior

**It always targets the caller's own tab.** This is the reason the script exists
rather than agents calling `tmux rename-window` directly. A bare
`tmux rename-window NAME` renames whichever tab the *client is currently
viewing* — wherever the human happens to be looking — **not** the tab the calling
process is in. Observed directly: two identical `tmux display-message` calls
minutes apart reported different tabs, because the human had switched tabs in
between. With several agents running in several tabs, a naive rename silently
relabels somebody else's work.

The tab is resolved from `$TMUX_PANE`, falling back to walking the caller's
process ancestry against `tmux list-panes -a -F '#{pane_pid} #{pane_id}'` if that
variable has been scrubbed. If neither resolves the script fails and asks for
`-t`; it never degrades to an untargeted tmux call.

**Naming a tab opts it out of automatic naming — permanently.** tmux normally
names a tab after whatever is running in it (`automatic-rename on`, format
`#{pane_current_command}`), which is why an untouched tab reads `zsh` when idle
and `vim` while vim runs. `rename-window` sets `automatic-rename off` on that tab,
so a tab that has ever been named — by this script, or by the right-click
`Rename` — stops following the program until it is reset.

This is the usual cause of "the tab name does nothing": the tab was renamed at
some point in the past and is doing exactly what it was told. `--show` will not
reveal it; check `tmux display-message -p -t <tab> '#{automatic-rename}'`, where
`0` means opted out.

**`--reset` does not write a fixed name — and does not necessarily produce
`"zsh"`.** It unsets that window-level `automatic-rename`, handing naming back to
tmux, which then names the tab after whatever is running in it:

| What is running in the tab | Name after `--reset` |
|---|---|
| an idle shell | `zsh` |
| a Claude Code session | `claude` |
| vim | `vim` |

`zsh` is the idle case, not the reset case. A `--reset` that yields `claude` while
Claude is running is correct behaviour, not a defect.

If `automatic-rename` is off *globally* — where unsetting the per-tab option would
change nothing and leave a stale label — the script names the tab after `$SHELL`'s
basename instead, so `--reset` always does something.

Note that `--reset` is **not** what closes out a ticket, and has not been since
2026-08-23: the directives call for the `c` suffix instead, precisely because a
reset tab forgets the ticket. `--reset` is for a tab with no finished ticket to
remember.

**In a split tab, the name follows the active pane.** A tab holds one or more
panes; only tabs have names. With automatic naming on, the name tracks whichever
pane is focused and re-evaluates the moment focus moves — so a long build in an
unfocused pane will not show.

**Name validation.** Rejects an empty name, any name containing control
characters (which would corrupt the status bar, or outside tmux allow further
escape sequences to be injected), and names longer than 128 characters.

**Target validation uses `list-panes`, not `display-message`.** A bad target does
not make `display-message` fail: `tmux display-message -p -t main:999
'#{window_index}'` exits `0` and answers about the *current* tab, so a typo in
`-t` would read or rename the wrong tab silently. `tmux list-panes -t` exits `1`
on a bad target, so that is what the guard uses.

### Outside tmux

A bare Ghostty tab, or macOS without tmux: the script emits a BEL-terminated
`OSC 2` title escape instead, which is how a terminal tab is titled directly.
`--show` cannot work there — a terminal does not report its own title — and says
so rather than guessing.

The write target is probed with a real `open()` rather than `[[ -w /dev/tty ]]`:
that test reports writable even when the process has no controlling terminal, and
the open then fails with `ENXIO`. Falls back to stderr, which is still the
terminal in the common case of stdout having been redirected.

### Dependencies

`tmux` when inside tmux; `ps` for the ancestry fallback. Nothing beyond a POSIX
shell outside tmux.

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

---

## Cross-platform sync after a release

The four hosts that share `~/tools` do **not** sync automatically — the repo is
pulled by hand on each one. After pushing a tag and/or releasing any tool here
(a script update counts, not just a compiled binary), append a dated entry to
the `~/todo` file of every host other than the one you are on, so the sync is
not forgotten.

`~/todo` is a separate repo (`todo-os` on Gitea) with one directory per host:

| `~/todo` file | Host | Platform |
|---|---|---|
| `FLDW/TODO.md` | FLDW — Kevin's Fedora desktop, `hostname` = `kevin` | linux/amd64 |
| `mac/TODO.md` | macOS work machine | darwin/arm64 |
| `rpi/TODO.md` | Raspberry Pi 5, aka **rpi5** / **core**, `hostname` = `core` | linux/arm64 |
| `mac-container/TODO.md` | Docker container running Fedora Linux, hosted on the macOS work machine | linux/amd64 |

Releases are normally cut from the FLDW, so the usual case is entries in the
other three. **`mac-container` is the one that gets missed** — it shares the
Mac's hardware but is a distinct host with its own `~/tools` clone and needs its
own `git pull`.

**Minimum entry for every release** — a `git pull` to pick up the latest scripts:

```
YYYY-MM-DD cd ~/tools && git pull  # <tool-name> vX.Y.Z: <one-line summary of what changed>
```

**Additional entry when a compiled binary was released** — the binary also has
to be downloaded and installed. Add a second entry on each platform the binary
runs on, using the install command from that tool's `README.md`:

```
YYYY-MM-DD <install command from the tool's README.md>  # install <tool-name> vX.Y.Z binary
```

Mind the architecture column above when writing those: `mac` is darwin/arm64
while `mac-container` is linux/amd64 despite running on the same physical Mac,
so the two need different download URLs. Never copy the `mac` entry verbatim
into `mac-container`.

Use today's date, and commit the `~/todo` changes in the same session as the
release — `todo: remind mac+rpi+mac-container to sync tools after <tool-name>
vX.Y.Z`.

> This section mirrors "Cross-platform sync after any release" in
> `~/tools/CLAUDE.md`. Update both together.
