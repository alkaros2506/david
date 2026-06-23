# Triage Taxonomy & Rubric

This is the **single source of truth** for how changes are classified. The skill
prompt, the classifier subagent, and the viewer all defer to it. Keep it versioned;
when it changes, the classifier output changes.

A change **group** is a set of related hunks that together accomplish one logical
thing. Each group gets two scores: a **novelty tier** and a **blast level**. Their
combination sets the review **priority**.

---

## Axis 1 — Novelty (how much new thinking the reviewer must do)

Decide by asking: **does this follow a pattern that already exists in this repo
(per its code and its `CLAUDE.md`/`AGENTS.md`), or does it introduce something new?**

### 🟢 `busy_work` — extends an existing pattern
Mechanical, low-judgement extension of something already established. The reviewer
is checking *correctness and completeness*, not *design*.
- Add a field to a table / API / DTO
- Add an enum value or a constant
- Add tests, fixtures, or seed data
- Add comments or documentation
- Rename / move following an established convention

### 🟡 `new_capability` — new instance of an existing architectural pattern
New behavior, but built the way the codebase already builds that kind of thing. The
reviewer is checking **pattern fit**: does it look like its siblings?
- A new form on a page (when forms already exist)
- A new datatable / list view
- A new resolver, controller, or endpoint that fits the app architecture
- A new background job using the existing job framework

### 🔴 `new_architecture` — new pattern, exposure, or infrastructure
Introduces something the codebase has not done before, or changes a load-bearing
assumption. The reviewer is checking **design and consequences**.
- Introduces a new queue, cache, or database
- Adds a new microfrontend / service / deployment unit
- A new external dependency or third-party integration
- A new public exposure (a new endpoint surface, a new auth path)
- A significant fork in business logic or a new domain concept

**Tie-breaker:** if a group mixes tiers, score it at its **highest** tier and note
the lower-tier parts in `review_focus`. A "small" PR with one 🔴 hunk is a 🔴.

---

## Axis 2 — Blast radius (how far the change reaches)

LLM-inferred from the diff plus the repo's rules — **no dependency graph**. Reason
across these **8 surfaces** (borrowed from impact-analysis practice) and cite what
you find:

1. **Code dependencies** — how much else imports/calls the touched code.
2. **Public interfaces / API contracts** — anything an external or downstream caller relies on.
3. **Data stores** — schema, migrations, indexes, data shape.
4. **Security & auth paths** — authn/authz, permissions, secrets, validation.
5. **Sensitive domains** — payments, billing, PII, compliance (read the repo rules for which areas are flagged).
6. **Cross-service / network boundaries** — queues, events, RPC, webhooks.
7. **Runtime / infra / config** — deploy, env vars, feature flags, IaC.
8. **Shared primitives** — design-system components, shared libs, base classes.

Assign **`low` / `medium` / `high`** and list the specific surfaces that drove it.

| Level | Heuristic |
|---|---|
| `low` | Touches one isolated module; no surface above is meaningfully affected |
| `medium` | Touches 1–2 surfaces, or code with several internal dependents |
| `high` | Touches a sensitive domain, a public contract, data, security, or a network/infra boundary |

> A nullable-column migration on the **payments** table is `busy_work` novelty but
> `high` blast. That split is the whole point of two axes.

---

## The priority matrix

`priority` is `1` (look here first) … ascending. Acknowledgement requirements assume
enforcement is on; otherwise everything is advisory.

|                | Blast `low` | Blast `medium` | Blast `high` |
|----------------|:-----------:|:--------------:|:------------:|
| 🔴 `new_architecture` | P2 — deep review | **P1 — deep review** | **P1 — deep review + 2nd approver** |
| 🟡 `new_capability`   | P3 — pattern-fit check | P2 — pattern-fit check | **P1 — pattern fit + surface check** |
| 🟢 `busy_work`        | P4 — batch-ack | P3 — spot-check | P2 — verify the surface it touches |

- **P1** must be acknowledged individually (and walked through) before "review-clean".
- **P2 / P3** get a spot-check; the reviewer acks them.
- **P4** can be batch-acknowledged in one action.

---

## Grounding rules (non-negotiable)

- **Cite hunks.** Every group lists the `file` + line range that puts it in its tier.
- **Read the rules.** Use the repo's `CLAUDE.md` / `AGENTS.md` to decide "follows an
  existing pattern" (novelty) and "is this a sensitive area" (blast). Record which
  rule files were used in `rules_sources`.
- **Explain, don't restate.** The `why` says what to *worry* about, not what the code does.
