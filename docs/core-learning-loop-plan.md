# Core Learning Loop - Focused Implementation Plan

## Goal

Get the agent prototype to:
1. **Learn** procedures from chat messages (user teaches agent)
2. **Store** procedures in KnowShowGo semantic memory (as concepts with embeddings)
3. **Recall** procedures when similar tasks requested (fuzzy matching via embeddings)
4. **Execute** recalled procedures (DAG execution)
5. **Adapt** procedures when execution fails (modify and store new version)

## Core Flow

```
User Chat: "Log into X.com with email/password, then click submit"
  ↓
LLM interprets → Searches KnowShowGo for similar procedures
  ↓
No match found → LLM creates plan to store procedure
  ↓
Agent stores procedure as concept in KnowShowGo (with embedding)
  ↓
[Later...]
User Chat: "Log into Y.com"  
  ↓
LLM searches KnowShowGo → Finds similar "Log into X.com" procedure
  ↓
LLM adapts procedure for Y.com → Executes
  ↓
If execution fails → LLM adapts further → Stores adapted version
  ↓
If execution succeeds → Agent checks if multiple similar procedures exist
  ↓
If 2+ similar procedures work → Agent auto-generalizes:
  - Merges/averages embeddings
  - Extracts common steps
  - Creates generalized pattern
  - Links exemplars to generalized pattern
```

## Minimal Implementation (TDD)

### Module 1: Store Procedure from Chat ✅ (Mostly Done)

**Goal**: Agent can store learned procedures in KnowShowGo

**Test**: `tests/test_agent_learn_procedure.py`

```python
def test_agent_stores_procedure_from_chat():
    """User teaches procedure, agent stores it in KnowShowGo"""
    # User message
    user_msg = "Remember: to log into a site, first go to the login URL, "
                "then fill the email and password fields, then click submit"
    
    # LLM should create plan with ksg.create_concept
    # Agent should execute plan and store concept
    
    # Verify concept stored in KnowShowGo
    # Verify concept has embedding
    # Verify concept has procedure steps
```

**Status**: 
- ✅ ksg.create_concept tool exists
- ✅ Agent can execute ksg.create_concept
- ✅ Test: User chat → LLM creates concept → Agent stores it
- ✅ Verify embedding generated correctly
- ✅ Verify procedure steps stored correctly

---

### Module 2: Recall Procedure from Chat ✅ (Mostly Done)

**Goal**: Agent searches KnowShowGo when user requests task

**Test**: `tests/test_agent_recall_procedure.py`

```python
def test_agent_recalls_stored_procedure():
    """Agent recalls stored procedure when user requests similar task"""
    # Store a procedure first
    stored_proc = store_procedure("Log into X.com", steps=[...])
    
    # User requests similar task
    user_msg = "Log into Y.com"
    
    # Agent should:
    # 1. Search KnowShowGo (ksg.search_concepts)
    # 2. Find similar procedure
    # 3. Include in LLM context
    # 4. LLM should reuse/adapt it
    
    # Verify search was performed
    # Verify procedure found
    # Verify LLM receives it in context
```

**Status**:
- ✅ Agent searches KnowShowGo (line 119 in agent.py)
- ✅ Concept matches added to memory_results
- ✅ Test: Stored procedure → User request → Agent finds it
- ✅ Verify fuzzy matching works (similar embeddings)
- ✅ Verify LLM receives procedure in context

---

### Module 3: Execute Recalled Procedure ⚠️ (Needs Integration)

**Goal**: Agent can execute a recalled procedure (DAG execution)

**Test**: `tests/test_agent_execute_recalled_procedure.py`

```python
def test_agent_executes_recalled_procedure():
    """Agent executes a recalled procedure"""
    # Store procedure with steps
    stored_proc = store_procedure("Login Procedure", steps=[
        {"tool": "web.get", "params": {"url": "https://example.com/login"}},
        {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']"}}},
        {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
    ])
    
    # User requests execution
    user_msg = "Run the login procedure for example.com"
    
    # Agent should:
    # 1. Find procedure via search
    # 2. LLM creates plan with dag.execute
    # 3. Agent executes DAG
    # 4. Tools execute in order
    
    # Verify procedure found
    # Verify DAG executed
    # Verify tools called in order
```

**Status**:
- ✅ DAGExecutor exists
- ✅ dag.execute tool exists in agent
- ⚠️ Need test to verify end-to-end execution

**Implementation Tasks**:
- [ ] Test: Recall → Execute → Verify execution
- [ ] Verify DAG loads correctly from concept
- [ ] Verify tool commands execute in order

---

### Module 4: Adapt Failed Procedure ⏸️ (Not Started)

**Goal**: When execution fails, agent adapts procedure and stores new version

### Module 5: Auto-Generalize Working Procedures ⏸️ (Not Started)

**Goal**: When multiple similar procedures work, automatically merge/average them into a generalized pattern

