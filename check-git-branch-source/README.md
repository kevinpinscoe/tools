# check-git-branch

Walks git repositories under `$HOME` (or paths listed in `$CHECK_GIT_BRANCH`) and reports any that are not on their default branch or have non-default local branches left over from previous work. All repos are checked concurrently. Silent when everything is clean.

## Usage

```
check-git-branch                 # scan and report (with spinner in interactive terminals)
check-git-branch --batch-mode    # scan without spinner (for systemd/cron)
check-git-branch --ignore-prefix # treat ignore entries as text prefixes (see below)
check-git-branch --version       # print version and exit
check-git-branch --help          # print this help
```

Set `CHECK_GIT_BRANCH` to scan specific directory trees instead of `$HOME`:

```sh
export CHECK_GIT_BRANCH=~/Projects:~/work
check-git-branch
```

## Output

```
~/Projects/foo - NOT AT DEFAULT BRANCH (feature/login)
~/Projects/bar - non-current local branches: feature/old-work, hotfix/123
~/Projects/baz - NOT AT DEFAULT BRANCH (feature/wip) | non-current local branches: feature/old-work
~/Projects/qux - LOCAL ONLY
~/Projects/lib - ORIGIN/HEAD ISN'T SET
```

One line per repo. Silent when everything is clean. Both conditions appear on the same line separated by ` | ` when both fire.

| Status | Meaning |
|--------|---------|
| `NOT AT DEFAULT BRANCH (name)` | Current branch differs from the remote default |
| `non-current local branches: …` | Non-default local branches exist locally (stale work) |
| `LOCAL ONLY` | No remote configured |
| `ORIGIN/HEAD ISN'T SET` | origin remote exists but the `HEAD` ref has not been set — run `git remote set-head origin --auto` to fix |
| `REMOTE CANNOT BE DETERMINED` | git remote query failed |

The current branch is identified by name in the `NOT AT DEFAULT BRANCH (name)` part. The non-current-branches list shows all other non-default local branches, so together the single output line gives a complete picture of local branch state.

## Scan roots — `CHECK_GIT_BRANCH`

By default the tool scans `$HOME`. Set `CHECK_GIT_BRANCH` to a colon-separated list of paths to scan instead:

```sh
export CHECK_GIT_BRANCH=~/Projects:~/work:/srv/repos
```

Rules:

- `~` is expanded to the user's home directory.
- Every listed path must exist and be a directory — if not, the program exits with an error.
- A repository found via multiple roots (e.g. a symlink) is reported only once.
- Repos outside `$HOME` are displayed using their full absolute path.

## Ignore file

Create `~/.config/check-git-branch/ignore.txt` to skip repo subtrees. One path per line; `~` is expanded; lines beginning with `#` are comments. The file is optional.

```
# skip archived work
~/archives
~/Projects/workspaces
```

### `--ignore-prefix`

By default an ignore entry only matches an exact path or a parent directory: an
entry of `~/Projects/workspaces/DOSD` skips `~/Projects/workspaces/DOSD/foo`
but not `~/Projects/workspaces/DOSD-5844/foo`.

With `--ignore-prefix`, each entry is treated as a plain text path-prefix so the
same entry also skips `~/Projects/workspaces/DOSD-5844`, `…/DOSD-5904`, and any
path that starts with that text. Useful for ticket-prefix-style workspace layouts.

## Install

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases/tag/check-git-branch-v1.0.0), verify the checksum, and install to `~/bin`:

**Fedora / Linux x86\_64**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-branch-linux-amd64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/check-git-branch-linux-amd64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/checksums.txt \
  | grep check-git-branch-linux-amd64 | sha256sum -c ) \
  && install -m 755 "$TMP/check-git-branch-linux-amd64" ~/bin/check-git-branch
rm -rf "$TMP"
```

**Raspberry Pi 5 / ARM64 (Debian Trixie)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-branch-linux-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/check-git-branch-linux-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/checksums.txt \
  | grep check-git-branch-linux-arm64 | sha256sum -c ) \
  && install -m 755 "$TMP/check-git-branch-linux-arm64" ~/bin/check-git-branch
rm -rf "$TMP"
```

**macOS (Apple Silicon)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-branch-darwin-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/check-git-branch-darwin-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/checksums.txt \
  | grep check-git-branch-darwin-arm64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/check-git-branch-darwin-arm64" ~/bin/check-git-branch
rm -rf "$TMP"
```

**macOS (Intel)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/check-git-branch-darwin-amd64" \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/check-git-branch-darwin-amd64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/check-git-branch-v1.0.0/checksums.txt \
  | grep check-git-branch-darwin-amd64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/check-git-branch-darwin-amd64" ~/bin/check-git-branch
rm -rf "$TMP"
```

> The checksum step prints `check-git-branch-…: OK` on success and exits non-zero if the binary was corrupted or tampered with.

Make sure `~/bin` is on your `$PATH`.

## Build from source

```sh
cd ~/tools/check-git-branch-source
make install   # builds and installs to ~/bin/check-git-branch
make build     # local build only (outputs ./check-git-branch)
make clean     # remove local build artifact
```

### Prerequisites

- **Go 1.26+** — run `go version` to check; download from [go.dev/dl](https://go.dev/dl/)
- **git** — required at build time and at runtime (all branch checks invoke git)
- **make** — standard build automation tool (pre-installed on most Linux/macOS systems)

## How it works

For each discovered `.git` directory:

1. `git remote` — checks whether an `origin` remote exists.
2. `git symbolic-ref refs/remotes/origin/HEAD` — resolves the default branch name from the local ref set at clone time. No network call is made.
3. `git rev-parse --abbrev-ref HEAD` — identifies the current branch.
4. `git branch --format=%(refname:short)` — lists all local branches.

All repos are processed in parallel goroutines. No `git fetch` is performed — this tool checks purely local state, making it fast and safe to run alongside other git processes.

## Progress spinner

In interactive terminals a braille spinner is shown on stderr during the scan:

- Phase 1: `⠋ scanning for repositories…`
- Phase 2: `⠙ checking N repositories…`

The spinner is automatically suppressed when stderr is not a TTY. Use `--batch-mode` to explicitly suppress it for systemd units, cron jobs, or any automated context.
