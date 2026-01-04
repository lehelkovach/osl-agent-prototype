# Online Learning Agent Prototype - Minimal Implementation Plan

## Goal
Get a working prototype where the agent can:
1. Learn patterns from user instructions (store as concepts in KnowShowGo)
2. Search semantic memory (KnowShowGo) for similar patterns before asking user
3. Reuse/adapt learned patterns for new tasks
4. Use fuzzy matching (embedding similarity) to find similar patterns

## Core Flow

```
User: "Log into X.com with my default credentials"
  ↓
Agent searches KnowShowGo for similar concepts
  ↓
If found and similar enough → Adapt and use
If not found → Ask user for instructions
  ↓
User provides steps: "Go to X.com, fill email/password, click login"
  ↓
Agent creates concept in KnowShowGo with DAG structure
  ↓
Agent executes the pattern
  ↓
Future similar requests reuse/adapt the pattern
```

## Minimal KnowShowGo Features Needed

### Phase 1: Basic Learning (Must Have)

1. ✅ **Concept Creation**
   - `ksg.create_concept()` - Store learned patterns as concepts
   - Concepts have embeddings for similarity matching
   - Already implemented

2. ✅ **Concept Search**
   - `ksg.search_concepts()` - Find similar concepts by embedding
   - Returns ranked results by similarity
   - Already implemented

3. ⚠️ **Agent Integration**
   - Agent searches KnowShowGo before asking user
   - Agent creates concepts when user provides instructions
   - Partially implemented (search exists, creation needs testing)

### Phase 2: Pattern Reuse (Must Have)

4. ⚠️ **Pattern Adaptation**
   - When similar concept found, adapt it for new task
   - Store adapted version
   - Needs implementation/testing

5. ⚠️ **DAG Execution**
   - Execute learned patterns (DAG structures)
   - DAG executor exists but needs integration/testing

### Phase 3: Fuzzy Features (Add as Needed)

6. ⏸️ **Relationship Strength**
   - Add strength to associations (when needed)
   - Defer for now

7. ⏸️ **Object Properties**
   - ObjectProperty nodes (when needed)
   - Defer for now

8. ⏸️ **Advanced Generalization**
   - Multi-level generalization (when needed)
   - Defer for now

## Implementation Priority

### Step 1: Test End-to-End Flow (Current Focus)
**Goal**: Verify agent can learn and reuse patterns

**Test Scenarios**:
1. User requests task → Agent searches KnowShowGo → No match → Asks user
2. User provides steps → Agent creates concept → Stores in KnowShowGo
3. Similar request → Agent finds concept → Reuses/adapts pattern

**Files to Test/Create**:
- `tests/test_agent_concept_learning_flow.py` - End-to-end test
- Test with mock memory first
- Then test with ArangoDB

### Step 2: Ensure Core Features Work
- Verify concept creation stores embeddings
- Verify concept search returns similarity-ranked results
- Verify agent uses search results in decision-making

### Step 3: Add Features Incrementally
- Only add features when agent actually needs them
- Test each feature with agent use case
- Don't implement features "just in case"

## Current Status

### ✅ Working
- KnowShowGo API exists with basic methods
- Concept creation with embeddings
- Concept search with embeddings
- Agent has concept search in retrieval phase
- Agent has ksg.create_concept tool

### ⚠️ Needs Testing
- End-to-end flow: user instruction → concept creation → reuse
- Concept search actually finding similar concepts
- Agent using search results to decide whether to ask user
- Concept creation storing proper DAG structures

### ⏸️ Defer for Later
- Advanced fuzzy features (strength, ObjectProperty, etc.)
- Multi-level generalization
- Complex relationship types
- Advanced edge queries

## Next Steps

1. **Create end-to-end test** - Verify learning flow works
2. **Test with mock memory** - Get basic flow working
3. **Test with ArangoDB** - Verify persistence works
4. **Test with real OpenAI** - Verify embeddings work
5. **Add features only as needed** - Incremental enhancement

## Success Criteria

- [ ] Agent searches KnowShowGo before asking user
- [ ] Agent creates concepts when user provides instructions
- [ ] Agent finds and reuses similar concepts
- [ ] Concepts stored with embeddings
- [ ] Similarity matching works (fuzzy matching)
- [ ] Basic DAG execution works for learned patterns

## Notes

- Focus on **working prototype**, not complete feature set
- Implement features **incrementally as needed**
- Test each feature with **real agent use case**
- Defer advanced features until agent actually needs them
- Keep KnowShowGo simple and focused on agent needs

