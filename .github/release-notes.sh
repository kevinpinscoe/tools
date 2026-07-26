#!/usr/bin/env bash
#
# Build grouped release notes for one tool in this monorepo.
#
# Releases here are tagged per tool (menu-app-v2.0.0, check-git-repos-v1.10.1),
# so GitHub's own "generate release notes" is a poor fit twice over: it cannot
# scope commits to a single tool's source directory, and it lists only merged
# pull requests — most work in this repo lands directly on main and would be
# omitted entirely.
#
# This walks the git log between the previous tag for the same tool and the
# current one, restricted to that tool's source directory, and groups the
# subjects by conventional-commit type. Output matches the grouping used by the
# .goreleaser.yml changelog block in the standalone Go repos.
#
# Usage:  release-notes.sh <tool> <tag>            e.g. release-notes.sh menu-app menu-app-v2.0.0
# Output: markdown on stdout
#
set -euo pipefail

TOOL="${1:?usage: release-notes.sh <tool> <tag>}"
TAG="${2:?usage: release-notes.sh <tool> <tag>}"
SRC="${TOOL}-source"
REPO="${GITHUB_REPOSITORY:-kevinpinscoe/tools}"

# The tag immediately preceding $TAG for this tool, by tag creation date.
#
# Deliberately not "newest tag that isn't $TAG": these workflows accept an
# older tag via workflow_dispatch to rebuild packages, and that shortcut would
# then diff against the newest tag and produce backwards notes.
PREV="$(git tag -l "${TOOL}-v*" --sort=creatordate \
        | awk -v cur="$TAG" '$0 == cur { print prev; exit } { prev = $0 }')"

if [ -n "$PREV" ]; then
  RANGE="${PREV}..${TAG}"
else
  RANGE="$TAG"
fi

subjects="$(git log --no-merges --pretty=%s "$RANGE" -- "$SRC" \
            | grep -Ev '^(docs|test|chore|ci)[:(]|^Merge ' || true)"

emit_group() {
  local title="$1" pattern="$2" lines
  lines="$(printf '%s\n' "$subjects" | grep -Ei "$pattern" || true)"
  [ -z "$lines" ] && return 0
  printf '### %s\n\n' "$title"
  # Drop the conventional-commit scope: "feat(menu-app): x" -> "feat: x"
  printf '%s\n' "$lines" | sed -E 's/^([a-zA-Z]+)\([^)]+\)(!?):/\1\2:/' | sed 's/^/- /'
  printf '\n'
  # Remove the matched lines so a commit lands in exactly one group.
  subjects="$(printf '%s\n' "$subjects" | grep -Evi "$pattern" || true)"
}

{
  emit_group "⚠️ Security fixes" '^(sec|vuln)'
  emit_group "Breaking changes"  '^[a-zA-Z]+(\([^)]+\))?!:'
  emit_group "New features"      '^feat'
  emit_group "Bug fixes"         '^fix'
  # Whatever is left over.
  if [ -n "${subjects//[[:space:]]/}" ]; then
    printf '### Other changes\n\n'
    printf '%s\n' "$subjects" | sed -E 's/^([a-zA-Z]+)\([^)]+\)(!?):/\1\2:/' | sed 's/^/- /'
    printf '\n'
  fi

  if [ -n "$PREV" ]; then
    printf '**Full Changelog**: https://github.com/%s/compare/%s...%s\n' "$REPO" "$PREV" "$TAG"
  fi
} | sed '/./,$!d'
