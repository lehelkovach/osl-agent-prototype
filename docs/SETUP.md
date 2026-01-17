# Setup Guide

## Quick Start

```bash
# 1. Install dependencies
poetry install

# 2. Install Playwright browsers
poetry run playwright install --with-deps chromium

# 3. Copy environment template
cp .env.example .env.local

# 4. Edit .env.local with your keys (see below)

# 5. Run tests
poetry run pytest

# 6. Start service
poetry run python -m src.personal_assistant.service
```

---

## Environment Variables

Create `.env.local` with:

```bash
# === OpenAI (Required) ===
OPENAI_API_KEY=sk-...
USE_FAKE_OPENAI=0

# === ArangoDB (Optional - for persistent memory) ===
ARANGO_URL=https://your-instance.arangodb.cloud:8529
ARANGO_DB=osl-agent
ARANGO_USER=root
ARANGO_PASSWORD=...
ARANGO_VERIFY=true

# === Features ===
USE_PLAYWRIGHT=1
USE_CPMS_FOR_FORMS=1

# === KnowShowGo Service (Optional) ===
# KNOWSHOWGO_URL=http://localhost:8001
```

---

## API Keys

### OpenAI
1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Add to `.env.local` as `OPENAI_API_KEY`

### ArangoDB (Optional)
1. Create free account at https://cloud.arangodb.com
2. Create database
3. Get connection details from dashboard
4. Add to `.env.local`

---

## Running Modes

| Mode | Config | Use Case |
|------|--------|----------|
| **Mock** | `USE_FAKE_OPENAI=1` | Fast testing, no API costs |
| **Live** | `USE_FAKE_OPENAI=0` | Real LLM responses |
| **Full** | + `ARANGO_URL` set | Persistent memory |

---

## Troubleshooting

### Playwright not working
```bash
poetry run playwright install --with-deps chromium
```

### ArangoDB SSL errors
```bash
# In .env.local
ARANGO_VERIFY=false
```

### Import errors
```bash
poetry install
```
