# check-git-repos

Walks `$HOME` recursively, finds every git repository, and reports any that are out of sync with their remote. All repos are checked concurrently, making it significantly faster than an equivalent shell loop.

## Output

```
~/Projects/foo is AHEAD
~/Projects/bar is BEHIND
~/Projects/baz is AHEAD and BEHIND (diverged)
```

Prints `All repos are up to date` when everything is in sync. Repos with no configured upstream are silently skipped.

## Install

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases/tag/check-git-repos-v1.0.0), verify the checksum, and install to `~/bin`:

**Fedora / Linux x86\_64**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/check-git-repos-linux-amd64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/checksums.txt \
  | grep check-git-repos-linux-amd64 | sha256sum -c
chmod +x ~/bin/check-git-repos
```

**Raspberry Pi 5 / ARM64 (Debian Trixie)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/check-git-repos-linux-arm64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/checksums.txt \
  | grep check-git-repos-linux-arm64 | sha256sum -c
chmod +x ~/bin/check-git-repos
```

**macOS (Apple Silicon)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/check-git-repos-darwin-arm64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/checksums.txt \
  | grep check-git-repos-darwin-arm64 | shasum -a 256 -c
chmod +x ~/bin/check-git-repos
```

**macOS (Intel)**
```sh
curl -Lo ~/bin/check-git-repos \
  https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/check-git-repos-darwin-amd64
curl -sL https://github.com/kevinpinscoe/tools/releases/download/check-git-repos-v1.0.0/checksums.txt \
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

1. `git fetch --quiet` updates remote-tracking refs.
2. `git rev-list --count @{u}..HEAD` counts commits ahead of remote.
3. `git rev-list --count HEAD..@{u}` counts commits behind remote.

All repos are processed in parallel goroutines.
