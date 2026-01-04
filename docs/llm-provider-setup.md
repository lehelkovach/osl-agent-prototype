# LLM Provider Setup Guide

This guide explains how to configure the agent to use different LLM providers, including OpenAI Plus and Claude Max subscriptions.

## Supported Providers

- **OpenAI**: GPT-4o, GPT-4 Turbo, GPT-4, GPT-3.5
- **Anthropic Claude**: Claude 3.5 Sonnet, Claude 3 Opus (Claude Max), Claude 3.5 Haiku

## Configuration

### Method 1: Environment Variables (Recommended)

Create or edit `.env.local`:

```bash
# For OpenAI
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_CHAT_MODEL=gpt-4o  # or gpt-4-turbo, gpt-4, etc.

# For Claude
ANTHROPIC_API_KEY=sk-ant-your-claude-key-here
CLAUDE_CHAT_MODEL=claude-3-opus-20240229  # Claude Max (Opus)
# or
CLAUDE_CHAT_MODEL=claude-3-5-sonnet-20241022  # Claude 3.5 Sonnet

# Choose provider (auto-detects if both keys present)
LLM_PROVIDER=claude  # or "openai"

# Embeddings (Claude doesn't have embeddings, so use OpenAI or local)
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
# or use local embeddings
EMBEDDING_BACKEND=local
```

### Method 2: Config File

Edit `config/default.yaml`:

```yaml
llm:
  provider: "claude"  # or "openai"
  # OpenAI settings
  openai_chat_model: "gpt-4o"
  openai_embedding_model: "text-embedding-3-large"
  # Claude settings
  claude_chat_model: "claude-3-opus-20240229"  # Claude Max
```

## Claude Max Setup

1. **Get API Key**:
   - Go to https://console.anthropic.com/
   - Create an API key
   - Copy the key (starts with `sk-ant-`)

2. **Install Anthropic SDK**:
```bash
pip install anthropic
# or
poetry add anthropic
```

3. **Set Environment Variable**:
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
# Or add to .env.local
```

4. **Configure Model**:
```bash
export CLAUDE_CHAT_MODEL=claude-3-opus-20240229  # Claude Max
# Or use claude-3-5-sonnet-20241022 for Sonnet
```

5. **Set Provider**:
```bash
export LLM_PROVIDER=claude
```

## OpenAI Plus Setup

1. **Get API Key**:
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Copy the key (starts with `sk-`)

2. **Set Environment Variable**:
```bash
export OPENAI_API_KEY=sk-your-key-here
# Or add to .env.local
```

3. **Choose Model**:
```bash
export OPENAI_CHAT_MODEL=gpt-4o  # Recommended for Plus
# Or gpt-4-turbo, gpt-4, etc.
```

4. **Set Provider** (if using both):
```bash
export LLM_PROVIDER=openai
```

## Model Selection

### OpenAI Models

- `gpt-4o` - Latest GPT-4 Optimized (recommended for Plus)
- `gpt-4-turbo` - GPT-4 Turbo
- `gpt-4` - Standard GPT-4
- `gpt-3.5-turbo` - GPT-3.5 Turbo (faster, cheaper)

### Claude Models

- `claude-3-opus-20240229` - Claude Max (most capable, slowest)
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet (balanced, recommended)
- `claude-3-5-haiku-20241022` - Claude 3.5 Haiku (fastest, cheapest)

## Embeddings

**Important**: Claude doesn't have an embeddings API. Options:

1. **Use OpenAI for embeddings** (recommended):
   - Set `OPENAI_API_KEY` even when using Claude for chat
   - System will use OpenAI for embeddings automatically

2. **Use local embeddings**:
   - Set `EMBEDDING_BACKEND=local`
   - Install: `./scripts/install_local_embedder.sh`

## Auto-Detection

If you don't set `LLM_PROVIDER`, the system auto-detects:
1. If `ANTHROPIC_API_KEY` is set → uses Claude
2. If `OPENAI_API_KEY` is set → uses OpenAI
3. Defaults to OpenAI if neither is set

## Testing

Test your configuration:

```python
from src.personal_assistant.llm_client import create_llm_client

# Test Claude
client = create_llm_client(provider="claude")
response = client.chat([{"role": "user", "content": "Hello!"}])
print(response)

# Test OpenAI
client = create_llm_client(provider="openai")
response = client.chat([{"role": "user", "content": "Hello!"}])
print(response)
```

## Troubleshooting

### Claude Import Error

```
ImportError: anthropic package required
```

**Fix**: `pip install anthropic` or `poetry add anthropic`

### Embedding Error with Claude

```
Claude doesn't support embeddings
```

**Fix**: Set `OPENAI_API_KEY` for embeddings, or use `EMBEDDING_BACKEND=local`

### API Key Not Found

Check:
1. `.env.local` file exists and has the key
2. Environment variable is exported
3. Key format is correct (starts with `sk-` for OpenAI, `sk-ant-` for Claude)

## Cost Considerations

- **Claude Opus (Max)**: Most expensive, best quality
- **Claude Sonnet**: Balanced cost/quality
- **GPT-4o**: Good balance, fast
- **GPT-4 Turbo**: Slightly cheaper than GPT-4o
- **Claude Haiku**: Cheapest, good for simple tasks

Choose based on your needs and budget!