**Goal**: When execution fails, agent adapts procedure and stores new version

**Test**: `tests/test_agent_adapt_procedure.py`

```python
def test_agent_adapts_failed_procedure():
    """Agent adapts procedure when execution fails"""
    # Store procedure
    stored_proc = store_procedure("Login Procedure", steps=[...])
    
    # User requests with different parameters
    user_msg = "Log into newsite.com"  # Different site
    
    # Agent executes procedure (fails or needs adaptation)
    # Agent should:
    # 1. Detect failure/need for adaptation
    # 2. Adapt procedure (update URL, selectors, etc.)
    # 3. Store adapted version
    # 4. Link to original (optional)
    
    # Verify adaptation created
    # Verify adapted procedure works
    # Verify link to original (if implemented)
```

**Status**:
- ⏸️ Not implemented
- Agent has error handling but no adaptation logic

**Implementation Tasks**:
- [ ] Detect when procedure needs adaptation
- [ ] Adapt procedure (update parameters)
- [ ] Store adapted version
- [ ] Link to original (optional)

---

### Module 5: Auto-Generalize Working Procedures ⏸️ (Not Started)

**Goal**: When multiple similar procedures work, automatically merge/average them into a generalized pattern

**Test**: `tests/test_agent_auto_generalize.py`

```python
def test_agent_generalizes_working_procedures():
    """Agent automatically generalizes when multiple procedures work"""
    # Store multiple similar procedures
    proc1 = store_procedure("Login to X.com", steps=[...], embedding=[1.0, 0.5])
    proc2 = store_procedure("Login to Y.com", steps=[...], embedding=[0.95, 0.48])
    proc3 = store_procedure("Login to Z.com", steps=[...], embedding=[0.98, 0.49])
    
    # User requests similar task
    user_msg = "Log into newsite.com"
    
    # Agent should:
    # 1. Search KnowShowGo → Finds proc1, proc2, proc3
    # 2. Try each (or best match) → All work
    # 3. Automatically generalize:
    #    - Merge/average embeddings
    #    - Extract common steps
    #    - Create generalized pattern
    #    - Link exemplars to generalized pattern
    # 4. Store generalized pattern
    
    # Verify generalized pattern created
    # Verify exemplars linked to generalized pattern
    # Verify generalized pattern has averaged embedding
    # Verify common steps extracted
```

**Status**:
- ⏸️ Not implemented
- `generalize_concepts()` exists but not automatically triggered

**Implementation Tasks**:
- [x] Detect when multiple procedures work (after successful execution)
- [x] Trigger automatic generalization (in _auto_generalize_if_applicable)
- [x] Merge/average vector embeddings (dimension-wise averaging)
- [ ] Extract common steps/patterns (simplified for now)
- [x] Create generalized concept (via ksg.generalize_concepts)
- [x] Link exemplars to generalized pattern (has_exemplar edges)

**Status**: ✅ Core implementation complete - uses vector embedding averaging

---

## Implementation Order (Dependencies)

1. **Module 1: Store Procedure** (Foundation)
   - Dependencies: None
   - Status: ✅ Mostly done, needs testing

2. **Module 2: Recall Procedure** (Depends on 1)
   - Dependencies: Module 1 (procedures must be stored first)
   - Status: ✅ Mostly done, needs testing

3. **Module 3: Execute Procedure** (Depends on 1, 2)
   - Dependencies: Module 1 (procedures stored), Module 2 (procedures recalled)
   - Status: ⚠️ Needs integration testing

4. **Module 4: Adapt Procedure** (Depends on 1, 2, 3)
   - Dependencies: Modules 1, 2, 3 (need to store, recall, execute first)
   - Status: ⏸️ Not started

5. **Module 5: Auto-Generalize** (Depends on 1, 2, 3)
   - Dependencies: Modules 1, 2, 3 (need to store, recall, execute first)
   - Status: ⏸️ Not started
   - Note: Can be developed in parallel with Module 4

## TDD Test-Driven Development

### For Each Module:

**Step 1: Write Test First**
- Create test file
- Write test that describes desired behavior
- Run test (should fail - "red")

**Step 2: Implement Minimal Code**
- Write minimal code to pass test
- Run test (should pass - "green")

**Step 3: Refactor**
- Clean up code
- Run test (should still pass)

**Step 4: Verify End-to-End**
- Test with real agent flow
- Test with mock tools
- Verify behavior matches goal

## Focused Test Files

### `tests/test_agent_learn_procedure.py`
**Tests Module 1**: Storing procedures from chat

```python
class TestAgentLearnProcedure:
    def test_user_teaches_procedure_stored_in_ksg()
    def test_procedure_stored_with_embedding()
    def test_procedure_steps_stored_correctly()
    def test_end_to_end_learning_from_chat()
```

### `tests/test_agent_recall_procedure.py`
**Tests Module 2**: Recalling procedures

