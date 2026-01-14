# Master Plan: OSL Agent Prototype MVP

**Date**: 2026-01-14  
**Synthesized from**: Opus, GPT, Salvage (Claude/GPT-5.2/Gemini consensus)

---

## Executive Summary

This document merges planning from three sources into a unified roadmap:
1. **Salvage Plan** (`salvage-osl-agent-prototype.txt`) - Component porting from deprecated knowshowgo
2. **GPT Plans** (`gpt-plans.md`) - Refactor roadmap and milestone planning
3. **Opus Next Steps** (`opus-next-steps.md`) - Implementation priorities and live mode setup

**Goal**: Get the agent running in live mode (no MOCK components) with real OpenAI, Arango, and Playwright, capable of learning form patterns and applying them in novel situations.

---

## Current State (Post-Merge)

| Component | Status |
|-----------|--------|
| Core Learning Loop | ✅ Complete (Learn/Recall/Execute/Adapt/Generalize) |
| CPMS Integration | ✅ Integrated (detect_form + pattern storage) |
| Form Fingerprinting | ✅ Complete |
| Pattern Reuse | ✅ Basic implementation |
| Tests | 218 passed, 12 failed (env issues + pre-existing) |
| Documentation | ✅ Updated |

---

## Unified Implementation Roadmap

### Week 1: Foundation & Cleanup

#### Day 1-2: Environment Setup
- [ ] Install Playwright browsers: `poetry run playwright install --with-deps chromium`
- [ ] Fix 9 pre-existing test failures (queue/scheduler)
- [ ] Validate `.env.local` configuration for live services

#### Day 3-4: Repo Hygiene (per GPT recommendation)
- [ ] Remove `knowshowgo` gitlink from repo (or formalize as submodule)
- [ ] Remove `knowshowgo.bundle` artifact
- [ ] Update `.gitignore` as needed
- [ ] Consolidate overlapping docs (mark older plans as historical)

#### Day 5: Documentation Sync
- [ ] Update `README.md` with current setup instructions
- [ ] Mark `core-learning-loop-plan.md` as COMPLETE/historical
- [ ] Ensure `development-plan.md` is canonical next-steps

### Week 2: Salvage Components (Unanimous Priority)

#### WorkingMemoryGraph (Step A) - HIGH PRIORITY
```
src/personal_assistant/working_memory.py
tests/test_working_memory.py
```
- NetworkX-backed activation layer
- Reinforcement on access (Hebbian learning)
- Session-scoped, separate from semantic memory
- **Commit**: "feat: add WorkingMemoryGraph for activation tracking"

#### AsyncReplicator (Step B) - HIGH PRIORITY
```
src/personal_assistant/async_replicator.py
tests/test_async_replicator.py
```
- Queue-based background persistence
- Clean start/stop lifecycle
- Optional (behind `ASYNC_REPLICATION=1` flag)
- **Commit**: "feat: add AsyncReplicator for background persistence"

#### DeterministicParser (Step C) - MEDIUM PRIORITY
```
src/personal_assistant/deterministic_parser.py
tests/test_deterministic_parser.py
```
- Rule-based task/event classification
- Skip LLM for obvious intents
- Behind `SKIP_LLM_FOR_OBVIOUS_INTENTS=1` flag
- **Commit**: "feat: add deterministic parser for offline classification"

### Week 3: Agent Integration

#### Integrate WorkingMemory (Step D)
- Add `WorkingMemoryGraph` to `agent.py.__init__`
- Implement `_boost_by_activation()` for search results
- Implement `_reinforce_selection()` on concept use
- **Commit**: "feat: integrate working memory for retrieval boosting"

#### Wire AsyncReplicator (Step E) - Optional
- Add ASYNC_REPLICATION env flag check
- Start replicator in service startup
- Connect working memory to persistence
- **Commit**: "feat: enable async replication for activation persistence"

### Week 4: Live Mode & CPMS Flow

#### Eliminate MOCK Components
| Mock | Replacement | Flag |
|------|-------------|------|
| `MockWebTools` | `PlaywrightWebTools` | `USE_PLAYWRIGHT=1` |
| `FakeOpenAIClient` | Real OpenAI | `USE_FAKE_OPENAI=0` |
| In-memory `MemoryTools` | Arango backend | `ARANGO_URL` set |

