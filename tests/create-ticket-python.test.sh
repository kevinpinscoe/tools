#!/usr/bin/env bash
# create-ticket-python.test.sh -- which python3 create-ticket-in-youtrack starts (POE-67).
#
# A stub uname decides the OS and a stub python3 first on PATH records being run. On Darwin the stub
# must never run: reaching it is a silent fallback to PATH's Python. No credential is touched: HOME
# is empty, so the wrapper takes its no-AppRole path. Usage: bash tests/create-ticket-python.test.sh
set -uo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home"
printf '#!/bin/sh\necho "$STUB_UNAME"\n' > "$T/bin/uname"
printf '#!/bin/sh\nprintf "%%s\\n" "$@" > "$STUB_RAN"\nexit 42\n' > "$T/bin/python3"
chmod +x "$T/bin/uname" "$T/bin/python3"
PASS=0; FAIL=0
check() { if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "  ok   $1"; else FAIL=$((FAIL+1)); echo "  FAIL $1: got [$2], want [$3]"; fi; }

R="$T/ran"
env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" STUB_UNAME=Linux STUB_RAN="$R" \
  bash "$ROOT/create-ticket-in-youtrack" "a b" >/dev/null 2>&1
check "Linux keeps python3 from PATH and its exit status" "$?" 42
check "Linux passes the script and arguments" "$(cat "$R" 2>/dev/null)" "$(printf '%s\n%s' "$ROOT/create-ticket-in-youtrack.py" 'a b')"

if [ "$(/usr/bin/uname -s)" = Darwin ]; then
  rm -f "$R"
  env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" STUB_UNAME=Darwin STUB_RAN="$R" \
    bash "$ROOT/create-ticket-in-youtrack" --help >/dev/null 2>&1
  check "Darwin never runs python3 from PATH" "$([ -e "$R" ] && echo ran || echo not-run)" not-run
fi

echo "passed: $PASS   failed: $FAIL"
[ "$FAIL" -eq 0 ]
