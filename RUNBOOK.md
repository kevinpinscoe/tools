# RUNBOOK

Operational reference for the scripts in this repo. Each entry covers purpose,
usage, and notable behavior. Keep this in sync when script functionality changes.

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

## `skill`

Compiled Go binary; source is not in this repo. Listed in `.gitignore`.
