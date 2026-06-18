#!/usr/bin/env sh
# changelog.sh — add a line to CHANGELOG.md under ## [Unreleased].
#   scripts/changelog.sh "<line>"
#   scripts/changelog.sh --changed "<line>"   # --added(default)|--changed|--fixed|--removed|--rejected
set -e
section="Added"
case "$1" in
  --added) section="Added"; shift ;; --changed) section="Changed"; shift ;;
  --fixed) section="Fixed"; shift ;; --removed) section="Removed"; shift ;;
  --rejected) section="Investigated / Rejected"; shift ;;
esac
line="$*"
[ -n "$line" ] || { echo "usage: scripts/changelog.sh [--added|--changed|--fixed|--removed|--rejected] \"<line>\"" >&2; exit 2; }
root=$(git rev-parse --show-toplevel); cl="$root/CHANGELOG.md"
[ -f "$cl" ] || { echo "no CHANGELOG.md at repo root" >&2; exit 1; }
grep -Fq -- "- $line" "$cl" && { echo "changelog: already present, skipping"; exit 0; }
awk -v sec="### $section" -v entry="- $line" '
  BEGIN{u=0;d=0}
  /^## \[Unreleased\]/{print;u=1;next}
  u&&!d&&$0==sec{print;print entry;d=1;next}
  u&&!d&&/^## /{print sec;print entry;print "";print;u=0;d=1;next}
  {print}
  END{if(u&&!d){print sec;print entry}}' "$cl" > "$cl.tmp" && mv "$cl.tmp" "$cl"
git add "$cl"; echo "changelog: + [$section] $line"
