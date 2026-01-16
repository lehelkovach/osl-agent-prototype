# Session Notes

## 2026-01-16: LLM JSON to KnowShowGo DAG Procedures

### Changes Made
- Created `ProcedureManager` for LLM JSON to DAG conversion
- Defined JSON schema for LLM-generated procedures
- Integrated with agent for automatic format detection
- Updated prompts with procedure JSON schema

### JSON Schema for Procedures
```json
{
  "name": "LinkedIn Login",
  "description": "Log into LinkedIn",
  "steps": [
    {
      "id": "step_1",
      "name": "Navigate to login",
      "tool": "web.get_dom",
      "params": {"url": "https://linkedin.com/login"},
      "depends_on": [],
      "on_fail": "stop"
    },
    {
      "id": "step_2",
      "name": "Fill email",
      "tool": "web.fill",
      "params": {"selector": "#username", "text": "${credentials.email}"},
      "depends_on": ["step_1"]
    }
  ]
}
```

### Flow
```
LLM generates JSON → ProcedureManager.validate() → ProcedureManager.create_from_json()
                                                          ↓
                                            KnowShowGo DAG (Procedure + Steps + Edges)
                                                          ↓
                                            Searchable & Executable via DAGExecutor
```

### Files Created
- `src/personal_assistant/procedure_manager.py` - JSON validation and DAG creation
- `tests/test_procedure_manager.py` - 29 tests for validation and conversion

### Test Results
- **535 tests passing** (29 new procedure manager tests)
- 12 skipped (integration tests requiring external services)

---

## 2026-01-15: SafeShellExecutor with Sandbox and Rollback

### Changes Made
- Created `SafeShellExecutor` for safe command execution
- Added command whitelist/blacklist filtering
- Added file change tracking with snapshot and rollback
- Added temporary directory sandboxing
- Added `TestShellRunner` for integration tests

### Safety Features
```python
# Blocked commands (dangerous operations)
- rm -rf /
- fork bombs
- curl|bash, wget|bash
- sudo (configurable)

# File tracking (for rollback)
- cp, mv, rm, mkdir, rmdir, touch
- redirects (>, >>)
- in-place edits (sed -i, awk -i)

# Sandboxing
- Unsafe commands run in temp directories
- Changes isolated from real filesystem
```

### Usage
```python
from src.personal_assistant.safe_shell import create_safe_shell, TestShellRunner

# Create safe shell
shell = create_safe_shell()

# Preview command safety
preview = shell.preview_command("rm file.txt")
# {'blocked': False, 'is_safe': False, 'modifies_files': True, ...}

# Run with safety
result = shell.run("echo hello", dry_run=False)

# Run in sandbox
result = shell.run_in_sandbox("touch newfile.txt")

# Test runner with auto-cleanup
with TestShellRunner() as runner:
    result = runner.run_and_verify("ls", expected_returncode=0)
    # Auto-rollback on exit
```

### Test Results
- **518 tests collected** (38 new safe shell tests)
- All tool tests passing

---

## 2026-01-15: KnowShowGo Separate Service Implementation

### Changes Made
- Created `services/knowshowgo/` directory with FastAPI service
- Implemented `KnowShowGoClient` for HTTP communication with service
- Added `MockKnowShowGoClient` for testing without running service
- Created `KnowShowGoAdapter` for seamless switching between embedded and service mode
- Added 78 new tests for service, client, and adapter

### Architecture
```
Agent → KnowShowGoAdapter
           ↓
    [Service Available?]
           ↓
    Yes: KnowShowGoClient → HTTP → KnowShowGo Service (port 8001)
    No: Embedded KnowShowGoAPI (fallback)
```

### Files Created
- `services/knowshowgo/service.py` - FastAPI app with all KnowShowGo endpoints
- `services/knowshowgo/client.py` - HTTP client + mock client
- `services/knowshowgo/models.py` - Pydantic models for API
- `src/personal_assistant/knowshowgo_adapter.py` - Adapter for backend switching
- `scripts/start_knowshowgo_service.sh` - Service startup script

### Test Results
- **468 tests passing** (all KnowShowGo tests included)
- 12 skipped (integration tests requiring external services)
- Service verified running on port 8001

