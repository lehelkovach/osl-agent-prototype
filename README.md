# OSL Agent Prototype

Lightweight personal assistant agent that plans with OpenAI, executes tool calls (tasks, calendar, contacts, web, shell), and persists semantic memory in ChromaDB or ArangoDB with a small KnowShowGo (KSG) ontology.

## Purpose & Goals
- Run a loop that classifies intent, searches semantic memory, plans with an LLM, executes tool calls, and writes back results.
- Keep knowledge in a graph + embeddings store (Arango/Chroma) with seeded prototypes (Task, Event, DAG, List, Tag, etc.) for reuse and RAG.
- Support asynchronous-style event emission, task queueing, and time-based rules (scheduler) so the agent can react to conditions.
- Provide web/vision hooks (DOM HTML + screenshot + bounding-box queries) and shell commandlets for automation planning.
- Keep implementations swappable (mock vs. real) for fast iteration and testing; expose a simple HTTP UI for chat + logs.

## Architecture
```mermaid
flowchart TB
    User --> Service["FastAPI Service / CLI"]
    Service --> Agent["PersonalAssistantAgent\n(plan + execute)"]
    Agent -->|LLM chat/embeddings| OpenAI
    Agent --> Memory["MemoryTools (ArangoDB/ChromaDB)"]
    Memory --> KSG["KnowShowGo Store\n(seeds prototypes/tags)"]
    Agent --> Queue["TaskQueueManager"]
    Agent --> Scheduler["Scheduler (time rules)"]
    Scheduler --> Queue
    Agent --> Tasks["Task/Calendar/Contacts Tools"]
    Agent --> Web["WebTools\n(DOM fetch + screenshot)"]
    Agent --> Shell["ShellTools (staged)"]
    Agent --> Docs["VersionedDocumentStore"]
    Agent --> Events["EventBus"]
    Events --> Logs["Logging + history streams"]
    Service --> UI["/ui chat + log view"]
```

## Components
- `src/personal_assistant/agent.py`: Core loop (intent → memory search → LLM JSON plan → tool execution → memory upserts + queue enqueue).
- `src/personal_assistant/chroma_memory.py` / `arango_memory.py`: `MemoryTools` backed by ChromaDB or ArangoDB (graph + embeddings).
- `src/personal_assistant/ksg.py`: Minimal KSG store that seeds property defs, prototypes (Object, List, DAG, Procedure, Tag, etc.), and seed objects (self/assistant/home/work/language).
- `src/personal_assistant/task_queue.py`: Prioritized queue with enqueue/update operations that also persist to memory.
- `src/personal_assistant/scheduler.py`: Time-rule evaluator that enqueues tasks (optionally with DAG payloads) and persists them with embeddings.
- `src/personal_assistant/versioned_document.py`: Versioned JSON metadata store linked to concepts with embeddings and version chains.
- `src/personal_assistant/web_tools.py`: DOM fetch + screenshot + (mocked) bounding-box locator for vision-guided clicks/xpaths.
- `src/personal_assistant/prompts.py`: System/developer prompts that define the planning contract and tool catalog (tasks, calendar, contacts, web, shell, queue).
- `src/personal_assistant/service.py`: FastAPI service exposing `/health`, `/chat`, `/history`, `/logs`, and a lightweight `/ui` for chat + log viewing.
- `src/personal_assistant/logging_setup.py`: Structured logging configured for console and JSON log streaming to the service.
- `src/personal_assistant/tools.py`, `mock_tools.py`: Abstract tool interfaces + in-memory mocks for fast testing.
- `src/personal_assistant/cpms_adapter.py`: Thin wrapper around the published `cpms-client` package (no local cpms repo needed).
- `main.py`: Demo entrypoint that prefers Arango, then Chroma, then in-memory mock.

