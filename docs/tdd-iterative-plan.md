# Iterative TDD Plan for Online Learning Agent

## Approach
- **Test-Driven Development**: Write test first, then implement
- **Modular Development**: Build one module at a time
- **Dependency-Based Ordering**: Build dependencies first
- **Incremental Prototype**: Get working end-to-end quickly, then enhance

## Module Dependency Graph

```
KnowShowGo API (Core)
  ├─→ Agent Concept Search Integration
  │     └─→ Pattern Reuse/Adaptation
  ├─→ Agent Concept Creation Integration
  │     ├─→ Pattern Reuse/Adaptation
  │     └─→ DAG Execution
  └─→ Fuzzy Matching Enhancements
        └─→ Pattern Reuse/Adaptation
```

## Development Order (Based on Dependencies)

### Phase 1: Foundation (No Dependencies)
**Module 1**: KnowShowGo API - Basic Operations

### Phase 2: Agent Integration (Depends on Phase 1)
**Module 2**: Agent Concept Search Integration
**Module 3**: Agent Concept Creation Integration

### Phase 3: Pattern Execution (Depends on Phase 2)
**Module 4**: DAG Execution (Basic)

### Phase 4: Pattern Reuse (Depends on Phase 2, 3)
**Module 5**: Pattern Reuse/Adaptation

### Phase 5: Enhancements (Optional, as needed)
**Module 6**: Fuzzy Matching Enhancements
**Module 7**: Object Properties (if needed)
**Module 8**: Advanced Generalization (if needed)

---

## Module 1: KnowShowGo API - Basic Operations

### Status: ✅ Mostly Complete (needs TDD verification)

### Dependencies: None (Foundation)

### TDD Test Cases

#### Test 1.1: Create Concept with Embedding
**Test File**: `tests/test_knowshowgo_basic.py`

```python
def test_create_concept_stores_embedding():
    """Verify concept creation stores embedding for fuzzy matching"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [1.0, 0.5])
    proto_uuid = get_procedure_prototype(memory)
    
    # Act
    concept_uuid = ksg.create_concept(
        prototype_uuid=proto_uuid,
        json_obj={"name": "Test Concept", "steps": []},
        embedding=[1.0, 0.5]
    )
    
    # Assert
    concept = memory.nodes[concept_uuid]
    assert concept.llm_embedding == [1.0, 0.5]
    assert concept.kind == "Concept"
    assert concept.props["name"] == "Test Concept"
```

**Acceptance Criteria**:
- ✅ Concept created in memory
- ✅ Embedding stored correctly
- ✅ Instantiates prototype (edge created)

#### Test 1.2: Search Concepts by Similarity
**Test File**: `tests/test_knowshowgo_basic.py`

```python
def test_search_concepts_returns_similar():
    """Verify concept search uses embedding similarity"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    
    # Create concepts with different embeddings
    proto_uuid = get_procedure_prototype(memory)
    concept1 = ksg.create_concept(proto_uuid, {"name": "Login A"}, [1.0, 0.5])
    concept2 = ksg.create_concept(proto_uuid, {"name": "Login B"}, [0.95, 0.48])
    concept3 = ksg.create_concept(proto_uuid, {"name": "Other"}, [0.1, 0.9])
    
    # Act
    results = ksg.search_concepts("login procedure", top_k=2, query_embedding=[0.98, 0.49])
    
    # Assert
    assert len(results) <= 2
    # Should find Login A and B (similar embeddings), not Other
```

**Acceptance Criteria**:
- ✅ Returns concepts sorted by similarity
- ✅ Uses embedding similarity (fuzzy matching)
- ✅ Respects top_k limit

### Implementation Tasks
- [x] Basic create_concept() exists
- [x] Basic search_concepts() exists
- [ ] Add tests to verify fuzzy matching works correctly
- [ ] Verify with ArangoDB backend

### Exit Criteria
- All tests pass
- Concepts stored with embeddings
- Search returns similarity-ranked results
- Works with mock and ArangoDB backends

