#!/usr/bin/env bash

TOKEN="$(head -n 1 "$HOME/.config/kimai/api")"
BASE='https://kimai.kevininscoe.com'

curl -sS \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json" \
  "${BASE}/api/projects" | jq -r '.[] | "\(.id)\t\(.number // "-")\t\(.name)"'
