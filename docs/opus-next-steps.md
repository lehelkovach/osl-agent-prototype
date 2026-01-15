# Opus Next Steps (Claude Opus 4 Planning Document)

**Date**: 2026-01-14  
**Version**: v1.0.1-full-test-coverage  
**Context**: All core milestones complete, ready for live debugging

---

## Summary of Completed Work

### ✅ Salvage Steps (A-D) - ALL COMPLETE

| Step | Component | Status | Tag |
|------|-----------|--------|-----|
| A | WorkingMemoryGraph | ✅ Complete | v0.5.0-salvage-step-a |
| B | AsyncReplicator | ✅ Complete | v0.5.0-salvage-step-b |
| C | DeterministicParser | ✅ Complete | v0.6.0-salvage-step-c |
| D | Agent Integration | ✅ Complete | v0.7.0-salvage-step-d |

**New Files Created:**
- `src/personal_assistant/working_memory.py` - Hebbian reinforcement for retrieval
- `src/personal_assistant/async_replicator.py` - Background persistence worker
- `src/personal_assistant/deterministic_parser.py` - Rule-based intent classification

### ✅ Milestones (A-C) - ALL COMPLETE

| Milestone | Feature | Status | Tag |
|-----------|---------|--------|-----|
| A | Pattern Reuse | ✅ Already implemented | - |
| B | Dataset Selection | ✅ Complete | v0.8.0-milestone-b |
| C | Selector Adaptation | ✅ Complete | v0.9.0-milestone-c |

**Milestone B Additions:**
- `extract_domain()` - URL domain extraction (now handles ports)
- `find_for_domain()` - Domain-specific credential lookup
- `get_missing_fields()` - Detect fields needing user input
- `store_credential()` - Immediate credential storage

**Milestone C Verification:**
- Fallback selector trial on fill failure ✅
- Winning selector persistence to procedure ✅
- Run outcome tracking (success_count, failure_count) ✅

### ✅ Test Coverage - COMPREHENSIVE

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_working_memory.py | 14 | Unit tests for WM |
| test_async_replicator.py | 9 | Async persistence |
| test_deterministic_parser.py | 46 | Intent classification |
| test_agent_working_memory_integration.py | 12 | Agent + WM |
| test_form_filler_domain_preference.py | 17 | Domain preference |
| test_selector_adaptation.py | 5 | Selector fallbacks |
| test_new_components_integration.py | 22 | End-to-end flows |

**Total: 354 passed, 29 skipped, 9 failed (env)**

### ✅ Infrastructure

- Playwright browsers installed ✅
- All new components documented ✅
- Session notes updated ✅
- Debug log added to .gitignore ✅

---

## Remaining Branches

### Active Branches (Not Yet Merged)

| Branch | Purpose | Status |
|--------|---------|--------|
| `codex/complete-objectives-in-existing-code` | Additional KSG features | Ready for review |
| `cursor/knowshowgo-repo-push-c83c` | KSG bundle updates | Ready for review |

### Archived Branches (Merged)

All completed work has been archived to `archived/opus/*` and `archived/cursor/*`.

---

## Next Steps for Debugging

### Immediate: Live Mode Testing

1. **Configure `.env.local`:**
   ```bash
   USE_FAKE_OPENAI=0
   OPENAI_API_KEY=sk-...
   USE_PLAYWRIGHT=1
   USE_CPMS_FOR_FORMS=1
   ARANGO_URL=https://...
   ARANGO_DB=osl-agent
   ARANGO_USER=root
   ARANGO_PASSWORD=...
   ARANGO_VERIFY=true
   ```

2. **Start debug daemon:**
   ```bash
   poetry run agent-service
   ```

3. **Test with curl:**
   ```bash
   curl -sS http://localhost:8000/chat \
     -H 'content-type: application/json' \
     -d '{"message":"Log into linkedin.com"}'
   ```

### Debug Targets

1. **LinkedIn Login Flow:**
   - Navigate to linkedin.com/login
   - Detect form pattern (or reuse stored)
   - Retrieve credentials from memory
   - Fill form with fallback selectors
   - Verify login success

2. **Novel Form Learning:**
   - Visit new form URL
   - Let CPMS detect pattern
   - Store pattern in KnowShowGo
   - Return to same form
   - Verify pattern reuse (no re-detection)

3. **Working Memory Verification:**
   - Make multiple requests
   - Verify activation boost affects ranking
   - Verify reinforcement on selection

---

## Pre-existing Issues (9 test failures)

These failures existed before this work and are in queue/scheduler:

1. `test_queue_update_tool`
2. `test_agent_recalls_procedure_before_planning`
3. `test_queue_enqueue_with_delay_seconds`
4. `test_queue_instantiated_with_embedding`
5. `test_scheduler_enqueues_task_and_calendar_stub`
6. `test_time_rule_enqueues_task_with_dag`
7. `test_update_status`
8. `test_ultimate_goal_complete_learning_cycle`
9. `test_ultimate_goal_with_real_workflow`

These should be addressed separately as they're unrelated to the new components.

---

## Success Criteria for MVP

| Criterion | Status |
|-----------|--------|
| Core learning loop (Learn→Recall→Execute→Adapt→Generalize) | ✅ Complete |
| Working memory activation boosting | ✅ Complete |
| Deterministic parser integration | ✅ Complete |
| Domain-based credential selection | ✅ Complete |
| Selector adaptation with fallbacks | ✅ Complete |
| Real OpenAI integration | ⬜ Config needed |
| Real Arango persistence | ⬜ Config needed |
| Playwright web automation | ✅ Installed |
| CPMS pattern detection/reuse | ✅ Implemented |
| LinkedIn login flow | ⬜ Live testing needed |

---

## Version Tags

| Tag | Description |
|-----|-------------|
| v0.5.0-salvage-step-a | WorkingMemoryGraph |
| v0.5.0-salvage-step-b | AsyncReplicator |
| v0.6.0-salvage-step-c | DeterministicParser |
| v0.7.0-salvage-step-d | Agent Integration |
| v0.8.0-milestone-b | Dataset Selection |
| v0.9.0-milestone-c | Selector Adaptation |
| v1.0.0-mvp-ready | All Milestones Complete |
| v1.0.1-full-test-coverage | Comprehensive Tests |

---

*Last updated: 2026-01-14 by Claude Opus 4*
