#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename "$0") <file>" >&2
    exit 1
fi

src="$1"

if [[ ! -e "$src" ]]; then
    echo "Error: '$src' not found" >&2
    exit 1
fi

dir=$(dirname "$src")
base=$(basename "$src")

# Replace runs of non-alphanumeric characters (preserving dots) with a single hyphen,
# lowercase the result, then strip any leading or trailing hyphens
new_base=$(printf '%s' "$base" \
    | sed -E 's/[^a-zA-Z0-9.]+/-/g' \
    | sed -E 's/-\././g' \
    | sed -E 's/^-+//; s/-+$//' \
    | tr '[:upper:]' '[:lower:]')

if [[ "$base" == "$new_base" ]]; then
    echo "No change needed: '$base'"
    exit 0
fi

dst="$dir/$new_base"

if [[ -e "$dst" && ! "$src" -ef "$dst" ]]; then
    echo "Error: destination '$dst' already exists" >&2
    exit 1
fi

mv -- "$src" "$dst"
echo "'$base'  ->  '$new_base'"
