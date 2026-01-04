# Parallel Work Plan (While Waiting for CPMS)

## Goal: Test and Enhance KnowShowGo + ArangoDB + OpenAI Integration

### Priority 1: End-to-End Testing with Real Systems

#### Task 1.1: Test Recursive Concept Creation with ArangoDB
**File**: `tests/test_knowshowgo_recursive_arango.py` (new)

**What to Test**:
- Create a concept with nested sub-procedures (recursive structure)
- Store in ArangoDB
- Verify nested concepts are created and linked correctly
- Test with real OpenAI embeddings

**Test Scenario**:
```python
# Create "Login to X.com" concept with nested steps:
# - Step 1: Navigate to X.com (sub-procedure concept)
# - Step 2: Fill credentials (sub-procedure concept)  
# - Step 3: Submit form (sub-procedure concept)
# Each sub-procedure is itself a concept that can be reused
```

**Status**: Not started

---

#### Task 1.2: Test DAG Execution with Real Concepts
**File**: `tests/test_dag_executor_arango.py` (new)

**What to Test**:
- Load DAG from ArangoDB-stored concept
- Execute DAG with dependency resolution
- Test nested DAG execution (procedure calling sub-procedure)
- Test guard evaluation
- Verify tool commands are enqueued correctly

**Test Scenario**:
```python
# 1. Create concept with DAG structure in ArangoDB
# 2. Load DAG via DAGExecutor
# 3. Execute and verify:
#    - Bottom nodes execute first
#    - Dependencies respected
#    - Guards evaluated
#    - Commands enqueued
```

**Status**: Not started

---

#### Task 1.3: Test Full Flow: User Instruction → Concept Creation → Execution
**File**: `tests/test_agent_concept_learning_flow.py` (new)

**What to Test**:
- User says: "Log into X.com with my default credentials"
- Agent searches KnowShowGo (should find nothing initially)
- Agent asks user for instructions
- User provides steps
- LLM creates concept with DAG structure
- Agent executes the DAG
- Future similar requests reuse the concept

**Test Scenario**:
```python
# 1. First request: "Log into X.com" → asks user
# 2. User provides: "Go to X.com, fill email/password, click login"
# 3. Agent creates concept with DAG
# 4. Agent executes DAG
# 5. Second request: "Log into Y.com" → finds similar concept, adapts
```

**Status**: Not started

---

### Priority 2: Enhance DAG Execution Engine

#### Task 2.1: Improve Dependency Resolution
**File**: `src/personal_assistant/dag_executor.py`

**Current Issue**: Dependency tracking is simplified - doesn't properly track when dependent nodes become ready after prerequisites complete.