#### CPMS Pattern Reuse Flow (Milestone A)
1. `web.get_dom(url)` → get HTML
2. `ksg.find_best_cpms_pattern(url, html)` → try reuse
3. If weak match: `cpms.detect_form` → store exemplar
4. Fill form with stored/detected selectors

#### Dataset Selection (Milestone B)
- Prefer same-domain Credential/Identity/PaymentMethod
- Prompt only for missing required fields
- Store values immediately after user provides

### Week 5: Trial/Adapt & Validation

#### Selector Adaptation (Milestone C)
- On fill failure: try fallback selectors
- Persist winning selector to pattern
- Record run outcomes for weighting

#### End-to-End Validation
- Run debug daemon with all real services
- Execute LinkedIn login flow with learned patterns
- Verify pattern recall and reuse
- Test novel form detection and learning

---

## Environment Variables Summary

```bash
# Core Services
USE_FAKE_OPENAI=0
OPENAI_API_KEY=sk-...
ARANGO_URL=https://...
ARANGO_DB=osl-agent
ARANGO_USER=...
ARANGO_PASSWORD=...
ARANGO_VERIFY=true

# Features
USE_PLAYWRIGHT=1
USE_CPMS_FOR_FORMS=1
KSG_PATTERN_REUSE_MIN_SCORE=2.0

# New (Salvage Components)
WORKING_MEMORY_REINFORCE_DELTA=1.0
WORKING_MEMORY_MAX_WEIGHT=100.0
ASYNC_REPLICATION=0
SKIP_LLM_FOR_OBVIOUS_INTENTS=0
```

---

## Architecture After Implementation

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT LOOP (agent.py)                         │
│  1. User request → Deterministic parse (obvious?) → skip LLM?       │
│  2. Memory search + activation boost                                 │
│  3. LLM planning (if needed)                                        │
│  4. Plan execution                                                   │
│  5. Reinforce working memory on selection                           │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                         │
         ▼                    ▼                         ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│ WorkingMemory   │  │  Semantic Memory    │  │  AsyncReplicator    │
│ (session-scope) │  │  (Arango/Chroma)    │  │  (optional persist) │
│ - link/access   │  │  - search/upsert    │  │  - queue + worker   │
│ - boost scores  │  │  - KSG operations   │  │  - flush semantics  │
└─────────────────┘  └─────────────────────┘  └─────────────────────┘
```

---

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Tests Passing | >95% | 218/267 (81%) |
| MOCK Components | 0 in live mode | 3 (Web, OpenAI, Memory) |
| Pattern Reuse Rate | >50% for known forms | Not measured |
| LinkedIn Login Success | 100% with credentials | Not tested |
| Memory Recall Accuracy | >80% for procedures | ~90% (tested) |

---

## Risk Mitigation

1. **Activation pollution**: Keep working memory separate from semantic memory; combine scores with small multiplier only
2. **Large refactors**: Avoid until CPMS/dataset/autofill milestones working end-to-end
3. **Breaking changes**: Prefer small commits: new module + tests first, then integration wiring
4. **CI failures**: Gate Playwright tests behind env flag; add quick smoke test job

---

## Files Reference

| File | Purpose |
|------|---------|
| `docs/MASTER-PLAN.md` | This file - unified roadmap |
| `docs/opus-next-steps.md` | Opus agent's priorities |
| `docs/gpt-plans.md` | GPT agent's roadmap |
| `docs/salvage-osl-agent-prototype.txt` | Component porting guide |
| `docs/development-plan.md` | Canonical milestone checklist |
| `docs/session-notes.md` | Running session log |

---

## Next Actions (Immediate)

1. **Tag current version**: `v0.5.0-cpms-integration`
2. **Archive remaining branches**: `codex/complete-objectives-in-existing-code`, `cursor/knowshowgo-repo-push-c83c`
3. **Start Salvage Step A**: Create `working_memory.py` with tests
4. **Validate live mode**: Test with real OpenAI + Arango + Playwright

---

*This plan will be updated as milestones are completed.*
