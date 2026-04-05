#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "Usage: $(basename "$0") <search-term>" >&2
  exit 1
fi

rg -i "$1" -g '*.md'

#rg -n 'search-text' -g '*.md'      # show line numbers
#rg -i 'search-text' -g '*.md'      # case-insensitive
#rg -l 'search-text' -g '*.md'      # only show matching file names
#rg -C 2 'search-text' -g '*.md'    # show 2 lines of context
