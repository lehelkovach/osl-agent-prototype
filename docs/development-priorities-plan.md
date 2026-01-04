# Development Priorities and Integration Plan

## Analysis: Current State & Goals Alignment

### Current Progress Summary

**Completed (60% of Core Loop):**
- ✅ **Module 1: Learn** - Agent learns procedures from chat, stores in KnowShowGo
- ✅ **Module 2: Recall** - Agent recalls procedures via fuzzy matching (vector embeddings)
- ✅ **Module 5: Auto-Generalize** - Agent auto-generalizes working procedures (via vector embeddings)

**Pending (40% of Core Loop):**
- ⏳ **Module 3: Execute** - Agent executes recalled procedures (DAG execution)
  - Status: DAGExecutor exists, needs integration tests
- ⏳ **Module 4: Adapt** - Agent adapts procedures when execution fails
  - Status: Needs implementation

**External Integration:**
- ⏳ **CPMS Integration** - Ready to integrate
  - Status: Basic adapter exists, integration points defined
  - Can enhance Module 4 (Adapt) with pattern matching

### Goal Alignment Analysis

**Primary Goal:** Working prototype for agent's learning cycle (Learn → Recall → Execute → Adapt)

**Development Methods:**
- ✅ TDD (Test-Driven Development)
- ✅ Modular development (one module at a time)
- ✅ Dependency-based ordering
- ✅ Incremental enhancement (only add features as needed)

**Key Insights:**
1. **Core loop completion is priority** - Execute + Adapt are required for full cycle
2. **CPMS enhances Adapt** - Pattern matching helps with procedure adaptation
3. **Dependency order matters** - Execute must work before Adapt
4. **Incremental integration** - CPMS can be integrated as part of Module 4

---

## Recommended Development Plan

### Phase 1: Complete Core Learning Loop (PRIORITY 1)

**Goal:** Get end-to-end learning cycle working without CPMS first

#### Step 1.1: Module 3 - Execute (2-3 hours)
**Why First:** Required prerequisite for Adapt

**Tasks:**
1. Create `tests/test_agent_execute_recalled_procedure.py`
   - Test: Store procedure → Recall → Execute DAG → Verify execution
   - Test: DAG loads correctly from concept
   - Test: Tool commands execute in order
   - Test: Error handling (invalid concept, missing steps)

2. Fix any DAG executor issues discovered in tests
   - Ensure enqueue_fn signature matches TaskQueueManager
   - Verify DAG structure loading from concept props
   - Test nested DAG execution (if needed)

3. Integration test with agent
   - End-to-end: User request → Recall → Execute → Verify

**Acceptance Criteria:**
- ✅ All tests pass
- ✅ DAG execution works end-to-end
- ✅ Tools execute in correct order
- ✅ Errors handled gracefully

**Dependencies:** None (DAGExecutor exists)

---

#### Step 1.2: Module 4 - Adapt (4-6 hours)
**Why Second:** Depends on Execute working

**Tasks:**
1. Create `tests/test_agent_adapt_procedure.py`
   - Test: Execution fails → Agent detects failure
   - Test: Agent adapts procedure (updates URL, selectors, params)
   - Test: Agent stores adapted version
   - Test: Adapted version linked to original (via `previous_version_uuid`)

2. Implement adaptation logic in agent
   - Detect execution failures
   - Extract failure context (which step failed, error message)
   - Adapt procedure parameters (URL, selectors, etc.)
   - Store adapted version via `ksg.create_concept()` with `previous_version_uuid`

3. Integration test
   - End-to-end: Execute fails → Adapt → Store → Re-execute → Verify

**Acceptance Criteria:**
- ✅ All tests pass
- ✅ Agent detects execution failures
- ✅ Agent creates adapted procedures
- ✅ Adapted procedures work correctly
- ✅ Version linking works

**Dependencies:** Module 3 (Execute) must work

---

### Phase 2: CPMS Integration for Enhanced Adaptation (PRIORITY 2)

**Goal:** Enhance Module 4 with CPMS pattern matching for better adaptation

#### Step 2.1: CPMS Form Detection Integration (3-4 hours)
**Why Now:** Enhances Adapt module with pattern matching

