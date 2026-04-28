# check-git-repos

Walks `$HOME` recursively, finds every git repository, and reports any that are out of sync with their remote or have a dirty working tree. All repos are checked concurrently, making it significantly faster than an equivalent shell loop.

## Usage

```
check-git-repos                # scan and report (with spinner in interactive terminals)
check-git-repos --batch-mode   # scan without spinner (for systemd/cron)
check-git-repos --disable-lock # avoid git lock files (skips fetch — see warning below)
check-git-repos --version      # print version and exit
check-git-repos --help         # print this help
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

Prints `All repos are up to date` when everything is clean. Repos with no configured upstream are still reported if their working tree is dirty.

## Ignore file

Create `~/.config/check-git-repos-source/ignore.txt` to skip repo subtrees. One path per line; `~` is expanded; lines beginning with `#` are comments. The file is optional — if it does not exist the tool runs without error.

```
# skip archived work
~/archives/playbook
```

Any repo whose path starts with an ignored prefix is skipped entirely during the directory walk.

## Install

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases/tag/check-git-repos-v1.4.0), verify the checksum, and install to `~/bin`:

**Fedora / Linux x86\_64**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/check-git-repos-linux-amd64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/checksums.txt \
  | grep check-git-repos-linux-amd64 | sha256sum -c
chmod +x ~/bin/check-git-repos
```

**Raspberry Pi 5 / ARM64 (Debian Trixie)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/check-git-repos-linux-arm64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/checksums.txt \
  | grep check-git-repos-linux-arm64 | sha256sum -c
chmod +x ~/bin/check-git-repos
```

**macOS (Apple Silicon)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/check-git-repos-darwin-arm64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/checksums.txt \
  | grep check-git-repos-darwin-arm64 | shasum -a 256 -c
chmod +x ~/bin/check-git-repos
```

**macOS (Intel)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/check-git-repos-darwin-amd64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.4.0/checksums.txt \
  | grep check-git-repos-darwin-amd64 | shasum -a 256 -c
chmod +x ~/bin/check-git-repos
```

> The checksum step prints `check-git-repos-...: OK` on success and exits non-zero if the binary was corrupted or tampered with.

Make sure `~/bin` is on your `$PATH`.

## Build from source

```sh
cd ~/tools/check-git-repos-source
make install   # builds and installs to ~/bin/check-git-repos
make build     # local build only (outputs ./check-git-repos)
make clean     # remove local build artifact
```

Requires Go 1.21+ and `git` on `$PATH`.

## How it works

For each discovered `.git` directory:

1. `git fetch --quiet` updates remote-tracking refs. (Skipped when `--disable-lock` is set.)
2. `git rev-list --count @{u}..HEAD` counts commits ahead of remote.
3. `git rev-list --count HEAD..@{u}` counts commits behind remote.
4. `git status --porcelain` detects staged changes, unstaged edits, and untracked files.

All repos are processed in parallel goroutines. With `--disable-lock`, every git
invocation is run with the top-level `--no-optional-locks` option so it cannot
acquire optional locks (e.g. the index refresh in `git status`).

## Progress spinner

In interactive terminals a braille spinner is shown on stderr during the scan:

- Phase 1: `⠋ scanning for repositories…`
- Phase 2: `⠙ checking N repositories…`

The spinner is automatically suppressed when stderr is not a TTY (piped output, redirected scripts). Use `--batch-mode` to explicitly suppress it for systemd units, cron jobs, or any automated context where the spinner output would be noise.
