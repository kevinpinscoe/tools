#!/usr/bin/env bash
#
# work-ai-credential.test.sh — on work-macbook, what-did-i and
# create-ticket-in-youtrack never read OpenBao with the ambient (administrator)
# CLI token (AI-85).
#
# Run:  bash ~/tools/tests/work-ai-credential.test.sh
# Exits non-zero on any failure; exits 0 with "SKIP" off macOS.
#
# The real modules are loaded in a temporary HOME. On PATH, an ambient `bao`
# stands for the administrator's CLI: it answers with an ADMIN value and records
# every call. A stand-in work-ai-bao (the restricted reader) is placed where the
# tools look for it, $HOME/Projects/private/secrets-management/scripts/work-ai-bao,
# and each case sets how it behaves. A file holding an ADMIN token stands for the
# administrator's token file (the one tools PR 47 points what-did-i at). Nothing
# contacts a real OpenBao, parzival, Gitea, GitHub or YouTrack.

set -uo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ROOTDIR="$(cd "$HERE/.." && pwd -P)"

pass=0; fail=0
ok()  { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL %s\n      %s\n' "$1" "${2:-}"; }
check() { if eval "$2"; then ok "$1"; else bad "$1" "$2"; fi; }

[ "$(uname -s)" = Darwin ] || { echo "SKIP: the work-macbook cases need macOS"; exit 0; }

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"; mkdir -p "$HOME" "$TMP/bin"
RUNNER="$HOME/Projects/private/secrets-management/scripts/work-ai-bao"
mkdir -p "$(dirname "$RUNNER")"
export CALLS="$TMP/calls.log"

cat > "$TMP/bin/bao" <<EOF
#!/bin/bash
echo "AMBIENT \$*" >> "$CALLS"; printf 'ADMIN-GITEA-SENTINEL'
EOF
cat > "$TMP/bin/parzival" <<EOF
#!/bin/bash
echo "PARZIVAL \$*" >> "$CALLS"; exit 1
EOF
cat > "$TMP/bin/python3-stub" <<EOF
#!/bin/bash
echo "PY \$*" >> "$CALLS"
EOF
printf '#!/bin/sh\necho KevinI-MBP24\n' > "$TMP/bin/hostname"
chmod +x "$TMP/bin/"*
( umask 077; printf 'ADMIN-TOKEN-FILE-SENTINEL' > "$TMP/admin-token" )
REAL_PY="$(command -v python3)"

runner() {  # runner MODE : stand-in work-ai-bao
  rm -f "$RUNNER"
  case "$1" in
    ok)      printf '#!/bin/bash\necho "RUNNER $*" >> "%s"\nprintf RESTRICTED-GITEA-SENTINEL\n' "$CALLS" > "$RUNNER" ;;
    refused) printf '#!/bin/bash\necho "RUNNER $*" >> "%s"\necho "work-ai-bao: REFUSED: the token carries the root policy. Your command was not run, and no other token was used." >&2\nexit 3\n' "$CALLS" > "$RUNNER" ;;
    missing) return 0 ;;
  esac
  chmod +x "$RUNNER"
}

# get_gitea_token() from the real module. VAULT_TOKEN_FILE is pointed at the ADMIN
# file, as tools PR 47 would on this Mac, and every open() is recorded.
gitea() {
  : > "$CALLS"
  out=$(env PATH="$TMP/bin:/usr/bin:/bin" JOURNAL_PATH="$TMP/journal" BAO_TOKEN=ADMIN-ENV-SENTINEL VAULT_TOKEN=ADMIN-ENV-SENTINEL \
        "$REAL_PY" - "$ROOTDIR/what-did-i-accomplish-today.py" "$TMP/admin-token" "$TMP/opens.log" <<'PY' 2>"$TMP/err"
import builtins, importlib.util, sys
path, admin, opens = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("wdi", path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.VAULT_TOKEN_FILE = admin
m.wait_for_openbao = lambda *a, **k: None
real_open = builtins.open
def spy(f, *a, **k):
    with real_open(opens, "a") as log:
        log.write(str(f) + "\n")
    return real_open(f, *a, **k)
builtins.open = spy
print("token=%s" % m.get_gitea_token())
PY
); rc=$?
}
ambient_never() { ! grep -qE '^(AMBIENT|PARZIVAL)' "$CALLS"; }
admin_never_opened() { ! grep -qxF "$TMP/admin-token" "$TMP/opens.log" 2>/dev/null; }

# --- what-did-i-accomplish-today.py ---------------------------------------------
runner ok; gitea
check "what-did-i: on the Mac the Gitea token comes from work-ai-bao" '[ $rc -eq 0 ] && [ "$out" = "token=RESTRICTED-GITEA-SENTINEL" ]'
check "what-did-i: ...asking for exactly app/gitea#token" 'grep -qx "RUNNER kv get -mount=app -field=token gitea" "$CALLS"'
check "what-did-i: ...the ambient bao is never run" 'ambient_never'
check "what-did-i: ...and the administrator token file is never opened" 'admin_never_opened'

runner refused; gitea
check "what-did-i: work-ai-bao refuses: no token (GitHub-only report), says why" \
  '[ $rc -eq 0 ] && [ "$out" = "token=None" ] && grep -q "REFUSED: the token carries the root policy" "$TMP/err"'
check "what-did-i: ...no fallback: ambient bao never run, administrator file never opened" 'ambient_never && admin_never_opened'

runner missing; gitea
check "what-did-i: work-ai-bao missing: no token, ambient bao never run, administrator file never opened" \
  '[ "$out" = "token=None" ] && ambient_never && admin_never_opened && grep -q "no other token is used on this Mac" "$TMP/err"'
check "what-did-i: no token value reaches stderr" '! grep -q SENTINEL "$TMP/err"'

# --- the what-did-i wrapper -------------------------------------------------------
sed "s|exec python3 |exec \"$TMP/bin/python3-stub\" |" "$ROOTDIR/what-did-i" > "$TMP/what-did-i"
check "wrapper copy: only the python3 launch differs" '[ "$(diff "$ROOTDIR/what-did-i" "$TMP/what-did-i" | grep -c "^<")" -le 2 ]'
: > "$CALLS"; PATH="$TMP/bin:/usr/bin:/bin" bash "$TMP/what-did-i" yesterday >/dev/null 2>&1
check "wrapper: on the Mac parzival (ambient mode there) is never run; the .py is" \
  '! grep -q "^PARZIVAL" "$CALLS" && grep -q "^PY .*what-did-i-accomplish-today.py yesterday" "$CALLS"'

# --- create-ticket-in-youtrack.py ---------------------------------------------------
: > "$CALLS"
out=$(env PATH="$TMP/bin:/usr/bin:/bin" BAO_TOKEN=ADMIN-ENV-SENTINEL "$REAL_PY" - "$ROOTDIR/create-ticket-in-youtrack.py" <<'PY' 2>&1
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ctiy", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
try:
    print("token=%s" % m.load_youtrack_token())
except SystemExit as e:
    print("exit=%s" % e.code)
PY
); rc=$?
check "create-ticket .py run directly on work-macbook: stops, names the wrapper" \
  'printf "%s" "$out" | grep -q "^exit=" && printf "%s" "$out" | grep -q "Run .create-ticket-in-youtrack. (the wrapper)" && ! printf "%s" "$out" | grep -q "^token="'
check "create-ticket .py: the ambient bao is never run" '! grep -q "^AMBIENT" "$CALLS"'

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