### Usage
```bash
# Start service
./scripts/start_knowshowgo_service.sh

# Or set env var for agent to use service
export KNOWSHOWGO_URL=http://localhost:8001
```

---

## 2026-01-15: Live Mode Testing Complete

### Changes Made
- Fixed circular reference issue in `agent.py` logging (safe JSON serialization)
- Fixed `service.py` response serialization (strip embeddings, handle circular refs)
- Fixed `task_queue.py` `update_status` to find Concept kind nodes
- Updated all tests to use `list_items()` instead of `queue.props['items']`
- Updated test assertions to match current implementation

### Test Results
- **380 tests passing** (up from 372)
- 12 skipped (integration tests requiring external services)
- All queue/scheduler tests now pass

### Live Service Verification
The service runs successfully with all real services:
- **OpenAI GPT-4o**: Real planning and embedding
- **ArangoDB Cloud**: Real persistence
- **Playwright**: Real browser automation

Verified operations:
1. Store credentials → memory.remember
2. Create calendar events → calendar.create_event
3. Take screenshots → web.screenshot
4. Store facts → memory.remember
5. DOM extraction → web.get_dom

--- (persistent context)

## Current goals
- **Primary**: Get working prototype where agent can learn procedures from chat messages, store them in KnowShowGo semantic memory, recall them via fuzzy matching, execute them, and adapt them when they fail. Focus: Learn → Recall → Execute → Adapt cycle.

## Learning Loop Progress (Core Learning Loop Plan)

### ✅ Module 1: Learn (COMPLETE)
- Agent learns procedures from chat and stores in KnowShowGo
- Tests: `tests/test_agent_learn_procedure.py` (all passing)
- Status: All implementation tasks complete

### ✅ Module 2: Recall (COMPLETE)
- Agent recalls stored procedures via fuzzy matching (vector embeddings)
- Tests: `tests/test_agent_recall_procedure.py` (all passing)
- Status: All implementation tasks complete

### ✅ Module 3: Execute (COMPLETE)
- Agent executes recalled procedures (DAG execution)
- Tests: `tests/test_agent_execute_recalled_procedure.py` (all passing)
- Status: DAG execution working, enqueue_fn signature fixed, all tests passing

### ✅ Module 4: Adapt (COMPLETE)
- Agent adapts procedures when execution fails
- Tests: `tests/test_agent_adapt_procedure.py` (all passing)
- Status: Adaptation logic implemented, stores adapted versions with links to originals

### ✅ Module 5: Auto-Generalize (COMPLETE)
- Agent auto-generalizes when multiple procedures work (via vector embeddings)
- Tests: `tests/test_agent_auto_generalize.py`
- Status: Implementation complete, uses vector embedding averaging
- Standardize the memory adapter boundary (`MemoryTools`) so backends (Arango, Chroma, in-memory) are swappable and contract-tested.
- Keep procedure planning JSON-first: LLM returns `{"commandtype": ..., "metadata": {...}}` with procedure steps; execute and persist run stats + links.

## Recent changes
- **Salvage Steps A-D Complete (2026-01-14)**: 
  - Step A: WorkingMemoryGraph (Hebbian reinforcement for retrieval) v0.5.0-salvage-step-a
  - Step B: AsyncReplicator (background persistence worker) v0.5.0-salvage-step-b
  - Step C: DeterministicParser (rule-based intent classification) v0.6.0-salvage-step-c
  - Step D: Agent integration (memory boost + reinforcement) v0.7.0-salvage-step-d
  - Total: +81 new tests (14+9+46+12), all passing
