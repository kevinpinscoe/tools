# menu-app

A small terminal UI that turns a per-repository `.menu-app.yaml` file into a
selectable menu of scripts. Run `menu-app` anywhere inside a git repository,
pick an item, and its script runs from the repository root — then you are
returned to the menu.

> **Note:** menu-app is opinionated. It is built and customized around my own
> workflow — git-root config discovery, a flat list of scripts, run-and-return
> behavior, and so on. It is shared here in case it is useful to others: feel
> free to fork it, modify it, and adapt it to your own benefit.

## What this is

- A single Go binary built from this source tree (`menu-app-source/`).
- A [Bubble Tea](https://github.com/charmbracelet/bubbletea) TUI, the same
  stack used by `skills-tui`.
- Driven entirely by a YAML file that lives at the **git root** of whatever
  repository you are in.

## How to use it

1. Add a `.menu-app.yaml` file to the root of a git repository:

   ```yaml
   items:
     - name: Run tests
       script: scripts/test.sh
     - name: Build project
       script: scripts/build.sh
   ```

   - `script` is a path **relative to the git root**.
   - Each script must be **executable** (`chmod +x scripts/test.sh`).
   - Scripts run with the git root as their working directory.

2. Run `menu-app` from anywhere inside that repository.
3. Use the arrow keys to highlight an item, press **Enter** to run it, then
   press any key to return to the menu.

### Keys

| Key     | Action                          |
|---------|---------------------------------|
| `Enter` | Run the highlighted script      |
| `/`     | Filter the list                 |
| `q`     | Quit                            |
| `Ctrl+C`| Quit                            |

### Flags

```
menu-app --version    # print version and exit
menu-app --help       # print help and exit
```

## Install

### APT (Debian, Ubuntu, Raspberry Pi OS)

```sh
curl -sL https://kevinpinscoe.github.io/apt/gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kevinpinscoe.gpg

echo "deb [signed-by=/etc/apt/keyrings/kevinpinscoe.gpg] \
  https://kevinpinscoe.github.io/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/kevinpinscoe.list

sudo apt update
sudo apt install menu-app
```

### DNF (Fedora, RHEL)

```sh
sudo curl -fsSL https://kevinpinscoe.github.io/rpm/kevinpinscoe.repo \
  -o /etc/yum.repos.d/kevinpinscoe.repo
sudo dnf install menu-app
```

### Binary download

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases), verify the checksum, and install to `~/bin`:

**Fedora / Linux x86\_64**

```sh
TAG=menu-app-vX.Y.Z   # replace with the tag you want
TMP=$(mktemp -d)
curl -fLo "$TMP/menu-app-linux-amd64" \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/menu-app-linux-amd64"
( cd "$TMP" && curl -fsSL \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/checksums.txt" \
  | grep menu-app-linux-amd64 | sha256sum -c ) \
  && install -m 755 "$TMP/menu-app-linux-amd64" ~/bin/menu-app
rm -rf "$TMP"
```

**Raspberry Pi 5 / ARM64 (Debian Trixie)**

```sh
TAG=menu-app-vX.Y.Z
TMP=$(mktemp -d)
curl -fLo "$TMP/menu-app-linux-arm64" \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/menu-app-linux-arm64"
( cd "$TMP" && curl -fsSL \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/checksums.txt" \
  | grep menu-app-linux-arm64 | sha256sum -c ) \
  && install -m 755 "$TMP/menu-app-linux-arm64" ~/bin/menu-app
rm -rf "$TMP"
```

**macOS (Apple Silicon)**

```sh
TAG=menu-app-vX.Y.Z
TMP=$(mktemp -d)
curl -fLo "$TMP/menu-app-darwin-arm64" \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/menu-app-darwin-arm64"
( cd "$TMP" && curl -fsSL \
  "https://github.com/kevinpinscoe/tools/releases/download/${TAG}/checksums.txt" \
  | grep menu-app-darwin-arm64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/menu-app-darwin-arm64" ~/bin/menu-app
rm -rf "$TMP"
```

Make sure `~/bin` is on your `$PATH`.

## Behavior

| Situation                                   | What happens                                              |
|---------------------------------------------|-----------------------------------------------------------|
| Not inside a git repository                 | Prints `not a git initialized directory` and exits `1`.   |
| Inside a repo but no `.menu-app.yaml`       | Offers to create one from a built-in template, then exits.|
| `.menu-app.yaml` present with items         | Shows the menu.                                           |
| `.menu-app.yaml` has no `items:`            | Prints an error and exits `1`.                            |
| Malformed YAML                              | Prints the parse error with the file path and exits `1`.  |
| Selected script is missing / a directory    | Shows an error screen, then returns to the menu.          |
| Selected script exits non-zero              | Shows the exit code, then returns to the menu.            |

The git root is located with `git rev-parse --show-toplevel`.

A copy of the starter template also lives at `~/tools/menu-app-template.yaml`.

## Build and install

```sh
# from menu-app-source/
make build      # build ./menu-app
make install    # build and install to ~/bin/menu-app
make clean      # remove the local binary
```

`make build` and `make install` stamp the version into the binary from the
latest `menu-app-v*` git tag (via `git describe`), so `menu-app --version`
reports e.g. `v1.0.0` on a tag or `v1.0.0-3-gabc123` when ahead of one. Outside
git, or with no matching tag, the version falls back to `dev`.

Or directly (no version stamping — reports `dev`):

```sh
go build -o menu-app .
```

The `go` directive in `go.mod` tracks the latest stable Go installed on the
development workstation.

## How to troubleshoot it

- **`not a git initialized directory`** — you are not inside a git repo. Run
  `git init` or `cd` into a repository first.
- **A menu item does nothing / errors immediately** — the script is probably
  not executable. Run `chmod +x <path>`.
- **`Cannot run … : no such file or directory`** — the `script:` path in
  `.menu-app.yaml` is wrong; it must be relative to the git root.
- **Scripts can't find files they expect** — remember scripts run with the
  **git root** as the working directory, not the directory you launched
  `menu-app` from.

## Releasing

Tagging `menu-app-vX.Y.Z` triggers `.github/workflows/menu-app-release.yml`,
which cross-compiles binaries, generates `checksums.txt`, signs it with cosign
into a Sigstore bundle (`checksums.txt.bundle`), and publishes a GitHub release.
`menu-app` is also included in the repository's unified `.goreleaser.yml`
(deb/rpm/brew) pipeline. See the repo `RUNBOOK.md` "Release signing" section for
how to verify a download.
