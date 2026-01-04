# How to Add API Keys to Cursor IDE (For AI Assistant)

This guide shows how to configure Cursor IDE so the AI assistant (me) can use your Claude, OpenAI, and Gemini subscriptions.

## Quick Steps

### 1. Open Cursor Settings

**Method 1: Keyboard Shortcut**
- Press `Ctrl+,` (Windows/Linux) or `Cmd+,` (Mac)

**Method 2: Menu**
- Go to `File > Preferences > Settings` (Windows/Linux)
- Or `Cursor > Settings` (Mac)

### 2. Add Your API Keys

In the settings search bar, type "API" and you'll see these settings:

#### OpenAI API Key
1. Search for: `OpenAI API Key` or `cursor.openaiApiKey`
2. Click "Edit in settings.json" or enter the key directly
3. Paste your OpenAI API key (starts with `sk-`)
4. Get your key from: https://platform.openai.com/api-keys

#### Anthropic Claude API Key
1. Search for: `Anthropic API Key` or `cursor.anthropicApiKey` or `Claude API Key`
2. Enter your Anthropic API key (starts with `sk-ant-`)
3. Get your key from: https://console.anthropic.com/

#### Google Gemini API Key
1. Search for: `Google API Key` or `Gemini API Key` or `cursor.googleApiKey`
2. Enter your Google API key
3. Get your key from: https://makersuite.google.com/app/apikey

### 3. Alternative: Edit settings.json Directly

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: "Preferences: Open User Settings (JSON)"
3. Add these lines:

```json
{
  "cursor.openaiApiKey": "sk-your-openai-key-here",
  "cursor.anthropicApiKey": "sk-ant-your-anthropic-key-here",
  "cursor.googleApiKey": "your-google-api-key-here",
  
  // Optional: Set default model
  "cursor.chatModel": "claude-3-5-sonnet-20241022",
  "cursor.useClaude": true
}
```

### 4. Select Your Preferred Model

**In Chat Interface:**
- Look for a model selector dropdown in the chat panel
- Choose from: GPT-4o, Claude 3.5 Sonnet, Claude 3 Opus, Gemini 1.5 Pro, etc.

**In Settings:**
- Search for "Model" or "Chat Model"
- Set your default model preference

### 5. Verify It's Working

1. Open a new chat in Cursor
2. Check the model indicator (usually shows current model)
3. Ask a question - I should now be using your subscription!

## Model Options

### OpenAI (Plus)
- `gpt-4o` (recommended)
- `gpt-4-turbo`
- `gpt-4`

### Anthropic Claude (Max)
- `claude-3-5-sonnet-20241022` (recommended)
- `claude-3-opus-20240229` (most capable)
- `claude-3-5-haiku-20241022` (fastest)

### Google Gemini (Ultra)
- `gemini-1.5-pro` (recommended)
- `gemini-1.5-ultra` (most capable)

## Troubleshooting

### Can't Find API Key Settings
- Try searching for "API" in settings
- Or search for the provider name: "OpenAI", "Claude", "Gemini"
- Some versions use: `cursor.general.openaiApiKey`

### Keys Not Working
- Verify keys are correct (no extra spaces)
- Check your subscription is active
- Ensure keys have proper permissions

### Model Not Available
- Verify your subscription tier includes that model
- Check model name spelling
- Try a different model from the same provider

### Still Using Free Tier
- Make sure you've entered the API keys correctly
- Restart Cursor after adding keys
- Check the model selector shows premium models

## Security Notes

- ✅ API keys are stored locally in your Cursor settings
- ✅ They're not shared with anyone
- ✅ Each key gives access to your account - keep them secure
- ✅ Don't share screenshots with keys visible

## Next Steps

Once configured:
- I'll automatically use your preferred model
- You can switch models per chat using the dropdown
- Premium features will be available based on your subscriptions

## Need Help?

If you can't find the settings:
1. Check Cursor's documentation: https://cursor.sh/docs
2. Look for "API" or "Model" in the settings search
3. The exact setting names may vary by Cursor version