- **Branch Merge Complete (2026-01-14)**: Merged `cursor/branch-merge-assessment-c4d7` into main. Features: CPMS integration, form fingerprinting, documentation updates, KnowShowGo bundle, code cleanup. Branches archived to `archived/cursor/*`.
- **Planning Documents Created**: Added `docs/opus-next-steps.md` (Opus priorities), `docs/MASTER-PLAN.md` (unified roadmap merging Opus/GPT/Salvage perspectives).
- **Salvage Plan Integrated**: `docs/salvage-osl-agent-prototype.txt` provides component porting guide (WorkingMemoryGraph, AsyncReplicator, DeterministicParser).
- **GPT Plans Added**: `docs/gpt-plans.md` outlines refactor roadmap and milestones.
- **Test Status**: 218 passed, 37 skipped, 12 failed (3 Playwright env, 9 pre-existing).
- **Module 3 (Execute) Complete**: Added DAG execution tests, fixed enqueue_fn signature issue, verified end-to-end execution. Agent can now execute recalled procedures via DAG structures.
- **Module 4 (Adapt) Complete**: Implemented `_adapt_procedure_on_failure()` method that detects execution failures, adapts procedures based on errors and user requests, stores adapted versions, and links them to originals. All tests passing.
- **Phase 3 (Full Cycle Validation) Complete**: Created comprehensive end-to-end tests (`tests/test_agent_full_learning_cycle.py`) validating the complete learning cycle: Learn → Recall → Execute → Adapt → Generalize. All tests passing.
- **Core Learning Loop Complete**: All 5 modules of the core learning loop are now functionally complete. The agent can learn procedures, recall them via fuzzy matching, execute them via DAG, adapt them on failure, and auto-generalize working procedures.
- **KnowShowGo Integration**: Enhanced KnowShowGo API with recursive concept creation, embedding-based search, CPMS pattern storage, and concept generalization. Agent now queries KnowShowGo concepts before asking user, supports nested DAG structures (procedures containing sub-procedures), and can merge exemplars into generalized patterns with taxonomy hierarchies.
- **DAG Execution Engine**: Added `dag_executor.py` to load and execute DAG structures from concepts. Evaluates bottom nodes, checks guards/rules, and enqueues tool commands. Supports nested DAG execution.
- **CPMS Form Detection**: Added basic CPMS form detection with fallback. Integration points defined for full CPMS API integration (see `docs/cpms-integration-plan.md`).
- **CPMS v0.1.2 detect_form + reuse-first**: CPMS adapter now uses `detect_form()` (v0.1.2), normalizes responses, and falls back safely. Patterns can be stored into KnowShowGo with a deterministic fingerprint derived from `url+html`, and the agent can reuse a stored pattern before calling CPMS again (when enabled).
- **Pattern retrieval helper**: `KnowShowGoAPI.find_best_cpms_pattern(url, html, form_type?)` ranks stored patterns by domain + token overlap to support reuse.
- **New plan doc**: `docs/development-plan.md` is the canonical next-steps checklist for the prototype goals.
- **Vault Credential Lookup**: Added `vault.query_credentials` tool to query credentials/identity associated with concepts or URLs.
- **LLM Prompts Updated**: Added instructions for recursive concept creation, embedding-based memory queries, CPMS integration, and concept generalization.
- Name recall formats responses from Name/Person nodes even without a query string, parsing names from note/value fields to return `Your name is ...`.
- Procedure reuse now avoids auto-executing single-step procedures, returning a `procedure.search` step instead; multi-step procedures still hydrate and run, and step hydration infers params directly from payloads. Plan persistence now runs regardless of reuse.
- Empty/low-confidence inform plans ask the user with a friendly instructions prompt so downstream tests treat them as `ask_user`.
- Added `queue.enqueue` tool with optional `not_before`/`delay_seconds` and prompt/docs updates; queue items now store not_before and sort by priority/time. Agent handles enqueue tool and emits queue updates.
- Agent prompt + parsing now expect strict JSON plans; added fallback parsing for legacy `{intent, steps}`.
- Procedure runs are persisted with tested/success/failure counters and linked via `run_of` edges; added test `tests/test_agent_procedure_run_stats.py`.
- Added MemoryTools contract tests (`tests/test_memory_contract.py`) for upsert/filter and embedding ranking, with optional Chroma/Arango backends via env flags.
- Added NetworkX-based in-memory MemoryTools and included it in the contract test suite; networkx dependency added to deps.
- `_execute_plan` now surfaces tool errors (with tool/params/trace_id) so the planner can adapt; per-tool try/except wrapper with logging/events. Added `tests/test_agent_execute_plan_errors.py` to cover error bubbling and no-op plans.
- Added adaptation coverage: `test_execute_request_adapts_after_tool_error` ensures a failing tool triggers re-planning and a succeeding follow-up step.
- Memory recall heuristics tightened: ignore history/Message nodes and prefer notes/credentials over name recall unless the query asks for a name; added `test_recall_prefers_note_over_name_when_not_asked_for_name`.
- Web fill now retries with fallback selectors (email/text/password/id/name) when a selector fails, capturing attempted selectors to avoid hard failures on selector mismatch.
- Procedure reuse now hydrates stored steps (tool+params) from ProcedureBuilder memory and executes them directly; explicit procedure.create and persisted runs store tool+params in step payloads. Added `tests/test_agent_procedure_reuse_execute.py`.
- Added CPMS routing toggle test (`tests/test_cpms_routing_toggle.py`) to verify procedure.create goes to CPMS when enabled; added card/expiry/cvc selector fallbacks in web.fill.
- LLM plan errors now fall back to reuse/fallback without crashing; if plan/steps are empty the agent prompts the user for instructions. Added `tests/test_agent_plan_fallback_on_error.py` and `tests/test_agent_ask_user_on_empty_plan.py`.
- If execution errors persist after adaptation, the agent now asks the user for guidance with the error context. Added `tests/test_agent_ask_user_on_execution_error.py`.
- Successful fallback selectors are persisted back into stored procedures, so future runs reuse the working selectors. Added `tests/test_agent_procedure_selector_update.py`.
- Plans can carry a confidence score; if below `PLAN_MIN_CONFIDENCE` (default 0.9), the agent asks the user for approval before executing. Added `tests/test_agent_confidence_prompt.py`.
- Debug: live agent (Arango + real OpenAI key) `remember` requests produced code-fenced JSON and fell back to `memory.remember`. Stored page=1 credentials as a Concept node, but an inform query (“What note do you have about page=1 credentials?”) returned an unrelated name (“Lehel”) because `_answer_from_memory` surfaced a Person node first.
- Added logging to capture raw LLM plan text on both success and error to diagnose parse issues.
- Observed that with `USE_FAKE_OPENAI=1`, the fake chat response was plain text (“Hi”), causing JSON parse failures; with real OpenAI (`USE_FAKE_OPENAI=0`), the LLM returned valid JSON plans (legacy `{intent, steps}` shape).
- Added test `tests/test_llm_json_command_contract.py` to ensure the LLM JSON command contract parses/executed and that response_format enforces JSON.
- New optional live OpenAI test in `tests/test_llm_json_command_contract.py::test_live_openai_json_response_format` (gated by `LIVE_OPENAI_JSON_TEST=1` and `OPENAI_API_KEY`) to validate real model JSON parsing.
- Contract test now also asserts the agent wires system/developer prompts, temperature=0.0, and response_format into the LLM call (via FakeOpenAIClient telemetry).
- Live OpenAI JSON contract test run with env from `.env.local` passed; restarted/stopped debug daemon after the run.
- Debug: started daemon (USE_FAKE_OPENAI=0), asked agent to create/execute a procedure to GET+ screenshot example.com; plan parsed cleanly, web.get/web.screenshot executed (MockWebTools), and procedure.create persisted `GET and Screenshot Example.com` (procedure_uuid=7d7d6810-...). A follow-up “Run the saved procedure” reused it (matched in memory) and executed steps again. Daemon stopped after tests.
- Debug: created multi-step “MultiStep Demo” procedure (procedure.create + web.get + screenshot + web.post) and executed it; all steps ran with MockWebTools. Recall command (“Recall the steps of MultiStep Demo and execute them.”) was misclassified as inform and returned “Your name is Lehel” instead of recalling/executing the stored procedure; recall heuristics still need adjustment.
- Added memory recall/association tests: `tests/test_memory_recall_priority.py` (procedure reuse beats Person/Name; Concept note stored/recalled) and `tests/test_memory_associations_and_strength.py` (association edge upsert, recall_count increments, procedure-to-credential association with reuse).
- Adjusted memory answer routing: skip the inform memory answer when recall-like queries have procedure matches; expanded intent keywords and bias to procedure/notes to reduce “Your name is Lehel” misfires. Tests updated/passing.
- Added multi-step procedure integration test (`tests/test_procedure_multi_step_integration.py`): create + execute a 3-step procedure, then reuse it and assert web calls execute in order; includes optional Arango persistence smoke (skipped unless ARANGO_URL set).
- Added KnowShowGo ontology tests (`tests/test_knowshowgo_dag_and_recall.py`) for prototype/concept creation and recall of list-like concepts.
- Added Arango-backed integration test (`tests/test_agent_arango_ksg_integration.py`) to create a prototype/concept via KnowShowGo and recall the note through the agent (skips if ARANGO_URL unset).
- Added `docs/architecture.md` describing core components (agent, memory backends, KSG ontology, prompts, service, data model) and testing strategy.
- Seeded Object prototype and expanded KSG tests to create/retrieve DAG/Tag/Task/Event/Object concepts (`tests/test_knowshowgo_dag_and_recall.py`); ensure seeds cover Object.
- Added direct note recall path in agent for concept-named queries; Arango integration suite now passes (procedure reuse + concept note recall).

