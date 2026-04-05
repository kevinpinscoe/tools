#!/usr/bin/env bash

# The structure of that URL reveals the destination by URL-decoding it. 

# Here's the breakdown:
# 
# Pattern:
#
# https://tracking.tldrnewsletter.com/CL0/<URL-ENCODED-DESTINATION>/1/<tracking-id>/<hash>
# Extract the encoded part between /CL0/ and /1/:
# https:%2F%2Flinks.tldrnewsletter.com%2FgJPATV
# URL-decode it:
# https://links.tldrnewsletter.com/gJPATV
# That's still a TLDR short link. 
# Let me follow it:Identified blocking issue and 
# devised manual decoding strategyIdentified blocking 
# issue and devised manual decoding strategyBlocked 
# by robots.txt. Here's how to do it yourself:

# Quick decode — bash one-liner:
#
# bashpython3 -c "import urllib.parse; print(urllib.parse.unquote('https:%2F%2Flinks.tldrnewsletter.com%2FgJPATV'))"
#
# Then follow the short link with curl (no-execute, just get the redirect):
# bashcurl -sI https://links.tldrnewsletter.com/gJPATV | grep -i location

# General rule for any TLDR tracking URL:
#
# bash# Extract and decode in one shot
#
# echo "https://tracking.tldrnewsletter.com/CL0/https:%2F%2Flinks.tldrnewsletter.com%2FgJPATV/..." \
#   | grep -oP '(?<=/CL0/)[^/]+' \
#   | python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read().strip()))"
# The final destination is always the URL sandwiched between /CL0/ and /1/ — just URL-decode it. If it resolves to another links.tldrnewsletter.com short URL, curl -sI that to get the final redirect Location: header.