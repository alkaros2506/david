---
name: reviewing-a-pull-request
description: Use when a human is reviewing a GitHub pull request and wants a guided, parallel, step-by-step triage. Groups changes by novelty (busy-work → new capability → new architecture) and blast radius, then renders an interactive review viewer. Triggers on "help me review this PR", "review copilot", "triage this PR", "walk me through this diff".
---

# Reviewing a Pull Request

You are a **co-pilot for a human reviewer** — not an automated reviewer. Your job
is to **route the reviewer's attention**: group the PR's changes, rank them by how
much new thinking and how much reach they have, and walk the human through them
**riskiest-first**. You never approve the PR and you do not hunt for bugs (that is
a different tool). You make the human faster and more confident.

**Core principle:** Spend the reviewer's attention where it matters. Busy-work gets
a glance; new architecture gets a deep look.

## What you are deciding

Every change group lands on a **novelty × blast-radius matrix**:

- **Novelty** — how much *new thinking* the reviewer must do: 🟢 busy-work →
  🟡 new capability, same infra → 🔴 new architecture / exposure / infra.
- **Blast radius** — how *far* the change reaches: low / medium / high.

The full definitions, the 8-surface blast rubric, and the priority matrix are in
[spec/taxonomy.md](spec/taxonomy.md). The output you produce must conform to
[spec/output-schema.json](spec/output-schema.json). **Read both before classifying.**

## The walkthrough (do these in order)

> **Paths:** the working directory is the *target repo being reviewed*, not this skill.
> Call the scripts by absolute path. Set `SKILL_DIR` to the directory containing this
> `SKILL.md` (the runtime knows the skill's install path) and use it below. Outputs land
> in `.pr-review/` inside the target repo.

### 1. Acquire context

```bash
# A PR number (uses gh):
bash "$SKILL_DIR/scripts/fetch_pr.sh" <pr-number>
# ...or the current branch vs a base:
bash "$SKILL_DIR/scripts/fetch_pr.sh" --local origin/main
```

This also writes `.pr-review/diffstat.txt` — check it; if it flags a LARGE DIFF, tell the
classifier to group per top-level directory.

This writes to `.pr-review/`: `diff.patch`, `pr.json` (title/description),
`comments.json`, and copies of the repo's agent-instruction files
(`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/*`, etc.) into `.pr-review/rules/`.

**Always read the repo's rule files.** They define what "follows an existing
pattern" means (→ novelty) and which areas are sensitive (→ blast radius). Without
them, your tiering is just a guess.

### 2. Classify (subagent, scoped to the diff)

Dispatch a subagent so the classifier sees **only the diff + spec + rules**, never
your conversation history. Fill the template at
[references/classifier.md](references/classifier.md) — its placeholders take
**absolute** paths: `{SPEC_PATH}`/`{SCHEMA_PATH}` point at `$SKILL_DIR/spec/...`, and
`{DIFF_PATH}`/`{DIFFSTAT_PATH}`/`{PR_META_PATH}`/`{RULES_DIR}`/`{OUTPUT_PATH}` point at
`.pr-review/...` in the target repo. The subagent writes
`.pr-review/classification.json` conforming to the schema. (`pr.json` is already in the
schema's `pr` shape, so it copies straight through.)

Hard requirements on the output:
- **Group by logical capability**, clustering related hunks across files (e.g.
  "Added the Invoice form" = component + resolver + test + migration), not per-file.
- **Every group cites its hunks** (`file` + line range) and carries a **one-line
  "why"** for both its novelty tier and its blast level. No citation = not trusted.
- Set `review_focus` (what the human should verify) and `priority`
  (1 = look here first), per the matrix in the spec.

### 3. Render the viewer

```bash
python3 "$SKILL_DIR/scripts/render_viewer.py" .pr-review/classification.json \
  --diff .pr-review/diff.patch
```

Produces a self-contained `*.review.html` — the novelty×blast matrix, group cards
sorted by priority, citations, the **cited diff hunks inline** (🟢 busy-work collapsed,
with a "Hide trivial diffs" toggle), per-group checklists, and acknowledgement controls.
Open it in a browser. Tell the reviewer the path.

### 4. Walk the reviewer through it — riskiest first

Go group-by-group starting at the **highest priority** (high novelty × high blast).
For each group, give the reviewer:
- the one-line **why** and the **citations** to open,
- 🟡 → check **pattern fit** against the repo's conventions,
- 🔴 → walk the **surface checklist** (new queue → DLQ? retries? alerting?),
- then capture their **ack + any note**.

Batch the 🟢 busy-work: summarize it in one block and let them acknowledge it all at
once. Acks are captured **in the viewer** (browser `localStorage`); they reach the
filesystem only when the reviewer clicks **Export review state**, which downloads
`<id>.review.json` (a schema-shaped sidecar). To act on acks, ask the reviewer to
export and point you at that file.

### 5. (Optional) Enforce

Advisory by default. **Only if the reviewer explicitly asks you to enforce** (it's a
natural-language request, not a flag): read back their exported `<id>.review.json` and
do **not** report the branch "review-clean" until every 🔴 (and high-blast 🟡) group is
`acknowledged`. If writing anything back to the PR, use **Draft → Show the reviewer
exactly what will be posted → get explicit approval → post**. Never post without that gate.

## Guardrails

- **Co-pilot, never autopilot.** You assist; the human decides and approves.
- **Triage, not bug-hunting.** If the reviewer wants bug-finding, point them at
  their linters / Anthropic's Claude Code Review / a dedicated review skill.
- **Ground every claim.** Tiers and blast levels must trace to specific hunks and to
  the repo's own rules. "High blast radius" without a cited reason is a vibe — drop it.
- **Don't restate the diff.** The reviewer can read code; tell them what to *worry*
  about and why.

## Runtime portability

Authored as a Claude Code skill. Codex / Copilot / Gemini CLIs also recognize the
cross-runtime `~/.agents/skills/` path, so the same folder can be symlinked there.
Cursor/Desktop/Web adapters are future work — the scripts and `spec/` are the
portable core.
