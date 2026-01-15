# GPT Plans (project update + refactor roadmap)

**Last updated**: 2026-01-14  
**Scope**: `osl-agent-prototype` (this repo)  

This document captures the current recommendations for getting the project to its stated goals (per `docs/development-plan.md`, `docs/AGENT-HANDOFF.md`) and integrating the salvage guidance from `docs/salvage-osl-agent-prototype.txt`.

## What to keep
- **Keep the `MemoryTools` boundary** as the main swap interface (Arango/Chroma/in-memory) and keep contract tests that enforce consistent behavior.
- **Keep JSON-first planning** (LLM outputs strict JSON commands) with the existing backward-compatible fallback parsing for legacy plans.
- **Keep the CPMS + pattern reuse direction**:
  - deterministic fingerprinting (`url+html`)
  - storage in KSG
  - “reuse-first” before re-detecting patterns
- **Keep “mock-first” tests** and gate live/integration tests behind env flags.

## What to change (high leverage, minimal churn)

### 1) Fix repo hygiene around `knowshowgo`
There is a gitlink/submodule-like entry at `knowshowgo` without `.gitmodules`, and a `knowshowgo.bundle` artifact in-repo.

Choose one and enforce it:
- **Recommended**: remove the gitlink + bundle from the mainline repo, keep KSG in-repo (`src/personal_assistant/knowshowgo.py`) until extraction is explicitly scheduled.
- Alternative: formalize as a real submodule (`.gitmodules`, documented init/update, CI support), and remove the bundle unless there’s a documented reason for shipping it.

### 2) Consolidate “source of truth” docs
Docs currently overlap and conflict (older “plans” say Execute/Adapt are pending while `docs/session-notes.md` says they’re complete).

Recommendation:
- Treat **`docs/development-plan.md`** as canonical “what’s next”.
- Treat **`docs/session-notes.md`** as the running log.
- Update or clearly label older plan docs (`core-learning-loop-plan.md`, `development-priorities-summary.md`) as historical.

### 3) Add a session-scoped activation layer (“working memory”)
From salvage plan: add a **WorkingMemoryGraph** that boosts retrieval/ranking based on recent selections/uses (Hebbian reinforcement), without polluting long-term semantic memory.

Reference: `docs/salvage-osl-agent-prototype.txt` Part 1.

**Key principle**: activation is **separate** from semantic memory; persistence is optional.

### 4) Add deterministic parsing for obvious intents
Add lightweight rule-based classification (task/event/reminder-ish) and only call the LLM for ambiguous/complex cases.

This reduces cost/latency and makes behavior more deterministic for simple requests.

## What to add next (implementation order)

### Milestone A — Pattern reuse in real web flows (current project goal)
Per `docs/development-plan.md`:
- Add an agent helper that for a given `url`:
  - gets DOM (`web.get_dom(url)`)
  - tries `ksg.find_best_cpms_pattern(url, html, form_type)`
  - falls back to CPMS detect + store exemplar when match is weak

### Milestone B — Dataset selection (Credential/Identity/PaymentMethod/FormData)
Per `docs/development-plan.md`:
- Prefer same-domain datasets.
- Prompt only for missing required fields.
- Store immediately after user provides values.

### Milestone C — Trial/adapt loop for selectors
Per `docs/development-plan.md`:
- On fill failure: try fallback selectors, and persist the winning selector to pattern/exemplar.

### Milestone D — Salvage components (incremental, test-first)
Per `docs/salvage-osl-agent-prototype.txt`:
- **Step D1**: `src/personal_assistant/working_memory.py` + `tests/test_working_memory.py`
- **Step D2**: optional `src/personal_assistant/async_replicator.py` + tests (behind a flag)
- **Step D3**: `src/personal_assistant/deterministic_parser.py` + tests
- **Step D4**: integrate into `agent.py`:
  - add `_activation_boost` to results
  - reinforce on selection/execution
  - keep persistence off by default (or behind `ASYNC_REPLICATION=1`)

### Milestone E — Immutable prototype model (defer)
Only after the above is stable:
- introduce immutable prototype/version-chain types alongside existing KSG seeding
- migrate gradually

## CI / testing recommendations
- Ensure Playwright-backed tests have a defined contract:
  - either install browsers in CI (`playwright install chromium`)
  - or gate those tests behind an explicit flag
- Add a quick “smoke” test job (unit-only) and keep live tests opt-in.

## Branching & merge policy (recommended)

### Default strategy
- **Small, focused branches**: one feature/fix per branch where feasible.
- **Prefer fast-forward or rebase-based merges** to keep history readable.

### When to cherry-pick vs merge
- **Cherry-pick** when:
  - the change is **docs-only** (or otherwise low-risk and self-contained),
  - you want to avoid pulling in unrelated commits from a long-lived branch.
- **Merge (or rebase then merge)** when:
  - the branch is the canonical implementation branch for a feature,
  - it has passed the full expected test matrix.

### Minimum “ready to merge” checklist
- **Tests**: `poetry run pytest` passes in the expected environment (and CI, if present).
- **Playwright**: either CI installs browsers or Playwright tests are explicitly gated (no accidental hard-fails).
- **Repo hygiene**: no stray artifacts (e.g., accidental gitlinks/submodules without `.gitmodules`, local debug logs, bundles) unless explicitly intended and documented.
- **Docs**: update `docs/development-plan.md` (next steps) and `docs/session-notes.md` (what changed) when behavior or interfaces change.

### Archiving policy
- After a branch is merged to `main`, **delete the non-archived remote branch** and keep an `archived/...` copy if you want a preserved pointer.
- Keep “active” branches limited to the few currently under development.

## Risks / guardrails
- Avoid mixing activation directly into long-term similarity scoring; keep a separate `_activation_boost` and combine with a small multiplier.
- Avoid large refactors in `agent.py` until the CPMS/dataset/autofill milestones are working end-to-end.
- Prefer small commits: new module + tests first, then integration wiring.

