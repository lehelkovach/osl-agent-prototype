# Agent Handoff Documentation

**Purpose**: This document provides comprehensive context for another Cursor AI agent to take over development of the `osl-agent-prototype` project.

**Last Updated**: 2024-12-19

---

## Project Overview

The **OSL Agent Prototype** is a lightweight personal assistant agent that:
- Plans with LLMs (OpenAI, Anthropic Claude, Google Gemini)
- Executes tool calls (tasks, calendar, contacts, web automation, shell)
- Persists semantic memory in ChromaDB or ArangoDB
- Uses a KnowShowGo (KSG) fuzzy ontology knowledge graph
- Implements a core learning loop: Learn → Recall → Execute → Adapt → Auto-Generalize

---

## Project Documentation Locations

### Primary Documentation Files

1. **`README.md`** (root)
   - Project overview, architecture, setup instructions
   - Current state and known gaps
   - Development roadmap

2. **`docs/architecture.md`**
   - Detailed component architecture
   - Planning and execution flow
   - Memory backends and ontology structure

3. **`docs/core-learning-loop-plan.md`**
   - Core learning cycle implementation plan
   - Module-by-module breakdown (Learn, Recall, Execute, Adapt, Auto-Generalize)
   - Test-driven development approach
   - Current status of each module

4. **`docs/development-priorities-summary.md`**
   - Executive summary of development priorities
   - Phase-by-phase implementation plan
   - Timeline estimates

5. **`docs/cpms-integration-plan.md`**
   - CPMS (Concept Pattern Matching System) integration tasks
   - Form pattern detection and matching
   - Pattern storage and reuse

6. **`docs/knowshowgo-fuzzy-ontology.md`** and **`docs/knowshowgo-ontology-architecture.md`**
   - KnowShowGo ontology design and implementation
   - Prototype and concept structure
   - Recursive concept creation

### Configuration Files

- **`config/default.yaml`**: Main configuration (LLM providers, embedding backends, etc.)
- **`pyproject.toml`**: Poetry dependencies and project metadata
- **`requirements.txt`**: Alternative pip requirements

### Key Source Files

- **`src/personal_assistant/agent.py`**: Core agent loop (planning, execution, learning)
- **`src/personal_assistant/service.py`**: FastAPI service and HTTP endpoints
- **`src/personal_assistant/knowshowgo.py`**: KSG ontology store and operations
- **`src/personal_assistant/ksg.py`**: KSG seed data and initialization
- **`src/personal_assistant/dag_executor.py`**: DAG execution engine
- **`src/personal_assistant/cpms_adapter.py`**: CPMS client adapter
- **`src/personal_assistant/llm_client.py`**: Multi-provider LLM client abstraction
- **`src/personal_assistant/prompts.py`**: System and developer prompts for LLM

### Test Files

- **`tests/test_agent_*.py`**: Agent behavior tests
- **`tests/test_knowshowgo_*.py`**: KSG ontology tests
- **`tests/test_dag_executor_*.py`**: DAG execution tests
- **`tests/test_cpms_*.py`**: CPMS integration tests

---

## Project Functionality Goals

### Core Learning Loop (Primary Goal)

The agent implements a complete learning cycle:

1. **Learn**: Agent learns procedures from user chat messages
   - User teaches: "To log into X.com, go to URL, fill email/password, click submit"
   - Agent stores procedure as a concept in KnowShowGo with embeddings
   - Status: ✅ **Complete**

2. **Recall**: Agent recalls similar procedures via fuzzy matching
   - User requests: "Log into Y.com"
   - Agent searches KnowShowGo using embeddings
   - Finds similar "Log into X.com" procedure
   - Status: ✅ **Complete**

3. **Execute**: Agent executes recalled procedures via DAG execution
   - Agent loads procedure DAG from concept
   - Executes tool commands in dependency order
   - Status: ✅ **Complete** (needs more integration testing)

4. **Adapt**: Agent adapts procedures when execution fails
   - Execution fails (wrong URL, changed selectors, etc.)
   - Agent detects failure and triggers adaptation
   - LLM adapts procedure (updates URL, selectors, parameters)
   - Stores adapted version for future use
   - Status: ✅ **Complete** (basic implementation)

5. **Auto-Generalize**: Agent automatically generalizes working procedures
   - Multiple similar procedures execute successfully
   - Agent detects opportunity to generalize
   - Merges/averages embeddings, extracts common steps
   - Creates generalized pattern, links exemplars
   - Status: ✅ **Complete** (uses vector embedding averaging)

