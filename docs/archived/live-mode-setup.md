# Live Mode Setup Guide

**Goal**: Run the OSL Agent with real services (no MOCK components) for live testing and debugging.

## MOCK Components and Their Replacements

| Mock Component | Location | Real Replacement | Enable Flag |
|----------------|----------|------------------|-------------|
| `FakeOpenAIClient` | `openai_client.py` | OpenAI API | `USE_FAKE_OPENAI=0` + `OPENAI_API_KEY` |
| `MockWebTools` | `mock_tools.py` | `PlaywrightWebTools` | `USE_PLAYWRIGHT=1` |
| `MockMemoryTools` | `mock_tools.py` | `ArangoMemoryTools` | `ARANGO_URL` set |
| `MockCalendarTools` | `mock_tools.py` | (future) Google Calendar | N/A |
| `MockTaskTools` | `mock_tools.py` | (future) Todoist/etc | N/A |
| `MockContactsTools` | `mock_tools.py` | (future) Contacts API | N/A |
| `MockShellTools` | `mock_tools.py` | `RealShellTools` | Already default |

## Required Environment Variables

### Essential for Live Mode
```bash
# OpenAI (required)
USE_FAKE_OPENAI=0
OPENAI_API_KEY=sk-...

# Playwright (required for web automation)
USE_PLAYWRIGHT=1

# Arango (required for persistent memory)
ARANGO_URL=https://your-arango-instance.arangodb.cloud:8529
ARANGO_DB=osl-agent
ARANGO_USER=root
ARANGO_PASSWORD=...
ARANGO_VERIFY=true
```

### Optional Feature Flags
```bash
# CPMS pattern detection
USE_CPMS_FOR_FORMS=1
KSG_PATTERN_REUSE_MIN_SCORE=2.0

# Debug/development
LOG_LEVEL=debug
ASK_USER_FALLBACK=1
```

## Setup Steps

### 1. Install Dependencies
```bash
# Install Python dependencies
poetry install

# Install Playwright browsers (CRITICAL for web automation)
poetry run playwright install --with-deps chromium
```

### 2. Create `.env.local`
```bash
cp .env.example .env.local
# Edit .env.local with your real credentials
```

### 3. Verify Arango Connection
```bash
# Run Arango connection test
poetry run pytest tests/test_arango_connection.py -v
```

### 4. Verify OpenAI Connection
```bash
# Run OpenAI live test (requires LIVE_OPENAI_JSON_TEST=1)
LIVE_OPENAI_JSON_TEST=1 poetry run pytest tests/test_openai_live.py -v
```

### 5. Start the Service
```bash
# Start in live mode
poetry run agent-service

# Or with explicit env vars
USE_FAKE_OPENAI=0 USE_PLAYWRIGHT=1 poetry run agent-service
```

### 6. Test with curl
```bash
# Send a test request
curl -sS http://localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"Log into linkedin.com"}'

# Check logs
tail -f log_dump.txt
```

## Debug Loop

1. Start daemon: `poetry run agent-service`
2. Send request: `curl ...`
3. Check logs: `cat log_dump.txt`
4. Clear logs: `> log_dump.txt`
5. If bug: stop daemon, fix, restart
6. Repeat

## Playwright-Specific Tests

```bash
# Run with Playwright (requires browser installation)
USE_PLAYWRIGHT=1 poetry run pytest tests/test_web_playwright_actions.py -v

# Run LinkedIn login flow test
USE_PLAYWRIGHT=1 poetry run pytest tests/test_web_linkedin_login_flow.py -v
```

## Troubleshooting

### "Playwright browsers not installed"
```bash
poetry run playwright install --with-deps chromium
```

### "OpenAI API key not set"
```bash
export OPENAI_API_KEY=sk-...
# Or add to .env.local
```

### "Arango connection failed"
- Check ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD
- Verify TLS: `ARANGO_VERIFY=true` for production, `false` for self-signed certs

### "CPMS not installed"
```bash
pip install cpms-client
```

## Service Configuration File

The service reads from `config/default.yaml`:

```yaml
# Override via environment variables
use_fake_openai: false
use_playwright: true
embedding_backend: openai  # or "local"

arango:
  url: ${ARANGO_URL}
  db: ${ARANGO_DB}
  user: ${ARANGO_USER}
  password: ${ARANGO_PASSWORD}
```

## Next Steps After Live Mode Setup

1. **Test Pattern Learning**: Visit a login form, let agent detect and store pattern
2. **Test Pattern Reuse**: Return to same form, verify reuse without re-detection
3. **Test Credential Recall**: Store credentials, verify autofill works
4. **Test LinkedIn Flow**: Complete login flow using learned patterns

---

*See `docs/development-plan.md` for milestone details.*
