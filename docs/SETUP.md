# Setup Guide

## Prerequisites

- **Python 3.12+**
- **Poetry** (recommended) or pip
- **OpenAI API key**

## Quick Start

```bash
# Clone and install
git clone <repo>
cd osl-agent-prototype
poetry install
poetry run playwright install --with-deps chromium

# Configure
cp .env.example .env.local
# Edit .env.local:
OPENAI_API_KEY=sk-your-key-here

# Test
poetry run pytest

# Run
poetry run python -m src.personal_assistant.service
```

## Environment Variables

Create `.env.local` in project root:

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional - Persistent Memory (ArangoDB)
ARANGO_URL=https://your-instance.arangodb.cloud:8529
ARANGO_DB=osl-agent
ARANGO_USER=root
ARANGO_PASSWORD=...

# Optional - Features
USE_PLAYWRIGHT=1           # Enable web automation
USE_CPMS_FOR_FORMS=1       # Enable CPMS form detection
```

## Running

### CLI Mode
```bash
poetry run python main.py
```

### HTTP Service
```bash
poetry run python -m src.personal_assistant.service
# → http://localhost:8000/ui
```

### Debug daemon + live flow smoke test
```bash
# Start the agent with log capture
./scripts/debug_daemon.sh start

# Run a live form flow (requires real LLM + Playwright for full fidelity)
chmod +x ./scripts/run_live_form_flow.sh
./scripts/run_live_form_flow.sh

# Run a live multi-step survey flow
chmod +x ./scripts/run_live_survey_flow.sh
SURVEY_URL="https://your-survey-url" ./scripts/run_live_survey_flow.sh
```

This flow:
1) Stores credentials
2) Creates a login procedure (DAG schema)
3) Executes via `dag.execute` to queue each step
4) Asks the agent to recite the stored steps

### Tests
```bash
# All tests
poetry run pytest

# Specific file
poetry run pytest tests/test_agent.py -v

# With coverage
poetry run pytest --cov=src
```

## Memory Backends

| Backend | When to Use |
|---------|-------------|
| NetworkX (default) | Testing, development |
| ChromaDB | Local persistence |
| ArangoDB | Production, cloud |

The agent auto-detects available backends.

## Troubleshooting

**OpenAI errors**: Check `OPENAI_API_KEY` is set correctly

**Playwright errors**: Run `poetry run playwright install --with-deps chromium`

**Import errors**: Run `poetry install` again

**Test failures**: Check `.env.local` has correct values

## Procedure Graph Schema

For control-flow procedures (loops, conditionals, subprocedures), see:
`docs/PROCEDURE-GRAPH-SCHEMA.md`

## Multi-step survey flow (sessioned web tools)

The `survey.fill_multi_step` tool uses an optional `session_id` to keep browser
state across pages. When using Playwright, provide a fixed `session_id` for the
entire flow and call `web.close_session` once finished.