**Enhancement**:
- Track which nodes are waiting on which dependencies
- When a node completes, check if dependent nodes are now ready
- Proper topological sort execution
- Handle cycles (shouldn't happen but good to detect)

**Status**: Needs improvement

---

#### Task 2.2: Enhanced Guard/Rule Evaluation
**File**: `src/personal_assistant/dag_executor.py`

**Current Issue**: Guard evaluation is very simple (just boolean/string checks).

**Enhancement**:
- Support conditional expressions (e.g., "if url contains 'login'")
- Support context-based guards (check execution context)
- Support LLM-based guard evaluation (ask LLM if condition is met)
- Support guard chaining (AND/OR logic)

**Status**: Needs enhancement

---

#### Task 2.3: Better Error Handling in DAG Execution
**File**: `src/personal_assistant/dag_executor.py`

**Enhancement**:
- Handle node execution failures gracefully
- Support `on_fail` handlers in nodes
- Retry logic for failed nodes
- Rollback/compensation actions
- Better error reporting

**Status**: Needs enhancement

---

### Priority 3: Concept Search and Reuse

#### Task 3.1: Test Concept Search Before Asking User
**File**: `tests/test_agent_concept_search.py` (new)

**What to Test**:
- Agent searches KnowShowGo when user requests task
- If similar concept found, adapts it instead of asking user
- Tests with various similarity thresholds
- Tests with ArangoDB-backed memory

**Test Scenarios**:
```python
# 1. "Log into X.com" → finds "Log into Y.com" concept → adapts
# 2. "Fill out billing form" → finds "Fill out payment form" → adapts
# 3. "New task with no similar concept" → asks user
```

**Status**: Not started

---

#### Task 3.2: Test Concept Generalization
**File**: `tests/test_knowshowgo_generalization.py` (new)

**What to Test**:
- Create multiple exemplar concepts (e.g., "Log into X", "Log into Y")
- Generalize them into parent concept ("Log into site")
- Verify taxonomy hierarchy
- Test that new similar concepts link to generalized parent

**Status**: Not started

---

### Priority 4: Integration with Real OpenAI

#### Task 4.1: Test LLM Concept Creation with Real OpenAI
**File**: `tests/test_agent_llm_concept_creation.py` (new)

**What to Test**:
- Use real OpenAI (not fake) to create concepts
- Test that LLM generates proper DAG structures
- Test recursive concept creation via LLM
- Verify embeddings are generated correctly

**Requirements**:
- `OPENAI_API_KEY` set
- `USE_FAKE_OPENAI=0`
- Gated test (skip if no key)

**Status**: Not started

---

#### Task 4.2: Test LLM Concept Adaptation
**File**: `tests/test_agent_llm_concept_adaptation.py` (new)

**What to Test**:
- LLM finds similar concept
- LLM adapts it for new use case
- LLM creates new concept variant
- Links to original concept

**Status**: Not started

---

### Priority 5: Vault Integration

#### Task 5.1: Test Vault Credential Lookup
**File**: `tests/test_vault_credential_lookup.py` (new)

**What to Test**:
- Store credentials in vault (as Credential/Identity concepts)
- Query vault by URL or concept UUID
- Retrieve credentials for form filling
- Test with ArangoDB persistence

**Status**: Not started

---

#### Task 5.2: Test Credential Association with Concepts
**File**: `tests/test_credential_concept_association.py` (new)

**What to Test**:
- Associate credentials with login concepts
- When executing login procedure, auto-retrieve credentials
- Test credential matching by URL/domain

**Status**: Not started

---

### Priority 6: ArangoDB-Specific Enhancements

#### Task 6.1: Test Edge Queries in ArangoDB
**File**: `tests/test_arango_edge_queries.py` (new)

**What to Test**:
- Query concepts by prototype (via `instantiates` edges)
- Query child concepts (via `has_step`, `has_child` edges)
- Query generalized concepts (via `generalized_by` edges)
- Query patterns (via `has_pattern` edges)

**Status**: Not started

---

#### Task 6.2: Test ArangoDB Performance with Large Concept Graphs
**File**: `tests/test_arango_performance.py` (new)

**What to Test**:
- Create many concepts (100+)
- Test search performance
- Test edge traversal performance
- Test embedding similarity search performance

**Status**: Not started

---

## Quick Wins (Can Start Immediately)

### 1. Add Test for Recursive Concept Creation (Mock)
**File**: `tests/test_knowshowgo_recursive.py` (new)
- Test `create_concept_recursive()` with nested structures
- Verify child concepts are created
- Verify edges are linked correctly
- **Time**: ~30 minutes

### 2. Add Test for Concept Generalization (Mock)
**File**: `tests/test_knowshowgo_generalization.py` (new)
- Test `generalize_concepts()` method
- Verify parent-child relationships
- Verify taxonomy structure
- **Time**: ~30 minutes

### 3. Improve DAG Executor Dependency Tracking
**File**: `src/personal_assistant/dag_executor.py`
- Fix dependency resolution to track when nodes become ready
- Add proper topological sort
- **Time**: ~1-2 hours

### 4. Add Integration Test for Concept Search
**File**: `tests/test_agent_concept_search_integration.py` (new)
- Test agent searches concepts before asking user
- Test with mock memory first, then ArangoDB
- **Time**: ~1 hour

---

## Recommended Order

1. **Start with Quick Wins** (Tasks 1-4 above) - builds confidence
2. **Test Recursive Concept Creation** (Task 1.1) - core functionality
3. **Test DAG Execution** (Task 1.2) - execution engine
4. **Test Full Flow** (Task 1.3) - end-to-end validation
5. **Enhance DAG Engine** (Tasks 2.1-2.3) - improve robustness
6. **Test with Real OpenAI** (Tasks 4.1-4.2) - production readiness
7. **ArangoDB Performance** (Task 6.2) - scalability

---

## Files to Create/Modify

### New Test Files:
- `tests/test_knowshowgo_recursive.py`
- `tests/test_knowshowgo_recursive_arango.py`
- `tests/test_knowshowgo_generalization.py`
- `tests/test_dag_executor_arango.py`
- `tests/test_agent_concept_learning_flow.py`
- `tests/test_agent_concept_search.py`
- `tests/test_agent_llm_concept_creation.py`
- `tests/test_vault_credential_lookup.py`
- `tests/test_arango_edge_queries.py`

### Files to Enhance:
- `src/personal_assistant/dag_executor.py` - dependency tracking, guards, error handling
- `src/personal_assistant/knowshowgo.py` - may need edge query helpers for ArangoDB

---

## Success Criteria

- [ ] Recursive concept creation works with ArangoDB
- [ ] DAG execution works with real concepts
- [ ] Full flow: user instruction → concept creation → execution
- [ ] Concept search finds similar concepts before asking user
- [ ] Concept generalization creates taxonomy hierarchies
- [ ] Vault credential lookup works end-to-end
- [ ] All tests pass with real ArangoDB + OpenAI

