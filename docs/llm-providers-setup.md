# LLM Provider Setup Guide

This guide shows how to configure your agent to use different LLM providers: OpenAI, Anthropic Claude, or Google Gemini.

## Quick Setup

### 1. Install Required Packages

```bash
# For OpenAI (already installed)
# openai package is already in dependencies

# For Claude
pip install anthropic

# For Gemini
pip install google-generativeai
```

### 2. Set API Keys

Add to `.env.local`:

```bash
# OpenAI (Plus subscription)
OPENAI_API_KEY=sk-your-openai-key

# Anthropic Claude (Max subscription)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Google Gemini (Ultra subscription)
GOOGLE_API_KEY=your-google-api-key
# or
GEMINI_API_KEY=your-google-api-key
```

### 3. Configure Provider

#### Option A: Environment Variable

```bash
LLM_PROVIDER=claude  # or "openai" or "gemini"
```

#### Option B: Config File

Edit `config/default.yaml`:

```yaml
llm_provider: "claude"  # or "openai" or "gemini"
llm_models:
  openai:
    chat: "gpt-4o"
    embedding: "text-embedding-3-large"
  claude:
    chat: "claude-3-5-sonnet-20241022"
    embedding: null  # Claude doesn't provide embeddings
  gemini:
    chat: "gemini-1.5-pro"
    embedding: "models/embedding-001"
```

## Available Models

### OpenAI (Plus Subscription)
- **Chat**: `gpt-4o`, `gpt-4-turbo`, `gpt-4`
- **Embeddings**: `text-embedding-3-large`, `text-embedding-3-small`

### Anthropic Claude (Max Subscription)
- **Chat**: 
  - `claude-3-5-sonnet-20241022` (recommended)
  - `claude-3-opus-20240229` (most capable)
  - `claude-3-5-haiku-20241022` (fastest)
- **Embeddings**: Not available (falls back to OpenAI or local)

### Google Gemini (Ultra Subscription)
- **Chat**: 
  - `gemini-1.5-pro` (recommended)
  - `gemini-1.5-ultra` (most capable)
- **Embeddings**: `models/embedding-001`

## Model Selection

### For Different Use Cases

**Complex Reasoning / Long Context:**
```yaml
llm_provider: "claude"
llm_models:
  claude:
    chat: "claude-3-opus-20240229"
```

**Code Generation:**
```yaml
llm_provider: "openai"
llm_models:
  openai:
    chat: "gpt-4o"
```

**Multimodal / Large Context:**
```yaml
llm_provider: "gemini"
llm_models:
  gemini:
    chat: "gemini-1.5-ultra"
```

## Embeddings

- **OpenAI**: Full embedding support
- **Claude**: No embeddings (automatically falls back to OpenAI or local)
- **Gemini**: Full embedding support

## Testing

Test your configuration:

```python
from src.personal_assistant.llm_client import create_llm_client

# Test OpenAI
client = create_llm_client(provider="openai")
response = client.chat([{"role": "user", "content": "Hello"}])
print(f"OpenAI: {response}")

# Test Claude
client = create_llm_client(provider="claude")
response = client.chat([{"role": "user", "content": "Hello"}])
print(f"Claude: {response}")

# Test Gemini
client = create_llm_client(provider="gemini")
response = client.chat([{"role": "user", "content": "Hello"}])
print(f"Gemini: {response}")
```

## Troubleshooting

### Claude Not Working
- Install: `pip install anthropic`
- Check API key: `ANTHROPIC_API_KEY` set correctly
- Verify subscription includes the model

### Gemini Not Working
- Install: `pip install google-generativeai`
- Check API key: `GOOGLE_API_KEY` or `GEMINI_API_KEY` set
- Enable API in Google Cloud Console

### Embeddings Failing (Claude)
- Claude doesn't provide embeddings
- System automatically falls back to OpenAI embeddings
- Or use local embeddings: `embedding_backend: "local"`

## Switching Providers

You can switch providers without code changes:

1. Change `LLM_PROVIDER` env var or config
2. Restart the service
3. Agent will use the new provider

Example:
```bash
# Switch to Claude
export LLM_PROVIDER=claude
poetry run agent-service

# Switch to Gemini
export LLM_PROVIDER=gemini
poetry run agent-service
```

