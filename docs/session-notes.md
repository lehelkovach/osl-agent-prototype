# Session Notes (persistent context)

## Current goals
- Standardize the memory adapter boundary (`MemoryTools`) so backends (Arango, Chroma, in-memory) are swappable and contract-tested.
- Keep procedure planning JSON-first: LLM returns `{"commandtype": ..., "metadata": {...}}` with procedure steps; execute and persist run stats + links.

## Recent changes
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
- Extend contract coverage across real backends (enable env-flagged Arango/Chroma runs) and align behaviors where they diverge.
- Consider beefing up NetworkX/Mock backends to mirror DB edge queries if needed.
- Adjust memory recall heuristics so inform queries prefer the most relevant Concept/note over Person/Name nodes.
- Decide on dual-write/strength-weighting later; defer until core abstraction is stable.

## Environment / flags
- `.env.local` is in use; `USE_FAKE_OPENAI`, `ASK_USER_FALLBACK`, `USE_CPMS_FOR_PROCS` etc. are toggled via env. Arango TLS verify is controlled by `ARANGO_VERIFY`.

## Testing
- Last run: `pytest tests/test_task_queue.py tests/test_agent_queue_enqueue.py -q` (queue enqueue/delay coverage; passing).
- Last run: `pytest tests/test_memory_contract.py -q` (passing across mock + networkx).
- Additional recent: `pytest tests/test_llm_json_command_contract.py -q` (pass/skip live), `pytest tests/test_memory_recall_priority.py -q`, `pytest tests/test_memory_associations_and_strength.py -q`.
- New: `pytest tests/test_procedure_multi_step_integration.py -q` (pass, Arango path skipped), `pytest tests/test_knowshowgo_dag_and_recall.py -q`, `pytest tests/test_agent_arango_ksg_integration.py -q` (passes with `.env.local`).
- Latest: `pytest tests/test_agent_execute_plan_errors.py -q` (passes; includes adaptation replan path).
- Latest: `pytest tests/test_memory_recall_priority.py -q` (passes; includes name-vs-note preference fix).
- Latest: `pytest tests/test_agent_execute_plan_errors.py -q` (post-fill-fallback tweak; passing).
- Latest: `pytest tests/test_agent_procedure_reuse_execute.py tests/test_agent_execute_plan_errors.py -q` (passing).

## Guidance
- See `copilot-prompt.txt` for condensed operating instructions for future sessions (including how to keep `docs/session-notes.md` current, debug loop: run daemon, send curl requests, read/clear `log_dump.txt`, fix/restart on errors, and commit after completing goals).
- Architecture reference: `docs/architecture.md` for components/ontology/memory/testing; re-read it alongside `copilot-prompt.txt` and this file when resuming work.
- Test coverage summary lives in `docs/architecture.md` (memory/recall, procedures, LLM plan contract, KSG tools, forms/credentials, Arango smoke) plus noted gaps (no real Playwright/Appium, shell executor, etc.).
