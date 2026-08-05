# check-git-repos

Walks `$HOME` recursively, finds every git repository, and reports any that are out of sync with their remote or have a dirty working tree. All repos are checked concurrently, making it significantly faster than an equivalent shell loop.

## Usage

```
check-git-repos                 # scan and report (with spinner in interactive terminals)
check-git-repos --batch-mode    # scan without spinner (for systemd/cron)
check-git-repos --disable-lock  # avoid git lock files (skips fetch — see warning below)
check-git-repos --ignore-prefix # treat ignore entries as text prefixes (see below)
check-git-repos --remove-locks  # remove stale .git/*.lock files before scanning
check-git-repos --lock-stale-after 5m   # how old a lock must be to count as stale
check-git-repos --version       # print version and exit
check-git-repos --help          # print this help
```

Set `CHECK_GIT_REPOS` to scan additional directory trees beyond `$HOME`:

```sh
export CHECK_GIT_REPOS=/srv/repos:/opt/src
check-git-repos
```

### `--disable-lock`

Use when another git process (an IDE, another `check-git-repos` run) may be running
concurrently against the same repos. With this flag the tool:

- skips `git fetch` entirely, and
- passes `--no-optional-locks` to all other git invocations (`rev-list`, `status`).

This avoids contention on `.git/index.lock`, `.git/FETCH_HEAD`, and refs.

> **Warning:** because no fetch runs, `AHEAD` / `BEHIND` results reflect whatever
> state the last fetch saw — they will be stale relative to the remote. Dirty-tree
> detection (`STAGED` / `UNSTAGED` / `UNTRACKED`) is unaffected.

## Output

```
~/Projects/foo is AHEAD
~/Projects/bar is BEHIND
~/Projects/baz is AHEAD and BEHIND (diverged)
~/Journal/Personal Journal is UNSTAGED
~/Projects/qux is STAGED, UNTRACKED
~/Projects/wip is AHEAD, STAGED, UNSTAGED, UNTRACKED
```

Each repo can report one or more conditions, comma-separated:

| Status | Meaning |
|--------|---------|
| `AHEAD` | Local commits not yet pushed |
| `BEHIND` | Remote commits not yet pulled |
| `AHEAD and BEHIND (diverged)` | Both of the above |
| `STAGED` | Changes indexed but not committed |
| `UNSTAGED` | Tracked files with uncommitted edits |
| `UNTRACKED` | Files not yet added to git |
| `LOCKED` | Stale `*.lock` files present under `.git/`, older than `--lock-stale-after` — use `--remove-locks` to clear them |

Prints `All repos are up to date` when everything is clean. Repos with no configured upstream are still reported if their working tree is dirty.

## Extra scan roots — `CHECK_GIT_REPOS`

By default the tool scans only `$HOME`. Set the `CHECK_GIT_REPOS` environment variable to a colon-separated list of additional directory paths to scan as well:

```sh
export CHECK_GIT_REPOS=/srv/repos:/opt/src:~/work
```

Rules:

- `~` is expanded to the user's home directory.
- Every listed path must exist and be a directory — if a path does not exist, cannot be read, or is not a directory the program exits with an error. This catches typos and stale config early.
- `$HOME` is always scanned regardless of whether it also appears in `CHECK_GIT_REPOS`.
- A repository that would be found via both `$HOME` and an extra root (e.g. a symlink) is reported only once.
- Repos discovered outside `$HOME` are displayed using their full absolute path.

## Nested repos inside gitignored directories

If a directory is itself a git repository and lives inside another git repository
that gitignores it (e.g. a reference clone dropped into a subdirectory that the
parent lists in `.gitignore`), `check-git-repos` automatically skips it. No
ignore file entry is needed.

This is detected after the directory walk: for every discovered repo, the tool
checks whether any ancestor directory is also a repo and, if so, runs
`git check-ignore` against the ancestor. If the parent repo gitignores the
nested repo's path, it is silently excluded from the check.

## Ignore file

Create `~/.config/check-git-repos-source/ignore.txt` to skip repo subtrees. One path per line; `~` is expanded; lines beginning with `#` are comments. The file is optional — if it does not exist the tool runs without error.

```
# skip archived work
~/archives/playbook
```

Any repo whose path starts with an ignored prefix is skipped entirely during the directory walk.

### `--remove-locks`

Removes stale `*.lock` files from every discovered repository's `.git/` directory before running the check. Each removed path is printed to stdout. If no locks are found, prints `no stale locks found` and proceeds normally.

Only lock files older than `--lock-stale-after` (default 5 minutes) are removed, so a lock held by a live git process is left alone.

> **Warning:** passing `--lock-stale-after 0` disables that protection and removes every `*.lock` file regardless of age. Only do that when no other git processes are active against these repositories — removing a lock a live process holds will corrupt whatever operation it was protecting (fetch, index update, ref write, etc.).

Combining with `--batch-mode` is useful in recovery scripts:

```sh
check-git-repos --remove-locks --batch-mode
```

### `--lock-stale-after`

Sets how old a `*.lock` file must be before it counts as stale. Applies to both
the `LOCKED` status and `--remove-locks`, so the two always agree on what "stale"
means.

```sh
check-git-repos --lock-stale-after 30s   # more aggressive
check-git-repos --lock-stale-after 1h    # more conservative
check-git-repos --lock-stale-after 0     # no age test — every *.lock counts
```

Accepts any Go duration string (`90s`, `5m`, `1h`). The default is `5m`: git holds
its lock files for well under a second in normal use, so five minutes clears any
live operation by a wide margin while still catching locks orphaned by a crashed
or killed git process.

