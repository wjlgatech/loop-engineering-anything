#!/usr/bin/env sh
# doc-sync-check.sh — enforce "log + sync docs on every feature change" at the
# push/merge boundary (per-feature, not per-commit). Shared by the pre-push git
# hook AND the global Claude Code hook (~/.claude/settings.json).
#
# Rule: if the branch's diff vs the default branch touches FEATURE CODE
# (src/lib/app/packages, tests excluded), it MUST also touch all three:
#   1. CHANGELOG.md            (the log)
#   2. a human doc             (README.md OR docs/**)
#   3. an agent guide          (CLAUDE.md OR AGENTS.md)
# Missing any -> the push/merge is blocked with an itemized list.
#
# Conscious bypass for genuinely no-doc changes:  SKIP_DOC_SYNC=1
#
# Exit: 0 = ok / not applicable.  1 = doc-sync violation (caller maps to its own
# blocking code; the Claude hook maps 1 -> 2).
set -u

[ "${SKIP_DOC_SYNC:-}" = "1" ] && exit 0

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0   # not a git repo -> nothing to enforce
cd "$root" || exit 0

# Resolve the default branch to diff against.
base=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$base" ]; then
  for c in main master; do
    if git rev-parse --verify "origin/$c" >/dev/null 2>&1; then base="$c"; break; fi
  done
fi
[ -z "$base" ] && base="main"

baseref="origin/$base"
git rev-parse --verify "$baseref" >/dev/null 2>&1 || baseref="$base"
git rev-parse --verify "$baseref" >/dev/null 2>&1 || exit 0   # no base to compare -> skip

mb=$(git merge-base "$baseref" HEAD 2>/dev/null) || exit 0
changed=$(git diff --name-only "$mb" HEAD 2>/dev/null)
[ -z "$changed" ] && exit 0   # nothing ahead of base (e.g. pushing the default branch itself)

code=$(printf '%s\n' "$changed" \
  | grep -E '^(apps/[^/]+/src/|packages/[^/]+/|src/|lib/|app/)' \
  | grep -vE '\.(test|spec)\.|/__tests__/|/tests?/' || true)
[ -z "$code" ] && exit 0   # no feature code in this branch -> nothing to sync

missing=""
printf '%s\n' "$changed" | grep -qE '^CHANGELOG\.md$'            || missing="$missing\n   • CHANGELOG.md           — add: scripts/changelog.sh \"<what changed & why>\""
printf '%s\n' "$changed" | grep -qE '^(README\.md|docs/)'         || missing="$missing\n   • a human doc            — README.md or docs/** (what changed for users)"
printf '%s\n' "$changed" | grep -qE '^(CLAUDE\.md|AGENTS\.md)'    || missing="$missing\n   • an agent guide         — CLAUDE.md or AGENTS.md (contract/surface for agents)"

[ -z "$missing" ] && exit 0

{
  echo "✋ doc-sync: this branch changes feature code but is missing essential doc updates:"
  printf "$missing\n"
  echo ""
  echo "   Update them in this branch (the global engineering policy: log + sync human AND agent docs"
  echo "   in the same change). If this change genuinely needs none, bypass consciously:"
  echo "       SKIP_DOC_SYNC=1 <your push/merge command>"
} >&2
exit 1