## Setup (Poetry)
0) Prereqs: Python + venv support + Poetry (recommended)
   - **Python**: this repo targets Python 3.12+ (`python3 --version`)
   - **Ubuntu/Debian venv requirement** (needed for `pipx`/Poetry to work):
     - `sudo apt-get update && sudo apt-get install -y python3.12-venv`
     - (If you’re not on 3.12 specifically, `sudo apt-get install -y python3-venv` is usually sufficient.)
   - **Install Poetry via pipx** (recommended):
     - `python3 -m pip install --user pipx`
     - `~/.local/bin/pipx install poetry`
     - Ensure it’s on PATH: `export PATH="$HOME/.local/bin:$PATH"`
     - Verify: `poetry --version`

1) Install dependencies with Poetry:
   - `poetry install`
   - **Playwright browsers (required for Playwright-backed tests and web tools)**:
     - `poetry run playwright install --with-deps chromium`
2) Environment (put these in `.env.local` — no quotes):
   - **OpenAI (Plus)**: `OPENAI_API_KEY=your-key`
   - **Claude (Max)**: `ANTHROPIC_API_KEY=your-key`
   - **Gemini (Ultra)**: `GOOGLE_API_KEY=your-key` or `GEMINI_API_KEY=your-key`
   - **Provider selection**: `LLM_PROVIDER=openai|claude|gemini` (default: `openai`)
   - Optional model overrides: `OPENAI_CHAT_MODEL`, `ANTHROPIC_CHAT_MODEL`, `GEMINI_CHAT_MODEL`
   
   See [LLM Provider Setup Guide](docs/llm-providers-setup.md) for detailed configuration.
3) Optional Arango memory:
   - `ARANGO_URL`, `ARANGO_DB`, `ARANGO_USER`, `ARANGO_PASSWORD`
   - `ARANGO_VERIFY` set to a CA bundle path for cloud CAs (do **not** commit certs). Use `false` only for local dev and ccurrently bugged so just dont include it with arango cloud's cert which is
   presently setup in the project.
   - `.env.local` is not committed; populate it locally with your ARANGO_* and OPENAI_* values (the current developer setup has these set there).
4) Optional local embeddings (no OpenAI needed):
   - Run `./scripts/install_local_embedder.sh` once (installs `sentence-transformers`).
   - Set `EMBEDDING_BACKEND=local`; optionally `LOCAL_EMBED_MODEL` (or `config/default.yaml: local_embed_model`) to force a specific model, or `LOCAL_EMBED_DIM` to control the hash-fallback size.
5) Run the demo: `python main.py` (prefers Arango → Chroma at `.chroma/` → in-memory mock).
6) Run tests: `poetry run pytest` (a conftest pins the repo root on `sys.path`; currently 535+ passing tests, env-guarded for Playwright/Arango).
7) Run the HTTP service: `uvicorn src.personal_assistant.service:main --reload` or `poetry run agent-service`. Open `http://localhost:8000/ui` for chat/logs/runs tabs.

## Current State
- **535+ tests passing** with comprehensive coverage
- Agent loop exercises tasks/calendar/contacts/web tools with mock and real backends
- Semantic memory can be Arango or Chroma; KSG seeds property defs, prototypes and seed objects
- **KnowShowGo runs as separate service** (port 8001) or embedded with automatic fallback
- **SafeShellExecutor** provides sandboxed command execution with rollback
- **ProcedureManager** converts LLM JSON to KnowShowGo DAGs
- Time-based scheduler enqueues tasks with optional DAG payloads
- Web automation via Playwright (DOM fetch, screenshot, fill, click)
- FastAPI service streams chat history and event logs; `/ui` renders chat + log panes
- Form pattern learning (login, billing, survey) with answer reuse

## Recent Features

### KnowShowGo Service (Separate Process)
KnowShowGo can run as a separate FastAPI service:
```bash
./scripts/start_knowshowgo_service.sh  # Starts on port 8001
export KNOWSHOWGO_URL=http://localhost:8001  # Agent uses service
```
- `KnowShowGoClient` for HTTP communication
- `MockKnowShowGoClient` for testing
- `KnowShowGoAdapter` for seamless embedded/service switching

### SafeShellExecutor (Sandboxed Commands)
Safe shell execution with rollback:
```python
from src.personal_assistant.safe_shell import create_safe_shell
shell = create_safe_shell()
result = shell.run("echo hello", dry_run=False)
result = shell.run_in_sandbox("touch file.txt")  # Isolated
```
- Command whitelist/blacklist (blocks `rm -rf /`, fork bombs, etc.)
- File change tracking with rollback
- Temporary directory sandboxing