Before v1.11.0 there was no age test, and the tool reported `LOCKED` for lock
files created moments earlier by its own `git fetch` — see [Why locks used to be
misreported](#why-locks-used-to-be-misreported).

### `--ignore-prefix`

By default an ignore entry only matches an exact path or a parent directory: an
entry of `~/Projects/workspaces/DOSD` will skip `~/Projects/workspaces/DOSD/foo`
but not `~/Projects/workspaces/DOSD-5844/foo`, because `DOSD-5844` is a sibling,
not a child, of `DOSD`.

With `--ignore-prefix`, each entry is treated as a plain text path-prefix. The
same `~/Projects/workspaces/DOSD` entry then also skips
`~/Projects/workspaces/DOSD-5844`, `…/DOSD-5904`, and any other path that
starts with that text. Useful when the ignore file lists a ticket-prefix like
`DOSD` or `SRE` and you want every workspace named with that prefix to be
ignored.

## Install

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases/tag/check-git-repos-v1.11.0), verify the checksum, and install to `~/bin`:

Each block downloads the binary to a temporary directory under its original
release name, verifies the SHA-256 checksum there (this only works when the
file on disk matches the name listed in `checksums.txt`), and only then
installs it to `~/bin/check-git-repos`. If the checksum fails, the install
step is not reached.

**Fedora / Linux x86\_64**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-repos-linux-amd64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/check-git-repos-linux-amd64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/checksums.txt \
  | grep check-git-repos-linux-amd64 | sha256sum -c ) \
  && install -m 755 "$TMP/check-git-repos-linux-amd64" ~/bin/check-git-repos
rm -rf "$TMP"
```

**Raspberry Pi 5 / ARM64 (Debian Trixie)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-repos-linux-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/check-git-repos-linux-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/checksums.txt \
  | grep check-git-repos-linux-arm64 | sha256sum -c ) \
  && install -m 755 "$TMP/check-git-repos-linux-arm64" ~/bin/check-git-repos
rm -rf "$TMP"
```

**macOS (Apple Silicon)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-repos-darwin-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/check-git-repos-darwin-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/checksums.txt \
  | grep check-git-repos-darwin-arm64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/check-git-repos-darwin-arm64" ~/bin/check-git-repos
rm -rf "$TMP"
```

**macOS (Intel)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-repos-darwin-amd64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/check-git-repos-darwin-amd64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.11.0/checksums.txt \
  | grep check-git-repos-darwin-amd64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/check-git-repos-darwin-amd64" ~/bin/check-git-repos
rm -rf "$TMP"
```

> The checksum step prints `check-git-repos-...: OK` on success and exits non-zero if the binary was corrupted or tampered with — the `&&` then prevents `install` from running so `~/bin/check-git-repos` is left untouched.

Make sure `~/bin` is on your `$PATH`.

## Build from source

```sh
cd ~/tools/check-git-repos-source
make install   # builds and installs to ~/bin/check-git-repos
make build     # local build only (outputs ./check-git-repos)
make clean     # remove local build artifact
```

### Prerequisites

- **Go 1.26+** — run `go version` to check; download from [go.dev/dl](https://go.dev/dl/)
- **git** — required at build time and at runtime (all status checks invoke git)
- **make** — standard build automation tool (pre-installed on most Linux/macOS systems)

## How it works

For each discovered `.git` directory:

1. The `.git/` tree is scanned for `*.lock` files older than `--lock-stale-after`.
   This happens **before** any git command runs, so the tool can never observe a
   lock created by its own git invocations.
2. `git fetch --quiet` updates remote-tracking refs, with `maintenance.auto=false`
   and `gc.auto=0`. (Skipped when `--disable-lock` is set.)
3. `git rev-list --count @{u}..HEAD` counts commits ahead of remote.
4. `git rev-list --count HEAD..@{u}` counts commits behind remote.
5. `git status --porcelain` detects staged changes, unstaged edits, and untracked files.

All repos are processed in parallel goroutines. With `--disable-lock`, every git
invocation is run with the top-level `--no-optional-locks` option so it cannot
acquire optional locks (e.g. the index refresh in `git status`).

## Why locks used to be misreported

Through v1.10.2 the tool regularly reported `LOCKED` for repositories that had no
lock files at all — often a dozen at once, and `--remove-locks` would print
`no stale locks found` in the very same run that then declared them locked.

Two defects combined to cause it:

1. **The tool created the locks it was reporting.** `git fetch` spawns a detached
   background process, `git maintenance run --auto --quiet --detach`, which keeps
   running after `fetch` has returned. That process runs `gc`, `pack-refs`,
   `commit-graph`, and `incremental-repack` tasks, each creating `*.lock` files
   under `.git/`. The lock scan ran *after* the fetch in the same repo, so it saw
   them. `--remove-locks` ran before any fetch, which is why it correctly found
   nothing and the scan still reported `LOCKED` moments later.
2. **"Stale" was never tested.** The scan flagged any file ending in `.lock`
   anywhere under `.git/`, with no age check and no check for a live owner —
   despite the help text promising *stale* lock files. `--remove-locks` had the
   same gap and would happily delete a lock a live git process was holding.

v1.11.0 fixes both: the fetch is run with `maintenance.auto=false` and `gc.auto=0`
so no background maintenance is spawned, the lock scan moved ahead of every git
invocation, and both the `LOCKED` status and `--remove-locks` now honour the
`--lock-stale-after` age threshold.

## Progress spinner

In interactive terminals a braille spinner is shown on stderr during the scan:

- Phase 1: `⠋ scanning for repositories…`
- Phase 2: `⠙ checking N repositories…`

The spinner is automatically suppressed when stderr is not a TTY (piped output, redirected scripts). Use `--batch-mode` to explicitly suppress it for systemd units, cron jobs, or any automated context where the spinner output would be noise.