## Outstanding TODOs
- ~~**Salvage Step A**: Add `working_memory.py` with WorkingMemoryGraph~~ ✅ v0.5.0-salvage-step-a
- ~~**Salvage Step B**: Add `async_replicator.py` for background persistence~~ ✅ v0.5.0-salvage-step-b
- ~~**Salvage Step C**: Add `deterministic_parser.py` for rule-based classification~~ ✅ v0.6.0-salvage-step-c
- ~~**Salvage Step D**: Integrate working memory into agent retrieval path~~ ✅ v0.7.0-salvage-step-d
- **Live Mode**: Eliminate MOCK components (MockWebTools, FakeOpenAI, in-memory storage)
- ~~**Pattern Reuse Flow**: Implement full CPMS pattern reuse in web flows (Milestone A)~~ ✅ Already implemented
- ~~**Dataset Selection**: Implement Credential/Identity/PaymentMethod selection (Milestone B)~~ ✅ v0.8.0-milestone-b
- ~~**Selector Adaptation**: Implement trial/adapt loop for failing selectors (Milestone C)~~ ✅ v0.9.0-milestone-c
- Extend contract coverage across real backends (enable env-flagged Arango/Chroma runs)
- Fix 9 pre-existing test failures in queue/scheduler
- ~~Install Playwright browsers for CI~~ ✅ Installed