---

## Module 2: Agent Concept Search Integration

### Status: ⚠️ Partial (exists but needs TDD verification)

### Dependencies: Module 1 (KnowShowGo API)

### TDD Test Cases

#### Test 2.1: Agent Searches KnowShowGo Before Asking User
**Test File**: `tests/test_agent_concept_search.py`

```python
def test_agent_searches_concepts_in_retrieval_phase():
    """Verify agent searches KnowShowGo concepts during memory retrieval"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    agent = create_agent_with_ksg(memory, ksg)
    
    # Create a stored concept
    proto_uuid = get_procedure_prototype(memory)
    ksg.create_concept(proto_uuid, {"name": "Login Pattern"}, [1.0, 0.5])
    
    # Act
    result = agent.execute_request("Log into X.com")
    
    # Assert
    # Verify concept search was called (check events/logs)
    # Verify concept matches included in memory_results
    # (Implementation: check event emission or spy on ksg.search_concepts)
```

**Acceptance Criteria**:
- ✅ Agent calls ksg.search_concepts() during retrieval
- ✅ Concept matches added to memory_results
- ✅ Results available to LLM for planning

#### Test 2.2: Agent Uses Search Results in Context
**Test File**: `tests/test_agent_concept_search.py`

```python
def test_concept_matches_included_in_llm_context():
    """Verify concept matches are included in LLM planning context"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    
    # Create stored concepts
    proto_uuid = get_procedure_prototype(memory)
    stored_concept = ksg.create_concept(
        proto_uuid,
        {"name": "Login Pattern", "steps": [...]},
        [1.0, 0.5]
    )
    
    # Spy on LLM call to verify context
    llm_spy = SpyOpenAIClient()
    agent = create_agent_with_ksg(memory, ksg, openai_client=llm_spy)
    
    # Act
    agent.execute_request("Log into Y.com")
    
    # Assert
    # Verify stored concept in LLM context
    assert stored_concept in llm_spy.last_context
```

**Acceptance Criteria**:
- ✅ Concept matches passed to LLM
- ✅ LLM receives concept data for planning
- ✅ Concept data format is correct

### Implementation Tasks
- [x] Agent calls ksg.search_concepts() (exists)
- [ ] Add tests to verify integration
- [ ] Verify concept matches used by LLM
- [ ] Test with real LLM (optional)

### Exit Criteria
- Agent searches KnowShowGo during retrieval
- Concept matches included in LLM context
- Tests verify integration works

---

## Module 3: Agent Concept Creation Integration

### Status: ⚠️ Partial (tool exists but needs TDD)

### Dependencies: Module 1 (KnowShowGo API)

### TDD Test Cases

#### Test 3.1: Agent Can Create Concept via Tool
**Test File**: `tests/test_agent_concept_creation.py`

```python
def test_agent_creates_concept_via_ksg_tool():
    """Verify agent can create concept using ksg.create_concept tool"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    agent = create_agent_with_ksg(memory, ksg)
    proto_uuid = get_procedure_prototype(memory)
    
    # Simulate LLM plan that creates concept
    plan = {
        "intent": "task",
        "steps": [{
            "tool": "ksg.create_concept",
            "params": {
                "prototype_uuid": proto_uuid,
                "json_obj": {"name": "Learned Pattern", "steps": []},
                "embedding": [1.0, 0.5]
            }
        }]
    }
    
    # Act
    result = agent._execute_plan(plan, provenance)
    
    # Assert
    assert result["status"] == "completed"
    # Verify concept created in memory
    concepts = [n for n in memory.nodes.values() if n.kind == "Concept"]
    assert len(concepts) > 0
    assert concepts[-1].props["name"] == "Learned Pattern"
```

**Acceptance Criteria**:
- ✅ ksg.create_concept tool executes successfully
- ✅ Concept stored in memory
- ✅ Embedding stored correctly

#### Test 3.2: Agent Creates Concept from User Instructions
**Test File**: `tests/test_agent_concept_creation.py`

