# Opus Next Steps (Claude Opus 4 Planning Document)

**Date**: 2026-01-14  
**Context**: Branch merge assessment and forward planning for osl-agent-prototype

## Summary of Completed Work

### Branch Merge (✅ Complete)
- Merged `cursor/branch-merge-assessment-c4d7` into `main`
- Identical branch `cursor/agent-local-vs-here-b8ca` also merged (same content)
- Both branches archived to `archived/cursor/*`

### Features Integrated
1. **CPMS Integration**: Form fingerprinting (`form_fingerprint.py`), pattern matching via `cpms_adapter.py`
2. **Documentation**: HANDOFF.md, development-plan.md updates, live testing docs
3. **KnowShowGo Bundle**: Binary bundle for knowledge graph
4. **Code Cleanup**: Major refactoring (70 files, net reduction in code)
5. **Pillow Dependency**: Added for vision tests

### Test Status Post-Merge
- **218 passed**, 37 skipped, 12 failed
- 3 failures: Playwright browser not installed (environment)
- 9 failures: Pre-existing issues from main branch (queue/scheduler edge cases)

## Recommended Next Steps (Priority Order)

### Phase 1: Infrastructure Stability (Immediate)
1. **Install Playwright browsers in CI/dev environments**
   ```bash
   poetry run playwright install --with-deps chromium
   ```
2. **Fix pre-existing test failures** in queue/scheduler (9 tests)
3. **Clean up repo hygiene**: Remove `knowshowgo` gitlink and `knowshowgo.bundle` from mainline OR formalize as submodule

### Phase 2: Salvage Components (Per salvage-osl-agent-prototype.txt)
Execute in order, each independently testable:

| Step | Component | File | Priority |
|------|-----------|------|----------|
| A | WorkingMemoryGraph | `working_memory.py` | HIGH (unanimous) |
| B | AsyncReplicator | `async_replicator.py` | HIGH (unanimous) |
| C | DeterministicParser | `deterministic_parser.py` | MEDIUM |
| D | Agent Integration | Modify `agent.py` | MEDIUM |
| E | ImmutablePrototype | Refactor `ksg.py` | LOW (defer) |

### Phase 3: CPMS Pattern Reuse (Per development-plan.md)
1. **Milestone A**: Reuse stored patterns in web flows
   - Agent helper: `web.get_dom(url)` → `ksg.find_best_cpms_pattern()` → fill
   - Fall back to CPMS detect + store exemplar when no strong match

2. **Milestone B**: Dataset learning (Credential/Identity/PaymentMethod)
   - Prefer same-domain datasets
   - Prompt only for missing required fields

3. **Milestone C**: Trial/adapt loop for selectors
   - On fill failure, try fallback selectors
   - Persist winning selector to pattern/exemplar

### Phase 4: Eliminate MOCK Components
Goal: Run debug daemon with real services, execute novel web operations

**Current MOCK dependencies:**
- `MockWebTools` → Replace with `PlaywrightWebTools` (USE_PLAYWRIGHT=1)
- `FakeOpenAIClient` → Replace with real OpenAI (USE_FAKE_OPENAI=0)
- In-memory `MemoryTools` → Replace with Arango backend

**Target state:**
- Debug daemon running with real OpenAI + Arango + Playwright
- Execute LinkedIn login flow using learned patterns
- Store/recall form patterns from KnowShowGo memory

## Environment Configuration for Live Mode

```bash
# .env.local for live testing
USE_FAKE_OPENAI=0
OPENAI_API_KEY=sk-...
USE_PLAYWRIGHT=1
USE_CPMS_FOR_FORMS=1
ARANGO_URL=https://...
ARANGO_DB=...
ARANGO_USER=...
ARANGO_PASSWORD=...
ARANGO_VERIFY=true
```

## Files to Monitor
- `docs/session-notes.md` - Running log, update after each session
- `docs/development-plan.md` - Canonical next steps
- `docs/salvage-osl-agent-prototype.txt` - Component porting guide
- `docs/gpt-plans.md` - GPT agent's roadmap

## Success Criteria for MVP
1. ✅ Core learning loop complete (Learn → Recall → Execute → Adapt → Generalize)
2. ⬜ Real OpenAI integration working (not mocked)
3. ⬜ Real Arango persistence working
4. ⬜ Playwright web automation working
5. ⬜ CPMS pattern detection and reuse working
6. ⬜ LinkedIn login flow succeeds with learned patterns
7. ⬜ Working memory activation boosting retrieval