**Tasks:**
1. Review CPMS API (github.com/lehelkovach/cpms)
   - Understand `match_pattern` API endpoint
   - Document request/response format
   - Test with real CPMS instance

2. Enhance `CPMSAdapter.detect_form_pattern()`
   - Implement full CPMS API integration
   - Build observations from HTML + screenshot
   - Parse CPMS pattern responses
   - Keep fallback for when CPMS unavailable

3. Create `tests/test_cpms_form_detection.py`
   - Test: CPMS pattern detection
   - Test: Fallback when CPMS unavailable
   - Test: Various form types (login, billing, etc.)
   - Integration test with real CPMS (gated by env)

**Acceptance Criteria:**
- ✅ CPMS API integration working
- ✅ Pattern detection returns structured data
- ✅ Fallback works when CPMS unavailable
- ✅ Tests pass

**Dependencies:** CPMS service ready (user confirmed)

---

#### Step 2.2: CPMS-Enhanced Adaptation (4-5 hours)
**Why Second:** Builds on form detection

**Tasks:**
1. Integrate CPMS into adaptation logic
   - When form filling fails, use CPMS to detect form pattern
   - Match stored patterns to new forms
   - Extract selectors from CPMS patterns
   - Update procedure with new selectors

2. Store CPMS patterns in KnowShowGo
   - Use existing `ksg.store_cpms_pattern()`
   - Link patterns to procedures
   - Enable pattern reuse

3. Create `tests/test_agent_cpms_adaptation.py`
   - Test: Form failure → CPMS detection → Pattern matching → Adaptation
   - Test: Pattern storage and retrieval
   - Test: Pattern reuse across similar forms

**Acceptance Criteria:**
- ✅ CPMS enhances adaptation accuracy
- ✅ Patterns stored and reused
- ✅ Adaptation works with CPMS patterns
- ✅ Tests pass

**Dependencies:** Step 2.1 (CPMS form detection)

---

### Phase 3: End-to-End Validation (PRIORITY 3)

**Goal:** Validate complete learning cycle works end-to-end

#### Step 3.1: Full Cycle Integration Test (2-3 hours)

**Tasks:**
1. Create `tests/test_agent_full_learning_cycle.py`
   - Test: Learn → Recall → Execute → Adapt → Generalize
   - Test: Multiple cycles (learn multiple procedures, generalize)
   - Test: With and without CPMS

2. Create demo scenario
   - User teaches login procedure
   - User requests similar login
   - Agent recalls, executes, adapts if needed
   - Agent generalizes after multiple successes

