# How to Add Your API Keys for Claude, OpenAI, and Gemini

## Overview

To use your subscriptions (Claude Max, OpenAI Plus, Google Gemini Ultra), you need to:
1. Get API keys from each provider
2. Add them to your project's `.env.local` file
3. The agent will automatically use them based on your configuration

## Step-by-Step Guide

### Step 1: Get Your API Keys

#### OpenAI (Plus Subscription)
1. Go to: https://platform.openai.com/api-keys
2. Sign in with your OpenAI account
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. **Important**: Save it immediately - you can't see it again!

#### Anthropic Claude (Max Subscription)
1. Go to: https://console.anthropic.com/
2. Sign in with your Anthropic account
3. Navigate to "API Keys" section
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)
6. **Important**: Save it immediately - you can't see it again!

#### Google Gemini (Ultra Subscription)
1. Go to: https://makersuite.google.com/app/apikey
   - Or: https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key (long alphanumeric string)
5. **Important**: Save it immediately - you can't see it again!

### Step 2: Add Keys to Your Project

#### Create/Edit `.env.local` File

In your project root (`/home/johncofax/Dev/git-source/osl-agent-prototype/`), create or edit `.env.local`:

```bash
# OpenAI API Key (for GPT-4o, GPT-4 Turbo, etc.)
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Anthropic Claude API Key (for Claude 3.5 Sonnet, Claude 3 Opus, etc.)
ANTHROPIC_API_KEY=sk-ant-your-actual-anthropic-key-here

# Google Gemini API Key (for Gemini 1.5 Pro, Gemini 1.5 Ultra, etc.)
GOOGLE_API_KEY=your-actual-google-api-key-here
# Alternative name (both work):
# GEMINI_API_KEY=your-actual-google-api-key-here

# Choose which provider to use (optional, defaults to "openai")
LLM_PROVIDER=openai
# Options: "openai", "claude", or "gemini"
```

#### Important Security Notes

- ✅ `.env.local` is in `.gitignore` - your keys won't be committed
- ✅ Never share your API keys publicly
- ✅ Never commit keys to git
- ✅ Each key gives full access to your account - treat them like passwords

### Step 3: Install Required Packages

```bash
# Make sure you're in the project directory
cd /home/johncofax/Dev/git-source/osl-agent-prototype

# Install Claude support
poetry add anthropic

# Install Gemini support
poetry add google-generativeai
```

### Step 4: Configure Which Provider to Use

#### Option A: Environment Variable (Recommended)

In `.env.local`, add:
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
  claude:
    chat: "claude-3-5-sonnet-20241022"
  gemini:
    chat: "gemini-1.5-pro"
```

### Step 5: Restart Your Agent Service

```bash
# Stop the current service (Ctrl+C if running)
# Then restart:
poetry run agent-service
```

The agent will now use your selected provider!

## Verify It's Working

### Check Logs

When the service starts, you should see:
```
llm_provider_initialized provider=claude chat_model=claude-3-5-sonnet-20241022
```

### Test in Chat

1. Open the agent UI: http://localhost:8000/ui
2. Send a message
3. The agent will use your configured provider

### Test Programmatically

```python
from src.personal_assistant.llm_client import create_llm_client

# Test your configured provider
client = create_llm_client()
response = client.chat([{"role": "user", "content": "Hello!"}])
print(response)
```

## Switching Providers

You can switch providers without code changes:

```bash
# Edit .env.local and change:
LLM_PROVIDER=gemini  # Switch to Gemini

# Restart service
poetry run agent-service
```

## Troubleshooting

### "API key not found"
- Check `.env.local` exists in project root
- Verify key names are correct (case-sensitive)
- Make sure there are no extra spaces or quotes around keys

### "Invalid API key"
- Verify the key is correct (copy-paste again)
- Check the key hasn't expired or been revoked
- Ensure your subscription is active

### "Module not found: anthropic" or "google-generativeai"
```bash
poetry add anthropic google-generativeai
```

### "Rate limit exceeded"
- Check your subscription tier limits
- Wait a moment and try again
- Consider using a different provider temporarily

### Keys Not Loading
- Make sure `.env.local` is in the project root (same directory as `pyproject.toml`)
- Restart the service after adding keys
- Check for typos in variable names

## Example `.env.local` File

Here's a complete example (with placeholder keys):

```bash
# OpenAI (Plus subscription)
OPENAI_API_KEY=sk-proj-abc123xyz789...

# Anthropic Claude (Max subscription)
ANTHROPIC_API_KEY=sk-ant-api03-abc123xyz789...

# Google Gemini (Ultra subscription)
GOOGLE_API_KEY=AIzaSyAbc123Xyz789...

# Choose provider (defaults to "openai" if not set)
LLM_PROVIDER=claude

# Optional: Override default models
OPENAI_CHAT_MODEL=gpt-4o
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
GEMINI_CHAT_MODEL=gemini-1.5-pro
```

## Security Best Practices

1. **Never commit `.env.local`** - It's already in `.gitignore`
2. **Rotate keys periodically** - Create new keys and delete old ones
3. **Use separate keys for dev/prod** - Different keys for different environments
4. **Monitor usage** - Check provider dashboards for unexpected usage
5. **Set usage limits** - Configure spending limits in provider dashboards

## Next Steps

Once your keys are set up:
- See [QUICK-START-SUBSCRIPTIONS.md](QUICK-START-SUBSCRIPTIONS.md) for quick reference
- See [llm-providers-setup.md](llm-providers-setup.md) for advanced configuration
- The agent will automatically use your configured provider!