```python
def test_agent_learns_concept_from_user_instructions():
    """End-to-end: User provides instructions, agent creates concept"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    
    # Mock LLM to return plan with concept creation
    llm_response = json.dumps({
        "intent": "task",
        "steps": [{
            "tool": "ksg.create_concept",
            "params": {
                "prototype_uuid": "...",
                "json_obj": {"name": "Login Pattern", "steps": [...]},
                "embedding": [1.0, 0.5]
            }
        }]
    })
    llm_client = FakeOpenAIClient(chat_response=llm_response)
    agent = create_agent_with_ksg(memory, ksg, openai_client=llm_client)
    
    # Act
    result = agent.execute_request("Teach me how to log into X.com")
    
    # Assert
    # Verify concept was created
    concepts = [n for n in memory.nodes.values() if n.kind == "Concept" and n.props.get("name") == "Login Pattern"]
    assert len(concepts) == 1
```

**Acceptance Criteria**:
- ✅ Agent processes user instruction
- ✅ LLM generates plan with concept creation
- ✅ Concept created and stored
- ✅ Embedding generated and stored

### Implementation Tasks
- [x] ksg.create_concept tool exists in agent
- [ ] Add tests for tool execution
- [ ] Test end-to-end concept creation
- [ ] Verify embedding generation

### Exit Criteria
- Agent can create concepts via tool
- Concepts stored with embeddings
- End-to-end learning flow works

---

## Module 4: DAG Execution (Basic)

### Status: ⚠️ Exists but needs integration testing

### Dependencies: Module 1, Module 3 (Concepts must be stored first)

### TDD Test Cases

#### Test 4.1: Load DAG from Concept
**Test File**: `tests/test_dag_executor.py`

```python
def test_load_dag_from_concept():
    """Verify DAG executor can load DAG structure from concept"""
    # Arrange
    memory = MockMemoryTools()
    executor = DAGExecutor(memory)
    
    # Create concept with DAG structure
    concept = Node(
        kind="Concept",
        props={
            "name": "Test DAG",
            "steps": [
                {"tool": "web.get", "order": 0},
                {"tool": "web.fill", "order": 1},
                {"tool": "web.click", "order": 2}
            ]
        }
    )
    memory.upsert(concept, provenance)
    
    # Act
    dag = executor.load_dag_from_concept(concept.uuid)
    
    # Assert
    assert dag is not None
    assert len(dag["nodes"]) == 3
    assert dag["nodes"][0]["tool"] == "web.get"
```

**Acceptance Criteria**:
- ✅ DAG structure loaded from concept
- ✅ Steps/nodes extracted correctly
- ✅ Handles various DAG formats

#### Test 4.2: Execute Simple DAG
**Test File**: `tests/test_dag_executor.py`

```python
def test_execute_simple_dag():
    """Verify DAG executor executes simple linear DAG"""
    # Arrange
    memory = MockMemoryTools()
    command_queue = []
    executor = DAGExecutor(memory, queue_manager=None)
    
    # Create concept with simple DAG
    concept = create_concept_with_dag(memory, [
        {"tool": "web.get", "params": {"url": "https://example.com"}},
        {"tool": "web.fill", "params": {"selectors": {"email": "input"}}},
    ])
    
    # Act
    result = executor.execute_dag(
        concept.uuid,
        enqueue_fn=lambda cmd: command_queue.append(cmd)
    )
    
    # Assert
    assert result["status"] == "completed"
    assert len(command_queue) == 2
    assert command_queue[0]["tool"] == "web.get"
```

**Acceptance Criteria**:
- ✅ DAG executes successfully
- ✅ Commands enqueued in order
- ✅ Execution status tracked

### Implementation Tasks
- [x] DAGExecutor exists
- [ ] Add integration tests
- [ ] Test with agent execution
- [ ] Verify tool command extraction

### Exit Criteria
- DAG loads from concept
- DAG executes and enqueues commands
- Works with agent execution flow