### Secondary Goals

- **Multi-Provider LLM Support**: Support OpenAI, Anthropic Claude, Google Gemini
  - Status: ✅ **Complete** (via `llm_client.py` abstraction)

- **CPMS Integration**: Form pattern detection and matching
  - Status: ⏳ **In Progress** (v0.1.2 client published, integration ongoing)

- **Web Automation**: Playwright-based web tools (DOM, screenshots, clicks, fills)
  - Status: ⏳ **Partial** (basic tools exist, needs more testing)

- **Semantic Memory**: Persistent storage with embeddings (ArangoDB/ChromaDB)
  - Status: ✅ **Complete**

- **Task Queue & Scheduler**: Prioritized task queue with time-based rules
  - Status: ✅ **Complete**

---

## Current State

### Completed Features (✅)

1. **Core Learning Loop Modules**
   - ✅ Learn: Procedure storage from chat
   - ✅ Recall: Fuzzy matching via embeddings
   - ✅ Execute: DAG execution engine
   - ✅ Adapt: Basic adaptation on failure
   - ✅ Auto-Generalize: Vector embedding averaging

2. **Infrastructure**
   - ✅ Multi-provider LLM client (OpenAI, Claude, Gemini)
   - ✅ Semantic memory backends (ArangoDB, ChromaDB, Mock)
   - ✅ KnowShowGo ontology store
   - ✅ DAG executor with dependency resolution
   - ✅ FastAPI service with `/ui` chat interface
   - ✅ Structured logging and event bus

3. **Tools & Integrations**
   - ✅ Task/Calendar/Contacts tools (mock and real)
   - ✅ Web tools (DOM fetch, screenshot, basic clicks/fills)
   - ✅ Shell executor (staged execution)
   - ✅ CPMS adapter (basic integration, v0.1.2 client installed)

4. **Testing**
   - ✅ 90+ passing tests
   - ✅ Test coverage for core modules
   - ✅ Integration tests for agent flow

### In Progress (⏳)

1. **CPMS Integration**
   - ⏳ Full `detect_form()` integration (v0.1.2 client just installed)
   - ⏳ Pattern storage and reuse
   - ⏳ CPMS-enhanced adaptation

2. **Web Automation**
   - ⏳ Playwright integration testing
   - ⏳ Vision-assisted element location
   - ⏳ End-to-end form filling flows

### Known Gaps / Not Yet Implemented

1. **Production-Grade Features**
   - Shell executor sandboxing/confirmation
   - Secrets/vault encryption at rest
   - Native Arango vector indexes (currently client-side cosine)
   - Live CPMS integration tests with real endpoint

2. **UI/UX Enhancements**
   - Ontology workbench UI for browsing/editing concepts
   - Richer run replay with embedded screenshots/DOM
   - Live event/log streams in UI

3. **Advanced Features**
   - Twilio (SMS/voice) support
   - Advanced pattern generalization (beyond vector averaging)
   - Multi-level taxonomy building
   - Pattern composition and inheritance

---

## Development Stages Planned

### Phase 1: Complete Core Loop ✅ (COMPLETE)

**Status**: All core modules implemented and tested

- ✅ Module 1: Learn (procedure storage)
- ✅ Module 2: Recall (fuzzy matching)
- ✅ Module 3: Execute (DAG execution)
- ✅ Module 4: Adapt (failure adaptation)
- ✅ Module 5: Auto-Generalize (embedding averaging)

**Next Steps**: More integration testing, edge case handling

---

### Phase 2: CPMS Integration ⏳ (IN PROGRESS)

**Status**: CPMS client v0.1.2 published, integration ongoing

**Tasks**:

1. **CPMS Form Detection** (3-4 hours)
   - ✅ Update `cpms-client` dependency to >=0.1.2
   - ✅ Install updated client
   - ⏳ Update `cpms_adapter.py` to use `detect_form()` method
   - ⏳ Test form pattern detection
   - ⏳ Enhance pattern data structure

2. **CPMS-Enhanced Adaptation** (4-5 hours)
   - ⏳ Use CPMS patterns in adaptation logic
   - ⏳ Store patterns in KnowShowGo
   - ⏳ Pattern matching for form adaptation
   - ⏳ Add integration tests