```python
class TestAgentRecallProcedure:
    def test_agent_searches_ksg_on_request()
    def test_finds_similar_procedure()
    def test_llm_receives_procedure_in_context()
    def test_fuzzy_matching_works()
```

### `tests/test_agent_execute_recalled_procedure.py`
**Tests Module 3**: Executing recalled procedures

```python
class TestAgentExecuteRecalledProcedure:
    def test_dag_loads_from_concept()
    def test_dag_executes_tool_commands()
    def test_execution_order_correct()
    def test_end_to_end_recall_and_execute()
```

### `tests/test_agent_adapt_procedure.py`
**Tests Module 4**: Adapting failed procedures

```python
class TestAgentAdaptProcedure:
    def test_detects_need_for_adaptation()
    def test_adapts_procedure_parameters()
    def test_stores_adapted_version()
    def test_adapted_version_works()
```

### `tests/test_agent_auto_generalize.py`
**Tests Module 5**: Auto-generalizing working procedures

```python
class TestAgentAutoGeneralize:
    def test_detects_multiple_working_procedures()
    def test_merges_embeddings_for_generalization()
    def test_extracts_common_steps()
    def test_creates_generalized_pattern()
    def test_links_exemplars_to_generalized()
    def test_end_to_end_auto_generalization()
```

## Current Status

### ✅ What Works
- Agent searches KnowShowGo concepts (line 119)
- Agent has ksg.create_concept tool
- DAGExecutor exists
- Agent has dag.execute tool

### ⚠️ What Needs Testing
- End-to-end: User chat → Store procedure
- End-to-end: Stored procedure → Recall → Use
- End-to-end: Recall → Execute → Verify execution
- Integration: KnowShowGo → Agent → Execution

### ⏸️ What Needs Implementation
- Adaptation logic when execution fails
- Linking adapted versions to originals
- Error detection and adaptation triggering

## Success Criteria

### Milestone 1: Learning ✅
- [ ] User teaches procedure via chat
- [ ] Agent stores procedure in KnowShowGo
- [ ] Procedure stored with embedding
- [ ] Test passes

### Milestone 2: Recall ✅
- [ ] User requests similar task
- [ ] Agent searches KnowShowGo
- [ ] Agent finds stored procedure
- [ ] LLM receives procedure in context
- [ ] Test passes

### Milestone 3: Execution ✅
- [ ] Agent recalls procedure
- [ ] Agent executes procedure (DAG)
- [ ] Tool commands execute in order
- [ ] Execution succeeds
- [ ] Test passes

### Milestone 4: Adaptation ✅
- [ ] Execution fails or needs adaptation
- [ ] Agent detects need for adaptation
- [ ] Agent adapts procedure
- [ ] Agent stores adapted version
- [ ] Adapted version works
- [ ] Test passes

### Milestone 5: Auto-Generalization ✅
- [ ] Multiple similar procedures found
- [ ] Procedures execute successfully
- [ ] Agent detects opportunity to generalize
- [ ] Agent merges/averages embeddings
- [ ] Agent extracts common steps
- [ ] Agent creates generalized pattern
- [ ] Exemplars linked to generalized pattern
- [ ] Test passes

### Milestone 6: Working Prototype ✅
- [ ] Full cycle: Learn → Recall → Execute → Adapt
- [ ] All tests pass
- [ ] Works with mock tools
- [ ] Works with ArangoDB (optional)

## Next Steps (Immediate)

1. **Start with Module 1 Test**
   - Create `tests/test_agent_learn_procedure.py`
   - Write test for learning from chat
   - Verify it works (or fix if broken)

2. **Then Module 2 Test**
   - Create `tests/test_agent_recall_procedure.py`
   - Write test for recall
   - Verify fuzzy matching works

3. **Then Module 3 Test**
   - Create `tests/test_agent_execute_recalled_procedure.py`
   - Write test for execution
   - Verify DAG execution works

4. **Finally Module 4**
   - Create `tests/test_agent_adapt_procedure.py`
   - Implement adaptation logic
   - Test adaptation flow

## Key Implementation Notes

### Procedure Storage Format
Procedures stored as concepts with:
```json
{
  "name": "Login Procedure",
  "description": "Procedure for logging into sites",
  "steps": [
    {"tool": "web.get", "params": {"url": "..."}},
    {"tool": "web.fill", "params": {"selectors": {...}}},
    {"tool": "web.click_selector", "params": {"selector": "..."}}
  ]
}
```

### Embedding Generation
- Generate embedding from procedure name + description
- Use for fuzzy matching
- Store in concept.llm_embedding

### Adaptation Strategy
- When execution fails, LLM receives error
- LLM adapts procedure (updates URL, selectors, etc.)
- Store new version (can link to original via edge)
- Future requests use adapted version

## Deferred (Not Needed for Core Loop)

- Advanced generalization (merging multiple exemplars)
- Object properties (ObjectProperty nodes)
- Complex relationship types
- Multi-level taxonomies
- CPMS integration (separate work)

