# pause

A `sleep` replacement that shows a live countdown status line on stderr while waiting. Drop it into any shell script wherever `sleep N` would leave the user wondering how long is left.

## Usage

```
pause <seconds>      # sleep with live countdown
pause --version      # print version and exit
pause --help         # print this help
```

`<seconds>` is a required non-negative integer.

## Status line (interactive terminal)

When stderr is a terminal, a single overwriting line is displayed and updated continuously:

- Total ≤ 60 s: `Pausing for 45 seconds   ⠙   32s remaining`
- Total > 60 s: `Pausing for 1m 30s   ⠙   1m 15s remaining`

The braille spinner character rotates every 100 ms; the remaining-time counter decrements each second. When the pause ends the status line is erased and the cursor is left at the beginning of the line.

## Non-TTY behavior

When stderr is not a terminal (piped output, redirected, systemd unit, cron job), a single line is printed and the process sleeps silently:

```
Waiting for 1m 30s
```

## Examples

```sh
pause 10                        # 10-second pause with spinner
pause 90                        # 1m 30s pause with live countdown
pause 30 && echo "done"         # sequential command after pause
```

## Install

Download the binary for your platform from the [latest release](https://github.com/kevinpinscoe/tools/releases/tag/pause-v1.0.0), verify the checksum, and install to `~/tools`:

**Fedora / Linux x86_64**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/pause-linux-amd64" \
  https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/pause-linux-amd64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/checksums.txt \
  | grep pause-linux-amd64 | sha256sum -c ) \
  && install -m 755 "$TMP/pause-linux-amd64" ~/tools/pause
rm -rf "$TMP"
```

**Raspberry Pi / Linux ARM64**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/pause-linux-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/pause-linux-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/checksums.txt \
  | grep pause-linux-arm64 | sha256sum -c ) \
  && install -m 755 "$TMP/pause-linux-arm64" ~/tools/pause
rm -rf "$TMP"
```

**macOS (Apple Silicon)**
```sh
TMP=$(mktemp -d)
curl -fLo "$TMP/pause-darwin-arm64" \
  https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/pause-darwin-arm64
( cd "$TMP" && curl -fsSL https://github.com/kevinpinscoe/tools/releases/download/pause-v1.0.0/checksums.txt \
  | grep pause-darwin-arm64 | shasum -a 256 -c ) \
  && install -m 755 "$TMP/pause-darwin-arm64" ~/tools/pause
rm -rf "$TMP"
```

> The checksum step prints `pause-...: OK` on success and exits non-zero if the binary was tampered with — the `&&` then prevents `install` from running.

Make sure `~/tools` is on your `$PATH`.

## Build from source

```sh
cd ~/tools/pause-source
make install   # builds and installs to ~/tools/pause
make build     # local build only (outputs ./pause)
make clean     # remove local build artifact
```

Requires Go 1.21+.