**Files to Modify**:
- `src/personal_assistant/cpms_adapter.py` (primary)
- `src/personal_assistant/agent.py` (adaptation logic)
- `src/personal_assistant/knowshowgo.py` (pattern storage)
- `tests/test_cpms_*.py` (test files)

**Documentation**: See `docs/cpms-integration-plan.md` for detailed tasks

---

### Phase 3: Enhanced KnowShowGo Integration (PENDING)

**Status**: Not started

**Tasks**:

1. **Recursive Concept Creation with ArangoDB**
   - Test recursive concept creation with real ArangoDB
   - Verify nested concepts are created and linked correctly
   - Test with real OpenAI embeddings

2. **DAG Execution with Real Concepts**
   - Load DAG from ArangoDB-stored concept
   - Execute DAG with dependency resolution
   - Test nested DAG execution (procedure calling sub-procedure)
   - Test guard evaluation

3. **Full Flow Testing**
   - User instruction → Concept creation → Execution
   - Verify end-to-end learning cycle with real storage

**Files to Create/Modify**:
- `tests/test_knowshowgo_recursive_arango.py` (new)
- `tests/test_dag_executor_arango.py` (new)
- `tests/test_agent_concept_learning_flow.py` (new)

**Documentation**: See `docs/parallel-work-plan.md` for details

---

### Phase 4: Web Automation Enhancement (PENDING)

**Status**: Not started

**Tasks**:

1. **Playwright Integration**
   - Enable Playwright-backed WebTools (`USE_PLAYWRIGHT=1`)
   - Test screenshot, DOM fetch, fill, click, wait_for
   - Capture paths in `/tmp/agent-captures`

2. **Procedure Learning from Web Actions**
   - Derive/store/reuse procedures for logins and form fills
   - Serialize successful steps as DAG/Procedure nodes
   - Embed fingerprints (labels/placeholders/types/layout)
   - Reuse via RAG when confidence ≥0.8

3. **CPMS Integration for Forms**
   - Build observations from Playwright snapshots
   - Call CPMS `match_pattern` for form element matching
   - Map assignments to selectors before filling

4. **Scheduler/Queue Integration**
   - Generated procedures enqueue as tasks
   - Execute step-by-step with feedback
   - Failed steps trigger patch/retry and updated procedure storage

**Files to Modify**:
- `src/personal_assistant/web_tools.py`
- `src/personal_assistant/form_filler.py`
- `src/personal_assistant/agent.py`

---

### Phase 5: Production Hardening (PENDING)

**Status**: Not started

**Tasks**:

1. **Security**
   - Shell executor sandboxing/confirmation
   - Secrets/vault encryption at rest
   - Scoped access controls

2. **Performance**
   - Native Arango vector indexes (AQL scoring)
   - Cache flattening for fast queries
   - Optimize embedding generation

3. **Deployment**
   - Docker containerization
   - Auth/SSO integration
   - Metering/billing hooks

4. **Testing**
   - Live CPMS integration tests
   - End-to-end web automation tests
   - Load testing

---

## Key Technical Concepts

### KnowShowGo (KSG) Ontology

- **Fuzzy Ontology**: Graph-based knowledge store with embeddings for similarity matching
- **Concepts**: Nodes with `kind`, `labels`, `props`, and `llm_embedding`
- **Prototypes**: Base types (Object, List, DAG, Procedure, Tag, etc.)
- **Recursive Creation**: Concepts can contain nested child concepts
- **Generalization**: Multiple exemplars can be merged into generalized patterns

### DAG Execution

- **Dependency Resolution**: Bottom-up execution (dependencies first)
- **Guard Evaluation**: Conditional step execution
- **Tool Command Enqueueing**: Steps enqueue tool commands to task queue
- **Context Passing**: Context variables passed between steps

### CPMS Integration

- **Form Pattern Detection**: Detects email/password/submit patterns in HTML
- **Pattern Storage**: Patterns stored as concepts in KnowShowGo
- **Pattern Matching**: Match new forms against stored patterns
- **Adaptation**: Use patterns to adapt procedures for similar forms

### Multi-Provider LLM

- **Abstraction**: `LLMClient` base class with provider-specific implementations
- **Providers**: OpenAI, Anthropic Claude, Google Gemini
- **Embedding Fallback**: Claude uses OpenAI or local embeddings (no native embedding)

---

## Development Workflow

### Setup

1. **Install Dependencies**
   ```bash
   poetry install
   poetry run playwright install --with-deps chromium
   ```

