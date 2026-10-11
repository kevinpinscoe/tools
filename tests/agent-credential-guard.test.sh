#!/usr/bin/env bash
#
# agent-credential-guard.test.sh -- the agent launchers must refuse to start from a
# shell that carries an elevated OpenBao session, without printing its value.
#
# Run:  bash ~/tools/tests/agent-credential-guard.test.sh     (exit 0 = pass)
#
# No agent, no OpenBao, no real credential. HOME is a temporary directory and
# claude, codex, abduco, screen and script are stubs first on PATH that would
# leave a marker file if a launcher ever reached them. The container and
# other-host branches are exercised on a COPY of the guard in which the three
# host literals are rewritten; the shipped guard has no test hook.

set -uo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ROOT=$(cd -- "$HERE/.." && pwd -P)
GUARD="$ROOT/agent-credential-guard"

pass=0; fail=0
ok()  { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL %s\n      %s\n' "$1" "${2:-}"; }
check() { if eval "$2"; then ok "$1"; else bad "$1" "$2"; fi; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/machome" "$TMP/shm"
SECRET="s.ADMIN-SENTINEL-$RANDOM$RANDOM"; INJECTED="s.INJECTED-SENTINEL-$RANDOM$RANDOM"
for c in claude codex abduco screen script; do printf '#!/bin/sh\ntouch "%s/agent-started"\n' "$TMP" > "$TMP/bin/$c"; chmod +x "$TMP/bin/$c"; done
CLEAN=(env -i PATH="$TMP/bin:/usr/bin:/bin:/usr/sbin:/sbin" HOME="$TMP/home" TERM=dumb)
g() { out=$("${CLEAN[@]}" "$@" 2>&1); rc=$?; }

# --- this host's branch (macOS: no token belongs in an ordinary shell) -----------
if [ "$(uname -s)" = "Darwin" ]; then
  g bash "$GUARD" t;                                   check "mac: clean shell is allowed" '[ $rc -eq 0 ] && [ -z "$out" ]'
  g OPENBAO_ADMIN_SESSION=mac-local bash "$GUARD" t;   check "mac: the bao-auth flag is refused (77)" '[ $rc -eq 77 ]'
  g BAO_TOKEN="$SECRET" bash "$GUARD" t;               check "mac: an inherited BAO_TOKEN is refused" '[ $rc -eq 77 ] && printf "%s" "$out" | grep -q "BAO_TOKEN is set"'
  g VAULT_TOKEN="$SECRET" bash "$GUARD" t;             check "mac: an inherited VAULT_TOKEN is refused" '[ $rc -eq 77 ] && printf "%s" "$out" | grep -q "VAULT_TOKEN is set"'
  g BAO_TOKEN="$SECRET" VAULT_TOKEN="$SECRET" OPENBAO_ADMIN_SESSION=home bash "$GUARD" t
  check "the refusal names variables and never prints a value" '[ $rc -eq 77 ] && ! printf "%s" "$out" | grep -qF "$SECRET" && [ "$(printf "%s\n" "$out" | grep -c "^  - ")" = 3 ]'
else
  echo "skip: macOS branch (not on macOS)"
fi
g OPENBAO_ADMIN_SESSION=home bash "$GUARD" t;          check "any host: the bao-auth flag is refused" '[ $rc -eq 77 ]'

# --- container branch, on a rewritten copy --------------------------------------
sed -e 's|"\$(uname -s)" = "Darwin"|"" = "Darwin"|' -e "s|-d /mac-home|-d $TMP/machome|" -e "s|/dev/shm|$TMP/shm|" "$GUARD" > "$TMP/guard-container"
CACHE="$TMP/shm/.bao-token-$(id -u)"; printf '%s' "$INJECTED" > "$CACHE"
check "container copy was rewritten as intended" 'grep -q "$TMP/machome" "$TMP/guard-container" && grep -q "$TMP/shm" "$TMP/guard-container"'
g BAO_TOKEN="$INJECTED" bash "$TMP/guard-container" t;  check "container: the injected token is the ordinary state and is allowed" '[ $rc -eq 0 ]'
g BAO_TOKEN="$SECRET" bash "$TMP/guard-container" t;    check "container: a BAO_TOKEN that is not the injected one is refused" '[ $rc -eq 77 ] && ! printf "%s" "$out" | grep -qF -e "$SECRET" -e "$INJECTED"'
g BAO_TOKEN="$INJECTED" VAULT_TOKEN="$SECRET" bash "$TMP/guard-container" t; check "container: VAULT_TOKEN is refused even beside the injected BAO_TOKEN" '[ $rc -eq 77 ]'
g BAO_TOKEN="$INJECTED" OPENBAO_ADMIN_SESSION=mac-local bash "$TMP/guard-container" t; check "container: the flag is refused" '[ $rc -eq 77 ]'
g bash "$TMP/guard-container" t;                        check "container: a shell with no token is allowed" '[ $rc -eq 0 ]'
rm -f "$CACHE"
g BAO_TOKEN="$SECRET" bash "$TMP/guard-container" t;    check "container: with no injected token, any BAO_TOKEN is refused" '[ $rc -eq 77 ]'

# --- any other host, on a rewritten copy ----------------------------------------
sed -e 's|"\$(uname -s)" = "Darwin"|"" = "Darwin"|' -e "s|-d /mac-home|-d $TMP/does-not-exist|" "$GUARD" > "$TMP/guard-other"
g BAO_TOKEN="$SECRET" bash "$TMP/guard-other" t;        check "other host: a token in an ordinary shell is not second-guessed" '[ $rc -eq 0 ]'
g BAO_TOKEN="$SECRET" OPENBAO_ADMIN_SESSION=home bash "$TMP/guard-other" t; check "other host: the flag is still refused" '[ $rc -eq 77 ]'

# --- the launch paths ------------------------------------------------------------
for l in myclaude mycodex myclaude-screen; do
  rm -f "$TMP/agent-started"
  g OPENBAO_ADMIN_SESSION=mac-local BAO_TOKEN="$SECRET" bash "$ROOT/$l"
  check "$l: refuses from an administrator shell, starts nothing, prints no value" \
    '[ $rc -eq 77 ] && [ ! -e "$TMP/agent-started" ] && printf "%s" "$out" | grep -q "^$l: refused" && ! printf "%s" "$out" | grep -qF "$SECRET"'
  g bash "$ROOT/$l"
  check "$l: from a clean shell the guard lets it continue" '[ $rc -ne 77 ] && ! printf "%s" "$out" | grep -q "refused to start"'
  check "$l: calls the guard before its first requirement check" \
    '[ "$(grep -n "agent-credential-guard\" \"$l\"" "$ROOT/$l" | cut -d: -f1)" -lt "$(grep -n "^require_cmd " "$ROOT/$l" | head -1 | cut -d: -f1)" ]'
done
check "guard has no override flag or variable" '! grep -vE "^[[:space:]]*#" "$GUARD" | grep -qiE "override|force|skip|ALLOW"'

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
