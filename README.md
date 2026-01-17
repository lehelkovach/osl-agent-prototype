# OSL Agent Prototype

Personal assistant agent with a **learning memory system**. Learns procedures from conversation, transfers patterns between contexts, and auto-generalizes from experience.

## What It Does

- **Learns**: Store procedures and patterns from chat
- **Recalls**: Find similar procedures via embedding similarity
- **Executes**: Run multi-step procedures (DAG execution)
- **Adapts**: Update procedures when they fail
- **Generalizes**: Auto-create abstract patterns from exemplars
- **Transfers**: Apply learned patterns to novel situations

## Key Features

| Feature | Description |
|---------|-------------|
| **KnowShowGo** | Fuzzy ontology knowledge graph with pattern evolution |
| **Form Learning** | Learn form patterns, transfer to similar forms |
| **Procedure DAGs** | Multi-step procedures as directed acyclic graphs |
| **Centroid Embeddings** | Concepts evolve toward actual usage |
| **Web Automation** | Playwright-based browser control |
| **Safe Shell** | Sandboxed command execution with rollback |

## Quick Start

```bash
# Install
poetry install
poetry run playwright install --with-deps chromium

# Configure
cp .env.example .env.local
# Edit .env.local with your OPENAI_API_KEY

# Test
poetry run pytest

# Run
poetry run python -m src.personal_assistant.service
```

See [docs/SETUP.md](docs/SETUP.md) for full setup guide.

## Architecture

```
User Request
    ↓
┌─────────────────────────────────────┐
│         PersonalAssistantAgent       │
│  ┌─────────┐  ┌─────────┐          │
│  │ Classify │→│  Plan   │→ Execute  │
│  │  Intent  │  │  (LLM)  │          │
│  └─────────┘  └─────────┘          │
└─────────────────────────────────────┘
    ↓               ↓
┌─────────┐  ┌─────────────────┐
│ Memory  │  │   KnowShowGo    │
│ (Arango │  │ Pattern Evolution│
│  Chroma)│  │ Auto-Generalize │
└─────────┘  └─────────────────┘
```

## Project Structure

```
src/personal_assistant/
├── agent.py           # Core agent loop
├── knowshowgo.py      # Fuzzy ontology + pattern evolution
├── form_filler.py     # Form pattern learning
├── procedure_manager.py # JSON → DAG procedures
├── safe_shell.py      # Sandboxed shell execution
├── web_tools.py       # Playwright web automation
└── ...

docs/
├── MASTER-PLAN.md     # Roadmap and status
├── SETUP.md           # Setup guide
├── KNOWSHOWGO-VISION.md # KnowShowGo future
├── KNOWSHOWGO-SERVICE-HANDOFF.md # For standalone service
└── session-notes.md   # Development log
```

## Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_knowshowgo_pattern_evolution.py -v
```

**592+ tests** covering agent, KnowShowGo, form filling, procedures, and more.

## Documentation

| Doc | Purpose |
|-----|---------|
| [MASTER-PLAN.md](docs/MASTER-PLAN.md) | Current status, roadmap, goals |
| [SETUP.md](docs/SETUP.md) | Installation and configuration |
| [KNOWSHOWGO-VISION.md](docs/KNOWSHOWGO-VISION.md) | KnowShowGo future and market |
| [KNOWSHOWGO-SERVICE-HANDOFF.md](docs/KNOWSHOWGO-SERVICE-HANDOFF.md) | For building standalone service |

## Tech Stack

- **Python 3.12+**
- **OpenAI** - LLM for planning and embeddings
- **ArangoDB/ChromaDB** - Persistent memory
- **Playwright** - Browser automation
- **FastAPI** - HTTP service
- **NetworkX** - In-memory graph (testing)

## License

MIT