2. **Environment Variables** (`.env.local` - not committed)
   ```bash
   # LLM Provider (choose one)
   OPENAI_API_KEY=your-key
   ANTHROPIC_API_KEY=your-key
   GOOGLE_API_KEY=your-key
   LLM_PROVIDER=openai|claude|gemini  # default: openai
   
   # Optional: ArangoDB
   ARANGO_URL=https://...
   ARANGO_DB=...
   ARANGO_USER=...
   ARANGO_PASSWORD=...
   
   # Optional: CPMS
   CPMS_BASE_URL=http://localhost:8787
   CPMS_TOKEN=...
   
   # Optional: Embeddings
   EMBEDDING_BACKEND=local|openai
   ```

3. **Run Tests**
   ```bash
   poetry run pytest
   ```

4. **Run Service**
   ```bash
   poetry run agent-service
   # or
   uvicorn src.personal_assistant.service:main --reload
   ```
   Open `http://localhost:8000/ui` for chat interface

### Testing Strategy

- **TDD Approach**: Write tests first, then implement
- **Mock Tools**: Use `MockMemoryTools`, `MockWebTools`, etc. for unit tests
- **Integration Tests**: Test with real ArangoDB/ChromaDB (gated by env)
- **Test Files**: Organized by module (`test_agent_*.py`, `test_knowshowgo_*.py`, etc.)

### Code Style

- **Type Hints**: Use type hints throughout
- **Docstrings**: Document classes and methods
- **Error Handling**: Graceful fallbacks (e.g., CPMS unavailable → simple detection)
- **Logging**: Use structured logging (`structlog`)

---

## Immediate Next Steps

### Priority 1: Complete CPMS Integration

1. **Update `cpms_adapter.py`** to use `detect_form()` from v0.1.2 client
   - Remove fallback comments
   - Test with real CPMS service (if available)
   - Add error handling

2. **Test CPMS Integration**
   - Unit tests with mock client
   - Integration tests with real CPMS (gated by env)
   - Test fallback behavior

3. **Enhance Pattern Storage**
   - Store patterns in KnowShowGo via `ksg.store_cpms_pattern()`
   - Link patterns to concepts
   - Test pattern retrieval and matching

### Priority 2: Enhanced Testing

1. **Integration Tests for Core Loop**
   - Test full cycle: Learn → Recall → Execute → Adapt → Generalize
   - Test with real ArangoDB
   - Test edge cases

2. **CPMS Integration Tests**
   - Test form detection with various HTML structures
   - Test pattern matching and adaptation
   - Test fallback behavior

### Priority 3: Documentation Updates

1. **Update README.md** with latest status
2. **Update development-priorities-summary.md** with completed phases
3. **Add examples** of successful learning cycles

---

## Important Notes

### Removed Features

- **TTS/STT**: Text-to-Speech and Speech-to-Text functionality was removed (intended for Cursor installation, not this project)
  - Files deleted: `src/personal_assistant/tts_helper.py`, `src/personal_assistant/tts_event_listener.py`
  - Configuration removed from `config/default.yaml`
  - Service initialization cleaned up

### Dependencies

- **cpms-client**: Now at v0.1.2 (just updated)
  - Includes `detect_form()` method
  - Published to PyPI

### Known Issues

- ArangoDB certificate verification: Currently bugged, don't include `ARANGO_VERIFY` for cloud CAs
- Shell executor: Runs commands directly (needs sandboxing)
- Playwright: Currently mocked in most tests (needs real integration)

---

## Getting Started Prompt for New Agent

When starting a new Cursor conversation, use this prompt:

```
I'm working on the osl-agent-prototype project. Please review:
1. docs/AGENT-HANDOFF.md for project context
2. docs/core-learning-loop-plan.md for implementation details
3. docs/development-priorities-summary.md for current priorities
4. docs/cpms-integration-plan.md for CPMS integration tasks

Current priority: Complete CPMS integration (Phase 2)
- cpms-client v0.1.2 is installed
- Need to update cpms_adapter.py to use detect_form() method
- Need to test and enhance pattern storage

Please help me continue development following the TDD approach and existing code patterns.
```

---

## Contact / Questions

For questions about the project:
- Review the documentation files listed above
- Check test files for usage examples
- Review `src/personal_assistant/prompts.py` for LLM contract details

---

**End of Handoff Documentation**