### LLM Procedures as DAGs
Procedures are generated by LLM as JSON and stored as DAGs:
```json
{
  "name": "LinkedIn Login",
  "steps": [
    {"id": "step_1", "tool": "web.get_dom", "params": {...}, "depends_on": []},
    {"id": "step_2", "tool": "web.fill", "params": {...}, "depends_on": ["step_1"]}
  ]
}
```
- `ProcedureManager` validates and converts to KnowShowGo DAG
- Steps stored as nodes with `depends_on` edges
- Searchable by semantic similarity

## Known Gaps / Next Steps
- Flesh out Playwright/Appium flows (HTML + screenshot + vision queries + click/fill) and add end-to-end coverage.
- Push more logic into KSG: materialize more property defs/prototypes (Contact/Message/PreferenceRule), cache flattening, and Arango vector indexes.
- Persist event/log streams to storage and broaden the UI to show live streams + memory/task views.
- Add richer RAG prompts so the agent can synthesize/reuse stored DAG procedures (e.g., LinkedIn recruiter workflows) and learn from prior embeddings.
- Evaluate hosting options for local LLMs: free persistent GPU endpoints are effectively unavailable; small CPU models (4/5-bit 7–8B) are slow on free-tier Oracle/Ampere. Plan for paid hosted GPUs (HF/Together/etc.) or larger self-hosted hardware when moving off OpenAI.
- Comms roadmap: add Twilio (SMS/voice) support and a TTS/STT pipeline. Consider integrating with an Asterisk/voice service API to enable automated outbound calls and logging of call transcripts.
- Web automation roadmap:
  - Use the Playwright-backed WebTools (enable with `USE_PLAYWRIGHT=1`) so the exposed web commands in prompts actually hit live pages: screenshot, get_dom, fill, click, wait_for. Capture paths land in `/tmp/agent-captures` by default.
  - Teach the agent to derive/store/reuse procedures for logins and form fills: serialize successful steps as DAG/Procedure nodes, embed fingerprints (labels/placeholders/types/layout), and reuse via RAG when confidence ≥0.8.
  - Incorporate CPMS for form element matching: build observations from Playwright snapshots, call CPMS match_pattern, and map assignments to selectors before filling.
  - Add scheduler/queue integration: generated procedures should enqueue as tasks and execute step-by-step with feedback; failed steps trigger patch/retry and updated procedure storage.
  - Vault/KnowShowGo: remember formdata/credentials provided in chat; on new login tasks, query vault first, then plan/fill/submit; store updated form exemplars and selectors on success.

## Development Roadmap / Not Yet Implemented
- Production-grade Playwright/Appium flows with retries/timeouts and real vision-assisted locators; live end-to-end tests beyond fixtures.
- Sandbox/confirmation-backed shell executor (the current real executor runs commands directly).
- Secrets/vault hardening (encryption at rest, scoped access) beyond the current Credential/FormData prototypes.
- Ontology workbench UI for browsing/editing concepts, tags, and prototypes; richer run replay with embedded screenshots/DOM.
- Native Arango vector indexes/AQL scoring (currently client-side cosine) and cache flattening for fast queries.
- Live CPMS integration test hitting a real endpoint (adapter is wired, but test falls back to fake without env).
- Deployment hardening (Docker, auth/SSO, metering/billing hooks).

## Version History (high level)
- Added KSG seeds: DAG/List/Queue/Procedure/Step/Tag, plus vault/credential/identity/payment/form data prototypes and properties.
- Added ProcedureBuilder (create/search) with procedure reuse in agent planning.
- Added CPMS adapter and tools; agent supports cpms.* calls.
- Added form autofill (form.autofill) backed by stored FormData/Identity/Credential/PaymentMethod.
- Added real shell executor (staged vs execute) alongside mock.
- Added Playwright captures for web actions and run replay endpoints/UI (chat/logs/runs tabs).
- Added semantic memory “remember” tool with embedding enforcement and credential recall tests.