---

## Module 5: Pattern Reuse/Adaptation

### Status: ⏸️ Not Started

### Dependencies: Module 2 (Search), Module 3 (Creation), Module 4 (Execution)

### TDD Test Cases

#### Test 5.1: Agent Finds Similar Pattern and Reuses
**Test File**: `tests/test_agent_pattern_reuse.py`

```python
def test_agent_reuses_similar_pattern():
    """Verify agent finds similar pattern and reuses it"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    
    # Create stored pattern
    proto_uuid = get_procedure_prototype(memory)
    stored_pattern = ksg.create_concept(
        proto_uuid,
        {"name": "Login to X.com", "steps": [...]},
        [1.0, 0.5]
    )
    
    # Mock LLM to reuse pattern
    llm_response = json.dumps({
        "intent": "task",
        "steps": [{
            "tool": "dag.execute",
            "params": {"concept_uuid": stored_pattern}
        }]
    })
    agent = create_agent_with_ksg(memory, ksg, llm_client=FakeOpenAIClient(llm_response))
    
    # Act
    result = agent.execute_request("Log into Y.com")
    
    # Assert
    # Verify pattern was reused (not asking user)
    assert result["plan"].get("fallback") != True  # Not asking user
    # Verify DAG execution attempted
```

**Acceptance Criteria**:
- ✅ Agent finds similar pattern via search
- ✅ Agent reuses pattern (doesn't ask user)
- ✅ Pattern executed successfully

#### Test 5.2: Agent Adapts Pattern for New Use Case
**Test File**: `tests/test_agent_pattern_reuse.py`

```python
def test_agent_adapts_pattern():
    """Verify agent adapts similar pattern for new use case"""
    # Arrange
    memory = MockMemoryTools()
    ksg = KnowShowGoAPI(memory, embed_fn=lambda t: [len(t), 0.1])
    
    # Create stored pattern
    stored_pattern = create_login_pattern(memory, ksg, "X.com", "https://x.com/login")
    
    # Mock LLM to adapt pattern
    llm_response = json.dumps({
        "intent": "task",
        "steps": [{
            "tool": "ksg.create_concept",
            "params": {
                "prototype_uuid": proto_uuid,
                "json_obj": {
                    "name": "Login to Y.com",
                    "steps": [...],  # Adapted steps with Y.com URL
                    "adapted_from": stored_pattern
                }
            }
        }]
    })
    agent = create_agent_with_ksg(memory, ksg, llm_client=FakeOpenAIClient(llm_response))
    
    # Act
    result = agent.execute_request("Log into Y.com")
    
    # Assert
    # Verify new adapted pattern created
    # Verify adaptation references original
```

**Acceptance Criteria**:
- ✅ Agent finds similar pattern
- ✅ Agent creates adapted version
- ✅ Adaptation linked to original

### Implementation Tasks
- [ ] Implement pattern similarity checking
- [ ] Implement pattern adaptation logic
- [ ] Test reuse flow
- [ ] Test adaptation flow

### Exit Criteria
- Agent reuses similar patterns
- Agent adapts patterns for new cases
- Patterns linked appropriately

---

## Module 6: Fuzzy Matching Enhancements (Optional)

### Status: ⏸️ Defer until needed

### Dependencies: Module 1, Module 2

### When to Implement
- Only if agent needs better similarity thresholds
- Only if similarity scoring needs improvement
- Only if confidence-based filtering needed

### TDD Test Cases (Deferred)

#### Test 6.1: Similarity Threshold Filtering
#### Test 6.2: Confidence-Based Pattern Selection
#### Test 6.3: Fuzzy Relationship Strength

---

## Module 7: Object Properties (Optional)

### Status: ⏸️ Defer until needed

### Dependencies: Module 1

### When to Implement
- Only if agent needs to store objects with properties
- Only if property relationships needed
- Only if ObjectProperty nodes needed

---

## Module 8: Advanced Generalization (Optional)

### Status: ⏸️ Defer until needed

### Dependencies: Module 1, Module 3

### When to Implement
- Only if agent needs to merge multiple exemplars
- Only if taxonomy hierarchies needed
- Only if pattern generalization needed

---

## Development Workflow (TDD Cycle)

### For Each Module:

1. **Write Test First**
   - Create test file
   - Write failing test
   - Run test (should fail)

2. **Implement Minimal Code**
   - Write minimal code to pass test
   - Run test (should pass)
   - No extra features

3. **Refactor**
   - Clean up code
   - Improve structure
   - Run tests (should still pass)

4. **Verify Integration**
   - Test with dependent modules
   - Test end-to-end if applicable
   - Document usage

5. **Move to Next Module**
   - Only move when current module is complete
   - Follow dependency order

---

## Milestones

### Milestone 1: Foundation (Module 1)
**Goal**: KnowShowGo API works correctly
- [x] Concept creation with embeddings
- [x] Concept search with similarity
- [ ] Tests verify fuzzy matching
- [ ] Works with ArangoDB

**Acceptance**: All Module 1 tests pass

### Milestone 2: Basic Learning (Modules 2, 3)
**Goal**: Agent can learn patterns
- [ ] Agent searches concepts
- [ ] Agent creates concepts
- [ ] End-to-end learning flow works

**Acceptance**: Agent learns pattern from user instruction

### Milestone 3: Pattern Execution (Module 4)
**Goal**: Agent can execute learned patterns
- [ ] DAG loads from concept
- [ ] DAG executes commands
- [ ] Integration with agent works

**Acceptance**: Agent executes learned pattern

### Milestone 4: Pattern Reuse (Module 5)
**Goal**: Agent reuses and adapts patterns
- [ ] Agent finds similar patterns
- [ ] Agent reuses patterns
- [ ] Agent adapts patterns

**Acceptance**: Agent reuses pattern for similar task

### Milestone 5: Working Prototype ✅
**Goal**: End-to-end learning and reuse
- [ ] User teaches agent pattern
- [ ] Agent stores pattern
- [ ] Agent reuses pattern for similar task
- [ ] Agent adapts pattern when needed

**Acceptance**: Full learning cycle works end-to-end

---

## Testing Strategy

### Unit Tests
- Test each module in isolation
- Mock dependencies
- Fast execution
- High coverage

### Integration Tests
- Test modules together
- Use real dependencies where possible
- Verify interfaces work correctly

### End-to-End Tests
- Test full agent flow
- Use mock tools (MockWebTools, etc.)
- Verify learning cycle works

### Backend Tests
- Test with ArangoDB
- Test with MockMemoryTools
- Verify backend compatibility

---

## Dependency Resolution

### Build Order
1. **Module 1** (no dependencies) → Build first
2. **Module 2, 3** (depend on 1) → Build in parallel after 1
3. **Module 4** (depends on 1, 3) → Build after 2, 3
4. **Module 5** (depends on 2, 3, 4) → Build after 4
5. **Modules 6-8** (optional) → Build only if needed

### Parallel Development
- Module 2 and 3 can be developed in parallel (both depend only on 1)
- Module 4 must wait for 3
- Module 5 must wait for 2, 3, 4

### Testing Dependencies
- Each module's tests should mock dependencies
- Integration tests use real dependencies
- End-to-end tests use full stack

---

## Next Steps

1. **Start with Module 1 tests** - Verify foundation works
2. **Complete Module 2, 3** - Get basic learning working
3. **Add Module 4** - Enable pattern execution
4. **Add Module 5** - Enable pattern reuse
5. **Test end-to-end** - Verify prototype works
6. **Add features only as needed** - Incremental enhancement

---

## Notes

- **Focus on prototype first** - Get working end-to-end quickly
- **Defer optional modules** - Only implement when needed
- **Test-driven** - Write tests first, then implement
- **Modular** - One module at a time, verify before moving on
- **Dependency-aware** - Build dependencies first
- **Incremental** - Small, testable steps

