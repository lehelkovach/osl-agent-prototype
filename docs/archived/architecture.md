# Architecture Overview

## Core Components
- **PersonalAssistantAgent (`src/personal_assistant/agent.py`)**: Orchestrates the execution loop (intent classification → RAG retrieval → plan generation via LLM → tool execution → persistence). Handles procedure persistence/run stats, memory recall heuristics, and event emission.
- **Memory Backends (`MemoryTools`)**: Swappable adapters for semantic storage/retrieval.
  - `MockMemoryTools` (in-memory dicts) for unit tests.
  - `NetworkXMemoryTools` (in-memory graph) for DAG-like tests.
  - `ArangoMemoryTools` (ArangoDB) for persistent graph storage.
  - `ChromaMemoryTools` (Chroma) for vector-store backed memory.
  - Contract tests: `tests/test_memory_contract.py`, `tests/test_memory_recall_priority.py`, `tests/test_memory_associations_and_strength.py`.
- **KnowShowGo (KSG) Ontology**:
  - `ksg.py`: seeds prototypes (`Object`, `List`, `DAG`, `Procedure` inherits `DAG`, `Queue` inherits `List`, `Vault` + Credential/Identity/PaymentMethod/FormData inherit Vault), property defs, and default objects. Inheritance edges (`inherits_from`) encode hierarchy.
  - `knowshowgo.py`: API to create prototypes/concepts and versioned edges.
  - Tests: `tests/test_ksg_seed.py`, `tests/test_knowshowgo_dag_and_recall.py`, `tests/test_agent_ksg_prototype_concept.py`.
- **Procedure Builder (`procedure_builder.py`)**: Persists Procedure + Step nodes, dependency edges; used by the agent and tests. Tracks embeddings via provided `embed_fn`.
- **Web/Forms Tools**: `web_tools.py`, `form_filler.py`, plus mocks for testing.
- **Prompts (`prompts.py`)**: System/developer prompts instruct the LLM to emit strict JSON plans (commandtype/metadata or intent/steps) and describe available tools, including KSG prototype/concept creation.
- **Service Layer (`service.py`)**: FastAPI app + uvicorn runner; uses `.env.local` for config (Arango, OpenAI, embedding backend, CPMS, Playwright flags).

## Planning & Execution
- LLM plans are requested with `response_format={"type": "json_object"}` and must emit strict JSON (intent/steps or commandtype/metadata). Fallback parsing for legacy shapes exists.
- Plan execution dispatches tool calls (`web.*`, `tasks.*`, `calendar.*`, `procedure.create/search`, `ksg.create_prototype/concept`, etc.). Results and events are logged; procedure runs are persisted with success/failure stats and `run_of` edges.
- Memory recall heuristics: for recall-like queries, procedures/notes are preferred; Person/Name shortcuts are skipped when recall keywords/procedure matches exist.

## Testing Strategy
- **Unit/Contract**: Memory adapter contract, procedure stats/linking, LLM JSON contract (`tests/test_llm_json_command_contract.py`), ontology seed/recall.
- **Integration (mocked)**: Multi-step procedure creation/reuse (`tests/test_procedure_multi_step_integration.py`), associations/credential links, KSG prototype/concept via agent.
- **Integration (Arango)**: `tests/test_agent_arango_ksg_integration.py` (creates concept/procedure in Arango and recalls/reuses; skips without `ARANGO_URL`). Requires valid TLS/verify settings (see `.env.local`).

## Operator Reminder
- When resuming work, re-read `copilot-prompt.txt` and `docs/session-notes.md` to regain scope, goals, flags, and recent changes.
- Consult this architecture doc and README before changing behavior; follow the debug loop (daemon, curl, `log_dump.txt` read/clear) for live checks.

## Test Coverage (what is exercised)
- **Memory/Recall**: contract search/upsert (`tests/test_memory_contract.py`), recall priority (procedures/notes vs name), associations/strength counters (`tests/test_memory_recall_priority.py`, `tests/test_memory_associations_and_strength.py`), KSG seeds/inheritance and typed concepts (Object/DAG/Task/Event/Tag) in `tests/test_ksg_seed.py`, `tests/test_knowshowgo_dag_and_recall.py`.
- **Procedures**: run stats + `run_of` edges (`tests/test_agent_procedure_run_stats.py`), multi-step creation/reuse/order (`tests/test_procedure_multi_step_integration.py`), Arango procedure reuse in `tests/test_agent_arango_ksg_integration.py`.
- **LLM Plan Contract**: JSON-only plan parsing/enforcement, prompt wiring (`tests/test_llm_json_command_contract.py` with optional live OpenAI).
- **KSG Tools via Agent**: prototype/concept creation (`tests/test_agent_ksg_prototype_concept.py`).
- **Queue/Scheduling**: priority queue ordering, delay/not_before enqueues, scheduler-triggered tasks (`tests/test_task_queue.py`, `tests/test_agent_scheduler_queue.py`, `tests/test_scheduler.py`, `tests/test_agent_queue_enqueue.py`).
- **Forms/Credentials (mocked)**: form autofill from stored FormData/Identity/Credential/PaymentMethod (`tests/test_agent_form_autofill.py`), webform fills/clicks via MockWebTools (`tests/test_agent_webform_dynamic.py`), credential recall (`tests/test_agent_credential_recall.py`).
- **Arango**: connection/AQL smoke (`tests/test_arango_connection.py`, `tests/test_arango_aql_queries.py`, `tests/test_arango_memory.py`), agent concept note recall/procedure reuse (`tests/test_agent_arango_ksg_integration.py`).
- **Other agent flows**: scheduler/queue, shell mock, CPMS routing, web DOM/screenshot (mock) in respective tests.

Gaps: no real Playwright/Appium E2E, no live shell executor tests, limited CPMS live coverage, limited adversarial recall/intent cases, no real-world form HTML fixtures beyond simple mocks.

## Configuration
- `.env.local` controls OpenAI keys/models, Arango connection (`ARANGO_URL/DB/USER/PASSWORD/VERIFY`), embedding backend (local vs OpenAI), USE_FAKE_OPENAI, USE_PLAYWRIGHT, USE_CPMS_FOR_PROCS, etc.
- Scripts:
  - `scripts/debug_daemon.sh`: start/stop/status agent daemon; logs to `log_dump.txt`; supports STOP_ON_ERROR, log snapshots.
  - `scripts/log_summary.py`: summarize logs.
  - `scripts/install_arango_ca.sh`: helper for Arango TLS CA install.

## Data Model (Nodes/Edges)
- **Node**: `{uuid, kind, labels, props, llm_embedding?, status}`. Common kinds: Concept, Prototype, Procedure, Step, ProcedureRun, Message, Person, Name, Credential, etc.
- **Edge**: `{uuid, kind:"edge", from_node, to_node, rel, props}`. Common rels: `has_step`, `depends_on`, `run_of`, `instantiates`, `inherits_from`, `associated_with`, `uses_credential`.

## Known Behaviors/Heuristics
- Recall bias: queries with “recall/steps/procedure/run/execute/note/concept” prioritize procedures or notes over Person/Name; inform answers are skipped if reuse path applies.
- Procedure persistence: unless the plan explicitly includes `procedure.create`, executed plans are stored as Procedures with tested/success/failure counters and linked runs (`run_of`).

## How to Extend
- Add new tools: expose in agent `_execute_plan`, document in `prompts.py`.
- New memory backend: implement `MemoryTools` (search/upsert), add to contract tests, wire into `service.py` selection.
- Ontology extension: seed new prototypes/property defs in `ksg.py` and add tests for inheritance/recall.
