#!/usr/bin/env bash
# Acquire everything the PR triage needs into .pr-review/
#
#   fetch_pr.sh <pr-number>            # uses gh to pull a GitHub PR
#   fetch_pr.sh --local [base-ref]     # diff current branch vs base (default origin/main)
#
# Writes: diff.patch, pr.json, comments.json, rules/<copied agent-instruction files>
set -euo pipefail

OUTDIR="${PR_REVIEW_DIR:-.pr-review}"
mkdir -p "$OUTDIR/rules"

# --- gather repo agent-instruction / rule files (define "pattern" + "sensitive") ---
collect_rules() {
  local found=0
  while IFS= read -r -d '' f; do
    # flatten path into the rules dir so names don't collide
    local flat="${f#./}"; flat="${flat//\//__}"
    cp "$f" "$OUTDIR/rules/$flat" 2>/dev/null && { echo "  $f"; found=1; }
  done < <(find . \
      \( -path ./.git -o -path ./node_modules -o -path "./$OUTDIR" \) -prune -o \
      -type f \( \
        -iname 'CLAUDE.md' -o -iname 'AGENTS.md' -o -iname 'GEMINI.md' \
        -o -iname '.cursorrules' -o -iname '.clinerules' -o -iname '.windsurfrules' \
        -o -path '*/.cursor/rules/*' \
      \) -print0)
  [ "$found" -eq 1 ] || echo "  (none found)"
}

echo "Collecting repo rule files into $OUTDIR/rules/ :"
collect_rules

# --- diff + metadata ---
if [ "${1:-}" = "--local" ]; then
  BASE="${2:-origin/main}"
  HEAD_SHA="$(git rev-parse HEAD)"
  BASE_SHA="$(git merge-base "$BASE" HEAD 2>/dev/null || git rev-parse "$BASE")"
  git diff "$BASE_SHA"..."$HEAD_SHA" > "$OUTDIR/diff.patch"
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  printf '{"id":"%s","title":"%s (local diff vs %s)","base_sha":"%s","head_sha":"%s"}\n' \
    "$BRANCH" "$BRANCH" "$BASE" "$BASE_SHA" "$HEAD_SHA" > "$OUTDIR/pr.json"
  echo '[]' > "$OUTDIR/comments.json"
  echo "Wrote local diff ($BASE_SHA..$HEAD_SHA) → $OUTDIR/diff.patch"
else
  PR="${1:?usage: fetch_pr.sh <pr-number> | --local [base-ref]}"
  command -v gh >/dev/null || { echo "gh CLI not found; use --local mode" >&2; exit 1; }
  gh pr diff "$PR" > "$OUTDIR/diff.patch"
  gh pr view "$PR" --json number,title,url,body,baseRefName,headRefOid,baseRefOid \
    > "$OUTDIR/pr.json"
  gh pr view "$PR" --json comments,reviews > "$OUTDIR/comments.json" 2>/dev/null || echo '{}' > "$OUTDIR/comments.json"
  echo "Wrote PR #$PR → $OUTDIR/diff.patch, pr.json, comments.json"
fi

echo "Done. Feed $OUTDIR/ to the classifier (see references/classifier.md)."
