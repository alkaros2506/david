# Review Copilot _(working name — rename me)_

> A reviewer's **co-pilot** for pull requests. It rides along **next to a human
> reviewer**, step by step, grouping a PR's changes by **how much new thinking
> they demand** (novelty) and **how far they reach** (blast radius) — then
> renders an interactive viewer so the reviewer spends attention where it
> actually matters.

## What this is — and isn't

| ✅ It is | ❌ It is not |
|---|---|
| A **parallel, step-by-step assistant** for a human reviewing a PR | An automated reviewer or auto-approver |
| A **triage / attention-router** — "where should I look hardest?" | A bug-finder (defer to linters / Claude Code Review / superpowers code-review) |
| A **confidence artifact** — a grouped, citation-backed viewer with per-group acknowledgements | A post-hoc assessment — it works _during_ review, not after |

The thesis: AI floods PRs faster than humans can review them, and reviewers
[start skimming past ~400 lines](https://gitrank.dev/blog/pull-request-best-practices-review-to-merge).
The bottleneck is **human attention**, not finding more bugs. This routes that
attention.

## The core idea: two axes

Every change group is plotted on a **novelty × blast-radius** matrix. The scary
quadrant (high novelty × high blast) gets deep review; busy-work gets a glance.

**Novelty — how much new thinking the reviewer must do:**

| Tier | Meaning | Examples |
|---|---|---|
| 🟢 **Busy work** | Extends an existing pattern | New field on a table/API, new enum/constant, tests & seed data, comments/docs |
| 🟡 **New capability, same infra** | A new instance of an existing architectural pattern | A form on a page, a datatable, a resolver/controller that fits the app architecture |
| 🔴 **New architecture / exposure / infra** | Introduces a new pattern, dependency, or surface | A new queue, a new database, a new microfrontend, a significant business-logic fork |

**Blast radius — how far the change reaches** (LLM-inferred across 8 surfaces;
see [`taxonomy.md`](skills/reviewing-a-pull-request/spec/taxonomy.md)).

Full definitions, the scoring rubric, and the priority matrix live in
[`skills/reviewing-a-pull-request/spec/taxonomy.md`](skills/reviewing-a-pull-request/spec/taxonomy.md).

## How it works (MVP: Claude Code + Cmux / Conductor)

```
1. ACQUIRE   fetch_pr.sh        → diff + description + comments + repo rule files + diffstat
2. CLASSIFY  subagent scoped to the diff, using spec/ → structured JSON (output-schema.json)
3. RENDER    render_viewer.py --diff → interactive HTML viewer, with cited hunks inline
4. WALK      agent walks the reviewer riskiest-first; captures per-group acks
5. (opt) ENFORCE   on request, won't call the branch "review-clean" until 🔴 groups are acked
```

The **host agent is the only runtime** — Claude reads the diff and the repo's own
`CLAUDE.md`/`AGENTS.md` and does the classification itself. No hosted service, no
separate API key, no webhook. The viewer is a single self-contained HTML file, so
it renders identically everywhere.

## Architecture decisions (from design)

- **Co-pilot, not autopilot** — assists a human reviewing in parallel; never approves.
- **Reasoning runs in the host agent** — guided by the skill. (A headless engine
  for CI was scoped _out_ of the MVP.)
- **Detection is LLM-first** — blast radius is inferred from the diff + the repo's
  system prompt / agent instructions, not a dependency graph.
- **One versioned spec** ([`spec/`](skills/reviewing-a-pull-request/spec/)) is the
  single source of truth for tiers, the blast rubric, and the output schema.
- **Enforcement is optional**, advisory by default.
- **Skill-canonical packaging** — authored once as a Claude Code skill; thin
  Codex/Cursor/Desktop/Web adapters come later via `~/.agents/skills/` + `AGENTS.md`.

## Prior art & positioning

There's real prior art on the _blast-radius_ axis (Meta's RADAR / "Risk-Aware Diff
Auto Review", the
[Impact Assessment skill](https://mcpmarket.com/tools/skills/impact-assessment-blast-radius-analysis),
[ARGUS](https://argus.reviews/)) and many _bug-finding_ reviewers (Anthropic's
Claude Code Review, [obra/superpowers](https://github.com/obra/superpowers)). **Nobody
combines the _novelty_ tiering + the 2D matrix + a grouped, citation-backed
reviewer viewer.** That's the wedge. We borrow patterns (subagent-scoped-to-diff,
Draft→Show→Approve, the 8-surface checklist) rather than reinventing them.

## Repo layout

```
skills/reviewing-a-pull-request/
  SKILL.md                  ← trigger + the riskiest-first walkthrough method
  spec/
    taxonomy.md             ← novelty tiers + 8-surface blast rubric + priority matrix
    output-schema.json      ← JSON schema for the classifier's output
  references/
    classifier.md           ← subagent prompt template (placeholders)
  scripts/
    fetch_pr.sh             ← gh/git: pull diff, description, comments, rule files
    render_viewer.py        ← classification JSON → self-contained HTML viewer
  examples/
    sample-classification.json  ← demo data; render it to see the viewer
```

## Roadmap

- **MVP** — Claude Code skill + viewer (Claude Code, Cmux, Conductor).
- **Next** — Codex & Cursor adapters (`AGENTS.md` + `~/.agents/skills/` alias).
- **Later** — Claude Desktop, Web; optional sync of the `.pr-review/` sidecar to a
  shared dashboard/overlay.
