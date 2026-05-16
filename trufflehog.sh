#!/usr/bin/env bash
set -euo pipefail

# trufflehog.sh — scan credential-relevant paths for secrets using TruffleHog.
# Detects the current platform (Fedora, macOS, Raspberry Pi) and adjusts scan
# paths accordingly. Paths that do not exist on the current machine are skipped.
#
# Usage: trufflehog.sh [OUTFILE]
#   OUTFILE  JSON file to write raw findings to (default: /tmp/trufflehog-findings.json)
#
# After the scan, a summary grouped by detector is printed to stdout.
# Compare findings against ~/.environment/.credentials-map.md to identify gaps.

OUTFILE="${1:-/tmp/trufflehog-findings.json}"

if ! command -v trufflehog >/dev/null 2>&1; then
    echo "ERROR: trufflehog not found in PATH" >&2
    echo "Install: curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b ~/.local/bin" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 not found in PATH" >&2
    exit 1
fi

# Paths scanned on every platform
COMMON=(
    "$HOME/.secrets"
    "$HOME/.config"
    "$HOME/.aws"
    "$HOME/.environment"
    "$HOME/.dotfiles"
    "$HOME/.vault-token"
    "$HOME/.codex"
    "$HOME/.jenkins_scripts_token"
    "$HOME/tools"
    "$HOME/admin"
    "$HOME/skills"
    "$HOME/todo"
)

# Platform-specific extras
EXTRA=()
case "$(uname -s)" in
    Darwin)
        EXTRA+=(
            "$HOME/.homebrew"
            "$HOME/.gh_token"
            "$HOME/.realm-release"
            "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
        )
        ;;
    Linux)
        # Fedora and Raspberry Pi / Debian — nothing extra beyond COMMON for now
        ;;
esac

# Build final list, skipping paths that don't exist on this machine
SCAN_PATHS=()
for p in "${COMMON[@]}" "${EXTRA[@]}"; do
    [[ -e "$p" ]] && SCAN_PATHS+=("$p")
done

printf "=== TruffleHog filesystem scan ===\n" >&2
printf "Host:   %s\n" "$(hostname)" >&2
printf "Date:   %s\n" "$(date)" >&2
printf "Output: %s\n" "$OUTFILE" >&2
printf "Paths:\n" >&2
printf "  %s\n" "${SCAN_PATHS[@]}" >&2
printf "\n" >&2

trufflehog filesystem \
    "${SCAN_PATHS[@]}" \
    --json \
    --no-verification \
    2>/dev/null \
    > "$OUTFILE"

COUNT=$(wc -l < "$OUTFILE")
printf "Done — %d raw findings written to %s\n\n" "$COUNT" "$OUTFILE" >&2

python3 - "$OUTFILE" <<'PYEOF'
import sys, json
from collections import defaultdict

findings = []
with open(sys.argv[1]) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except Exception:
            pass

seen = defaultdict(list)
for f in findings:
    detector = f.get("DetectorName", "unknown")
    src = f.get("SourceMetadata", {}).get("Data", {})
    path = None
    for v in src.values():
        if isinstance(v, dict):
            path = v.get("file") or v.get("filename") or str(v)
            break
    seen[(detector, path)].append(f)

print(f"Total raw findings:  {len(findings)}")
print(f"Unique detector+file: {len(seen)}")
print()
print("=== Findings by detector ===")
by_detector = defaultdict(set)
for (detector, path), _ in seen.items():
    by_detector[detector].add(path)

for det in sorted(by_detector):
    paths = sorted(by_detector[det])
    print(f"\n[{det}]")
    for p in paths:
        print(f"  {p}")
PYEOF
