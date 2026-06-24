#!/usr/bin/env bash
# Acquire everything the PR triage needs into .pr-review/
#
#   fetch_pr.sh <pr-number>            # uses gh to pull a GitHub PR
#   fetch_pr.sh --local [base-ref]     # diff current branch vs base (default origin/main)
#
# Writes: diff.patch, pr.json (schema-shaped), comments.json, diffstat.txt,
#         rules/<copied agent-instruction files>
set -euo pipefail

OUTDIR="${PR_REVIEW_DIR:-.pr-review}"
mkdir -p "$OUTDIR/rules"

# --- gather repo agent-instruction / rule files (define "pattern" + "sensitive") ---
collect_rules() {
  local found=0 flat
  while IFS= read -r -d '' f; do
    flat="${f#./}"; flat="${flat//\//__}"
    cp "$f" "$OUTDIR/rules/$flat" 2>/dev/null && { echo "  $f"; found=1; }
  done < <(find . \
      \( -path ./.git -o -path ./node_modules -o -path "./$OUTDIR" \) -prune -o \
      -type f \( \
        -iname 'CLAUDE.md' -o -iname 'AGENTS.md' -o -iname 'GEMINI.md' \
        -o -iname '.cursorrules' -o -iname '.clinerules' -o -iname '.windsurfrules' \
        -o -path '*/.cursor/rules/*' \
      \) -print0)
  [ "$found" -eq 1 ] || echo "  (none found — classify in degraded mode; see classifier.md)"
}

# --- summarize the diff so the agent can decide on chunking ---
diffstat() {
  python3 - "$OUTDIR/diff.patch" "$OUTDIR/diffstat.txt" <<'PY'
import sys
patch = open(sys.argv[1], encoding="utf-8", errors="replace").read()
files, cur, add, rem = {}, None, 0, 0
for line in patch.splitlines():
    if line.startswith("+++ "):
        p = line[4:].strip(); p = p[2:] if p.startswith("b/") else p
        cur = None if p == "/dev/null" else p
        if cur: files.setdefault(cur, [0, 0])
    elif cur and line.startswith("+") and not line.startswith("+++"):
        files[cur][0] += 1; add += 1
    elif cur and line.startswith("-") and not line.startswith("---"):
        files[cur][1] += 1; rem += 1
total = add + rem
out = [f"{len(files)} files, +{add} -{rem} ({total} changed lines)"]
if total > 1500:
    out.append("LARGE DIFF — classify per top-level directory and merge, or filter by path.")
for f, (a, r) in sorted(files.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
    out.append(f"  +{a} -{r}\t{f}")
open(sys.argv[2], "w").write("\n".join(out) + "\n")
print(out[0] + (("  [" + out[1] + "]") if total > 1500 else ""))
PY
}

echo "Collecting repo rule files into $OUTDIR/rules/ :"
collect_rules

if [ "${1:-}" = "--local" ]; then
  BASE="${2:-origin/main}"
  HEAD_SHA="$(git rev-parse HEAD)"
  if ! BASE_SHA="$(git merge-base "$BASE" HEAD 2>/dev/null || git rev-parse --verify "$BASE^{commit}" 2>/dev/null)"; then
    echo "Could not resolve base ref '$BASE'. Pass an existing ref, e.g. --local origin/main or --local master." >&2
    exit 1
  fi
  git diff "$BASE_SHA".."$HEAD_SHA" > "$OUTDIR/diff.patch"
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  python3 - "$BRANCH" "$BASE" "$BASE_SHA" "$HEAD_SHA" "$OUTDIR/pr.json" <<'PY'
import json, sys
branch, base, bs, hs, outp = sys.argv[1:6]
json.dump({"id": branch, "title": f"{branch} (local diff vs {base})",
           "base_sha": bs, "head_sha": hs, "description_summary": ""},
          open(outp, "w"), indent=2)
PY
  echo '[]' > "$OUTDIR/comments.json"
  echo "Wrote local diff ($BASE_SHA..$HEAD_SHA) → $OUTDIR/diff.patch"
else
  PR="${1:?usage: fetch_pr.sh <pr-number> | --local [base-ref]}"
  command -v gh >/dev/null || { echo "gh CLI not found; use --local mode" >&2; exit 1; }
  gh pr diff "$PR" > "$OUTDIR/diff.patch"
  gh pr view "$PR" --json number,title,url,body,headRefOid,baseRefOid > "$OUTDIR/_pr_raw.json"
  gh pr view "$PR" --json comments,reviews > "$OUTDIR/comments.json" 2>/dev/null || echo '{}' > "$OUTDIR/comments.json"
  # map gh's fields onto the schema's pr.* shape (id = owner/repo#number, summarized body)
  python3 - "$OUTDIR/_pr_raw.json" "$OUTDIR/pr.json" <<'PY'
import json, re, sys
raw = json.load(open(sys.argv[1]))
url = raw.get("url", "") or ""
m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
pid = f"{m.group(1)}#{m.group(2)}" if m else f"#{raw.get('number','')}"
body = (raw.get("body") or "").strip().replace("\r", "")
summary = (body[:280] + "…") if len(body) > 280 else body
json.dump({"id": pid, "title": raw.get("title", ""), "url": url,
           "base_sha": raw.get("baseRefOid", ""), "head_sha": raw.get("headRefOid", ""),
           "description_summary": summary},
          open(sys.argv[2], "w"), indent=2)
PY
  rm -f "$OUTDIR/_pr_raw.json"
  echo "Wrote PR #$PR → $OUTDIR/diff.patch, pr.json, comments.json"
fi

printf 'diffstat: '; diffstat
echo "Done. Feed $OUTDIR/ to the classifier (see references/classifier.md)."
