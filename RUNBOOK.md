# RUNBOOK

Operational reference for the scripts in this repo. Each entry covers purpose,
usage, and notable behavior. Keep this in sync when script functionality changes.

## `ticket`

Manage git worktrees for ticket-based development. Creates a worktree at
`<repo>/wt/kevini/<TICKET>`, saves a VS Code workspace file, and launches a
tmux session named `<TICKET>`.

### Usage

```
ticket                       # prompt for new ticket, or pick an existing one
ticket TICKET-ID             # create or open the given ticket
ticket -l | --list           # list tickets with their saved comments
ticket -d | --display        # list tickets with their saved worktree paths
ticket -r | --recover [ID]   # relaunch VS Code for an existing ticket
ticket --clean [ID]          # remove workspace files (not the worktree)
ticket -h | --help
```

### Key paths

- Workspaces dir: `~/Projects/workspaces/`
- Base VS Code workspace template: `~/Projects/kevins-work.code-workspace`
- Worktrees: `<repo>/wt/kevini/<TICKET>/`
- Branch: `kevini/<TICKET>`
- Saved worktree path per ticket: `~/Projects/workspaces/<TICKET>-path.txt`

### Notes

- Creating a new ticket requires being inside a git repo (main or worktree).
  `--clean`, `-l`, `-d`, and `-r` do not.
- Multi-repo convention: prefix the ticket ID with a letter to disambiguate
  the same ticket across repos (e.g. `rDOSD-5904`, `sDOSD-5904`, `tDOSD-5904`).
- Ticket IDs are sanitized and uppercased; a hyphen is inserted at the
  alpha/numeric boundary.
- Companion command: run `ticket --clean` before `mainbranch` to remove
  workspace files.

### Dependencies

`git`, `tmux`, `code`, `pick`, `jq`

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