**Acceptance Criteria:**
- ✅ Full cycle works end-to-end
- ✅ All modules integrated correctly
- ✅ CPMS integration enhances (but doesn't break) core loop

**Dependencies:** Phase 1 & 2 complete

---

## Detailed Task Breakdown

### Module 3: Execute (Step 1.1) - Detailed Tasks

**File:** `tests/test_agent_execute_recalled_procedure.py`

**Test Cases:**
1. `test_agent_executes_stored_procedure()`
   - Store procedure with steps
   - User requests execution
   - Verify DAG loads and executes
   - Verify tools called in order

2. `test_dag_execution_loads_from_concept()`
   - Verify DAG structure loaded from concept props
   - Verify steps extracted correctly

3. `test_dag_execution_handles_errors()`
   - Invalid concept UUID
   - Missing steps
   - Tool execution errors

**Implementation Notes:**
- DAGExecutor exists at `src/personal_assistant/dag_executor.py`
- Agent has `dag.execute` tool handler
- Need to fix `enqueue_fn` signature issue (TaskQueueManager.enqueue expects Node, not dict)
- Verify DAG structure format in concept props

---

### Module 4: Adapt (Step 1.2) - Detailed Tasks

**File:** `tests/test_agent_adapt_procedure.py`

**Test Cases:**
1. `test_agent_adapts_on_execution_failure()`
   - Store procedure
   - Execute fails (mock failure)
   - Agent detects failure
   - Agent creates adapted version

2. `test_adaptation_updates_parameters()`
   - Verify URL updated
   - Verify selectors updated
   - Verify other params updated

3. `test_adapted_procedure_linked_to_original()`
   - Verify `previous_version_uuid` set
   - Verify `next_version` edge created

4. `test_adapted_procedure_works()`
   - Execute adapted procedure
   - Verify it succeeds

**Implementation Notes:**
- Add `_adapt_procedure()` method to agent
- Detect failures in `_execute_plan()` or `_persist_procedure_run()`
- Use `ksg.create_concept()` with `previous_version_uuid` parameter
- Adaptation logic: Extract error context, update parameters, create new concept

---

### CPMS Integration (Step 2.1) - Detailed Tasks

**File:** `src/personal_assistant/cpms_adapter.py`

**Tasks:**
1. Review CPMS API documentation
2. Implement `_build_observation()` method (if not complete)
3. Implement `_call_cpms_api()` method
4. Enhance `detect_form_pattern()` to use CPMS API
5. Test with real CPMS instance

**File:** `tests/test_cpms_form_detection.py`

**Test Cases:**
1. `test_cpms_detects_login_form()`
2. `test_cpms_fallback_when_unavailable()`
3. `test_cpms_various_form_types()`
4. `test_cpms_pattern_storage()` (integration with KnowShowGo)

---

### CPMS-Enhanced Adaptation (Step 2.2) - Detailed Tasks

**File:** `src/personal_assistant/agent.py`

**Tasks:**
1. Integrate CPMS into `_adapt_procedure()`
   - Call `cpms.detect_form_pattern()` when form failure
   - Extract selectors from CPMS pattern
   - Update procedure with new selectors

2. Store CPMS patterns
   - Call `ksg.store_cpms_pattern()` after detection
   - Link pattern to procedure concept

**File:** `tests/test_agent_cpms_adaptation.py`

**Test Cases:**
1. `test_cpms_enhances_adaptation()`
2. `test_pattern_storage_and_retrieval()`
3. `test_pattern_reuse_across_forms()`

---

## Timeline Estimate

**Phase 1: Core Loop (6-9 hours)**
- Module 3: Execute - 2-3 hours
- Module 4: Adapt - 4-6 hours

**Phase 2: CPMS Integration (7-9 hours)**
- CPMS Form Detection - 3-4 hours
- CPMS-Enhanced Adaptation - 4-5 hours

**Phase 3: Validation (2-3 hours)**
- Full Cycle Test - 2-3 hours

**Total: 15-21 hours of development**

---

## Risk Assessment

**Low Risk:**
- Module 3 (Execute) - DAGExecutor exists, mostly integration work
- CPMS Form Detection - Adapter structure exists, API ready

**Medium Risk:**
- Module 4 (Adapt) - New logic, needs careful design
- CPMS-Enhanced Adaptation - Integration complexity

**Mitigation:**
- Use TDD approach (tests first)
- Incremental implementation
- Test each module independently before integration

---

## Success Criteria

**Phase 1 Complete When:**
- ✅ Module 3 tests pass
- ✅ Module 4 tests pass
- ✅ End-to-end learning cycle works (Learn → Recall → Execute → Adapt)
- ✅ All core loop modules have tests

**Phase 2 Complete When:**
- ✅ CPMS form detection works
- ✅ CPMS enhances adaptation
- ✅ Patterns stored and reused
- ✅ Tests pass with and without CPMS

**Project Complete When:**
- ✅ Full learning cycle validated
- ✅ CPMS integration enhances (but doesn't break) core loop
- ✅ All tests pass
- ✅ Demo scenario works

---

## Next Steps

1. **Start with Module 3 (Execute)**
   - Create test file
   - Write first test case
   - Fix any issues discovered
   - Complete all test cases

2. **Then Module 4 (Adapt)**
   - Create test file
   - Implement adaptation logic
   - Complete all test cases

3. **Then CPMS Integration**
   - Review CPMS API
   - Enhance form detection
   - Integrate into adaptation

4. **Finally Validation**
   - Create full cycle test
   - Validate end-to-end
   - Create demo

---

## Notes

- **Priority Order:** Complete core loop first, then enhance with CPMS
- **TDD Approach:** Write tests first, then implement
- **Incremental:** One module at a time, test before moving on
- **Dependencies:** Respect dependency order (Execute before Adapt)
- **CPMS Enhancement:** CPMS enhances but doesn't block core loop completion