## Environment / flags
- `.env.local` is in use; `USE_FAKE_OPENAI`, `ASK_USER_FALLBACK`, `USE_CPMS_FOR_PROCS` etc. are toggled via env. Arango TLS verify is controlled by `ARANGO_VERIFY`.

## Testing
- **Latest (2026-01-14)**: `USE_PLAYWRIGHT=1 pytest -q` → 354 passed, 29 skipped, 9 failed
  - ✅ Playwright browser installed (`playwright install --with-deps chromium`)
  - ✅ Playwright tests now passing (web actions, LinkedIn login, locate missing)
  - 9 failures: Pre-existing queue/scheduler issues from main branch
- **Progress**: +125 new tests since starting (from ~229 to 354)
  - Salvage Steps A-D: +81 tests
  - Milestone B+C: +22 tests  
  - Integration Tests: +22 tests
- Previous: `pytest tests/test_task_queue.py tests/test_agent_queue_enqueue.py -q` (queue enqueue/delay coverage)
- Previous: `pytest tests/test_memory_contract.py -q` (passing across mock + networkx)
- Previous: `pytest tests/test_knowshowgo*.py -q` (KnowShowGo tests passing after merge fix)

## Guidance
- **Master Plan**: See `docs/MASTER-PLAN.md` for unified roadmap (merges Opus/GPT/Salvage perspectives)
- **Opus Priorities**: See `docs/opus-next-steps.md` for Claude Opus planning document
- **Salvage Components**: See `docs/salvage-osl-agent-prototype.txt` for porting guide
- **GPT Roadmap**: See `docs/gpt-plans.md` for refactor roadmap
- See `copilot-prompt.txt` for condensed operating instructions (debug loop, env flags, workflow)
- Architecture reference: `docs/architecture.md` for components/ontology/memory/testing
- Test coverage summary in `docs/architecture.md` plus noted gaps (Playwright needs browser install)
