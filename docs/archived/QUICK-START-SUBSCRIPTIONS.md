# Quick Start: Adding Your Subscriptions

## For Cursor IDE (Chat Interface - So I Can Use Your Subscriptions!)

### Step 1: Open Cursor Settings
- Press `Ctrl+,` (or `Cmd+,` on Mac)
- Or: `File > Preferences > Settings`

### Step 2: Add API Keys

Search for "API" in settings and add:

1. **OpenAI API Key**
   - Setting: Search for `OpenAI API Key` or `cursor.openaiApiKey`
   - Get key: https://platform.openai.com/api-keys
   - Paste your key (starts with `sk-`)
   - Models: `gpt-4o`, `gpt-4-turbo`, `gpt-4`

2. **Anthropic API Key** (Claude)
   - Setting: Search for `Anthropic API Key` or `Claude API Key`
   - Get key: https://console.anthropic.com/
   - Paste your key (starts with `sk-ant-`)
   - Models: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`

3. **Google API Key** (Gemini)
   - Setting: Search for `Google API Key` or `Gemini API Key`
   - Get key: https://makersuite.google.com/app/apikey
   - Paste your key
   - Models: `gemini-1.5-pro`, `gemini-1.5-ultra`

### Step 3: Select Default Model
- In Cursor settings, choose your preferred default model
- Or use the model dropdown in the chat interface
- I'll automatically use your selected model!

**Done!** I (the AI assistant) will now use your subscriptions when you chat with me.

---

## For Your Agent Project

### Step 1: Install Packages

```bash
# Already installed: openai
# Install Claude support
poetry add anthropic

# Install Gemini support
poetry add google-generativeai
```

### Step 2: Add API Keys to `.env.local`

Create or edit `.env.local` in the project root:

```bash
# OpenAI (Plus subscription)
OPENAI_API_KEY=sk-your-openai-key

# Anthropic Claude (Max subscription)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Google Gemini (Ultra subscription)
GOOGLE_API_KEY=your-google-api-key
```

### Step 3: Choose Provider

**Option A: Environment Variable**
```bash
export LLM_PROVIDER=claude  # or "openai" or "gemini"
```

**Option B: Config File** (`config/default.yaml`)
```yaml
llm_provider: "claude"  # or "openai" or "gemini"
llm_models:
  openai:
    chat: "gpt-4o"
  claude:
    chat: "claude-3-5-sonnet-20241022"
  gemini:
    chat: "gemini-1.5-pro"
```

### Step 4: Restart Agent Service

```bash
poetry run agent-service
```

**Done!** Your agent will now use the selected provider.

---

## Quick Reference

### Switch Providers

**In Cursor IDE:**
- Use model dropdown in chat interface

**In Agent Project:**
```bash
# Switch to Claude
export LLM_PROVIDER=claude
poetry run agent-service

# Switch to Gemini
export LLM_PROVIDER=gemini
poetry run agent-service

# Switch to OpenAI
export LLM_PROVIDER=openai
poetry run agent-service
```

### Test Your Setup

```python
from src.personal_assistant.llm_client import create_llm_client

# Test any provider
client = create_llm_client(provider="claude")
response = client.chat([{"role": "user", "content": "Hello!"}])
print(response)
```

---

## Need More Details?

- **Cursor IDE Setup**: See [cursor-subscriptions-setup.md](cursor-subscriptions-setup.md)
- **Agent Project Setup**: See [llm-providers-setup.md](llm-providers-setup.md)

