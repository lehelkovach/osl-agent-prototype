# Setting Up Premium Subscriptions in Cursor IDE

## Overview

Cursor IDE can use multiple LLM providers. Here's how to configure your subscriptions:

## 1. Configure API Keys in Cursor

### Access Settings

1. Open Cursor Settings:
   - `Ctrl+,` (Windows/Linux) or `Cmd+,` (Mac)
   - Or: `File > Preferences > Settings`

2. Search for "API" or "Model"

### Add API Keys

#### OpenAI (Plus Subscription)
- Look for: `Cursor: OpenAI API Key` or `OpenAI API Key`
- Enter your OpenAI API key (from https://platform.openai.com/api-keys)
- Model options: `gpt-4o`, `gpt-4-turbo`, `gpt-4`, etc.

#### Anthropic Claude (Max Subscription)
- Look for: `Cursor: Anthropic API Key` or `Claude API Key`
- Enter your Anthropic API key (from https://console.anthropic.com/)
- Model options: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, `claude-3-5-haiku-20241022`

#### Google Gemini (Ultra Subscription)
- Look for: `Cursor: Google API Key` or `Gemini API Key`
- Enter your Google API key (from https://makersuite.google.com/app/apikey)
- Model options: `gemini-1.5-pro`, `gemini-1.5-ultra`, `gemini-pro`

### Alternative: Settings JSON

You can also edit `settings.json` directly:

```json
{
  "cursor.openaiApiKey": "sk-your-openai-key",
  "cursor.anthropicApiKey": "sk-ant-your-anthropic-key",
  "cursor.googleApiKey": "your-google-api-key",
  "cursor.chatModel": "claude-3-5-sonnet-20241022",
  "cursor.useClaude": true
}
```

## 2. Configure Model Selection

### Default Model
- In Cursor settings, set your preferred default model
- Or use the model selector in the chat interface

### Per-Request Model Selection
- Some Cursor versions allow selecting model per chat
- Look for a model dropdown in the chat interface

## 3. Verify Configuration

1. Open a new chat in Cursor
2. Check the model indicator (usually shows current model)
3. Try asking a question to verify it's using your subscription

## 4. Troubleshooting

### API Key Not Working
- Verify key is correct (no extra spaces)
- Check key has proper permissions
- Ensure subscription is active

### Model Not Available
- Verify your subscription tier includes that model
- Check model name spelling
- Some models may require specific API versions

### Rate Limits
- Check your subscription limits
- Monitor usage in provider dashboards
- Consider using different models for different tasks

## Provider-Specific Notes

### OpenAI Plus
- Access to: `gpt-4o`, `gpt-4-turbo`, `gpt-4`
- Rate limits: Higher than free tier
- Best for: Code generation, general tasks

### Claude Max
- Access to: `claude-3-5-sonnet`, `claude-3-opus`, `claude-3-5-haiku`
- Rate limits: Varies by tier
- Best for: Complex reasoning, long context

### Gemini Ultra
- Access to: `gemini-1.5-pro`, `gemini-1.5-ultra`
- Rate limits: Varies by tier
- Best for: Multimodal tasks, large context

## Next Steps

After configuring Cursor, you may also want to:
- Integrate these models into your agent project (see agent integration guide)
- Set up model routing based on task type
- Configure fallback models

