#!/usr/bin/env bash
# claude-settings-baseline.sh — bring ~/.claude/settings.json up to Kevin's
# Claude Code baseline on any host:
#
#   - permissions.defaultMode = "auto"
#   - every skill in ~/.claude/skills set to "user-invocable-only", so no skill
#     sits in Claude's context until it is run with /name or via skills-tui
#
# Skills arrive at any time (the Mac's shared library, a fresh clone), so this
# is meant to be re-run rather than applied once: mac-container runs it from
# container-zshrc.sh on every shell start. A skill added since the last run
# stays listed in Claude's context until this runs again.
#
# Fill-only: a key that is already set is never changed, so a deliberate
# per-skill "on"/"off" or a different defaultMode survives. The file is only
# rewritten when something actually changed. CWD-independent; runs under
# macOS's /bin/bash 3.2. Requires jq >= 1.6 (for --args).
set -euo pipefail

settings="${HOME}/.claude/settings.json"
skills_dir="${SKILLS_DIR:-${HOME}/.claude/skills}"

command -v jq >/dev/null 2>&1 || { echo "claude-settings-baseline: jq not found" >&2; exit 1; }

mkdir -p "$(dirname "$settings")"
[[ -s "$settings" ]] || printf '{}\n' > "$settings"
if ! jq empty "$settings" 2>/dev/null; then
    echo "claude-settings-baseline: $settings is not valid JSON; leaving it alone" >&2
    exit 1
fi

# Skill names are directory names (they match each SKILL.md's frontmatter
# name). A broken symlink fails the -f test and is skipped; a name outside a
# plain charset is skipped rather than written into JSON.
names=()
if [[ -d "$skills_dir" ]]; then
    for skill_md in "$skills_dir"/*/SKILL.md; do
        [[ -f "$skill_md" ]] || continue
        name="$(basename "$(dirname "$skill_md")")"
        [[ "$name" =~ ^[A-Za-z0-9_.:-]+$ ]] || continue
        names+=("$name")
    done
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# ${names[@]+...}: bash 3.2 treats an empty array as unbound under set -u.
jq '
  .permissions = ((.permissions // {}) | .defaultMode //= "auto")
  | .skillOverrides = (reduce $ARGS.positional[] as $n
      ((.skillOverrides // {}); .[$n] //= "user-invocable-only"))
' --args ${names[@]+"${names[@]}"} < "$settings" > "$tmp"

# Write in place (not mv) so the file keeps its inode, owner and mode.
if ! cmp -s <(jq -S . "$settings") <(jq -S . "$tmp"); then
    cat "$tmp" > "$settings"
fi
